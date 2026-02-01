from sqlalchemy import Column, String, DateTime, Text, ForeignKey, Boolean
from datetime import datetime
import uuid
import enum
from ..database import Base

class NotificationType(str, enum.Enum):
    BOOKING_CREATED = "booking_created"
    BOOKING_CONFIRMED = "booking_confirmed"
    BOOKING_CANCELLED = "booking_cancelled"
    NEGOTIATION_RECEIVED = "negotiation_received"
    PAYMENT_RECEIVED = "payment_received"
    TRUCK_ASSIGNED = "truck_assigned"
    DRIVER_ASSIGNED = "driver_assigned"
    GATE_IN = "gate_in"
    GATE_OUT = "gate_out"
    TRIP_COMPLETED = "trip_completed"
    SYSTEM_ALERT = "system_alert"

class NotificationLog(Base):
    __tablename__ = "notification_logs"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    notification_type = Column(String(100), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    data = Column(Text, nullable=True)  # JSON string
    
    is_read = Column(Boolean, default=False, index=True)
    read_at = Column(DateTime, nullable=True)
    
    sent_via = Column(String(50), nullable=True)  # 'push', 'sms', 'email', 'websocket'
    sent_at = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
