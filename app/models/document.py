from sqlalchemy import Column, String, DateTime, Text, ForeignKey, Boolean, Integer
from datetime import datetime
import uuid
from ..database import Base

class Document(Base):
    __tablename__ = "documents"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    truck_id = Column(String(36), ForeignKey("trucks.id"), nullable=True)
    driver_id = Column(String(36), ForeignKey("drivers.id"), nullable=True)
    booking_id = Column(String(36), ForeignKey("bookings.id"), nullable=True)
    
    document_type = Column(String(100), nullable=False)  # 'license', 'rc', 'insurance', 'aadhar', 'pan', etc.
    document_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer, nullable=True)
    mime_type = Column(String(100), nullable=True)
    
    verification_status = Column(String(50), default="pending")  # 'pending', 'verified', 'rejected'
    verified_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    verified_at = Column(DateTime, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    
    expiry_date = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
