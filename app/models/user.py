from sqlalchemy import Column, String, Boolean, DateTime, Float, Integer, Text, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum
from ..database import Base

class UserType(str, enum.Enum):
    CFS_ADMIN = "cfs_admin"
    SECURITY_OFFICER = "security_officer"
    AGGREGATOR = "aggregator"
    OWNER = "owner"
    DRIVER = "driver"

class User(Base):
    __tablename__ = "users"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    phone = Column(String(15), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=True)
    password_hash = Column(String(255), nullable=False)
    user_type = Column(String(50), nullable=False)
    profile_image = Column(String(500), nullable=True)
    address = Column(Text, nullable=True)
    
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    phone_verified = Column(Boolean, default=False)
    
    rating = Column(Float, default=0.0)
    completed_trips = Column(Integer, default=0)
    
    # CFS specific fields
    cfs_id = Column(String(36), ForeignKey("cfs_locations.id"), nullable=True)
    cfs_name = Column(String(200), nullable=True)
    cfs_address = Column(String(500), nullable=True)
    cfs_license = Column(String(100), nullable=True)
    
    # Security Officer - linked to admin who created them
    # This ensures security officers can only authenticate bookings from their admin
    created_by_admin_id = Column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    
    # Emergency contact
    emergency_contact_name = Column(String(255), nullable=True)
    emergency_contact_phone = Column(String(15), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)
    
    # Relationships
    bookings = relationship("Booking", back_populates="cfs", foreign_keys="Booking.cfs_id")
    trucks = relationship("Truck", back_populates="owner")
    cfs_location = relationship("CfsLocation", back_populates="users")
    # Security officers created by this admin
    security_officers = relationship("User", backref="created_by_admin", remote_side=[id], foreign_keys=[created_by_admin_id])

class CfsLocation(Base):
    __tablename__ = "cfs_locations"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    address = Column(Text, nullable=False)
    city = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)
    pincode = Column(String(10), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    contact_person = Column(String(255), nullable=True)
    contact_phone = Column(String(15), nullable=True)
    
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    users = relationship("User", back_populates="cfs_location")
    bays = relationship("CfsBay", back_populates="cfs")

class CfsBay(Base):
    __tablename__ = "cfs_bays"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    cfs_id = Column(String(36), ForeignKey("cfs_locations.id"), nullable=False)
    bay_number = Column(String(50), nullable=False)
    supervisor_name = Column(String(255), nullable=True)
    supervisor_phone = Column(String(15), nullable=True)
    is_available = Column(Boolean, default=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    cfs = relationship("CfsLocation", back_populates="bays")

class Aggregator(Base):
    __tablename__ = "aggregators"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    company_name = Column(String(255), nullable=True)
    gst_number = Column(String(15), nullable=True)
    pan_number = Column(String(10), nullable=True)
    business_type = Column(String(100), nullable=True)
    years_in_business = Column(String(50), nullable=True)
    fleet_size = Column(Integer, nullable=True)
    service_areas = Column(Text, nullable=True)  # JSON string
    verification_status = Column(String(50), default="pending")
    
    created_at = Column(DateTime, default=datetime.utcnow)

class BankDetails(Base):
    __tablename__ = "bank_details"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    account_number = Column(String(50), nullable=True)
    ifsc_code = Column(String(11), nullable=True)
    account_holder_name = Column(String(255), nullable=True)
    bank_name = Column(String(255), nullable=True)
    branch_name = Column(String(255), nullable=True)
    account_type = Column(String(50), nullable=True)
    upi_id = Column(String(255), nullable=True)
    is_verified = Column(Boolean, default=False)
    
    created_at = Column(DateTime, default=datetime.utcnow)
