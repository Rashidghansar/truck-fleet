from sqlalchemy import Column, String, Boolean, DateTime, Text, ForeignKey
from datetime import datetime
import uuid
from ..database import Base

class Notification(Base):
    __tablename__ = "notifications"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    notification_type = Column(String(50), nullable=False)  # booking, payment, trip, system, gate
    
    # Reference to related entity
    reference_id = Column(String(36), nullable=True)
    reference_type = Column(String(50), nullable=True)  # booking, trip, payment, etc.
    
    # Action data (JSON)
    action_data = Column(Text, nullable=True)
    
    # Status
    is_read = Column(Boolean, default=False)
    read_at = Column(DateTime, nullable=True)
    
    # Delivery status
    push_sent = Column(Boolean, default=False)
    push_sent_at = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
