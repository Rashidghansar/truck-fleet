from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime, date

class TruckCreate(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    
    truck_number: str = Field(..., min_length=4, max_length=20)
    truck_type: str
    capacity: str
    truck_make: Optional[str] = None
    model_year: Optional[int] = None
    fuel_type: Optional[str] = None
    load_capacity_tons: Optional[float] = None
    
    has_gps: bool = False
    gps_device_id: Optional[str] = None
    
    ownership_type: Optional[str] = None
    owner_name: Optional[str] = None
    owner_address: Optional[str] = None
    owner_phone: Optional[str] = None
    
    rc_number: Optional[str] = None
    registration_date: Optional[date] = None
    insurance_number: Optional[str] = None
    insurance_expiry: Optional[date] = None
    fitness_expiry: Optional[date] = None
    puc_expiry: Optional[date] = None
    permit_type: Optional[str] = None
    permit_expiry: Optional[date] = None

class TruckResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())
    
    id: str
    owner_id: str
    truck_number: str
    registration_number: Optional[str] = None
    truck_type: str
    capacity: str
    truck_make: Optional[str] = None
    model_year: Optional[int] = None
    fuel_type: Optional[str] = None
    load_capacity_tons: Optional[float] = None
    
    has_gps: bool
    gps_device_id: Optional[str] = None
    
    ownership_type: Optional[str] = None
    owner_name: Optional[str] = None
    
    rc_number: Optional[str] = None
    rc_book_image: Optional[str] = None
    insurance_expiry: Optional[datetime] = None
    fitness_expiry: Optional[datetime] = None
    puc_expiry: Optional[datetime] = None
    permit_type: Optional[str] = None
    permit_expiry: Optional[datetime] = None
    
    is_active: bool
    is_available: bool
    is_verified: bool
    current_status: str
    
    current_driver_id: Optional[str] = None
    current_driver_name: Optional[str] = None
    current_lat: Optional[float] = None
    current_lng: Optional[float] = None
    
    total_trips: int
    rating: float
    total_earnings: float
    
    created_at: datetime
    updated_at: datetime

class TruckUpdate(BaseModel):
    truck_type: Optional[str] = None
    capacity: Optional[str] = None
    truck_make: Optional[str] = None
    fuel_type: Optional[str] = None
    has_gps: Optional[bool] = None
    gps_device_id: Optional[str] = None
    insurance_expiry: Optional[date] = None
    fitness_expiry: Optional[date] = None
    puc_expiry: Optional[date] = None
    is_available: Optional[bool] = None
    current_status: Optional[str] = None
    current_lat: Optional[float] = None
    current_lng: Optional[float] = None

class TruckPhotoResponse(BaseModel):
    id: str
    truck_id: str
    photo_url: str
    photo_type: Optional[str] = None
    uploaded_at: datetime
    
    class Config:
        from_attributes = True
