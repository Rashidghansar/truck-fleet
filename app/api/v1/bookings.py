from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime
import uuid
from ...database import get_db
from ...models.booking import Booking, BookingStatus, Negotiation
from ...models.user import User, UserType
from ...models.truck import Truck
from ...models.driver import Driver
from ...schemas.booking import BookingCreate, BookingResponse, BookingUpdate, NegotiationCreate, NegotiationResponse
from ...schemas.response import ResponseModel
from ...core.deps import get_current_user
from . import websocket

router = APIRouter()

def generate_demand_number():
    now = datetime.now()
    return f"DEM-{now.year}-{now.month:02d}{now.day:02d}-{str(uuid.uuid4())[:3].upper()}"

@router.post("/create", response_model=ResponseModel)
async def create_booking(
    booking_data: BookingCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.user_type != UserType.CFS_ADMIN.value:
        raise HTTPException(status_code=403, detail="Only CFS admins can create bookings")
    
    # Validate required fields
    consignment_type = booking_data.consignment_type or booking_data.container_type
    if not consignment_type or consignment_type.strip() == "":
        raise HTTPException(status_code=400, detail="consignment_type is required")
    
    if not booking_data.truck_type or booking_data.truck_type.strip() == "":
        raise HTTPException(status_code=400, detail="truck_type is required")
    
    # Generate demand number
    demand_number = generate_demand_number()
    
    # Use CFS address as pickup location if not provided
    pickup_location = booking_data.pickup_location or current_user.cfs_address or current_user.address or "CFS Location"
    
    try:
        booking = Booking(
            demand_number=demand_number,
            cfs_id=current_user.id,
            consignment_type=consignment_type,
            container_number=booking_data.container_number,
            weight=booking_data.weight,
            special_instructions=booking_data.special_instructions,
            truck_type=booking_data.truck_type,
            truck_capacity=booking_data.truck_capacity,
            quantity=booking_data.quantity or 1,
            gate_in_time=booking_data.gate_in_time,
            gate_out_time=booking_data.gate_out_time,
            bay_number=booking_data.bay_number,
            bay_contact_name=booking_data.bay_contact_name,
            bay_contact_phone=booking_data.bay_contact_phone,
            pickup_location=pickup_location,
            pickup_lat=booking_data.pickup_lat,
            pickup_lng=booking_data.pickup_lng,
            destination_address=booking_data.destination_address or booking_data.delivery_location,
            destination_lat=booking_data.destination_lat or booking_data.delivery_lat,
            destination_lng=booking_data.destination_lng or booking_data.delivery_lng,
            destination_gate_in_time=booking_data.destination_gate_in_time,
            destination_contact_name=booking_data.destination_contact_name,
            destination_contact_phone=booking_data.destination_contact_phone,
            # Legacy
            container_type=booking_data.container_type,
            container_size=booking_data.container_size,
            delivery_location=booking_data.delivery_location,
            delivery_lat=booking_data.delivery_lat,
            delivery_lng=booking_data.delivery_lng,
            pickup_date=booking_data.pickup_date or booking_data.gate_in_time,
            pickup_time_slot=booking_data.pickup_time_slot,
            base_price=booking_data.base_price,
            published_rate=booking_data.published_rate or booking_data.base_price,
            payment_terms=booking_data.payment_terms or "immediate",
            is_negotiable=booking_data.is_negotiable if booking_data.is_negotiable is not None else False,
            notes=booking_data.notes,
            status=BookingStatus.PENDING.value,
        )
        
        # Auto-assign bay if not provided and CFS has configured bays
        if not booking.bay_number and current_user.cfs_id:
            from ...utils.bay_manager import get_available_bay, assign_bay_to_booking
            try:
                available_bay = get_available_bay(db, current_user.cfs_id)
                if available_bay:
                    assign_bay_to_booking(db, booking, available_bay)
            except Exception:
                # If bay assignment fails, continue without bay
                pass
        
        db.add(booking)
        db.commit()
        db.refresh(booking)
    except Exception as e:
        db.rollback()
        import traceback
        error_details = str(e)
        # Log the full traceback for debugging
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Database error creating booking: {error_details}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Database error occurred: {error_details}. Please check all required fields are provided."
        )
    
    # Notify all aggregators, owners, and drivers about new opportunity
    supply_users = db.query(User).filter(
        User.user_type.in_([UserType.AGGREGATOR.value, UserType.OWNER.value, UserType.DRIVER.value]),
        User.is_active == True
    ).all()
    
    supply_user_ids = [u.id for u in supply_users]
    
    if supply_user_ids:
        background_tasks.add_task(
            notify_new_booking,
            booking_data={
                "id": booking.id,
                "demand_number": booking.demand_number,
                "truck_type": booking.truck_type,
                "published_rate": booking.published_rate,
                "gate_in_time": booking.gate_in_time.isoformat() if booking.gate_in_time else None,
                "pickup_location": booking.pickup_location,
                "destination": booking.destination_address,
                "bay_number": booking.bay_number,
            },
            user_ids=supply_user_ids
        )
    
    return ResponseModel(
        success=True,
        message="Booking created successfully" + (f" and assigned to Bay {booking.bay_number}" if booking.bay_number else ""),
        data=BookingResponse.model_validate(booking)
    )

