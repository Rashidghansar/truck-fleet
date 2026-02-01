from fastapi import APIRouter, Depends, HTTPException, status, Request, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from datetime import datetime, timedelta
from typing import Optional
from ...database import get_db
from ...models.user import User, UserType, Aggregator, BankDetails
from ...models.driver import Driver
from ...models.user_session import UserSession
from ...schemas.user import UserCreate, UserLogin, UserResponse, TokenResponse, UserUpdate
from ...schemas.response import ResponseModel
from ...core.security import get_password_hash, verify_password, create_access_token, create_refresh_token, decode_token
from ...core.deps import get_current_user
from ...services.otp_service import generate_otp, verify_otp
from ...config import settings

router = APIRouter()

@router.post("/register", response_model=ResponseModel)
async def register(user_data: UserCreate, db: Session = Depends(get_db)):
    # Check existing phone
    existing_user = db.query(User).filter(User.phone == user_data.phone).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phone number already registered"
        )
    
    # Check existing email
    if user_data.email:
        existing_email = db.query(User).filter(User.email == user_data.email).first()
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
    
    # Create user
    try:
        user = User(
            name=user_data.name,
            phone=user_data.phone,
            email=user_data.email,
            password_hash=get_password_hash(user_data.password),
            user_type=user_data.user_type,
            cfs_name=user_data.cfs_name,
            cfs_address=user_data.cfs_address,
            cfs_license=user_data.cfs_license,
            address=user_data.address,
            emergency_contact_name=user_data.emergency_contact_name,
            emergency_contact_phone=user_data.emergency_contact_phone,
        )
        
        db.add(user)
        db.commit()
        db.refresh(user)
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Registration failed due to data constraints"
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed"
        )
    
    # Create additional records based on user type
    if user_data.user_type == UserType.DRIVER.value:
        driver = Driver(
            user_id=user.id,
            name=user.name,
            phone=user.phone,
            email=user.email,
        )
        db.add(driver)
        db.commit()
    
    return ResponseModel(
        success=True,
        message="Registration successful. Please verify your phone number.",
        data={"user_id": user.id, "user_type": user.user_type}
    )

@router.post("/login", response_model=TokenResponse)
async def login(login_data: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.phone == login_data.phone).first()
    
    if not user or not verify_password(login_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is inactive"
        )
    
    # Validate user type if provided
    if login_data.user_type and user.user_type != login_data.user_type:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user type for this account"
        )
    
    # For drivers, ensure their profile is linked
    driver_profile = None
    requires_password_change = False
    
    if user.user_type == UserType.DRIVER.value:
        # Check if driver profile exists and link it
        driver = db.query(Driver).filter(Driver.phone == user.phone).first()
        if driver:
            # Ensure user_id is set on driver profile
            if driver.user_id != user.id:
                driver.user_id = user.id
            
            # Check if password change is required (auto-created drivers)
            if driver.auto_created and not driver.password_changed:
                requires_password_change = True
            
            driver_profile = {
                "id": driver.id,
                "name": driver.name,
                "license_number": driver.license_number,
                "is_available": driver.is_available,
                "current_status": driver.current_status,
                "assigned_truck_id": driver.assigned_truck_id,
                "owner_id": driver.owner_id,
                "auto_created": driver.auto_created,
                "requires_password_change": requires_password_change
            }
    
    # Update last login
    user.last_login = datetime.utcnow()
    
    # Create tokens
    access_token = create_access_token(data={"sub": user.id})
    refresh_token = create_refresh_token(data={"sub": user.id})
    
    # Create session
    session = UserSession(
        user_id=user.id,
        token=access_token,
        refresh_token=refresh_token,
        device_id=None,  # Can be passed from request headers
        device_type="web",
        ip_address=None,  # Can be extracted from request
        user_agent=None,  # Can be extracted from request
        expires_at=datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    )
    db.add(session)
    db.commit()
    
    # Prepare user response with driver profile if applicable
    user_response = UserResponse.model_validate(user)
    
    response_data = {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user": user_response,
        "driver_profile": driver_profile,
        "requires_password_change": requires_password_change
    }
    
    return TokenResponse(**response_data)

