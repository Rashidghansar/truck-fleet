from sqlalchemy import Column, String, Float, DateTime, ForeignKey, Text, Boolean, Integer
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum
from ..database import Base

class BookingStatus(str, enum.Enum):
    PENDING = "pending"
    NEGOTIATING = "negotiating"
    CONFIRMED = "confirmed"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

class ContainerType(str, enum.Enum):
    IMPORT = "Import Container"
    EXPORT = "Export Container"
    DOMESTIC = "Domestic Cargo"
    REEFER = "Reefer Container"
    HAZARDOUS = "Hazardous Material"

class ContainerSize(str, enum.Enum):
    TWENTY_FT = "20ft"
    FORTY_FT = "40ft"
    FORTY_FT_HC = "40ft HC"

class TruckType(str, enum.Enum):
    CONTAINER_20FT = "20ft Container Truck"
    CONTAINER_40FT = "40ft Container Truck"
    FLAT_BED = "Flat Bed Truck"
    REEFER = "Reefer Truck"
    TRAILER = "Trailer Truck"

class PaymentTerms(str, enum.Enum):
    IMMEDIATE = "immediate"
    SEVEN_DAYS = "7_days"
    FOURTEEN_DAYS = "14_days"
    THIRTY_DAYS = "30_days"

class Booking(Base):
    __tablename__ = "bookings"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    demand_number = Column(String(50), unique=True, nullable=False, index=True)
    
    cfs_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    aggregator_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    driver_id = Column(String(36), ForeignKey("drivers.id"), nullable=True)
    truck_id = Column(String(36), ForeignKey("trucks.id"), nullable=True)
    
    # Consignment details
    consignment_type = Column(String(100), nullable=False)
    container_number = Column(String(50), nullable=True)
    weight = Column(Float, nullable=True)
    special_instructions = Column(Text, nullable=True)
    
    # Truck requirements
    truck_type = Column(String(100), nullable=False)
    truck_capacity = Column(String(50), nullable=True)
    quantity = Column(Integer, default=1)
    
    # CFS Details
    gate_in_time = Column(DateTime, nullable=True)
    gate_out_time = Column(DateTime, nullable=True)
    bay_id = Column(String(36), nullable=True)
    bay_number = Column(String(50), nullable=True)
    bay_contact_name = Column(String(255), nullable=True)
    bay_contact_phone = Column(String(15), nullable=True)
    
    # Pickup location
    pickup_location = Column(String(500), nullable=False)
    pickup_lat = Column(Float, nullable=True)
    pickup_lng = Column(Float, nullable=True)
    
    # Destination details
    destination_address = Column(Text, nullable=True)
    destination_lat = Column(Float, nullable=True)
    destination_lng = Column(Float, nullable=True)
    destination_gate_in_time = Column(DateTime, nullable=True)
    destination_contact_name = Column(String(255), nullable=True)
    destination_contact_phone = Column(String(15), nullable=True)
    
    # Legacy fields for compatibility
    container_type = Column(String(100), nullable=True)
    container_size = Column(String(50), nullable=True)
    delivery_location = Column(String(500), nullable=True)
    delivery_lat = Column(Float, nullable=True)
    delivery_lng = Column(Float, nullable=True)
    pickup_date = Column(DateTime, nullable=True)
    pickup_time_slot = Column(String(50), nullable=True)
    
    # Pricing
    base_price = Column(Float, nullable=True)
    published_rate = Column(Float, nullable=True)
    agreed_rate = Column(Float, nullable=True)
    proposed_rate = Column(Float, nullable=True)
    
    # Payment
    payment_terms = Column(String(50), default="immediate")
    is_negotiable = Column(Boolean, default=False)
    
    # Status
    status = Column(String(50), default="pending")
    notes = Column(Text, nullable=True)
    
    # Actual times
    actual_gate_in_time = Column(DateTime, nullable=True)
    actual_gate_out_time = Column(DateTime, nullable=True)
    actual_delivery_time = Column(DateTime, nullable=True)
    
    # Distance
    distance_km = Column(Float, nullable=True)
    
    # QR Code and Numeric Code for gate check-in/checkout
    gate_qr_code = Column(String(255), nullable=True, unique=True, index=True)
    gate_numeric_code = Column(String(6), nullable=True, unique=True, index=True)
    gate_code_generated_at = Column(DateTime, nullable=True)
    
    # Check-in tracking
    checkin_qr_scanned = Column(Boolean, default=False)
    checkin_time = Column(DateTime, nullable=True)
    checkin_method = Column(String(20), nullable=True)  # 'qr' or 'numeric'
    
    # Checkout tracking
    checkout_qr_scanned = Column(Boolean, default=False)
    checkout_time = Column(DateTime, nullable=True)
    checkout_method = Column(String(20), nullable=True)  # 'qr' or 'numeric'
    
    # Legacy field for backward compatibility
    gate_qr_scanned = Column(Boolean, default=False)
    gate_qr_scanned_at = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    cfs = relationship("User", back_populates="bookings", foreign_keys=[cfs_id])
    driver = relationship("Driver", back_populates="bookings")
    truck = relationship("Truck", back_populates="bookings")
    gate_activities = relationship("GateActivity", back_populates="booking")
    negotiations = relationship("Negotiation", back_populates="booking")
    trip = relationship("Trip", back_populates="booking", uselist=False)

class Negotiation(Base):
    __tablename__ = "negotiations"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    booking_id = Column(String(36), ForeignKey("bookings.id"), nullable=False)
    offered_by = Column(String(36), ForeignKey("users.id"), nullable=False)
    offered_rate = Column(Float, nullable=False)
    justification = Column(Text, nullable=True)
    payment_terms = Column(String(50), nullable=True)
    status = Column(String(50), default="pending")  # pending, accepted, rejected, countered
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    booking = relationship("Booking", back_populates="negotiations")

def generate_demand_number():
    """Generate unique demand number"""
    from datetime import datetime
    now = datetime.now()
    return f"DEM-{now.year}-{now.month:02d}{now.day:02d}-{str(uuid.uuid4())[:3].upper()}"
