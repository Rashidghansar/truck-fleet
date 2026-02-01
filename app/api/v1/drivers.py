from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel
import os
import uuid
from ...database import get_db
from ...models.driver import Driver, DriverDocument
from ...models.truck import Truck
from ...models.user import User, UserType
from ...models.booking import Booking, BookingStatus
from ...schemas.driver import DriverCreate, DriverResponse, DriverUpdate
from ...schemas.response import ResponseModel
from ...core.deps import get_current_user
from ...core.security import get_password_hash
from ...config import settings

router = APIRouter()

@router.post("/add", response_model=ResponseModel)
async def add_driver(
    driver_data: DriverCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Add a new driver - creates User account with temporary credentials"""
    if current_user.user_type not in [UserType.AGGREGATOR.value, UserType.OWNER.value]:
        raise HTTPException(status_code=403, detail="Only aggregators and owners can add drivers")
    
    # Check existing driver
    existing_driver = db.query(Driver).filter(Driver.phone == driver_data.phone).first()
    if existing_driver:
        raise HTTPException(status_code=400, detail="Driver with this phone already exists")
    
    # Check if user with this phone exists
    existing_user = db.query(User).filter(User.phone == driver_data.phone).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Phone number already registered")
    
    # Generate temporary password
    from ...utils.code_generator import generate_temp_password
    temp_password = generate_temp_password()
    
    # Create User account
    driver_user = User(
        name=driver_data.name,
        phone=driver_data.phone,
        email=driver_data.email,
        password_hash=get_password_hash(temp_password),
        user_type=UserType.DRIVER.value,
        address=driver_data.address,
        emergency_contact_name=driver_data.emergency_contact_name,
        emergency_contact_phone=driver_data.emergency_contact_phone,
        is_active=True,
        is_verified=False,
    )
    
    db.add(driver_user)
    db.flush()
    
    # Create driver record
    driver = Driver(
        user_id=driver_user.id,
        owner_id=current_user.id,
        name=driver_data.name,
        phone=driver_data.phone,
        email=driver_data.email,
        date_of_birth=driver_data.date_of_birth,
        address=driver_data.address,
        identification_mark=driver_data.identification_mark,
        blood_group=driver_data.blood_group,
        emergency_contact_name=driver_data.emergency_contact_name,
        emergency_contact_phone=driver_data.emergency_contact_phone,
        license_number=driver_data.license_number,
        license_type=driver_data.license_type,
        license_issue_date=driver_data.license_issue_date,
        license_expiry=driver_data.license_expiry,
        aadhar_number=driver_data.aadhar_number,
        pan_number=driver_data.pan_number,
        medical_fitness_expiry=driver_data.medical_fitness_expiry,
        medical_conditions=driver_data.medical_conditions,
        experience_years=driver_data.experience_years,
        primary_vehicle_type=driver_data.primary_vehicle_type,
        bank_account_number=driver_data.bank_account_number,
        bank_ifsc_code=driver_data.bank_ifsc_code,
        bank_account_holder=driver_data.bank_account_holder,
        bank_name=driver_data.bank_name,
        upi_id=driver_data.upi_id,
        work_type=driver_data.work_type,
        assigned_truck_id=driver_data.assigned_truck_id,
        auto_created=True,
        temp_password=temp_password,
        password_changed=False,
        created_by_user_id=current_user.id
    )
    
    db.add(driver)
    db.commit()
    db.refresh(driver)
    
    response_data = DriverResponse.model_validate(driver).model_dump()
    response_data["login_credentials"] = {
        "phone": driver_data.phone,
        "password": temp_password,
        "message": "Share these credentials with driver. They must change password on first login."
    }
    
    return ResponseModel(
        success=True,
        message="Driver added successfully. Login credentials generated.",
        data=response_data
    )

@router.get("", response_model=ResponseModel)
async def get_drivers(
    status: Optional[str] = None,
    available_only: bool = False,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get drivers"""
    query = db.query(Driver)
    
    if current_user.user_type in [UserType.AGGREGATOR.value, UserType.OWNER.value]:
        query = query.filter(Driver.owner_id == current_user.id)
    
    if status:
        query = query.filter(Driver.current_status == status)
    
    if available_only:
        query = query.filter(Driver.is_available == True, Driver.is_active == True)
    
    total = query.count()
    query = query.order_by(Driver.created_at.desc())
    offset = (page - 1) * page_size
    drivers = query.offset(offset).limit(page_size).all()
    
    return ResponseModel(
        success=True,
        data={
            "drivers": [DriverResponse.model_validate(d) for d in drivers],
            "total": total,
            "page": page,
            "page_size": page_size
        }
    )

@router.get("/{driver_id}", response_model=ResponseModel)
async def get_driver(
    driver_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    driver = db.query(Driver).filter(Driver.id == driver_id).first()
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found")
    
    return ResponseModel(
        success=True,
        data=DriverResponse.model_validate(driver)
    )

@router.put("/{driver_id}", response_model=ResponseModel)
async def update_driver(
    driver_id: str,
    update_data: DriverUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    driver = db.query(Driver).filter(Driver.id == driver_id).first()
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found")
    
    update_dict = update_data.model_dump(exclude_unset=True)
    for key, value in update_dict.items():
        setattr(driver, key, value)
    
    driver.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(driver)
    
    return ResponseModel(
        success=True,
        message="Driver updated successfully",
        data=DriverResponse.model_validate(driver)
    )

@router.delete("/{driver_id}", response_model=ResponseModel)
async def delete_driver(
    driver_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    driver = db.query(Driver).filter(Driver.id == driver_id).first()
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found")
    
    if driver.current_status == "on_trip":
        raise HTTPException(status_code=400, detail="Cannot delete driver who is on a trip")
    
    driver.is_active = False
    db.commit()
    
    return ResponseModel(success=True, message="Driver deleted successfully")

@router.post("/{driver_id}/documents", response_model=ResponseModel)
async def upload_driver_document(
    driver_id: str,
    document_type: str = Form(...),
    document_number: Optional[str] = Form(None),
    expiry_date: Optional[str] = Form(None),
    document: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    driver = db.query(Driver).filter(Driver.id == driver_id).first()
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found")
    
    os.makedirs(settings.upload_path, exist_ok=True)
    
    filename = f"{uuid.uuid4()}_{document.filename}"
    filepath = os.path.join(settings.upload_path, filename)
    with open(filepath, "wb") as f:
        content = await document.read()
        f.write(content)
    
    from datetime import datetime as dt
    exp_date = None
    if expiry_date:
        exp_date = dt.strptime(expiry_date, "%Y-%m-%d").date()
    
    driver_doc = DriverDocument(
        driver_id=driver_id,
        document_type=document_type,
        document_url=f"/uploads/{filename}",
        document_number=document_number,
        expiry_date=exp_date
    )
    
    db.add(driver_doc)
    db.commit()
    
    return ResponseModel(
        success=True,
        message="Document uploaded successfully",
        data={"document_url": f"/uploads/{filename}"}
    )

@router.put("/{driver_id}/location", response_model=ResponseModel)
async def update_driver_location(
    driver_id: str,
    latitude: float,
    longitude: float,
    speed: Optional[float] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    driver = db.query(Driver).filter(Driver.id == driver_id).first()
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found")
    
    driver.current_lat = latitude
    driver.current_lng = longitude
    driver.last_location_update = datetime.utcnow()
    db.commit()
    
    return ResponseModel(success=True, message="Location updated")

@router.post("/{driver_id}/fingerprint", response_model=ResponseModel)
async def register_fingerprint(
    driver_id: str,
    fingerprint_data: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    driver = db.query(Driver).filter(Driver.id == driver_id).first()
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found")
    
    driver.fingerprint_data = fingerprint_data
    driver.fingerprint_registered = True
    db.commit()
    
    return ResponseModel(success=True, message="Fingerprint registered successfully")

@router.put("/{driver_id}/assign-truck", response_model=ResponseModel)
async def assign_truck_to_driver(
    driver_id: str,
    truck_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    driver = db.query(Driver).filter(Driver.id == driver_id).first()
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found")
    
    truck = db.query(Truck).filter(Truck.id == truck_id).first()
    if not truck:
        raise HTTPException(status_code=404, detail="Truck not found")
    
    driver.assigned_truck_id = truck_id
    truck.current_driver_id = driver_id
    db.commit()
    
    return ResponseModel(success=True, message="Truck assigned to driver")

@router.get("/{driver_id}/trips", response_model=ResponseModel)
async def get_driver_trips(
    driver_id: str,
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Booking).filter(Booking.driver_id == driver_id)
    
    if status:
        query = query.filter(Booking.status == status)
    
    total = query.count()
    query = query.order_by(Booking.created_at.desc())
    offset = (page - 1) * page_size
    bookings = query.offset(offset).limit(page_size).all()
    
    from ...schemas.booking import BookingResponse
    
    return ResponseModel(
        success=True,
        data={
            "trips": [BookingResponse.model_validate(b) for b in bookings],
            "total": total,
            "page": page
        }
    )

@router.post("/opportunities/{booking_id}/accept", response_model=ResponseModel)
async def driver_accept_opportunity(
    booking_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Driver accepts an opportunity assigned to them"""
    # Get driver profile
    driver = db.query(Driver).filter(Driver.user_id == current_user.id).first()
    if not driver:
        raise HTTPException(status_code=404, detail="Driver profile not found")
    
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    # Verify this booking is for this driver or available
    if booking.driver_id and booking.driver_id != driver.id:
        raise HTTPException(status_code=403, detail="This booking is assigned to another driver")
    
    # Update booking
    booking.driver_id = driver.id
    if not booking.truck_id and driver.assigned_truck_id:
        booking.truck_id = driver.assigned_truck_id
    
    if booking.status == BookingStatus.PENDING.value:
        booking.agreed_rate = booking.published_rate
        booking.status = BookingStatus.CONFIRMED.value
    
    # Update driver
    driver.is_available = False
    driver.current_status = "assigned"
    
    db.commit()
    
    from ...schemas.booking import BookingResponse
    return ResponseModel(
        success=True,
        message="Opportunity accepted",
        data=BookingResponse.model_validate(booking)
    )


@router.get("/my-assignments", response_model=ResponseModel)
async def get_driver_assignments(
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get bookings assigned to the logged-in driver with QR codes"""
    if current_user.user_type != UserType.DRIVER.value:
        raise HTTPException(status_code=403, detail="Only drivers can access this endpoint")
    
    # Get driver profile
    driver = db.query(Driver).filter(Driver.user_id == current_user.id).first()
    if not driver:
        # Try to find by phone
        driver = db.query(Driver).filter(Driver.phone == current_user.phone).first()
        if driver:
            # Link driver to user
            driver.user_id = current_user.id
            db.commit()
        else:
            raise HTTPException(status_code=404, detail="Driver profile not found")
    
    # Get assigned bookings
    query = db.query(Booking).filter(Booking.driver_id == driver.id)
    
    if status:
        query = query.filter(Booking.status == status)
    else:
        # Default: show active bookings (confirmed, in_progress)
        query = query.filter(Booking.status.in_([
            BookingStatus.CONFIRMED.value, 
            BookingStatus.IN_PROGRESS.value
        ]))
    
    bookings = query.order_by(Booking.created_at.desc()).all()
    
    assignments = []
    for booking in bookings:
        truck = db.query(Truck).filter(Truck.id == booking.truck_id).first() if booking.truck_id else None
        
        assignments.append({
            "id": booking.id,
            "demand_number": booking.demand_number,
            "status": booking.status,
            "pickup_location": booking.pickup_location,
            "destination_address": booking.destination_address,
            "consignment_type": booking.consignment_type,
            "gate_in_time": booking.gate_in_time.isoformat() if booking.gate_in_time else None,
            "bay_number": booking.bay_number,
            "special_instructions": booking.special_instructions,
            "agreed_rate": booking.agreed_rate,
            "truck": {
                "id": truck.id if truck else None,
                "truck_number": truck.truck_number if truck else None,
                "truck_type": truck.truck_type if truck else None
            },
            # QR Code for gate check-in
            "gate_qr_code": booking.gate_qr_code,
            "gate_numeric_code": booking.gate_numeric_code,
            "gate_qr_scanned": booking.gate_qr_scanned,
            "created_at": booking.created_at.isoformat() if booking.created_at else None
        })
    
    return ResponseModel(
        success=True,
        data={
            "assignments": assignments,
            "total": len(assignments),
            "driver": {
                "id": driver.id,
                "name": driver.name,
                "current_status": driver.current_status
            }
        }
    )


@router.get("/my-profile", response_model=ResponseModel)
async def get_driver_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get the logged-in driver's profile"""
    if current_user.user_type != UserType.DRIVER.value:
        raise HTTPException(status_code=403, detail="Only drivers can access this endpoint")
    
    # Get driver profile
    driver = db.query(Driver).filter(Driver.user_id == current_user.id).first()
    if not driver:
        # Try to find by phone
        driver = db.query(Driver).filter(Driver.phone == current_user.phone).first()
        if driver:
            # Link driver to user
            driver.user_id = current_user.id
            db.commit()
            db.refresh(driver)
        else:
            raise HTTPException(status_code=404, detail="Driver profile not found")
    
    # Get assigned truck info
    truck = None
    if driver.assigned_truck_id:
        truck_obj = db.query(Truck).filter(Truck.id == driver.assigned_truck_id).first()
        if truck_obj:
            truck = {
                "id": truck_obj.id,
                "truck_number": truck_obj.truck_number,
                "truck_type": truck_obj.truck_type
            }
    
    # Get owner/aggregator info
    owner = None
    if driver.owner_id:
        owner_obj = db.query(User).filter(User.id == driver.owner_id).first()
        if owner_obj:
            owner = {
                "id": owner_obj.id,
                "name": owner_obj.name,
                "phone": owner_obj.phone
            }
    
    return ResponseModel(
        success=True,
        data={
            "id": driver.id,
            "name": driver.name,
            "phone": driver.phone,
            "license_number": driver.license_number,
            "is_available": driver.is_available,
            "is_active": driver.is_active,
            "current_status": driver.current_status,
            "rating": driver.rating,
            "total_trips": driver.completed_trips,
            "experience_years": driver.experience_years,
            "assigned_truck": truck,
            "owner": owner
        }
    )


class AvailabilityUpdate(BaseModel):
    is_available: bool

@router.patch("/availability", response_model=ResponseModel)
async def update_driver_availability(
    availability_data: AvailabilityUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update driver's availability status"""
    is_available = availability_data.is_available
    if current_user.user_type != UserType.DRIVER.value:
        raise HTTPException(status_code=403, detail="Only drivers can update their availability")
    
    # Get driver profile
    driver = db.query(Driver).filter(Driver.user_id == current_user.id).first()
    if not driver:
        driver = db.query(Driver).filter(Driver.phone == current_user.phone).first()
        if not driver:
            raise HTTPException(status_code=404, detail="Driver profile not found")
    
    # Check if driver is on an active trip
    active_booking = db.query(Booking).filter(
        Booking.driver_id == driver.id,
        Booking.status.in_([BookingStatus.CONFIRMED.value, BookingStatus.IN_PROGRESS.value])
    ).first()
    
    if active_booking and is_available:
        raise HTTPException(
            status_code=400, 
            detail="Cannot set available while on an active booking"
        )
    
    # Update availability
    driver.is_available = is_available
    driver.current_status = "available" if is_available else "off_duty"
    
    db.commit()
    db.refresh(driver)
    
    return ResponseModel(
        success=True,
        message=f"Availability updated to {'available' if is_available else 'off duty'}",
        data={
            "is_available": driver.is_available,
            "current_status": driver.current_status
        }
    )


@router.get("/{driver_id}/otp", response_model=ResponseModel)
async def get_driver_otp(
    driver_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get OTP for a driver - for use by owner/aggregator to share with driver
    The driver shows this OTP to security officer at gate for verification
    """
    if current_user.user_type not in [UserType.AGGREGATOR.value, UserType.OWNER.value]:
        raise HTTPException(status_code=403, detail="Only owners/aggregators can access driver OTP")
    
    # Get driver
    driver = db.query(Driver).filter(Driver.id == driver_id).first()
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found")
    
    # Verify ownership
    if driver.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only access OTP for your own drivers")
    
    # Generate OTP
    from ...utils.code_generator import generate_driver_otp
    otp = generate_driver_otp(driver_id)
    
    return ResponseModel(
        success=True,
        message="Driver OTP generated",
        data={
            "driver_id": driver_id,
            "driver_name": driver.name,
            "driver_phone": driver.phone,
            "otp": otp,
            "instructions": "Share this OTP with the driver. They will show it to the security officer at the gate."
        }
    )


@router.get("/available", response_model=ResponseModel)
async def get_available_drivers(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get only available drivers for the current user"""
    if current_user.user_type not in [UserType.AGGREGATOR.value, UserType.OWNER.value]:
        raise HTTPException(status_code=403, detail="Only owners/aggregators can access this endpoint")
    
    drivers = db.query(Driver).filter(
        Driver.owner_id == current_user.id,
        Driver.is_available == True,
        Driver.is_active == True
    ).all()
    
    return ResponseModel(
        success=True,
        data={
            "drivers": [DriverResponse.model_validate(d) for d in drivers],
            "total": len(drivers)
        }
    )