async def notify_new_booking(booking_data: dict, user_ids: List[str]):
    """Background task to notify users about new booking"""
    await websocket.notify_new_opportunity(booking_data, user_ids)

@router.get("", response_model=ResponseModel)
async def get_bookings(
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Booking)
    
    # Filter based on user type
    if current_user.user_type == UserType.CFS_ADMIN.value:
        query = query.filter(Booking.cfs_id == current_user.id)
    elif current_user.user_type == UserType.SECURITY_OFFICER.value:
        # Security officers see bookings for their CFS
        query = query.filter(Booking.cfs_id == current_user.cfs_id)
    elif current_user.user_type in [UserType.AGGREGATOR.value, UserType.OWNER.value]:
        query = query.filter(
            (Booking.aggregator_id == current_user.id) |
            (Booking.status == BookingStatus.PENDING.value)
        )
    elif current_user.user_type == UserType.DRIVER.value:
        # Get driver's bookings
        driver = db.query(Driver).filter(Driver.user_id == current_user.id).first()
        if driver:
            query = query.filter(Booking.driver_id == driver.id)
    
    if status:
        query = query.filter(Booking.status == status)
    
    # Get total count
    total = query.count()
    
    # Order and paginate
    query = query.order_by(Booking.created_at.desc())
    offset = (page - 1) * page_size
    bookings = query.offset(offset).limit(page_size).all()
    
    return ResponseModel(
        success=True,
        data={
            "bookings": [BookingResponse.model_validate(b) for b in bookings],
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": (total + page_size - 1) // page_size
        }
    )

