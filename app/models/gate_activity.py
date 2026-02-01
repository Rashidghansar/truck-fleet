from sqlalchemy import Column, String, Boolean, DateTime, Float, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
from ..database import Base

class GateActivity(Base):
    __tablename__ = "gate_activities"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    booking_id = Column(String(36), ForeignKey("bookings.id"), nullable=True)
    driver_id = Column(String(36), ForeignKey("drivers.id"), nullable=False)
    truck_id = Column(String(36), ForeignKey("trucks.id"), nullable=True)
    
    # Activity type
    activity_type = Column(String(50), nullable=False)  # gate_in, gate_out
    security_officer_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    
    # Timing
    gate_time = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Location
    gps_latitude = Column(Float, nullable=True)
    gps_longitude = Column(Float, nullable=True)
    
    # Gate-in specific
    is_truck_empty = Column(Boolean, nullable=True)
    seal_status = Column(String(50), nullable=True)  # intact, broken, no_seal
    vehicle_condition = Column(String(50), nullable=True)  # no_damage, minor_damage, major_damage
    documents_verified = Column(Boolean, default=False)
    bay_number = Column(String(50), nullable=True)
    
    # Gate-out specific
    container_number = Column(String(50), nullable=True)
    seal_number = Column(String(100), nullable=True)
    loaded_weight = Column(Float, nullable=True)
    safety_checks_passed = Column(Boolean, default=False)
    destination_confirmed = Column(Boolean, default=False)
    
    # Photos (stored as JSON array of URLs)
    photos = Column(Text, nullable=True)
    seal_photos = Column(Text, nullable=True)
    container_photos = Column(Text, nullable=True)
    
    # Documents
    eway_bill = Column(String(500), nullable=True)
    loading_receipt = Column(String(500), nullable=True)
    delivery_challan = Column(String(500), nullable=True)
    
    # Remarks
    remarks = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    booking = relationship("Booking", back_populates="gate_activities")

class Trip(Base):
    __tablename__ = "trips"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    booking_id = Column(String(36), ForeignKey("bookings.id"), nullable=False)
    driver_id = Column(String(36), ForeignKey("drivers.id"), nullable=False)
    truck_id = Column(String(36), ForeignKey("trucks.id"), nullable=True)
    
    # Gate references
    gate_in_id = Column(String(36), ForeignKey("gate_activities.id"), nullable=True)
    gate_out_id = Column(String(36), ForeignKey("gate_activities.id"), nullable=True)
    
    # Timing and ETA
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)
    expected_arrival_time = Column(DateTime, nullable=True)
    expected_duration_minutes = Column(Float, nullable=True)
    actual_arrival_time = Column(DateTime, nullable=True)
    
    # Delay tracking
    is_delayed = Column(Boolean, default=False)
    delay_minutes = Column(Float, default=0.0)
    delay_reason = Column(Text, nullable=True)
    delay_notified_at = Column(DateTime, nullable=True)
    
    # Status
    status = Column(String(50), default="pending")  # pending, en_route_to_pickup, at_pickup, en_route_to_destination, completed, cancelled
    
    # Current location
    current_latitude = Column(Float, nullable=True)
    current_longitude = Column(Float, nullable=True)
    current_speed = Column(Float, nullable=True)
    last_location_update = Column(DateTime, nullable=True)
    
    # Progress
    distance_covered = Column(Float, default=0.0)
    distance_remaining = Column(Float, nullable=True)
    total_distance = Column(Float, nullable=True)
    progress_percentage = Column(Float, default=0.0)
    
    # Delivery
    delivery_photos = Column(Text, nullable=True)  # JSON array
    receiver_name = Column(String(255), nullable=True)
    receiver_phone = Column(String(15), nullable=True)
    receiver_signature = Column(Text, nullable=True)  # Base64
    delivery_otp = Column(String(6), nullable=True)
    delivery_otp_verified = Column(Boolean, default=False)
    delivery_condition = Column(String(100), nullable=True)
    delivery_remarks = Column(Text, nullable=True)
    actual_delivery_time = Column(DateTime, nullable=True)
    
    # Milestones (JSON array)
    milestones = Column(Text, nullable=True)
    
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    booking = relationship("Booking", back_populates="trip")
