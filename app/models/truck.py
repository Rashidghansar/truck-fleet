from sqlalchemy import Column, String, Boolean, DateTime, Float, Integer, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
from ..database import Base

class Truck(Base):
    __tablename__ = "trucks"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    owner_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    
    # Basic details
    truck_number = Column(String(20), unique=True, nullable=False, index=True)
    registration_number = Column(String(20), nullable=True)
    truck_type = Column(String(100), nullable=False)
    capacity = Column(String(50), nullable=False)
    truck_make = Column(String(100), nullable=True)
    model_year = Column(Integer, nullable=True)
    fuel_type = Column(String(50), nullable=True)
    load_capacity_tons = Column(Float, nullable=True)
    
    # GPS
    has_gps = Column(Boolean, default=False)
    gps_device_id = Column(String(255), nullable=True)
    
    # Ownership
    ownership_type = Column(String(50), nullable=True)
    owner_name = Column(String(255), nullable=True)
    owner_address = Column(Text, nullable=True)
    owner_phone = Column(String(15), nullable=True)
    
    # Documents
    rc_number = Column(String(255), nullable=True)
    rc_book_image = Column(String(500), nullable=True)
    registration_date = Column(DateTime, nullable=True)
    
    insurance_number = Column(String(255), nullable=True)
    insurance_image = Column(String(500), nullable=True)
    insurance_expiry = Column(DateTime, nullable=True)
    
    fitness_certificate = Column(String(500), nullable=True)
    fitness_expiry = Column(DateTime, nullable=True)
    
    puc_certificate = Column(String(500), nullable=True)
    puc_expiry = Column(DateTime, nullable=True)
    
    permit_type = Column(String(50), nullable=True)
    permit_expiry = Column(DateTime, nullable=True)
    
    # Status
    is_active = Column(Boolean, default=True)
    is_available = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    current_status = Column(String(50), default="available")  # available, in_trip, maintenance, offline
    
    # Current position
    current_driver_id = Column(String(36), nullable=True)
    current_lat = Column(Float, nullable=True)
    current_lng = Column(Float, nullable=True)
    last_location_update = Column(DateTime, nullable=True)
    
    # Statistics
    total_trips = Column(Integer, default=0)
    rating = Column(Float, default=0.0)
    total_earnings = Column(Float, default=0.0)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    owner = relationship("User", back_populates="trucks")
    bookings = relationship("Booking", back_populates="truck")
    photos = relationship("TruckPhoto", back_populates="truck")

class TruckPhoto(Base):
    __tablename__ = "truck_photos"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    truck_id = Column(String(36), ForeignKey("trucks.id"), nullable=False)
    photo_url = Column(String(500), nullable=False)
    photo_type = Column(String(50), nullable=True)  # front, side, rc_document, etc.
    
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    truck = relationship("Truck", back_populates="photos")
