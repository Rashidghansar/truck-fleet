from sqlalchemy import Column, String, DateTime, Boolean, Integer
from datetime import datetime, timedelta
import uuid
from ..database import Base

class OTP(Base):
    __tablename__ = "otps"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    phone = Column(String(15), nullable=False, index=True)
    otp_code = Column(String(10), nullable=False)
    purpose = Column(String(50), nullable=False)  # 'phone_verification', 'password_reset'
    is_used = Column(Boolean, default=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def is_expired(self) -> bool:
        return datetime.utcnow() > self.expires_at
    
    def is_valid(self) -> bool:
        return not self.is_used and not self.is_expired()
