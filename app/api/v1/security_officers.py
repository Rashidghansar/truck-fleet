from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel
from ...database import get_db
from ...models.user import User, UserType
from ...schemas.response import ResponseModel
from ...core.deps import get_current_user
from ...core.security import get_password_hash

router = APIRouter()


class SecurityOfficerCreate(BaseModel):
    name: str
    phone: str
    password: str
    email: Optional[str] = None


class SecurityOfficerResponse(BaseModel):
    id: str
    name: str
    phone: str
    email: Optional[str] = None
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


@router.post("/create", response_model=ResponseModel)
async def create_security_officer(
    officer_data: SecurityOfficerCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Admin creates a security officer linked to them.
    Only bookings from this admin can be authenticated by this security officer.
    """
    if current_user.user_type != UserType.CFS_ADMIN.value:
        raise HTTPException(status_code=403, detail="Only CFS admins can create security officers")
    
    # Check if phone already exists
    existing = db.query(User).filter(User.phone == officer_data.phone).first()
    if existing:
        raise HTTPException(status_code=400, detail="Phone number already registered")
    
    # Check if email already exists
    if officer_data.email:
        existing_email = db.query(User).filter(User.email == officer_data.email).first()
        if existing_email:
            raise HTTPException(status_code=400, detail="Email already registered")
    
    # Create security officer linked to this admin
    officer = User(
        name=officer_data.name,
        phone=officer_data.phone,
        email=officer_data.email,
        password_hash=get_password_hash(officer_data.password),
        user_type=UserType.SECURITY_OFFICER.value,
        is_active=True,
        is_verified=True,
        phone_verified=True,
        created_by_admin_id=current_user.id,  # Link to admin
        cfs_id=current_user.cfs_id,  # Also inherit CFS location
        cfs_name=current_user.cfs_name,
        cfs_address=current_user.cfs_address,
    )
    
    db.add(officer)
    db.commit()
    db.refresh(officer)
    
    return ResponseModel(
        success=True,
        message="Security officer created successfully",
        data=SecurityOfficerResponse.model_validate(officer)
    )


@router.get("", response_model=ResponseModel)
async def get_my_security_officers(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get security officers created by this admin"""
    if current_user.user_type != UserType.CFS_ADMIN.value:
        raise HTTPException(status_code=403, detail="Only CFS admins can view security officers")
    
    query = db.query(User).filter(
        User.user_type == UserType.SECURITY_OFFICER.value,
        User.created_by_admin_id == current_user.id
    )
    
    total = query.count()
    offset = (page - 1) * page_size
    officers = query.order_by(User.created_at.desc()).offset(offset).limit(page_size).all()
    
    return ResponseModel(
        success=True,
        data={
            "officers": [SecurityOfficerResponse.model_validate(o) for o in officers],
            "total": total,
            "page": page,
            "page_size": page_size
        }
    )


@router.put("/{officer_id}/toggle-status", response_model=ResponseModel)
async def toggle_security_officer_status(
    officer_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Enable/disable a security officer"""
    if current_user.user_type != UserType.CFS_ADMIN.value:
        raise HTTPException(status_code=403, detail="Only CFS admins can manage security officers")
    
    officer = db.query(User).filter(
        User.id == officer_id,
        User.user_type == UserType.SECURITY_OFFICER.value,
        User.created_by_admin_id == current_user.id
    ).first()
    
    if not officer:
        raise HTTPException(status_code=404, detail="Security officer not found")
    
    officer.is_active = not officer.is_active
    db.commit()
    
    return ResponseModel(
        success=True,
        message=f"Security officer {'enabled' if officer.is_active else 'disabled'}",
        data={"is_active": officer.is_active}
    )


@router.delete("/{officer_id}", response_model=ResponseModel)
async def delete_security_officer(
    officer_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a security officer"""
    if current_user.user_type != UserType.CFS_ADMIN.value:
        raise HTTPException(status_code=403, detail="Only CFS admins can delete security officers")
    
    officer = db.query(User).filter(
        User.id == officer_id,
        User.user_type == UserType.SECURITY_OFFICER.value,
        User.created_by_admin_id == current_user.id
    ).first()
    
    if not officer:
        raise HTTPException(status_code=404, detail="Security officer not found")
    
    # Soft delete - just deactivate
    officer.is_active = False
    db.commit()
    
    return ResponseModel(success=True, message="Security officer removed")


@router.get("/check-authorization/{booking_id}", response_model=ResponseModel)
async def check_security_officer_authorization(
    booking_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Check if the current security officer is authorized to authenticate a booking.
    Security officers can only authenticate bookings from the admin who created them.
    """
    if current_user.user_type != UserType.SECURITY_OFFICER.value:
        raise HTTPException(status_code=403, detail="Only security officers can use this endpoint")
    
    from ...models.booking import Booking
    
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    # Check if security officer was created by the admin who created this booking
    is_authorized = current_user.created_by_admin_id == booking.cfs_id
    
    if not is_authorized:
        # Get the correct admin name for helpful error message
        booking_admin = db.query(User).filter(User.id == booking.cfs_id).first()
        return ResponseModel(
            success=False,
            message=f"Not authorized. This booking belongs to {booking_admin.cfs_name or booking_admin.name if booking_admin else 'another admin'}. Contact your admin.",
            data={
                "authorized": False,
                "reason": "security_officer_admin_mismatch"
            }
        )
    
    return ResponseModel(
        success=True,
        message="Authorized to verify this booking",
        data={"authorized": True}
    )
