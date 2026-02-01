from sqlalchemy import Column, String, Float, DateTime, ForeignKey, Text, Integer
from datetime import datetime
import uuid
from ..database import Base

class Payment(Base):
    __tablename__ = "payments"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    booking_id = Column(String(36), ForeignKey("bookings.id"), nullable=False)
    
    payer_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    payee_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    
    amount = Column(Float, nullable=False)
    payment_type = Column(String(50), nullable=False)  # advance, full, partial
    payment_method = Column(String(50), nullable=True)  # upi, neft, imps, card, cash
    
    transaction_id = Column(String(255), nullable=True)
    payment_gateway_id = Column(String(255), nullable=True)
    
    payment_status = Column(String(50), default="pending")  # pending, completed, failed, refunded
    
    payment_date = Column(DateTime, nullable=True)
    due_date = Column(DateTime, nullable=True)
    
    # Fee breakdown
    base_amount = Column(Float, nullable=True)
    gst_amount = Column(Float, nullable=True)
    platform_fee = Column(Float, nullable=True)
    
    # Notes
    notes = Column(Text, nullable=True)
    failure_reason = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class RatingReview(Base):
    __tablename__ = "ratings_reviews"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    trip_id = Column(String(36), ForeignKey("trips.id"), nullable=False)
    
    rated_by = Column(String(36), ForeignKey("users.id"), nullable=False)
    rated_to = Column(String(36), ForeignKey("users.id"), nullable=False)
    
    rating = Column(Integer, nullable=False)  # 1-5
    review = Column(Text, nullable=True)
    
    # Rating categories (optional)
    punctuality_rating = Column(Integer, nullable=True)
    professionalism_rating = Column(Integer, nullable=True)
    vehicle_condition_rating = Column(Integer, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
