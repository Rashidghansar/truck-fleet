from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List
from datetime import datetime, date

class DriverCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    phone: str = Field(..., min_length=10, max_length=15)
    email: Optional[EmailStr] = None
    date_of_birth: Optional[date] = None
    address: Optional[str] = None
    identification_mark: Optional[str] = None
    blood_group: Optional[str] = None
    
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    
    license_number: Optional[str] = None
    license_type: Optional[str] = None
    license_issue_date: Optional[date] = None
    license_expiry: Optional[date] = None
    
    aadhar_number: Optional[str] = None
    pan_number: Optional[str] = None
    
    medical_fitness_expiry: Optional[date] = None
    medical_conditions: Optional[str] = None
    
    experience_years: Optional[int] = None
    primary_vehicle_type: Optional[str] = None
    
    bank_account_number: Optional[str] = None
    bank_ifsc_code: Optional[str] = None
    bank_account_holder: Optional[str] = None
    bank_name: Optional[str] = None
    upi_id: Optional[str] = None
    
    work_type: Optional[str] = None
    assigned_truck_id: Optional[str] = None

class DriverResponse(BaseModel):
    id: str
    user_id: Optional[str] = None
    owner_id: Optional[str] = None
    
    name: str
    phone: str
    email: Optional[str] = None
    date_of_birth: Optional[date] = None
    address: Optional[str] = None
    blood_group: Optional[str] = None
    profile_image: Optional[str] = None
    
    license_number: Optional[str] = None
    license_type: Optional[str] = None
    license_expiry: Optional[date] = None
    
    experience_years: Optional[int] = None
    primary_vehicle_type: Optional[str] = None
    
    is_active: bool
    is_available: bool
    is_verified: bool
    current_status: str
    
    assigned_truck_id: Optional[str] = None
    current_lat: Optional[float] = None
    current_lng: Optional[float] = None
    
    total_trips: int
    rating: float
    total_earnings: float
    adverse_remarks: Optional[str] = None
    
    fingerprint_registered: bool
    
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class DriverUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    address: Optional[str] = None
    
    license_number: Optional[str] = None
    license_type: Optional[str] = None
    license_expiry: Optional[date] = None
    
    medical_fitness_expiry: Optional[date] = None
    
    is_available: Optional[bool] = None
    current_status: Optional[str] = None
    assigned_truck_id: Optional[str] = None
    current_lat: Optional[float] = None
    current_lng: Optional[float] = None
    adverse_remarks: Optional[str] = None

class DriverDocumentResponse(BaseModel):
    id: str
    driver_id: str
    document_type: str
    document_url: str
    document_number: Optional[str] = None
    expiry_date: Optional[date] = None
    verified: bool
    uploaded_at: datetime
    
    class Config:
        from_attributes = True

class FingerprintVerify(BaseModel):
    driver_id: Optional[str] = None
    fingerprint_data: str
    
class FingerprintResponse(BaseModel):
    success: bool
    driver: Optional[DriverResponse] = None
    message: str
