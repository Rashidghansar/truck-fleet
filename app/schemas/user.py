from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime

class UserCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    phone: str = Field(..., min_length=10, max_length=15)
    email: Optional[EmailStr] = None
    password: str = Field(..., min_length=6)
    user_type: str
    cfs_name: Optional[str] = None
    cfs_address: Optional[str] = None
    cfs_license: Optional[str] = None
    address: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None

class UserLogin(BaseModel):
    phone: str
    password: str
    user_type: Optional[str] = None

class UserResponse(BaseModel):
    id: str
    name: str
    phone: str
    email: Optional[str] = None
    user_type: str
    profile_image: Optional[str] = None
    is_active: bool
    is_verified: bool
    rating: Optional[float] = None
    completed_trips: int = 0
    cfs_name: Optional[str] = None
    cfs_address: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True

class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    profile_image: Optional[str] = None
    address: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None

class DriverProfileInfo(BaseModel):
    id: str
    name: str
    license_number: Optional[str] = None
    is_available: bool = True
    current_status: str = "available"
    assigned_truck_id: Optional[str] = None
    owner_id: Optional[str] = None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse
    driver_profile: Optional[dict] = None  # Driver profile info for driver users
    requires_password_change: bool = False  # For auto-created drivers
