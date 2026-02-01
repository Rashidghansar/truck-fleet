from sqlalchemy import Column, String, Boolean, DateTime, Float, Integer, ForeignKey, Text, Date
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
from ..database import Base

class Driver(Base):
    __tablename__ = "drivers"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    owner_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    
    # Personal details
    name = Column(String(255), nullable=False)
    phone = Column(String(15), unique=True, nullable=False, index=True)
    email = Column(String(255), nullable=True)
    date_of_birth = Column(Date, nullable=True)
    address = Column(Text, nullable=True)
    identification_mark = Column(String(255), nullable=True)
    blood_group = Column(String(5), nullable=True)
    profile_image = Column(String(500), nullable=True)
    
    # Emergency contact
    emergency_contact_name = Column(String(255), nullable=True)
    emergency_contact_phone = Column(String(15), nullable=True)
    
    # License details
    license_number = Column(String(50), nullable=True, index=True)
    license_type = Column(String(50), nullable=True)
    license_image = Column(String(500), nullable=True)
    license_back_image = Column(String(500), nullable=True)
    license_issue_date = Column(Date, nullable=True)
    license_expiry = Column(Date, nullable=True)
    
    # Identity documents
    aadhar_number = Column(String(20), nullable=True)
    aadhar_image = Column(String(500), nullable=True)
    aadhar_back_image = Column(String(500), nullable=True)
    pan_number = Column(String(10), nullable=True)
    pan_image = Column(String(500), nullable=True)
    
    # Health
    medical_fitness_expiry = Column(Date, nullable=True)
    medical_fitness_image = Column(String(500), nullable=True)
    medical_conditions = Column(Text, nullable=True)
    
    # Experience
    experience_years = Column(Integer, nullable=True)
    primary_vehicle_type = Column(String(100), nullable=True)
    
    # Biometric
    fingerprint_data = Column(Text, nullable=True)
    fingerprint_registered = Column(Boolean, default=False)
    
    # Bank details
    bank_account_number = Column(String(50), nullable=True)
    bank_ifsc_code = Column(String(11), nullable=True)
    bank_account_holder = Column(String(255), nullable=True)
    bank_name = Column(String(255), nullable=True)
    upi_id = Column(String(255), nullable=True)
    
    # Status
    is_active = Column(Boolean, default=True)
    is_available = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    current_status = Column(String(50), default="available")  # available, on_trip, off_duty
    
    # Auto-created driver tracking
    auto_created = Column(Boolean, default=False)
    temp_password = Column(String(255), nullable=True)  # Temporary password for auto-created drivers
    password_changed = Column(Boolean, default=True)  # False for auto-created until they change it
    created_by_user_id = Column(String(36), nullable=True)  # Owner/Aggregator who created
    
    # Current assignment
    assigned_truck_id = Column(String(36), nullable=True)
    current_lat = Column(Float, nullable=True)
    current_lng = Column(Float, nullable=True)
    last_location_update = Column(DateTime, nullable=True)
    
    # Statistics
    total_trips = Column(Integer, default=0)
    rating = Column(Float, default=0.0)
    total_earnings = Column(Float, default=0.0)
    adverse_remarks = Column(Text, nullable=True)
    
    # Work preferences
    work_type = Column(String(100), nullable=True)  # full-time, part-time, contract, flexible
    preferred_routes = Column(Text, nullable=True)  # JSON string of cities/states
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    bookings = relationship("Booking", back_populates="driver")
    documents = relationship("DriverDocument", back_populates="driver")

class DriverDocument(Base):
    __tablename__ = "driver_documents"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    driver_id = Column(String(36), ForeignKey("drivers.id"), nullable=False)
    document_type = Column(String(100), nullable=False)
    document_url = Column(String(500), nullable=False)
    document_number = Column(String(100), nullable=True)
    expiry_date = Column(Date, nullable=True)
    verified = Column(Boolean, default=False)
    
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    driver = relationship("Driver", back_populates="documents")
