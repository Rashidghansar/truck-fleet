from sqlalchemy import Column, String, DateTime, Text, ForeignKey
from datetime import datetime
import uuid
from ..database import Base

class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    action = Column(String(100), nullable=False)  # 'create', 'update', 'delete', 'login', etc.
    resource_type = Column(String(100), nullable=False)  # 'booking', 'user', 'truck', etc.
    resource_id = Column(String(36), nullable=True)
    details = Column(Text, nullable=True)  # JSON string
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