@router.post("/send-otp", response_model=ResponseModel)
async def send_otp(phone: str, purpose: str = "phone_verification", db: Session = Depends(get_db)):
    """Send OTP to phone number for verification or password reset"""
    user = db.query(User).filter(User.phone == phone).first()
    
    if purpose == "password_reset" and not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Generate and store OTP
    otp_code = generate_otp(phone, purpose, db)
    
    # In production, send OTP via SMS service
    # For development, OTP is always 8805
    
    return ResponseModel(
        success=True,
        message="OTP sent successfully",
        data={"otp": otp_code if settings.DEBUG else None}  # Only return OTP in debug mode
    )

@router.post("/verify-phone", response_model=ResponseModel)
async def verify_phone(phone: str, otp: str, db: Session = Depends(get_db)):
    """Verify phone number with OTP - only accepts 8805"""
    user = db.query(User).filter(User.phone == phone).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Verify OTP using service (only accepts 8805)
    if not verify_otp(phone, otp, "phone_verification", db):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OTP. Please use 8805 for verification."
        )
    
    user.phone_verified = True
    user.is_verified = True
    db.commit()
    
    return ResponseModel(success=True, message="Phone verified successfully")

@router.post("/refresh-token", response_model=ResponseModel)
async def refresh_token(
    refresh_token: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """Refresh access token with refresh token rotation"""
    payload = decode_token(refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    
    user_id = payload.get("sub")
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if not user.is_active:
        raise HTTPException(status_code=401, detail="User account is inactive")
    
    # Check if refresh token exists in session (token blacklisting)
    session = db.query(UserSession).filter(
        UserSession.refresh_token == refresh_token,
        UserSession.is_active == True
    ).first()
    
    if not session:
        raise HTTPException(status_code=401, detail="Refresh token not found or revoked")
    
    # Rotate tokens - invalidate old refresh token
    session.is_active = False
    
    # Create new tokens
    new_access_token = create_access_token(data={"sub": user.id})
    new_refresh_token = create_refresh_token(data={"sub": user.id})
    
    # Create new session
    new_session = UserSession(
        user_id=user.id,
        token=new_access_token,
        refresh_token=new_refresh_token,
        device_id=request.headers.get("X-Device-ID") if request else None,
        device_type=request.headers.get("X-Device-Type", "web") if request else "web",
        ip_address=request.client.host if request and request.client else None,
        user_agent=request.headers.get("User-Agent") if request else None,
        expires_at=datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    )
    db.add(new_session)
    db.commit()
    
    return ResponseModel(
        success=True,
        data={
            "access_token": new_access_token,
            "refresh_token": new_refresh_token
        }
    )

@router.get("/me", response_model=ResponseModel)
async def get_me(current_user: User = Depends(get_current_user)):
    return ResponseModel(
        success=True,
        data=UserResponse.model_validate(current_user)
    )

@router.put("/me", response_model=ResponseModel)
async def update_me(
    update_data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update user profile"""
    update_dict = update_data.model_dump(exclude_unset=True)
    for key, value in update_dict.items():
        setattr(current_user, key, value)
    
    db.commit()
    db.refresh(current_user)
    
    return ResponseModel(
        success=True,
        message="Profile updated successfully",
        data=UserResponse.model_validate(current_user)
    )

@router.post("/me/upload-image", response_model=ResponseModel)
async def upload_profile_image(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Upload profile image"""
    import os
    import uuid
    from pathlib import Path
    
    # Validate file type
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")
    
    if not allowed_file(file.filename):
        raise HTTPException(
            status_code=400,
            detail=f"File type not allowed. Allowed types: {settings.ALLOWED_EXTENSIONS}"
        )
    
    # Read file
    file_content = await file.read()
    if len(file_content) > settings.MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File size exceeds maximum allowed size of {settings.MAX_FILE_SIZE} bytes"
        )
    
    # Generate unique filename
    file_ext = file.filename.rsplit(".", 1)[1].lower()
    unique_filename = f"profile_{current_user.id}_{uuid.uuid4()}.{file_ext}"
    
    # Create directory
    upload_dir = Path(settings.UPLOAD_DIR) / "profiles"
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    file_path = upload_dir / unique_filename
    
    # Delete old profile image if exists
    if current_user.profile_image and os.path.exists(current_user.profile_image):
        try:
            os.remove(current_user.profile_image)
        except:
            pass
    
    # Save new file
    with open(file_path, "wb") as f:
        f.write(file_content)
    
    # Update user profile
    current_user.profile_image = str(file_path)
    db.commit()
    db.refresh(current_user)
    
    return ResponseModel(
        success=True,
        message="Profile image uploaded successfully",
        data={"profile_image": current_user.profile_image}
    )

def allowed_file(filename: str) -> bool:
    """Check if file extension is allowed"""
    if not filename:
        return False
    allowed_extensions = set(settings.ALLOWED_EXTENSIONS.split(","))
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed_extensions

@router.post("/change-password", response_model=ResponseModel)
async def change_password(
    current_password: str,
    new_password: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not verify_password(current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    
    current_user.password_hash = get_password_hash(new_password)
    
    # If driver, mark password as changed
    if current_user.user_type == UserType.DRIVER.value:
        driver = db.query(Driver).filter(Driver.user_id == current_user.id).first()
        if driver and driver.auto_created:
            driver.password_changed = True
            driver.temp_password = None  # Clear temp password
    
    db.commit()
    
    return ResponseModel(success=True, message="Password changed successfully")


@router.post("/first-time-password-change", response_model=ResponseModel)
async def first_time_password_change(
    new_password: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    First-time password change for auto-created drivers
    No current password required
    """
    if current_user.user_type != UserType.DRIVER.value:
        raise HTTPException(status_code=403, detail="Only drivers can use this endpoint")
    
    # Get driver profile
    driver = db.query(Driver).filter(Driver.user_id == current_user.id).first()
    if not driver:
        raise HTTPException(status_code=404, detail="Driver profile not found")
    
    if not driver.auto_created:
        raise HTTPException(status_code=400, detail="This endpoint is only for auto-created drivers")
    
    if driver.password_changed:
        raise HTTPException(status_code=400, detail="Password already changed. Use regular password change endpoint")
    
    # Validate new password strength
    if len(new_password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters long")
    
    # Update password
    current_user.password_hash = get_password_hash(new_password)
    driver.password_changed = True
    driver.temp_password = None  # Clear temp password
    
    db.commit()
    
    return ResponseModel(
        success=True,
        message="Password changed successfully. You can now use your new password to login.",
        data={"password_changed": True}
    )

@router.get("/check-phone", response_model=ResponseModel)
async def check_phone(phone: str, db: Session = Depends(get_db)):
    """Check if phone number exists in the system"""
    user = db.query(User).filter(User.phone == phone).first()
    return ResponseModel(success=True, data={"exists": user is not None})

@router.post("/reset-password", response_model=ResponseModel)
async def reset_password(
    phone: str,
    otp: str,
    new_password: str,
    db: Session = Depends(get_db)
):
    """Reset password for a user with OTP verification - only accepts 8805"""
    user = db.query(User).filter(User.phone == phone).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Verify OTP before allowing password reset
    if not verify_otp(phone, otp, "password_reset", db):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OTP. Please use 8805 for password reset."
        )
    
    # Validate new password
    if len(new_password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 6 characters long"
        )
    
    user.password_hash = get_password_hash(new_password)
    db.commit()
    
    return ResponseModel(success=True, message="Password reset successfully")

@router.post("/logout", response_model=ResponseModel)
async def logout(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Logout user and blacklist tokens"""
    # Get token from request
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        
        # Deactivate session
        session = db.query(UserSession).filter(
            UserSession.user_id == current_user.id,
            UserSession.token == token,
            UserSession.is_active == True
        ).first()
        
        if session:
            session.is_active = False
            db.commit()
    
    return ResponseModel(success=True, message="Logged out successfully")
