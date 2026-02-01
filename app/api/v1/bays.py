"""API endpoints for bay management"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from ...database import get_db
from ...models.user import User, UserType, CfsBay, CfsLocation
from ...schemas.response import ResponseModel
from ...core.deps import get_current_user
from ...utils.bay_manager import (
    get_bay_occupancy_stats,
    get_bay_list,
    release_bay
)

router = APIRouter()


@router.post("/configure", response_model=ResponseModel)
async def configure_bays(
    total_bays: int,
    bay_prefix: str = "BAY-",
    supervisor_name: str = None,
    supervisor_phone: str = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Configure bays for CFS - creates bay records"""
    if current_user.user_type != UserType.CFS_ADMIN.value:
        raise HTTPException(status_code=403, detail="Only CFS admins can configure bays")
    
    # Get or create CFS location
    cfs_location = db.query(CfsLocation).filter(CfsLocation.id == current_user.cfs_id).first()
    
    if not cfs_location and current_user.cfs_name:
        # Create CFS location
        cfs_location = CfsLocation(
            name=current_user.cfs_name,
            address=current_user.cfs_address or "",
            contact_person=current_user.name,
            contact_phone=current_user.phone
        )
        db.add(cfs_location)
        db.flush()
        
        # Update user's cfs_id
        current_user.cfs_id = cfs_location.id
    
    if not cfs_location:
        raise HTTPException(status_code=400, detail="CFS location not configured")
    
    # Delete existing bays
    db.query(CfsBay).filter(CfsBay.cfs_id == cfs_location.id).delete()
    
    # Create new bays
    created_bays = []
    for i in range(1, total_bays + 1):
        bay = CfsBay(
            cfs_id=cfs_location.id,
            bay_number=f"{bay_prefix}{i:02d}",
            supervisor_name=supervisor_name,
            supervisor_phone=supervisor_phone,
            is_available=True
        )
        db.add(bay)
        created_bays.append({
            "bay_number": bay.bay_number,
            "supervisor_name": bay.supervisor_name
        })
    
    db.commit()
    
    return ResponseModel(
        success=True,
        message=f"Successfully configured {total_bays} bays",
        data={"bays": created_bays}
    )


@router.get("/occupancy", response_model=ResponseModel)
async def get_bay_occupancy(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get real-time bay occupancy statistics"""
    if current_user.user_type not in [UserType.CFS_ADMIN.value, UserType.SECURITY_OFFICER.value]:
        raise HTTPException(status_code=403, detail="Access denied")
    
    cfs_id = current_user.cfs_id
    if not cfs_id:
        return ResponseModel(
            success=True,
            data={"total": 0, "occupied": 0, "available": 0, "occupancy_percentage": 0}
        )
    
    stats = get_bay_occupancy_stats(db, cfs_id)
    
    return ResponseModel(
        success=True,
        data=stats
    )


@router.get("/list", response_model=ResponseModel)
async def list_bays(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get list of all bays with current status"""
    if current_user.user_type not in [UserType.CFS_ADMIN.value, UserType.SECURITY_OFFICER.value]:
        raise HTTPException(status_code=403, detail="Access denied")
    
    cfs_id = current_user.cfs_id
    if not cfs_id:
        return ResponseModel(
            success=True,
            data={"bays": []}
        )
    
    bays = get_bay_list(db, cfs_id)
    
    return ResponseModel(
        success=True,
        data={"bays": bays}
    )


@router.put("/{bay_id}/override", response_model=ResponseModel)
async def override_bay_assignment(
    bay_id: str,
    booking_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Security officer can override bay assignment"""
    if current_user.user_type != UserType.SECURITY_OFFICER.value:
        raise HTTPException(status_code=403, detail="Only security officers can override bay assignments")
    
    from ...models.booking import Booking
    
    bay = db.query(CfsBay).filter(CfsBay.id == bay_id).first()
    if not bay:
        raise HTTPException(status_code=404, detail="Bay not found")
    
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    # Release old bay if assigned
    if booking.bay_id:
        old_bay = db.query(CfsBay).filter(CfsBay.id == booking.bay_id).first()
        if old_bay:
            old_bay.is_available = True
    
    # Assign new bay
    booking.bay_id = bay.id
    booking.bay_number = bay.bay_number
    booking.bay_contact_name = bay.supervisor_name
    booking.bay_contact_phone = bay.supervisor_phone
    bay.is_available = False
    
    db.commit()
    
    return ResponseModel(
        success=True,
        message=f"Bay {bay.bay_number} assigned to booking {booking.demand_number}"
    )

