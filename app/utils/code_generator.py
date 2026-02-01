"""Code generation utilities for QR codes, numeric codes, and passwords"""
import random
import string
import hashlib
from datetime import datetime
from typing import Tuple


def generate_numeric_code(length: int = 6) -> str:
    """Generate a random numeric code"""
    return ''.join(random.choices(string.digits, k=length))


def generate_qr_code(booking_id: str, driver_id: str, truck_id: str = None) -> str:
    """
    Generate a unique QR code string for gate operations
    Format: GATE-{12-char-hash}
    """
    timestamp = datetime.utcnow().timestamp()
    data = f"{booking_id}:{driver_id}:{truck_id or 'NO_TRUCK'}:{timestamp}"
    hash_part = hashlib.sha256(data.encode()).hexdigest()[:12]
    return f"GATE-{hash_part.upper()}"


def generate_gate_codes(booking_id: str, driver_id: str, truck_id: str = None) -> Tuple[str, str]:
    """
    Generate both QR code and numeric code for gate operations
    Returns: (qr_code, numeric_code)
    """
    qr_code = generate_qr_code(booking_id, driver_id, truck_id)
    numeric_code = generate_numeric_code(6)
    return qr_code, numeric_code


def generate_temp_password(length: int = 8) -> str:
    """
    Generate a temporary password for auto-created drivers
    Contains uppercase, lowercase, and digits
    """
    chars = string.ascii_letters + string.digits
    password = ''.join(random.choices(chars, k=length))
    
    # Ensure it has at least one uppercase, one lowercase, and one digit
    if not any(c.isupper() for c in password):
        password = password[:-1] + random.choice(string.ascii_uppercase)
    if not any(c.islower() for c in password):
        password = password[:-2] + random.choice(string.ascii_lowercase) + password[-1]
    if not any(c.isdigit() for c in password):
        password = password[:-3] + random.choice(string.digits) + password[-2:]
    
    return password


def generate_username_from_phone(phone: str) -> str:
    """Generate username from phone number"""
    # Remove any non-digit characters
    clean_phone = ''.join(filter(str.isdigit, phone))
    return f"driver_{clean_phone}"


def validate_numeric_code(code: str) -> bool:
    """Validate numeric code format"""
    return code.isdigit() and len(code) == 6


def validate_qr_code(code: str) -> bool:
    """Validate QR code format"""
    return code.startswith("GATE-") and len(code) == 17  # GATE- + 12 chars


def generate_driver_otp(driver_id: str) -> str:
    """
    Generate a 6-digit OTP for driver based on their ID
    This is deterministic - same driver always gets same OTP
    Can be used by owner/aggregator to share with driver for gate verification
    """
    # Use driver_id hash to generate consistent OTP
    hash_val = hashlib.md5(driver_id.encode()).hexdigest()
    # Convert first 6 hex chars to digits
    otp_base = int(hash_val[:8], 16)
    otp = str(otp_base % 900000 + 100000)
    return otp