@router.get("/{booking_id}", response_model=ResponseModel)
async def get_booking(
    booking_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    return ResponseModel(
        success=True,
        data=BookingResponse.model_validate(booking)
    )

@router.put("/{booking_id}", response_model=ResponseModel)
async def update_booking(
    booking_id: str,
    update_data: BookingUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    update_dict = update_data.model_dump(exclude_unset=True)
    for key, value in update_dict.items():
        setattr(booking, key, value)
    
    booking.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(booking)
    
    return ResponseModel(
        success=True,
        message="Booking updated successfully",
        data=BookingResponse.model_validate(booking)
    )

@router.put("/{booking_id}/cancel", response_model=ResponseModel)
async def cancel_booking(
    booking_id: str,
    reason: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Cancel booking with proper cleanup"""
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    # Validate status transition
    valid_statuses = [BookingStatus.PENDING.value, BookingStatus.NEGOTIATING.value, BookingStatus.CONFIRMED.value]
    if booking.status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel booking in current status: {booking.status}"
        )
    
    booking.status = BookingStatus.CANCELLED.value
    if reason:
        booking.notes = f"Cancelled: {reason}"
    
    # Reset assignments
    if booking.truck_id:
        truck = db.query(Truck).filter(Truck.id == booking.truck_id).first()
        if truck:
            truck.is_available = True
            truck.current_status = "available"
    
    if booking.driver_id:
        driver = db.query(Driver).filter(Driver.id == booking.driver_id).first()
        if driver:
            driver.is_available = True
            driver.current_status = "available"
            driver.assigned_truck_id = None
    
    # Clean up gate activities
    from ...models.gate_activity import GateActivity
    gate_activities = db.query(GateActivity).filter(GateActivity.booking_id == booking_id).all()
    for activity in gate_activities:
        activity.is_active = False
    
    # Unassign aggregator
    booking.aggregator_id = None
    
    db.commit()
    
    return ResponseModel(success=True, message="Booking cancelled successfully")

@router.post("/{booking_id}/assign", response_model=ResponseModel)
async def assign_booking(
    booking_id: str,
    truck_id: str,
    driver_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    truck = db.query(Truck).filter(Truck.id == truck_id).first()
    if not truck:
        raise HTTPException(status_code=404, detail="Truck not found")
    
    driver = db.query(Driver).filter(Driver.id == driver_id).first()
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found")
    
    # Update booking
    booking.aggregator_id = current_user.id
    booking.truck_id = truck_id
    booking.driver_id = driver_id
    booking.status = BookingStatus.CONFIRMED.value
    
    # Update truck and driver
    truck.is_available = False
    truck.current_status = "assigned"
    truck.current_driver_id = driver_id
    
    driver.is_available = False
    driver.current_status = "assigned"
    driver.assigned_truck_id = truck_id
    
    db.commit()
    db.refresh(booking)
    
    return ResponseModel(
        success=True,
        message="Booking assigned successfully",
        data=BookingResponse.model_validate(booking)
    )

@router.get("/{booking_id}/negotiations", response_model=ResponseModel)
async def get_negotiations(
    booking_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    negotiations = db.query(Negotiation).filter(
        Negotiation.booking_id == booking_id
    ).order_by(Negotiation.created_at.desc()).all()
    
    return ResponseModel(
        success=True,
        data=[NegotiationResponse.model_validate(n) for n in negotiations]
    )

@router.post("/bulk-create", response_model=ResponseModel)
async def bulk_create_bookings(
    bookings_data: List[BookingCreate],
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create multiple bookings at once"""
    if current_user.user_type != UserType.CFS_ADMIN.value:
        raise HTTPException(status_code=403, detail="Only CFS admins can create bookings")
    
    created_bookings = []
    errors = []
    
    for idx, booking_data in enumerate(bookings_data):
        try:
            demand_number = generate_demand_number()
            pickup_location = booking_data.pickup_location or current_user.cfs_address or current_user.address or "CFS Location"
            
            booking = Booking(
                demand_number=demand_number,
                cfs_id=current_user.id,
                consignment_type=booking_data.consignment_type or booking_data.container_type,
                container_number=booking_data.container_number,
                weight=booking_data.weight,
                special_instructions=booking_data.special_instructions,
                truck_type=booking_data.truck_type,
                truck_capacity=booking_data.truck_capacity,
                quantity=booking_data.quantity,
                gate_in_time=booking_data.gate_in_time,
                gate_out_time=booking_data.gate_out_time,
                bay_number=booking_data.bay_number,
                bay_contact_name=booking_data.bay_contact_name,
                bay_contact_phone=booking_data.bay_contact_phone,
                pickup_location=pickup_location,
                pickup_lat=booking_data.pickup_lat,
                pickup_lng=booking_data.pickup_lng,
                destination_address=booking_data.destination_address or booking_data.delivery_location,
                destination_lat=booking_data.destination_lat or booking_data.delivery_lat,
                destination_lng=booking_data.destination_lng or booking_data.delivery_lng,
                base_price=booking_data.base_price,
                published_rate=booking_data.published_rate or booking_data.base_price,
                payment_terms=booking_data.payment_terms,
                is_negotiable=booking_data.is_negotiable,
                status=BookingStatus.PENDING.value,
            )
            
            db.add(booking)
            db.commit()
            db.refresh(booking)
            created_bookings.append(booking)
        except Exception as e:
            errors.append({"index": idx, "error": str(e)})
            db.rollback()
    
    return ResponseModel(
        success=True,
        message=f"Created {len(created_bookings)} bookings",
        data={
            "created": len(created_bookings),
            "failed": len(errors),
            "bookings": [BookingResponse.model_validate(b) for b in created_bookings],
            "errors": errors
        }
    )

@router.post("/{booking_id}/duplicate", response_model=ResponseModel)
async def duplicate_booking(
    booking_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Duplicate an existing booking"""
    original_booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not original_booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    if current_user.user_type != UserType.CFS_ADMIN.value:
        raise HTTPException(status_code=403, detail="Only CFS admins can duplicate bookings")
    
    # Create new booking with same data
    new_demand_number = generate_demand_number()
    new_booking = Booking(
        demand_number=new_demand_number,
        cfs_id=original_booking.cfs_id,
        consignment_type=original_booking.consignment_type,
        container_number=original_booking.container_number,
        weight=original_booking.weight,
        special_instructions=original_booking.special_instructions,
        truck_type=original_booking.truck_type,
        truck_capacity=original_booking.truck_capacity,
        quantity=original_booking.quantity,
        gate_in_time=original_booking.gate_in_time,
        gate_out_time=original_booking.gate_out_time,
        bay_number=original_booking.bay_number,
        bay_contact_name=original_booking.bay_contact_name,
        bay_contact_phone=original_booking.bay_contact_phone,
        pickup_location=original_booking.pickup_location,
        pickup_lat=original_booking.pickup_lat,
        pickup_lng=original_booking.pickup_lng,
        destination_address=original_booking.destination_address,
        destination_lat=original_booking.destination_lat,
        destination_lng=original_booking.destination_lng,
        base_price=original_booking.base_price,
        published_rate=original_booking.published_rate,
        payment_terms=original_booking.payment_terms,
        is_negotiable=original_booking.is_negotiable,
        status=BookingStatus.PENDING.value,
    )
    
    db.add(new_booking)
    db.commit()
    db.refresh(new_booking)
    
    return ResponseModel(
        success=True,
        message="Booking duplicated successfully",
        data=BookingResponse.model_validate(new_booking)
    )

@router.get("/search", response_model=ResponseModel)
async def search_bookings(
    query: Optional[str] = None,
    status: Optional[str] = None,
    truck_type: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Search bookings with filters"""
    from ...utils.pagination import paginate_query, create_paginated_response
    
    bookings_query = db.query(Booking)
    
    # Filter based on user type
    if current_user.user_type == UserType.CFS_ADMIN.value:
        bookings_query = bookings_query.filter(Booking.cfs_id == current_user.id)
    elif current_user.user_type == UserType.SECURITY_OFFICER.value:
        bookings_query = bookings_query.filter(Booking.cfs_id == current_user.cfs_id)
    elif current_user.user_type in [UserType.AGGREGATOR.value, UserType.OWNER.value]:
        bookings_query = bookings_query.filter(
            (Booking.aggregator_id == current_user.id) |
            (Booking.status == BookingStatus.PENDING.value)
        )
    
    # Apply filters
    if query:
        bookings_query = bookings_query.filter(
            (Booking.demand_number.contains(query)) |
            (Booking.container_number.contains(query)) |
            (Booking.pickup_location.contains(query)) |
            (Booking.destination_address.contains(query))
        )
    
    if status:
        bookings_query = bookings_query.filter(Booking.status == status)
    
    if truck_type:
        bookings_query = bookings_query.filter(Booking.truck_type == truck_type)
    
    if date_from:
        bookings_query = bookings_query.filter(Booking.created_at >= date_from)
    
    if date_to:
        bookings_query = bookings_query.filter(Booking.created_at <= date_to)
    
    paginated_query, pagination_info = paginate_query(bookings_query.order_by(Booking.created_at.desc()), page, page_size)
    bookings = paginated_query.all()
    
    return ResponseModel(
        success=True,
        data=create_paginated_response(
            [BookingResponse.model_validate(b) for b in bookings],
            pagination_info["total"],
            pagination_info["page"],
            pagination_info["page_size"]
        ).model_dump()
    )

@router.get("/analytics/stats", response_model=ResponseModel)
async def get_booking_analytics(
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get booking analytics and statistics"""
    from sqlalchemy import func
    
    query = db.query(Booking)
    
    # Filter based on user type
    if current_user.user_type == UserType.CFS_ADMIN.value:
        query = query.filter(Booking.cfs_id == current_user.id)
    elif current_user.user_type == UserType.SECURITY_OFFICER.value:
        query = query.filter(Booking.cfs_id == current_user.cfs_id)
    elif current_user.user_type in [UserType.AGGREGATOR.value, UserType.OWNER.value]:
        query = query.filter(Booking.aggregator_id == current_user.id)
    
    if date_from:
        query = query.filter(Booking.created_at >= date_from)
    if date_to:
        query = query.filter(Booking.created_at <= date_to)
    
    # Calculate statistics
    total_bookings = query.count()
    status_counts = db.query(Booking.status, func.count(Booking.id)).group_by(Booking.status).all()
    
    total_revenue = db.query(func.sum(Booking.agreed_rate)).filter(
        Booking.status == BookingStatus.COMPLETED.value
    ).scalar() or 0
    
    avg_rate = db.query(func.avg(Booking.agreed_rate)).filter(
        Booking.status == BookingStatus.COMPLETED.value
    ).scalar() or 0
    
    return ResponseModel(
        success=True,
        data={
            "total_bookings": total_bookings,
            "status_breakdown": {status: count for status, count in status_counts},
            "total_revenue": float(total_revenue),
            "average_rate": float(avg_rate),
            "period": {
                "from": date_from.isoformat() if date_from else None,
                "to": date_to.isoformat() if date_to else None
            }
        }
    )


@router.get("/bulk-upload/template", response_model=ResponseModel)
async def get_bulk_upload_template(
    current_user: User = Depends(get_current_user)
):
    """Get CSV template for bulk booking upload"""
    if current_user.user_type != UserType.CFS_ADMIN.value:
        raise HTTPException(status_code=403, detail="Only CFS admins can access bulk upload")
    
    from ...utils.bulk_upload import generate_csv_template
    
    template = generate_csv_template()
    
    return ResponseModel(
        success=True,
        message="CSV template generated",
        data={
            "template": template,
            "headers": [
                "container_number",
                "consignment_type",
                "weight",
                "truck_type",
                "truck_capacity",
                "destination_address",
                "gate_in_time",
                "published_rate",
                "payment_terms",
                "special_instructions"
            ]
        }
    )


@router.post("/bulk-upload", response_model=ResponseModel)
async def bulk_upload_bookings(
    csv_content: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Upload bookings in bulk via CSV"""
    if current_user.user_type != UserType.CFS_ADMIN.value:
        raise HTTPException(status_code=403, detail="Only CFS admins can bulk upload")
    
    from ...utils.bulk_upload import parse_csv_bookings
    from ...utils.bay_manager import get_available_bay, assign_bay_to_booking
    
    bookings_data, errors = parse_csv_bookings(csv_content)
    
    if errors and not bookings_data:
        return ResponseModel(
            success=False,
            message=f"CSV parsing failed with {len(errors)} errors",
            data={"errors": errors}
        )
    
    created_bookings = []
    creation_errors = []
    
    for idx, booking_data in enumerate(bookings_data):
        try:
            demand_number = generate_demand_number()
            pickup_location = current_user.cfs_address or current_user.address or "CFS Location"
            
            booking = Booking(
                demand_number=demand_number,
                cfs_id=current_user.id,
                consignment_type=booking_data["consignment_type"],
                container_number=booking_data.get("container_number"),
                weight=booking_data.get("weight"),
                truck_type=booking_data["truck_type"],
                truck_capacity=booking_data.get("truck_capacity"),
                quantity=booking_data.get("quantity", 1),
                gate_in_time=booking_data.get("gate_in_time"),
                pickup_location=pickup_location,
                destination_address=booking_data["destination_address"],
                published_rate=booking_data.get("published_rate"),
                base_price=booking_data.get("published_rate"),
                payment_terms=booking_data.get("payment_terms", "immediate"),
                special_instructions=booking_data.get("special_instructions"),
                is_negotiable=booking_data.get("is_negotiable", False),
                status=BookingStatus.PENDING.value,
            )
            
            # Auto-assign bay
            if current_user.cfs_id:
                available_bay = get_available_bay(db, current_user.cfs_id)
                if available_bay:
                    assign_bay_to_booking(db, booking, available_bay)
            
            db.add(booking)
            db.flush()
            created_bookings.append(booking)
            
        except Exception as e:
            creation_errors.append(f"Row {idx+2}: {str(e)}")
            db.rollback()
    
    if created_bookings:
        db.commit()
    
    # Notify supply users
    if created_bookings:
        supply_users = db.query(User).filter(
            User.user_type.in_([UserType.AGGREGATOR.value, UserType.OWNER.value, UserType.DRIVER.value]),
            User.is_active == True
        ).all()
        
        for booking in created_bookings:
            background_tasks.add_task(
                notify_new_booking,
                booking_data={
                    "id": booking.id,
                    "demand_number": booking.demand_number,
                    "truck_type": booking.truck_type,
                    "published_rate": booking.published_rate,
                },
                user_ids=[u.id for u in supply_users]
            )
    
    return ResponseModel(
        success=True,
        message=f"Created {len(created_bookings)} bookings. {len(creation_errors)} failed.",
        data={
            "created": len(created_bookings),
            "failed": len(creation_errors) + len(errors),
            "errors": errors + creation_errors,
            "bookings": [BookingResponse.model_validate(b) for b in created_bookings]
        }
    )
