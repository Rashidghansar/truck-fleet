from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime
import os
import uuid
from ...database import get_db
from ...models.truck import Truck, TruckPhoto
from ...models.driver import Driver
from ...models.user import User, UserType
from ...schemas.truck import TruckCreate, TruckResponse, TruckUpdate
from ...schemas.response import ResponseModel
from ...core.deps import get_current_user
from ...config import settings

router = APIRouter()


def truck_to_response(truck: Truck, db: Session) -> dict:
    """Convert truck model to response dict with driver name"""
    response = TruckResponse.model_validate(truck).model_dump()
    
    # Add driver name if driver is assigned
    if truck.current_driver_id:
        driver = db.query(Driver).filter(Driver.id == truck.current_driver_id).first()
        if driver:
            response['current_driver_name'] = driver.name
    
    return response

@router.post("/add", response_model=ResponseModel)
async def add_truck(
    truck_data: TruckCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Add a new truck"""
    if current_user.user_type not in [UserType.AGGREGATOR.value, UserType.OWNER.value]:
        raise HTTPException(status_code=403, detail="Only aggregators and owners can add trucks")
    
    # Check existing truck number
    existing = db.query(Truck).filter(Truck.truck_number == truck_data.truck_number).first()
    if existing:
        raise HTTPException(status_code=400, detail="Truck with this number already exists")
    
    truck = Truck(
        owner_id=current_user.id,
        truck_number=truck_data.truck_number,
        registration_number=truck_data.truck_number,
        truck_type=truck_data.truck_type,
        capacity=truck_data.capacity,
        truck_make=truck_data.truck_make,
        model_year=truck_data.model_year,
        fuel_type=truck_data.fuel_type,
        load_capacity_tons=truck_data.load_capacity_tons,
        has_gps=truck_data.has_gps,
        gps_device_id=truck_data.gps_device_id,
        ownership_type=truck_data.ownership_type,
        owner_name=truck_data.owner_name or current_user.name,
        owner_address=truck_data.owner_address,
        owner_phone=truck_data.owner_phone,
        rc_number=truck_data.rc_number,
        registration_date=truck_data.registration_date,
        insurance_number=truck_data.insurance_number,
        insurance_expiry=truck_data.insurance_expiry,
        fitness_expiry=truck_data.fitness_expiry,
        puc_expiry=truck_data.puc_expiry,
        permit_type=truck_data.permit_type,
        permit_expiry=truck_data.permit_expiry
    )
    
    db.add(truck)
    db.commit()
    db.refresh(truck)
    
    return ResponseModel(
        success=True,
        message="Truck added successfully",
        data=TruckResponse.model_validate(truck)
    )

@router.get("", response_model=ResponseModel)
async def get_trucks(
    status: Optional[str] = None,
    truck_type: Optional[str] = None,
    available_only: bool = False,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get user's trucks"""
    query = db.query(Truck).filter(Truck.owner_id == current_user.id)
    
    if status:
        query = query.filter(Truck.current_status == status)
    
    if truck_type:
        query = query.filter(Truck.truck_type == truck_type)
    
    if available_only:
        query = query.filter(Truck.is_available == True)
    
    total = query.count()
    query = query.order_by(Truck.created_at.desc())
    offset = (page - 1) * page_size
    trucks = query.offset(offset).limit(page_size).all()
    
    return ResponseModel(
        success=True,
        data={
            "trucks": [truck_to_response(t, db) for t in trucks],
            "total": total,
            "page": page,
            "page_size": page_size
        }
    )

@router.get("/{truck_id}", response_model=ResponseModel)
async def get_truck(
    truck_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    truck = db.query(Truck).filter(Truck.id == truck_id).first()
    if not truck:
        raise HTTPException(status_code=404, detail="Truck not found")
    
    return ResponseModel(
        success=True,
        data=truck_to_response(truck, db)
    )

@router.put("/{truck_id}", response_model=ResponseModel)
async def update_truck(
    truck_id: str,
    update_data: TruckUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    truck = db.query(Truck).filter(Truck.id == truck_id).first()
    if not truck:
        raise HTTPException(status_code=404, detail="Truck not found")
    
    if truck.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="You don't own this truck")
    
    update_dict = update_data.model_dump(exclude_unset=True)
    for key, value in update_dict.items():
        setattr(truck, key, value)
    
    truck.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(truck)
    
    return ResponseModel(
        success=True,
        message="Truck updated successfully",
        data=TruckResponse.model_validate(truck)
    )

@router.delete("/{truck_id}", response_model=ResponseModel)
async def delete_truck(
    truck_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    truck = db.query(Truck).filter(Truck.id == truck_id).first()
    if not truck:
        raise HTTPException(status_code=404, detail="Truck not found")
    
    if truck.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="You don't own this truck")
    
    if truck.current_status == "in_trip":
        raise HTTPException(status_code=400, detail="Cannot delete truck that is currently on a trip")
    
    truck.is_active = False
    db.commit()
    
    return ResponseModel(success=True, message="Truck deleted successfully")

@router.post("/{truck_id}/photos", response_model=ResponseModel)
async def upload_truck_photos(
    truck_id: str,
    photo_type: str = Form(...),
    photos: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    truck = db.query(Truck).filter(Truck.id == truck_id).first()
    if not truck:
        raise HTTPException(status_code=404, detail="Truck not found")
    
    if truck.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="You don't own this truck")
    
    os.makedirs(settings.upload_path, exist_ok=True)
    
    uploaded = []
    for photo in photos:
        if photo.filename:
            filename = f"{uuid.uuid4()}_{photo.filename}"
            filepath = os.path.join(settings.upload_path, filename)
            with open(filepath, "wb") as f:
                content = await photo.read()
                f.write(content)
            
            truck_photo = TruckPhoto(
                truck_id=truck_id,
                photo_url=f"/uploads/{filename}",
                photo_type=photo_type
            )
            db.add(truck_photo)
            uploaded.append(f"/uploads/{filename}")
    
    db.commit()
    
    return ResponseModel(
        success=True,
        message=f"{len(uploaded)} photos uploaded",
        data={"photos": uploaded}
    )

@router.put("/{truck_id}/location", response_model=ResponseModel)
async def update_truck_location(
    truck_id: str,
    latitude: float,
    longitude: float,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    truck = db.query(Truck).filter(Truck.id == truck_id).first()
    if not truck:
        raise HTTPException(status_code=404, detail="Truck not found")
    
    truck.current_lat = latitude
    truck.current_lng = longitude
    truck.last_location_update = datetime.utcnow()
    db.commit()
    
    return ResponseModel(success=True, message="Location updated")

@router.get("/{truck_id}/stats", response_model=ResponseModel)
async def get_truck_stats(
    truck_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    truck = db.query(Truck).filter(Truck.id == truck_id).first()
    if not truck:
        raise HTTPException(status_code=404, detail="Truck not found")
    
    return ResponseModel(
        success=True,
        data={
            "total_trips": truck.total_trips,
            "rating": truck.rating,
            "total_earnings": truck.total_earnings,
            "is_available": truck.is_available,
            "current_status": truck.current_status
        }
    )


@router.get("/available/list", response_model=ResponseModel)
async def get_available_trucks(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get only available trucks for assignment - used during booking acceptance"""
    if current_user.user_type not in [UserType.AGGREGATOR.value, UserType.OWNER.value]:
        raise HTTPException(status_code=403, detail="Only owners/aggregators can access this endpoint")
    
    trucks = db.query(Truck).filter(
        Truck.owner_id == current_user.id,
        Truck.is_available == True,
        Truck.is_active == True
    ).all()
    
    return ResponseModel(
        success=True,
        data={
            "trucks": [truck_to_response(t, db) for t in trucks],
            "total": len(trucks)
        }
    )