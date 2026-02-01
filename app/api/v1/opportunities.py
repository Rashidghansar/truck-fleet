from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime, timedelta
import uuid
import hashlib
from ...database import get_db
from ...models.booking import Booking, BookingStatus, Negotiation
from ...models.user import User, UserType
from ...models.truck import Truck
from ...models.driver import Driver
from ...models.gate_activity import Trip
from ...schemas.booking import BookingResponse, NegotiationCreate, NegotiationResponse
from ...schemas.response import ResponseModel
from ...core.deps import get_current_user
from ...utils.code_generator import generate_gate_codes
from ...services.trip_service import create_trip_from_booking, get_trip_details


def generate_gate_qr_code(booking_id: str, driver_id: str, truck_id: str) -> str:
    """Generate a unique QR code for gate check-in"""
    # Create a unique hash using booking, driver, truck IDs and timestamp
    data = f"{booking_id}:{driver_id}:{truck_id}:{datetime.utcnow().timestamp()}"
    hash_part = hashlib.sha256(data.encode()).hexdigest()[:12]
    return f"GATE-{hash_part.upper()}"

router = APIRouter()

@router.get("", response_model=ResponseModel)
async def get_opportunities(
    truck_type: Optional[str] = None,
    min_rate: Optional[float] = None,
    max_rate: Optional[float] = None,
    max_distance: Optional[float] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get available booking opportunities for aggregators/owners/drivers"""
    if current_user.user_type not in [UserType.AGGREGATOR.value, UserType.OWNER.value, UserType.DRIVER.value]:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Only show bookings created within the last 1 hour
    one_hour_ago = datetime.utcnow() - timedelta(hours=1)
    
    query = db.query(Booking).filter(
        Booking.status == BookingStatus.PENDING.value,
        Booking.created_at >= one_hour_ago
    )
    
    if truck_type:
        query = query.filter(Booking.truck_type == truck_type)
    
    if min_rate:
        query = query.filter(Booking.published_rate >= min_rate)
    
    if max_rate:
        query = query.filter(Booking.published_rate <= max_rate)
    
    # Order by creation time (newest first)
    query = query.order_by(Booking.created_at.desc())
    
    total = query.count()
    offset = (page - 1) * page_size
    opportunities = query.offset(offset).limit(page_size).all()
    
    # Convert bookings to opportunity format
    opportunity_list = []
    now = datetime.utcnow()
    for booking in opportunities:
        # Get CFS details for each booking
        cfs = db.query(User).filter(User.id == booking.cfs_id).first()
        
        # Calculate time remaining (expires 1 hour after creation)
        expiry_time = booking.created_at + timedelta(hours=1) if booking.created_at else now
        time_remaining_seconds = max(0, int((expiry_time - now).total_seconds()))
        time_remaining_minutes = time_remaining_seconds // 60
        
        opportunity_data = {
            "id": booking.id,
            "demand_number": booking.demand_number,
            "cfs_id": booking.cfs_id,
            "cfs_name": cfs.cfs_name or cfs.name if cfs else None,
            "container_type": booking.container_type or booking.consignment_type,
            "container_size": booking.container_size,
            "container_number": booking.container_number,
            "truck_type": booking.truck_type,
            "truck_capacity": booking.truck_capacity,
            "pickup_location": booking.pickup_location,
            "delivery_location": booking.delivery_location or booking.destination_address,
            "destination_address": booking.destination_address,
            "pickup_lat": booking.pickup_lat,
            "pickup_lng": booking.pickup_lng,
            "delivery_lat": booking.delivery_lat or booking.destination_lat,
            "delivery_lng": booking.delivery_lng or booking.destination_lng,
            "gate_in_time": booking.gate_in_time.isoformat() if booking.gate_in_time else None,
            "gate_out_time": booking.gate_out_time.isoformat() if booking.gate_out_time else None,
            "bay_number": booking.bay_number,
            "published_rate": booking.published_rate or booking.base_price or 0.0,
            "base_price": booking.base_price,
            "agreed_rate": booking.agreed_rate,
            "is_negotiable": booking.is_negotiable,
            "status": booking.status,
            "weight": booking.weight,
            "notes": booking.notes,
            "special_instructions": booking.special_instructions,
            "payment_terms": booking.payment_terms,
            "created_at": booking.created_at.isoformat() if booking.created_at else None,
            "time_remaining_minutes": time_remaining_minutes,
            "expires_at": expiry_time.isoformat() if booking.created_at else None,
        }
        opportunity_list.append(opportunity_data)
    
    return ResponseModel(
        success=True,
        data={
            "opportunities": opportunity_list,
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": (total + page_size - 1) // page_size
        }
    )

@router.get("/{booking_id}", response_model=ResponseModel)
async def get_opportunity_detail(
    booking_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    
    # Get CFS details
    cfs = db.query(User).filter(User.id == booking.cfs_id).first()
    
    # Create opportunity data in the format expected by frontend
    opportunity_data = {
        "id": booking.id,
        "demand_number": booking.demand_number,
        "cfs_id": booking.cfs_id,
        "cfs_name": cfs.cfs_name or cfs.name if cfs else None,
        "container_type": booking.container_type or booking.consignment_type,
        "container_size": booking.container_size,
        "container_number": booking.container_number,
        "truck_type": booking.truck_type,
        "truck_capacity": booking.truck_capacity,
        "pickup_location": booking.pickup_location,
        "delivery_location": booking.delivery_location or booking.destination_address,
        "destination_address": booking.destination_address,
        "pickup_lat": booking.pickup_lat,
        "pickup_lng": booking.pickup_lng,
        "delivery_lat": booking.delivery_lat or booking.destination_lat,
        "delivery_lng": booking.delivery_lng or booking.destination_lng,
        "gate_in_time": booking.gate_in_time.isoformat() if booking.gate_in_time else None,
        "gate_out_time": booking.gate_out_time.isoformat() if booking.gate_out_time else None,
        "bay_number": booking.bay_number,
        "published_rate": booking.published_rate or booking.base_price or 0.0,
        "base_price": booking.base_price,
        "agreed_rate": booking.agreed_rate,
        "is_negotiable": booking.is_negotiable,
        "status": booking.status,
        "weight": booking.weight,
        "notes": booking.notes,
        "special_instructions": booking.special_instructions,
        "payment_terms": booking.payment_terms,
        "created_at": booking.created_at.isoformat() if booking.created_at else None,
    }
    
    return ResponseModel(
        success=True,
        data=opportunity_data
    )

@router.get("/{booking_id}/negotiations", response_model=ResponseModel)
async def get_opportunity_negotiations(
    booking_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get negotiations for a booking - only visible to the CFS admin who created it"""
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    # Only the CFS admin who created the booking can see negotiations
    if current_user.user_type == UserType.CFS_ADMIN.value:
        if booking.cfs_id != current_user.id:
            raise HTTPException(status_code=403, detail="You can only view negotiations for your own bookings")
    # Supply side users can only see their own negotiations
    elif current_user.user_type in [UserType.AGGREGATOR.value, UserType.OWNER.value, UserType.DRIVER.value]:
        negotiations = db.query(Negotiation).filter(
            Negotiation.booking_id == booking_id,
            Negotiation.offered_by == current_user.id
        ).order_by(Negotiation.created_at.desc()).all()
        
        negotiation_list = []
        for neg in negotiations:
            negotiation_list.append({
                "id": neg.id,
                "booking_id": neg.booking_id,
                "offered_rate": neg.offered_rate,
                "justification": neg.justification,
                "payment_terms": neg.payment_terms,
                "status": neg.status,
                "created_at": neg.created_at.isoformat() if neg.created_at else None,
            })
        
        return ResponseModel(success=True, data=negotiation_list)
    else:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # For CFS admin - get all negotiations with supplier info
    negotiations = db.query(Negotiation).filter(
        Negotiation.booking_id == booking_id
    ).order_by(Negotiation.created_at.desc()).all()
    
    negotiation_list = []
    for neg in negotiations:
        # Get supplier info
        supplier = db.query(User).filter(User.id == neg.offered_by).first()
        negotiation_list.append({
            "id": neg.id,
            "booking_id": neg.booking_id,
            "offered_by": neg.offered_by,
            "supplier_name": supplier.name if supplier else "Unknown",
            "supplier_phone": supplier.phone if supplier else None,
            "offered_rate": neg.offered_rate,
            "justification": neg.justification,
            "payment_terms": neg.payment_terms,
            "status": neg.status,
            "created_at": neg.created_at.isoformat() if neg.created_at else None,
        })
    
    return ResponseModel(success=True, data=negotiation_list)

@router.post("/{booking_id}/accept", response_model=ResponseModel)
async def accept_opportunity(
    booking_id: str,
    truck_id: str,
    driver_id: Optional[str] = None,
    auto_assign_driver: bool = False,
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Accept a booking opportunity
    - Driver can accept directly
    - Owner/Aggregator must provide driver_id
    - Creates trip record with QR and numeric codes
    """
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    if booking.status != BookingStatus.PENDING.value:
        raise HTTPException(status_code=400, detail="Booking is no longer available")
    
    # Verify truck
    truck = db.query(Truck).filter(Truck.id == truck_id).first()
    if not truck:
        raise HTTPException(status_code=404, detail="Truck not found")
    
    if not truck.is_available:
        raise HTTPException(status_code=400, detail="Truck is not available")
    
    # Handle driver selection based on user type
    driver = None
    
    if current_user.user_type == UserType.DRIVER.value:
        # Driver accepting directly - find their driver record
        driver = db.query(Driver).filter(Driver.user_id == current_user.id).first()
        if not driver:
            raise HTTPException(status_code=400, detail="Driver profile not found")
        if not driver.is_available:
            raise HTTPException(status_code=400, detail="You are not available for trips")
        
    elif current_user.user_type in [UserType.OWNER.value, UserType.AGGREGATOR.value]:
        # Owner/Aggregator must provide driver_id
        if not driver_id:
            raise HTTPException(status_code=400, detail="Driver ID is required")
        
        driver = db.query(Driver).filter(Driver.id == driver_id).first()
        if not driver:
            raise HTTPException(status_code=404, detail="Driver not found")
        if not driver.is_available:
            raise HTTPException(status_code=400, detail="Driver is not available")
    else:
        raise HTTPException(status_code=403, detail="Invalid user type for accepting bookings")
    
    # Generate QR code and numeric code
    qr_code, numeric_code = generate_gate_codes(booking_id, driver.id, truck_id)
    
    # Update booking
    booking.aggregator_id = current_user.id if current_user.user_type != UserType.DRIVER.value else driver.owner_id
    booking.truck_id = truck_id
    booking.driver_id = driver.id
    booking.agreed_rate = booking.published_rate
    booking.status = BookingStatus.CONFIRMED.value
    booking.gate_qr_code = qr_code
    booking.gate_numeric_code = numeric_code
    booking.gate_code_generated_at = datetime.utcnow()
    
    # Update truck
    truck.is_available = False
    truck.current_status = "assigned"
    truck.current_driver_id = driver.id
    
    # Update driver
    driver.is_available = False
    driver.current_status = "assigned"
    driver.assigned_truck_id = truck_id
    
    # Create trip record with ETA and tracking
    trip = create_trip_from_booking(db, booking, driver.id, truck_id)
    
    db.commit()
    db.refresh(booking)
    db.refresh(trip)
    
    # Get complete trip details
    trip_details = get_trip_details(db, trip)
    
    # Prepare response
    response_data = {
        "booking": BookingResponse.model_validate(booking).model_dump(),
        "trip": trip_details,
        "codes": {
            "qr_code": qr_code,
            "numeric_code": numeric_code,
            "generated_at": booking.gate_code_generated_at.isoformat()
        },
        "message": "Booking accepted successfully. Use QR code or numeric code for gate check-in."
    }
    
    return ResponseModel(
        success=True,
        message="Booking accepted successfully",
        data=response_data
    )

@router.post("/{booking_id}/bid", response_model=ResponseModel)
async def place_bid(
    booking_id: str,
    bid_data: NegotiationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Place a bid on a negotiable booking"""
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    if booking.status not in [BookingStatus.PENDING.value, BookingStatus.NEGOTIATING.value]:
        raise HTTPException(status_code=400, detail="Booking is no longer available for bidding")
    
    if not booking.is_negotiable:
        raise HTTPException(status_code=400, detail="This booking is not negotiable")
    
    # Validate bid rate
    if booking.published_rate and bid_data.offered_rate < booking.published_rate * 0.5:
        raise HTTPException(status_code=400, detail="Bid cannot be less than 50% of published rate")
    
    # Create negotiation
    negotiation = Negotiation(
        booking_id=booking_id,
        offered_by=current_user.id,
        offered_rate=bid_data.offered_rate,
        justification=bid_data.justification,
        payment_terms=bid_data.payment_terms,
        status="pending"
    )
    
    db.add(negotiation)
    
    # Update booking status
    booking.status = BookingStatus.NEGOTIATING.value
    booking.proposed_rate = bid_data.offered_rate
    
    db.commit()
    db.refresh(negotiation)
    
    return ResponseModel(
        success=True,
        message="Bid placed successfully",
        data=NegotiationResponse.model_validate(negotiation)
    )

@router.post("/{booking_id}/counter-offer", response_model=ResponseModel)
async def counter_offer(
    booking_id: str,
    counter_rate: float,
    message: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Send a counter offer"""
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    # Create counter offer
    negotiation = Negotiation(
        booking_id=booking_id,
        offered_by=current_user.id,
        offered_rate=counter_rate,
        justification=message,
        status="pending"
    )
    
    # Mark previous negotiations as countered
    db.query(Negotiation).filter(
        Negotiation.booking_id == booking_id,
        Negotiation.status == "pending"
    ).update({"status": "countered"})
    
    db.add(negotiation)
    db.commit()
    db.refresh(negotiation)
    
    return ResponseModel(
        success=True,
        message="Counter offer sent",
        data=NegotiationResponse.model_validate(negotiation)
    )

@router.post("/negotiations/{negotiation_id}/accept", response_model=ResponseModel)
async def accept_negotiation(
    negotiation_id: str,
    truck_id: Optional[str] = None,
    driver_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Accept a negotiation offer"""
    negotiation = db.query(Negotiation).filter(Negotiation.id == negotiation_id).first()
    if not negotiation:
        raise HTTPException(status_code=404, detail="Negotiation not found")
    
    booking = db.query(Booking).filter(Booking.id == negotiation.booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    # Update negotiation
    negotiation.status = "accepted"
    
    # Update booking
    booking.agreed_rate = negotiation.offered_rate
    booking.status = BookingStatus.CONFIRMED.value
    
    if current_user.user_type in [UserType.AGGREGATOR.value, UserType.OWNER.value]:
        booking.aggregator_id = current_user.id
        if truck_id:
            booking.truck_id = truck_id
        if driver_id:
            booking.driver_id = driver_id
    
    db.commit()
    
    return ResponseModel(success=True, message="Offer accepted successfully")

@router.post("/negotiations/{negotiation_id}/decline", response_model=ResponseModel)
async def decline_negotiation(
    negotiation_id: str,
    reason: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Decline a negotiation offer"""
    negotiation = db.query(Negotiation).filter(Negotiation.id == negotiation_id).first()
    if not negotiation:
        raise HTTPException(status_code=404, detail="Negotiation not found")
    
    negotiation.status = "rejected"
    if reason:
        negotiation.justification = f"Declined: {reason}"
    
    db.commit()
    
    return ResponseModel(success=True, message="Offer declined")


@router.post("/{booking_id}/assign-driver", response_model=ResponseModel)
async def assign_driver_to_booking(
    booking_id: str,
    driver_phone: str,
    driver_name: str,
    truck_id: str,
    driver_id: Optional[str] = None,
    auto_create_driver: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Owner/Aggregator assigns a driver to accepted booking
    - If driver_id provided, uses existing driver
    - If driver doesn't exist and auto_create_driver=True, creates new driver with temp credentials
    """
    if current_user.user_type not in [UserType.OWNER.value, UserType.AGGREGATOR.value]:
        raise HTTPException(status_code=403, detail="Only owners/aggregators can assign drivers")
    
    # Get booking
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    if booking.aggregator_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only assign drivers to your own bookings")
    
    # Get truck
    truck = db.query(Truck).filter(Truck.id == truck_id).first()
    if not truck:
        raise HTTPException(status_code=404, detail="Truck not found")
    
    driver = None
    temp_credentials = None
    driver_created = False
    
    # Try to find existing driver
    if driver_id:
        driver = db.query(Driver).filter(Driver.id == driver_id).first()
    else:
        driver = db.query(Driver).filter(Driver.phone == driver_phone).first()
    
    # Create driver if doesn't exist
    if not driver and auto_create_driver:
        from ...utils.code_generator import generate_temp_password, generate_username_from_phone
        from ...core.security import get_password_hash
        
        temp_password = generate_temp_password()
        username = generate_username_from_phone(driver_phone)
        
        # Create User account for driver
        user = User(
            name=driver_name,
            phone=driver_phone,
            password_hash=get_password_hash(temp_password),
            user_type=UserType.DRIVER.value,
            is_active=True,
            is_verified=False,
            phone_verified=False
        )
        db.add(user)
        db.flush()
        
        # Create Driver profile
        driver = Driver(
            user_id=user.id,
            owner_id=current_user.id,
            name=driver_name,
            phone=driver_phone,
            is_active=True,
            is_available=True,
            auto_created=True,
            temp_password=temp_password,
            password_changed=False,
            created_by_user_id=current_user.id
        )
        db.add(driver)
        db.flush()
        
        driver_created = True
        temp_credentials = {
            "username": username,
            "phone": driver_phone,
            "temp_password": temp_password,
            "message": "Share these credentials with the driver. They must change password on first login."
        }
    
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found and auto-creation is disabled")
    
    # Generate codes if not already generated
    if not booking.gate_qr_code or not booking.gate_numeric_code:
        from ...utils.code_generator import generate_gate_codes
        qr_code, numeric_code = generate_gate_codes(booking_id, driver.id, truck_id)
        booking.gate_qr_code = qr_code
        booking.gate_numeric_code = numeric_code
        booking.gate_code_generated_at = datetime.utcnow()
    
    # Assign driver to booking
    booking.driver_id = driver.id
    booking.truck_id = truck_id
    
    # Update driver status
    driver.is_available = False
    driver.current_status = "assigned"
    driver.assigned_truck_id = truck_id
    
    # Update truck status
    truck.current_driver_id = driver.id
    truck.is_available = False
    truck.current_status = "assigned"
    
    # Create or update trip
    trip = db.query(Trip).filter(Trip.booking_id == booking_id).first()
    if not trip:
        trip = create_trip_from_booking(db, booking, driver.id, truck_id)
    else:
        trip.driver_id = driver.id
        trip.truck_id = truck_id
    
    db.commit()
    db.refresh(booking)
    db.refresh(driver)
    
    # Prepare response
    response_data = {
        "booking_id": booking.id,
        "driver": {
            "id": driver.id,
            "name": driver.name,
            "phone": driver.phone,
            "auto_created": driver.auto_created
        },
        "truck_id": truck_id,
        "codes": {
            "qr_code": booking.gate_qr_code,
            "numeric_code": booking.gate_numeric_code
        }
    }
    
    if driver_created and temp_credentials:
        response_data["temp_credentials"] = temp_credentials
    
    return ResponseModel(
        success=True,
        message="Driver assigned successfully" + (" (New driver created)" if driver_created else ""),
        data=response_data
    )
