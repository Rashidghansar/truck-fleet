from sqlalchemy import Column, String, DateTime, Float, ForeignKey, Text, Boolean, Integer
from datetime import datetime
import uuid
import enum
from ..database import Base

class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"
    CANCELLED = "cancelled"

class PaymentMethod(str, enum.Enum):
    CASH = "cash"
    UPI = "upi"
    BANK_TRANSFER = "bank_transfer"
    CHEQUE = "cheque"
    CARD = "card"

class PaymentTransaction(Base):
    __tablename__ = "payment_transactions"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    booking_id = Column(String(36), ForeignKey("bookings.id"), nullable=False, index=True)
    payer_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    payee_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    
    amount = Column(Float, nullable=False)
    currency = Column(String(10), default="INR")
    payment_method = Column(String(50), nullable=False)
    transaction_id = Column(String(255), nullable=True, unique=True, index=True)
    reference_number = Column(String(255), nullable=True)
    
    status = Column(String(50), default="pending", index=True)
    failure_reason = Column(Text, nullable=True)
    
    payment_date = Column(DateTime, nullable=True)
    processed_at = Column(DateTime, nullable=True)
    
    notes = Column(Text, nullable=True)
    payment_metadata = Column(Text, nullable=True)  # JSON string for additional data
    
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
