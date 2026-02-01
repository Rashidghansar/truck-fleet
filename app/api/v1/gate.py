from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime
import json
import os
import uuid
from ...database import get_db
from ...models.gate_activity import GateActivity, Trip
from ...models.booking import Booking, BookingStatus
from ...models.driver import Driver
from ...models.truck import Truck
from ...models.user import User, UserType
from ...schemas.response import ResponseModel
from ...schemas.driver import DriverCreate, DriverResponse, FingerprintVerify, FingerprintResponse
from ...core.deps import get_current_user
from ...config import settings

router = APIRouter()

@router.post("/check-in", response_model=ResponseModel)
async def gate_check_in(
    driver_id: str = Form(...),
    booking_id: Optional[str] = Form(None),
    truck_number: str = Form(...),
    bay_number: Optional[str] = Form(None),
    is_truck_empty: bool = Form(True),
    seal_status: Optional[str] = Form(None),
    vehicle_condition: str = Form("no_damage"),
    documents_verified: bool = Form(True),
    latitude: Optional[float] = Form(None),
    longitude: Optional[float] = Form(None),
    remarks: Optional[str] = Form(None),
    photos: List[UploadFile] = File(default=[]),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Record gate-in activity"""
    if current_user.user_type != UserType.SECURITY_OFFICER.value:
        raise HTTPException(status_code=403, detail="Only security officers can perform gate operations")
    
    # Verify driver
    driver = db.query(Driver).filter(Driver.id == driver_id).first()
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found")
    
    # Find or verify truck
    truck = db.query(Truck).filter(Truck.truck_number == truck_number).first()
    
    # Save photos
    photo_urls = []
    if photos:
        os.makedirs(settings.upload_path, exist_ok=True)
        for photo in photos:
            if photo.filename:
                filename = f"{uuid.uuid4()}_{photo.filename}"
                filepath = os.path.join(settings.upload_path, filename)
                with open(filepath, "wb") as f:
                    content = await photo.read()
                    f.write(content)
                photo_urls.append(f"/uploads/{filename}")
    
    # Create gate activity
    gate_activity = GateActivity(
        booking_id=booking_id,
        driver_id=driver_id,
        truck_id=truck.id if truck else None,
        activity_type="gate_in",
        security_officer_id=current_user.id,
        gate_time=datetime.utcnow(),
        gps_latitude=latitude,
        gps_longitude=longitude,
        is_truck_empty=is_truck_empty,
        seal_status=seal_status,
        vehicle_condition=vehicle_condition,
        documents_verified=documents_verified,
        bay_number=bay_number,
        photos=json.dumps(photo_urls) if photo_urls else None,
        remarks=remarks
    )
    
    db.add(gate_activity)
    
    # Update booking if associated
    if booking_id:
        booking = db.query(Booking).filter(Booking.id == booking_id).first()
        if booking:
            booking.actual_gate_in_time = datetime.utcnow()
            booking.bay_number = bay_number
    
    # Update driver status
    driver.current_status = "at_cfs"
    driver.current_lat = latitude
    driver.current_lng = longitude
    
    # Update truck status
    if truck:
        truck.current_status = "at_cfs"
        truck.current_lat = latitude
        truck.current_lng = longitude
    
    db.commit()
    db.refresh(gate_activity)
    
    return ResponseModel(
        success=True,
        message="Gate-in recorded successfully",
        data={
            "gate_in_id": gate_activity.id,
            "gate_in_time": gate_activity.gate_time.isoformat(),
            "driver_name": driver.name,
            "truck_number": truck_number,
            "bay_number": bay_number
        }
    )

@router.post("/checkout", response_model=ResponseModel)
async def gate_checkout(
    code: str,
    code_type: str = "auto",  # 'qr' or 'numeric' or 'auto'
    container_number: Optional[str] = None,
    seal_number: Optional[str] = None,
    loaded_weight: Optional[float] = None,
    vehicle_condition: str = "no_damage",
    safety_checks_passed: bool = True,
    destination_confirmed: bool = True,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    remarks: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Complete gate checkout using same QR code or numeric code
    Marks checkout complete and updates trip
    """
    if current_user.user_type != UserType.SECURITY_OFFICER.value:
        raise HTTPException(status_code=403, detail="Only security officers can perform gate checkout")
    
    # Find booking
    booking = None
    actual_code_type = code_type
    
    if code_type == "auto" or code_type == "qr":
        booking = db.query(Booking).filter(Booking.gate_qr_code == code).first()
        if booking:
            actual_code_type = "qr"
    
    if not booking and (code_type == "auto" or code_type == "numeric"):
        booking = db.query(Booking).filter(Booking.gate_numeric_code == code).first()
        if booking:
            actual_code_type = "numeric"
    
    if not booking:
        raise HTTPException(status_code=404, detail="Invalid code. No booking found.")
    
    if not booking.checkin_qr_scanned:
        raise HTTPException(status_code=400, detail="Must check-in before checkout")
    
    if booking.checkout_qr_scanned:
        raise HTTPException(status_code=400, detail="Already checked out")
    
    # Get driver and truck
    driver = db.query(Driver).filter(Driver.id == booking.driver_id).first() if booking.driver_id else None
    truck = db.query(Truck).filter(Truck.id == booking.truck_id).first() if booking.truck_id else None
    
    # Get gate-in activity
    gate_in = db.query(GateActivity).filter(
        GateActivity.booking_id == booking.id,
        GateActivity.activity_type == "gate_in"
    ).order_by(GateActivity.gate_time.desc()).first()
    
    # Mark as checked out
    booking.checkout_qr_scanned = True
    booking.checkout_time = datetime.utcnow()
    booking.checkout_method = actual_code_type
    booking.actual_gate_out_time = datetime.utcnow()
    
    if container_number:
        booking.container_number = container_number
    
    # Create gate-out activity
    gate_out = GateActivity(
        booking_id=booking.id,
        driver_id=driver.id if driver else None,
        truck_id=truck.id if truck else None,
        activity_type="gate_out",
        security_officer_id=current_user.id,
        gate_time=datetime.utcnow(),
        gps_latitude=latitude,
        gps_longitude=longitude,
        container_number=container_number,
        seal_number=seal_number,
        loaded_weight=loaded_weight,
        vehicle_condition=vehicle_condition,
        safety_checks_passed=safety_checks_passed,
        destination_confirmed=destination_confirmed,
        remarks=remarks
    )
    
    db.add(gate_out)
    
    # Update booking status
    booking.status = BookingStatus.IN_PROGRESS.value
    
    # Update driver status
    if driver:
        driver.current_status = "in_trip"
        driver.current_lat = latitude
        driver.current_lng = longitude
    
    # Update truck status
    if truck:
        truck.current_status = "in_trip"
        truck.current_lat = latitude
        truck.current_lng = longitude
    
    # Release bay after checkout
    if booking.bay_id:
        from ...utils.bay_manager import release_bay
        release_bay(db, booking)
    
    # Update trip
    trip = db.query(Trip).filter(Trip.booking_id == booking.id).first()
    if trip:
        trip.gate_out_id = gate_out.id
        trip.status = "en_route_to_destination"
        
        # Add milestone
        import json
        milestones = json.loads(trip.milestones) if trip.milestones else []
        milestones.append({
            "type": "gate_checkout",
            "timestamp": datetime.utcnow().isoformat(),
            "status": "Checked out from CFS - en route to destination"
        })
        trip.milestones = json.dumps(milestones)
    
    db.commit()
    db.refresh(gate_out)
    
    return ResponseModel(
        success=True,
        message="Gate checkout completed successfully. Trip in progress.",
        data={
            "gate_out_id": gate_out.id,
            "gate_out_time": gate_out.gate_time.isoformat(),
            "checkout_method": actual_code_type,
            "driver_name": driver.name if driver else None,
            "truck_number": truck.truck_number if truck else None,
            "container_number": container_number,
            "seal_number": seal_number,
            "booking_id": booking.id,
            "demand_number": booking.demand_number,
            "trip_id": trip.id if trip else None,
            "destination": booking.destination_address
        }
    )
async def gate_check_out(
    gate_in_id: str = Form(...),
    container_number: Optional[str] = Form(None),
    seal_number: Optional[str] = Form(None),
    loaded_weight: Optional[float] = Form(None),
    vehicle_condition: str = Form("no_damage"),
    safety_checks_passed: bool = Form(True),
    destination_confirmed: bool = Form(True),
    latitude: Optional[float] = Form(None),
    longitude: Optional[float] = Form(None),
    remarks: Optional[str] = Form(None),
    seal_photos: List[UploadFile] = File(default=[]),
    container_photos: List[UploadFile] = File(default=[]),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Record gate-out activity and start trip"""
    if current_user.user_type != UserType.SECURITY_OFFICER.value:
        raise HTTPException(status_code=403, detail="Only security officers can perform gate operations")
    
    # Get gate-in record
    gate_in = db.query(GateActivity).filter(GateActivity.id == gate_in_id).first()
    if not gate_in:
        raise HTTPException(status_code=404, detail="Gate-in record not found")
    
    # Save photos
    seal_photo_urls = []
    container_photo_urls = []
    os.makedirs(settings.upload_path, exist_ok=True)
    
    for photo in seal_photos:
        if photo.filename:
            filename = f"{uuid.uuid4()}_{photo.filename}"
            filepath = os.path.join(settings.upload_path, filename)
            with open(filepath, "wb") as f:
                content = await photo.read()
                f.write(content)
            seal_photo_urls.append(f"/uploads/{filename}")
    
    for photo in container_photos:
        if photo.filename:
            filename = f"{uuid.uuid4()}_{photo.filename}"
            filepath = os.path.join(settings.upload_path, filename)
            with open(filepath, "wb") as f:
                content = await photo.read()
                f.write(content)
            container_photo_urls.append(f"/uploads/{filename}")
    
    # Create gate-out activity
    gate_out = GateActivity(
        booking_id=gate_in.booking_id,
        driver_id=gate_in.driver_id,
        truck_id=gate_in.truck_id,
        activity_type="gate_out",
        security_officer_id=current_user.id,
        gate_time=datetime.utcnow(),
        gps_latitude=latitude,
        gps_longitude=longitude,
        container_number=container_number,
        seal_number=seal_number,
        loaded_weight=loaded_weight,
        vehicle_condition=vehicle_condition,
        safety_checks_passed=safety_checks_passed,
        destination_confirmed=destination_confirmed,
        seal_photos=json.dumps(seal_photo_urls) if seal_photo_urls else None,
        container_photos=json.dumps(container_photo_urls) if container_photo_urls else None,
        remarks=remarks
    )
    
    db.add(gate_out)
    db.commit()
    db.refresh(gate_out)
    
    # Create trip record
    trip = None
    if gate_in.booking_id:
        trip = Trip(
            booking_id=gate_in.booking_id,
            driver_id=gate_in.driver_id,
            truck_id=gate_in.truck_id,
            gate_in_id=gate_in.id,
            gate_out_id=gate_out.id,
            start_time=datetime.utcnow(),
            status="started",
            current_latitude=latitude,
            current_longitude=longitude
        )
        db.add(trip)
        
        # Update booking
        booking = db.query(Booking).filter(Booking.id == gate_in.booking_id).first()
        if booking:
            booking.actual_gate_out_time = datetime.utcnow()
            booking.container_number = container_number
            booking.status = BookingStatus.IN_PROGRESS.value
    
    # Update driver status
    driver = db.query(Driver).filter(Driver.id == gate_in.driver_id).first()
    if driver:
        driver.current_status = "in_trip"
        driver.current_lat = latitude
        driver.current_lng = longitude
    
    # Update truck status
    if gate_in.truck_id:
        truck = db.query(Truck).filter(Truck.id == gate_in.truck_id).first()
        if truck:
            truck.current_status = "in_trip"
            truck.current_lat = latitude
            truck.current_lng = longitude
    
    db.commit()
    
    return ResponseModel(
        success=True,
        message="Gate-out recorded successfully. Trip started.",
        data={
            "gate_out_id": gate_out.id,
            "gate_out_time": gate_out.gate_time.isoformat(),
            "trip_id": trip.id if trip else None,
            "container_number": container_number,
            "seal_number": seal_number
        }
    )

@router.get("/activities", response_model=ResponseModel)
async def get_gate_activities(
    activity_type: Optional[str] = None,
    date: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get gate activities"""
    query = db.query(GateActivity)
    
    if activity_type:
        query = query.filter(GateActivity.activity_type == activity_type)
    
    if date:
        # Filter by date
        from datetime import datetime as dt
        filter_date = dt.strptime(date, "%Y-%m-%d").date()
        query = query.filter(
            GateActivity.gate_time >= filter_date,
            GateActivity.gate_time < filter_date.replace(day=filter_date.day + 1)
        )
    
    total = query.count()
    query = query.order_by(GateActivity.gate_time.desc())
    offset = (page - 1) * page_size
    activities = query.offset(offset).limit(page_size).all()
    
    result = []
    for activity in activities:
        driver = db.query(Driver).filter(Driver.id == activity.driver_id).first()
        truck = db.query(Truck).filter(Truck.id == activity.truck_id).first() if activity.truck_id else None
        
        result.append({
            "id": activity.id,
            "activity_type": activity.activity_type,
            "gate_time": activity.gate_time.isoformat(),
            "driver_name": driver.name if driver else None,
            "driver_phone": driver.phone if driver else None,
            "truck_number": truck.truck_number if truck else None,
            "bay_number": activity.bay_number,
            "booking_id": activity.booking_id,
            "vehicle_condition": activity.vehicle_condition,
            "documents_verified": activity.documents_verified
        })
    
    return ResponseModel(
        success=True,
        data={
            "activities": result,
            "total": total,
            "page": page,
            "page_size": page_size
        }
    )

@router.post("/verify-fingerprint", response_model=FingerprintResponse)
async def verify_fingerprint(
    fingerprint_data: FingerprintVerify,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Verify driver fingerprint"""
    # In production, this would use actual fingerprint matching
    # For now, we'll do a simple lookup
    
    if fingerprint_data.driver_id:
        driver = db.query(Driver).filter(Driver.id == fingerprint_data.driver_id).first()
    else:
        # Search by fingerprint data (simplified)
        driver = db.query(Driver).filter(
            Driver.fingerprint_registered == True,
            Driver.is_active == True
        ).first()
    
    if not driver:
        return FingerprintResponse(
            success=False,
            driver=None,
            message="Driver not found or fingerprint not registered"
        )
    
    return FingerprintResponse(
        success=True,
        driver=DriverResponse.model_validate(driver),
        message="Driver verified successfully"
    )

@router.post("/register-driver", response_model=ResponseModel)
async def register_driver_at_gate(
    driver_data: DriverCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Register a new driver at the gate"""
    if current_user.user_type != UserType.SECURITY_OFFICER.value:
        raise HTTPException(status_code=403, detail="Only security officers can register drivers")
    
    # Check existing
    existing = db.query(Driver).filter(Driver.phone == driver_data.phone).first()
    if existing:
        raise HTTPException(status_code=400, detail="Driver with this phone already exists")
    
    driver = Driver(
        name=driver_data.name,
        phone=driver_data.phone,
        email=driver_data.email,
        date_of_birth=driver_data.date_of_birth,
        address=driver_data.address,
        identification_mark=driver_data.identification_mark,
        blood_group=driver_data.blood_group,
        emergency_contact_name=driver_data.emergency_contact_name,
        emergency_contact_phone=driver_data.emergency_contact_phone,
        license_number=driver_data.license_number,
        license_type=driver_data.license_type,
        license_issue_date=driver_data.license_issue_date,
        license_expiry=driver_data.license_expiry,
        aadhar_number=driver_data.aadhar_number,
        pan_number=driver_data.pan_number,
        medical_fitness_expiry=driver_data.medical_fitness_expiry,
        experience_years=driver_data.experience_years,
        primary_vehicle_type=driver_data.primary_vehicle_type,
        bank_account_number=driver_data.bank_account_number,
        bank_ifsc_code=driver_data.bank_ifsc_code,
        bank_account_holder=driver_data.bank_account_holder,
        bank_name=driver_data.bank_name,
        upi_id=driver_data.upi_id
    )
    
    db.add(driver)
    db.commit()
    db.refresh(driver)
    
    return ResponseModel(
        success=True,
        message="Driver registered successfully",
        data=DriverResponse.model_validate(driver)
    )


@router.post("/verify-code", response_model=ResponseModel)
async def verify_gate_code(
    code: str,
    code_type: str = "auto",  # 'qr', 'numeric', or 'auto'
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Verify QR code or numeric code for gate check-in/checkout
    Used by security app to scan or enter code
    Security officers can ONLY verify bookings from the admin who created them.
    """
    if current_user.user_type != UserType.SECURITY_OFFICER.value:
        raise HTTPException(status_code=403, detail="Only security officers can verify codes")
    
    # Determine code type if auto
    booking = None
    if code_type == "auto" or code_type == "qr":
        booking = db.query(Booking).filter(Booking.gate_qr_code == code).first()
    
    if not booking and (code_type == "auto" or code_type == "numeric"):
        booking = db.query(Booking).filter(Booking.gate_numeric_code == code).first()
    
    if not booking:
        return ResponseModel(
            success=False,
            message="Invalid code. No booking found.",
            data={"valid": False}
        )
    
    # CRITICAL: Check admin-security officer authorization
    # Security officer can ONLY verify bookings from the admin who created them
    is_authorized = True
    authorization_error = None
    
    if current_user.created_by_admin_id:
        # Security officer was created by an admin - check if it matches booking's admin
        if current_user.created_by_admin_id != booking.cfs_id:
            is_authorized = False
            booking_admin = db.query(User).filter(User.id == booking.cfs_id).first()
            authorization_error = f"Not authorized. This booking belongs to {booking_admin.cfs_name or booking_admin.name if booking_admin else 'another admin'}. You can only verify bookings from your admin."
    
    if not is_authorized:
        return ResponseModel(
            success=False,
            message=authorization_error,
            data={
                "valid": False,
                "authorized": False,
                "reason": "admin_mismatch"
            }
        )
    
    # Get driver and truck details
    driver = db.query(Driver).filter(Driver.id == booking.driver_id).first() if booking.driver_id else None
    truck = db.query(Truck).filter(Truck.id == booking.truck_id).first() if booking.truck_id else None
    
    # Determine which operation (check-in or checkout)
    can_checkin = not booking.checkin_qr_scanned and booking.status == BookingStatus.CONFIRMED.value
    can_checkout = booking.checkin_qr_scanned and not booking.checkout_qr_scanned
    
    # Get CFS info
    cfs_user = db.query(User).filter(User.id == booking.cfs_id).first()
    
    # Code is valid - return booking details for security officer
    return ResponseModel(
        success=True,
        message="Code verified successfully. You are authorized to process this booking.",
        data={
            "valid": True,
            "authorized": True,
            "booking_id": booking.id,
            "demand_number": booking.demand_number,
            "operation": "checkin" if can_checkin else ("checkout" if can_checkout else "completed"),
            "can_checkin": can_checkin,
            "can_checkout": can_checkout,
            "cfs": {
                "id": booking.cfs_id,
                "name": booking.cfs_location_name or (cfs_user.cfs_name if cfs_user else None) or (cfs_user.name if cfs_user else "Unknown"),
                "location_id": booking.cfs_location_id,
            },
            "driver": {
                "id": driver.id if driver else None,
                "name": driver.name if driver else "Not assigned",
                "phone": driver.phone if driver else None,
                "license_number": driver.license_number if driver else None,
                "profile_image": driver.profile_image if driver else None
            },
            "truck": {
                "id": truck.id if truck else None,
                "truck_number": truck.truck_number if truck else "Not assigned",
                "truck_type": truck.truck_type if truck else None
            },
            "booking": {
                "pickup_location": booking.pickup_location,
                "destination": booking.destination_address,
                "consignment_type": booking.consignment_type,
                "bay_number": booking.bay_number,
                "gate_in_time": booking.gate_in_time.isoformat() if booking.gate_in_time else None,
                "special_instructions": booking.special_instructions,
                "checkin_time": booking.checkin_time.isoformat() if booking.checkin_time else None,
                "checkout_time": booking.checkout_time.isoformat() if booking.checkout_time else None
            }
        }
    )


@router.post("/checkin", response_model=ResponseModel)
async def gate_checkin(
    code: str,
    code_type: str = "auto",  # 'qr' or 'numeric' or 'auto'
    bay_number: Optional[str] = None,
    vehicle_condition: str = "no_damage",
    documents_verified: bool = True,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    remarks: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Complete gate check-in using QR code or numeric code
    Marks code as used and creates gate activity
    Security officers can ONLY check-in bookings from the admin who created them.
    """
    if current_user.user_type != UserType.SECURITY_OFFICER.value:
        raise HTTPException(status_code=403, detail="Only security officers can perform gate check-in")
    
    # Find booking
    booking = None
    actual_code_type = code_type
    
    if code_type == "auto" or code_type == "qr":
        booking = db.query(Booking).filter(Booking.gate_qr_code == code).first()
        if booking:
            actual_code_type = "qr"
    
    if not booking and (code_type == "auto" or code_type == "numeric"):
        booking = db.query(Booking).filter(Booking.gate_numeric_code == code).first()
        if booking:
            actual_code_type = "numeric"
    
    if not booking:
        raise HTTPException(status_code=404, detail="Invalid code. No booking found.")
    
    # CRITICAL: Check admin-security officer authorization
    if current_user.created_by_admin_id and current_user.created_by_admin_id != booking.cfs_id:
        booking_admin = db.query(User).filter(User.id == booking.cfs_id).first()
        raise HTTPException(
            status_code=403, 
            detail=f"Not authorized. This booking belongs to {booking_admin.cfs_name or booking_admin.name if booking_admin else 'another admin'}."
        )
    
    if booking.checkin_qr_scanned:
        raise HTTPException(status_code=400, detail="Already checked in")
    
    if booking.status != BookingStatus.CONFIRMED.value:
        raise HTTPException(status_code=400, detail=f"Booking status is '{booking.status}'. Expected 'confirmed'.")
    
    # Get driver and truck
    driver = db.query(Driver).filter(Driver.id == booking.driver_id).first() if booking.driver_id else None
    truck = db.query(Truck).filter(Truck.id == booking.truck_id).first() if booking.truck_id else None
    
    if not driver:
        raise HTTPException(status_code=400, detail="No driver assigned to this booking")
    
    # Mark as checked in
    booking.checkin_qr_scanned = True
    booking.checkin_time = datetime.utcnow()
    booking.checkin_method = actual_code_type
    booking.gate_qr_scanned = True  # Legacy field
    booking.gate_qr_scanned_at = datetime.utcnow()
    booking.actual_gate_in_time = datetime.utcnow()
    
    if bay_number:
        booking.bay_number = bay_number
    
    # Create gate activity record
    gate_activity = GateActivity(
        booking_id=booking.id,
        driver_id=driver.id,
        truck_id=truck.id if truck else None,
        activity_type="gate_in",
        security_officer_id=current_user.id,
        gate_time=datetime.utcnow(),
        gps_latitude=latitude,
        gps_longitude=longitude,
        is_truck_empty=True,
        vehicle_condition=vehicle_condition,
        documents_verified=documents_verified,
        bay_number=bay_number or booking.bay_number,
        remarks=remarks
    )
    
    db.add(gate_activity)
    
    # Update driver status
    driver.current_status = "at_cfs"
    driver.current_lat = latitude
    driver.current_lng = longitude
    
    # Update truck status
    if truck:
        truck.current_status = "at_cfs"
        truck.current_lat = latitude
        truck.current_lng = longitude
    
    # Start trip if exists
    trip = db.query(Trip).filter(Trip.booking_id == booking.id).first()
    if trip and trip.status == "pending":
        from ...services.trip_service import start_trip
        start_trip(db, trip, gate_activity.id)
    
    db.commit()
    db.refresh(gate_activity)
    
    # Get bay info from CFS
    bay_info = None
    if booking.bay_number:
        from ...models.user import CfsBay
        bay = db.query(CfsBay).filter(
            CfsBay.bay_number == booking.bay_number
        ).first()
        
        if bay:
            bay_info = {
                "bay_number": bay.bay_number,
                "supervisor_name": bay.supervisor_name,
                "supervisor_phone": bay.supervisor_phone
            }
        else:
            bay_info = {
                "bay_number": booking.bay_number,
                "supervisor_name": booking.bay_contact_name,
                "supervisor_phone": booking.bay_contact_phone
            }
    
    return ResponseModel(
        success=True,
        message="Gate check-in completed successfully",
        data={
            "gate_in_id": gate_activity.id,
            "gate_in_time": gate_activity.gate_time.isoformat(),
            "checkin_method": actual_code_type,
            "driver_name": driver.name,
            "truck_number": truck.truck_number if truck else None,
            "bay_info": bay_info,
            "booking_id": booking.id,
            "demand_number": booking.demand_number
        }
    )


@router.post("/manual-verify", response_model=ResponseModel)
async def manual_verify_driver(
    otp_code: str,
    driver_name: str,
    truck_number: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Manual verification for drivers without phones.
    Security officer enters:
    - OTP code (6-digit numeric code given to driver by owner/aggregator)
    - Driver name (to verify against booking)
    - Truck number (to verify against booking)
    
    This matches the details and authenticates the driver.
    """
    if current_user.user_type != UserType.SECURITY_OFFICER.value:
        raise HTTPException(status_code=403, detail="Only security officers can verify drivers")
    
    # Find booking by numeric OTP code
    booking = db.query(Booking).filter(Booking.gate_numeric_code == otp_code).first()
    
    if not booking:
        return ResponseModel(
            success=False,
            message="Invalid OTP code. No booking found.",
            data={"valid": False, "verified": False}
        )
    
    # CRITICAL: Check admin-security officer authorization
    if current_user.created_by_admin_id and current_user.created_by_admin_id != booking.cfs_id:
        booking_admin = db.query(User).filter(User.id == booking.cfs_id).first()
        return ResponseModel(
            success=False,
            message=f"Not authorized. This booking belongs to {booking_admin.cfs_name or booking_admin.name if booking_admin else 'another admin'}.",
            data={"valid": False, "verified": False, "reason": "admin_mismatch"}
        )
    
    # Get driver and truck from booking
    driver = db.query(Driver).filter(Driver.id == booking.driver_id).first() if booking.driver_id else None
    truck = db.query(Truck).filter(Truck.id == booking.truck_id).first() if booking.truck_id else None
    
    if not driver or not truck:
        return ResponseModel(
            success=False,
            message="Booking has no driver or truck assigned.",
            data={"valid": False, "verified": False}
        )
    
    # Verify driver name and truck number (case-insensitive, partial match allowed)
    driver_name_match = driver_name.lower().strip() in driver.name.lower() or driver.name.lower() in driver_name.lower().strip()
    truck_number_match = truck_number.upper().replace(" ", "").replace("-", "") in truck.truck_number.upper().replace(" ", "").replace("-", "") or \
                         truck.truck_number.upper().replace(" ", "").replace("-", "") in truck_number.upper().replace(" ", "").replace("-", "")
    
    verification_result = {
        "otp_valid": True,
        "driver_name_provided": driver_name,
        "driver_name_expected": driver.name,
        "driver_name_match": driver_name_match,
        "truck_number_provided": truck_number,
        "truck_number_expected": truck.truck_number,
        "truck_number_match": truck_number_match,
        "booking_id": booking.id,
        "demand_number": booking.demand_number,
    }
    
    if not driver_name_match:
        return ResponseModel(
            success=False,
            message=f"Driver name mismatch. Expected: {driver.name}",
            data={**verification_result, "verified": False, "reason": "driver_name_mismatch"}
        )
    
    if not truck_number_match:
        return ResponseModel(
            success=False,
            message=f"Truck number mismatch. Expected: {truck.truck_number}",
            data={**verification_result, "verified": False, "reason": "truck_number_mismatch"}
        )
    
    # All checks passed - return full booking details
    can_checkin = not booking.checkin_qr_scanned and booking.status == BookingStatus.CONFIRMED.value
    can_checkout = booking.checkin_qr_scanned and not booking.checkout_qr_scanned
    
    return ResponseModel(
        success=True,
        message="Driver verified successfully! All details match.",
        data={
            **verification_result,
            "verified": True,
            "operation": "checkin" if can_checkin else ("checkout" if can_checkout else "completed"),
            "can_checkin": can_checkin,
            "can_checkout": can_checkout,
            "driver": {
                "id": driver.id,
                "name": driver.name,
                "phone": driver.phone,
                "license_number": driver.license_number,
            },
            "truck": {
                "id": truck.id,
                "truck_number": truck.truck_number,
                "truck_type": truck.truck_type,
            },
            "booking": {
                "pickup_location": booking.pickup_location,
                "destination": booking.destination_address,
                "consignment_type": booking.consignment_type,
                "bay_number": booking.bay_number,
                "gate_in_time": booking.gate_in_time.isoformat() if booking.gate_in_time else None,
                "special_instructions": booking.special_instructions,
            }
        }
    )


@router.post("/manual-checkin", response_model=ResponseModel)
async def manual_checkin_driver(
    otp_code: str,
    driver_name: str,
    truck_number: str,
    bay_number: Optional[str] = None,
    vehicle_condition: str = "no_damage",
    documents_verified: bool = True,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    remarks: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Manual check-in for drivers without phones.
    Security officer enters OTP + driver details to complete check-in.
    """
    if current_user.user_type != UserType.SECURITY_OFFICER.value:
        raise HTTPException(status_code=403, detail="Only security officers can perform gate check-in")
    
    # Find booking by numeric OTP code
    booking = db.query(Booking).filter(Booking.gate_numeric_code == otp_code).first()
    
    if not booking:
        raise HTTPException(status_code=404, detail="Invalid OTP code. No booking found.")
    
    # Check admin-security officer authorization
    if current_user.created_by_admin_id and current_user.created_by_admin_id != booking.cfs_id:
        booking_admin = db.query(User).filter(User.id == booking.cfs_id).first()
        raise HTTPException(
            status_code=403, 
            detail=f"Not authorized. This booking belongs to {booking_admin.cfs_name or booking_admin.name if booking_admin else 'another admin'}."
        )
    
    if booking.checkin_qr_scanned:
        raise HTTPException(status_code=400, detail="Already checked in")
    
    if booking.status != BookingStatus.CONFIRMED.value:
        raise HTTPException(status_code=400, detail=f"Booking status is '{booking.status}'. Expected 'confirmed'.")
    
    # Get driver and truck
    driver = db.query(Driver).filter(Driver.id == booking.driver_id).first() if booking.driver_id else None
    truck = db.query(Truck).filter(Truck.id == booking.truck_id).first() if booking.truck_id else None
    
    if not driver or not truck:
        raise HTTPException(status_code=400, detail="Booking has no driver or truck assigned.")
    
    # Verify driver name and truck number
    driver_name_match = driver_name.lower().strip() in driver.name.lower() or driver.name.lower() in driver_name.lower().strip()
    truck_number_clean = truck_number.upper().replace(" ", "").replace("-", "")
    expected_truck_clean = truck.truck_number.upper().replace(" ", "").replace("-", "")
    truck_number_match = truck_number_clean in expected_truck_clean or expected_truck_clean in truck_number_clean
    
    if not driver_name_match:
        raise HTTPException(status_code=400, detail=f"Driver name mismatch. Expected: {driver.name}")
    
    if not truck_number_match:
        raise HTTPException(status_code=400, detail=f"Truck number mismatch. Expected: {truck.truck_number}")
    
    # All verified - perform check-in
    booking.checkin_qr_scanned = True
    booking.checkin_time = datetime.utcnow()
    booking.checkin_method = "manual_otp"
    booking.gate_qr_scanned = True
    booking.gate_qr_scanned_at = datetime.utcnow()
    booking.actual_gate_in_time = datetime.utcnow()
    
    if bay_number:
        booking.bay_number = bay_number
    
    # Create gate activity record
    gate_activity = GateActivity(
        booking_id=booking.id,
        driver_id=driver.id,
        truck_id=truck.id,
        activity_type="gate_in",
        security_officer_id=current_user.id,
        gate_time=datetime.utcnow(),
        gps_latitude=latitude,
        gps_longitude=longitude,
        is_truck_empty=True,
        vehicle_condition=vehicle_condition,
        documents_verified=documents_verified,
        bay_number=bay_number or booking.bay_number,
        remarks=f"Manual check-in. Driver: {driver_name}, Truck: {truck_number}. {remarks or ''}"
    )
    
    db.add(gate_activity)
    
    # Update driver status
    driver.current_status = "at_cfs"
    driver.current_lat = latitude
    driver.current_lng = longitude
    
    # Update truck status
    truck.current_status = "at_cfs"
    truck.current_lat = latitude
    truck.current_lng = longitude
    
    # Start trip if exists
    trip = db.query(Trip).filter(Trip.booking_id == booking.id).first()
    if trip and trip.status == "pending":
        from ...services.trip_service import start_trip
        start_trip(db, trip, gate_activity.id)
    
    db.commit()
    db.refresh(gate_activity)
    
    return ResponseModel(
        success=True,
        message="Manual check-in completed successfully. Driver and truck verified.",
        data={
            "gate_in_id": gate_activity.id,
            "gate_in_time": gate_activity.gate_time.isoformat(),
            "checkin_method": "manual_otp",
            "driver_name": driver.name,
            "truck_number": truck.truck_number,
            "bay_number": booking.bay_number,
            "booking_id": booking.id,
            "demand_number": booking.demand_number,
            "verified_details": {
                "driver_name_provided": driver_name,
                "truck_number_provided": truck_number,
            }
        }
    )


@router.get("/arriving-drivers", response_model=ResponseModel)
async def get_arriving_drivers(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get list of drivers arriving at this admin's location.
    Shows confirmed bookings with driver/truck details for admin dashboard.
    """
    if current_user.user_type not in [UserType.CFS_ADMIN.value, UserType.SECURITY_OFFICER.value]:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # For security officers, get bookings from their admin
    admin_id = current_user.id if current_user.user_type == UserType.CFS_ADMIN.value else current_user.created_by_admin_id
    
    if not admin_id:
        raise HTTPException(status_code=400, detail="Cannot determine admin")
    
    # Get confirmed bookings that haven't been checked in yet
    bookings = db.query(Booking).filter(
        Booking.cfs_id == admin_id,
        Booking.status == BookingStatus.CONFIRMED.value,
        Booking.checkin_qr_scanned == False
    ).order_by(Booking.gate_in_time.asc()).all()
    
    arriving_list = []
    for booking in bookings:
        driver = db.query(Driver).filter(Driver.id == booking.driver_id).first() if booking.driver_id else None
        truck = db.query(Truck).filter(Truck.id == booking.truck_id).first() if booking.truck_id else None
        
        # Get owner/aggregator info
        owner = None
        if booking.aggregator_id:
            owner = db.query(User).filter(User.id == booking.aggregator_id).first()
        
        arriving_list.append({
            "booking_id": booking.id,
            "demand_number": booking.demand_number,
            "expected_arrival": booking.gate_in_time.isoformat() if booking.gate_in_time else None,
            "bay_number": booking.bay_number,
            "consignment_type": booking.consignment_type,
            "destination": booking.destination_address,
            "otp_code": booking.gate_numeric_code,
            "driver": {
                "id": driver.id if driver else None,
                "name": driver.name if driver else "Not assigned",
                "phone": driver.phone if driver else None,
                "license_number": driver.license_number if driver else None,
                "profile_image": driver.profile_image if driver else None,
            } if driver else None,
            "truck": {
                "id": truck.id if truck else None,
                "truck_number": truck.truck_number if truck else "Not assigned",
                "truck_type": truck.truck_type if truck else None,
            } if truck else None,
            "owner_aggregator": {
                "id": owner.id if owner else None,
                "name": owner.name if owner else None,
                "phone": owner.phone if owner else None,
                "type": owner.user_type if owner else None,
            } if owner else None,
            "special_instructions": booking.special_instructions,
            "created_at": booking.created_at.isoformat() if booking.created_at else None,
        })
    
    return ResponseModel(
        success=True,
        message=f"{len(arriving_list)} drivers arriving",
        data={
            "arriving": arriving_list,
            "total": len(arriving_list)
        }
    )