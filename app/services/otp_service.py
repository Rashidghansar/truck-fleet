from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from ..models.otp import OTP
from typing import Optional

# Hardcoded OTP for development - only 8805 is valid
VALID_OTP = "8805"

def generate_otp(phone: str, purpose: str, db: Session) -> str:
    """Generate and store OTP for phone verification or password reset"""
    # For development, always return 8805
    # In production, generate random OTP and send via SMS
    
    # Invalidate any existing unused OTPs for this phone and purpose
    db.query(OTP).filter(
        OTP.phone == phone,
        OTP.purpose == purpose,
        OTP.is_used == False
    ).update({"is_used": True})
    
    # Create new OTP record
    otp = OTP(
        phone=phone,
        otp_code=VALID_OTP,
        purpose=purpose,
        expires_at=datetime.utcnow() + timedelta(minutes=10)
    )
    db.add(otp)
    db.commit()
    db.refresh(otp)
    
    return VALID_OTP

def verify_otp(phone: str, otp_code: str, purpose: str, db: Session) -> bool:
    """Verify OTP for phone verification or password reset"""
    # Only accept 8805 as valid OTP
    if otp_code != VALID_OTP:
        return False
    
    # Find the most recent unused OTP for this phone and purpose
    otp = db.query(OTP).filter(
        OTP.phone == phone,
        OTP.purpose == purpose,
        OTP.is_used == False,
        OTP.otp_code == otp_code
    ).order_by(OTP.created_at.desc()).first()
    
    if not otp:
        return False
    
    if not otp.is_valid():
        return False
    
    # Mark OTP as used
    otp.is_used = True
    db.commit()
    
    return True

def cleanup_expired_otps(db: Session):
    """Clean up expired OTPs"""
    expired_otps = db.query(OTP).filter(
        OTP.is_used == False,
        OTP.expires_at < datetime.utcnow()
    ).all()
    
    for otp in expired_otps:
        otp.is_used = True
    
    db.commit()
