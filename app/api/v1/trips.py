"""Trip tracking endpoints"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime

from ...database import get_db
from ...models.gate_activity import Trip
from ...models.booking import Booking, BookingStatus
from ...models.driver import Driver
from ...models.user import User, UserType
from ...schemas.response import ResponseModel
from ...core.deps import get_current_user
from ...services.trip_service import (
    update_trip_location,
    check_and_notify_delay,
    get_trip_details,
    start_trip,
    complete_trip
)

router = APIRouter()


@router.get("/active", response_model=ResponseModel)
async def get_active_trip(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get driver's active trip"""
    if current_user.user_type != UserType.DRIVER.value:
        raise HTTPException(status_code=403, detail="Only drivers can access trips")
    
    # Get driver profile
    driver = db.query(Driver).filter(Driver.user_id == current_user.id).first()
    if not driver:
        raise HTTPException(status_code=404, detail="Driver profile not found")
    
    # Find active trip
    trip = db.query(Trip).filter(
        Trip.driver_id == driver.id,
        Trip.status.in_(["pending", "en_route_to_pickup", "at_pickup", "en_route_to_destination"])
    ).order_by(Trip.created_at.desc()).first()
    
    if not trip:
        return ResponseModel(
            success=True,
            message="No active trip",
            data={"has_active_trip": False}
        )
    
    trip_data = get_trip_details(db, trip)
    trip_data["has_active_trip"] = True
    
    return ResponseModel(
        success=True,
        data=trip_data
    )


@router.get("/{trip_id}", response_model=ResponseModel)
async def get_trip(
    trip_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get trip details"""
    trip = db.query(Trip).filter(Trip.id == trip_id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    
    trip_data = get_trip_details(db, trip)
    
    return ResponseModel(
        success=True,
        data=trip_data
    )


@router.post("/{trip_id}/update-location", response_model=ResponseModel)
async def update_location(
    trip_id: str,
    latitude: float,
    longitude: float,
    speed: Optional[float] = None,
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update trip location and check for delays"""
    trip = db.query(Trip).filter(Trip.id == trip_id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    
    # Verify driver
    if current_user.user_type == UserType.DRIVER.value:
        driver = db.query(Driver).filter(Driver.user_id == current_user.id).first()
        if not driver or driver.id != trip.driver_id:
            raise HTTPException(status_code=403, detail="Not authorized for this trip")
    
    # Update location
    trip = update_trip_location(db, trip, latitude, longitude, speed)
    
    # Check for delays and notify
    should_notify = check_and_notify_delay(db, trip)
    
    db.commit()
    
    response_data = {
        "trip_id": trip.id,
        "location_updated": True,
        "is_delayed": trip.is_delayed,
        "delay_minutes": trip.delay_minutes if trip.is_delayed else 0,
        "progress_percentage": trip.progress_percentage
    }
    
    if should_notify:
        response_data["delay_notification_sent"] = True
        # TODO: Send actual notification via WebSocket or push notification
        # background_tasks.add_task(send_delay_notification, trip)
    
    return ResponseModel(
        success=True,
        message="Location updated successfully",
        data=response_data
    )


@router.post("/{trip_id}/start", response_model=ResponseModel)
async def start_trip_endpoint(
    trip_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Start the trip (called after gate check-in)"""
    trip = db.query(Trip).filter(Trip.id == trip_id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    
    if trip.status != "pending":
        raise HTTPException(status_code=400, detail=f"Cannot start trip in status: {trip.status}")
    
    trip = start_trip(db, trip)
    
    # Update booking status
    booking = db.query(Booking).filter(Booking.id == trip.booking_id).first()
    if booking:
        booking.status = BookingStatus.IN_PROGRESS.value
    
    db.commit()
    
    trip_data = get_trip_details(db, trip)
    
    return ResponseModel(
        success=True,
        message="Trip started successfully",
        data=trip_data
    )


@router.get("/booking/{booking_id}/trip", response_model=ResponseModel)
async def get_trip_by_booking(
    booking_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get trip details by booking ID (for demand app to track driver)"""
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    # Verify access
    if current_user.user_type == UserType.CFS_ADMIN.value:
        if booking.cfs_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized to view this booking")
    
    trip = db.query(Trip).filter(Trip.booking_id == booking_id).order_by(Trip.created_at.desc()).first()
    
    if not trip:
        return ResponseModel(
            success=True,
            message="No trip found for this booking",
            data={"has_trip": False}
        )
    
    trip_data = get_trip_details(db, trip)
    trip_data["has_trip"] = True
    
    # Add driver details for demand app
    if trip.driver_id:
        driver = db.query(Driver).filter(Driver.id == trip.driver_id).first()
        if driver:
            trip_data["driver_details"] = {
                "id": driver.id,
                "name": driver.name,
                "phone": driver.phone,
                "profile_image": driver.profile_image,
                "license_number": driver.license_number,
                "rating": driver.rating,
                "total_trips": driver.total_trips,
                "current_status": driver.current_status
            }
    
    return ResponseModel(
        success=True,
        data=trip_data
    )


@router.get("/{trip_id}/codes", response_model=ResponseModel)
async def get_trip_codes(
    trip_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get QR and numeric codes for gate operations"""
    trip = db.query(Trip).filter(Trip.id == trip_id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    
    booking = db.query(Booking).filter(Booking.id == trip.booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    # Verify driver access
    if current_user.user_type == UserType.DRIVER.value:
        driver = db.query(Driver).filter(Driver.user_id == current_user.id).first()
        if not driver or driver.id != trip.driver_id:
            raise HTTPException(status_code=403, detail="Not authorized for this trip")
    
    return ResponseModel(
        success=True,
        data={
            "trip_id": trip.id,
            "booking_id": booking.id,
            "qr_code": booking.gate_qr_code,
            "numeric_code": booking.gate_numeric_code,
            "generated_at": booking.gate_code_generated_at.isoformat() if booking.gate_code_generated_at else None,
            "checkin_status": {
                "checked_in": booking.checkin_qr_scanned,
                "checkin_time": booking.checkin_time.isoformat() if booking.checkin_time else None,
                "checkin_method": booking.checkin_method
            },
            "checkout_status": {
                "checked_out": booking.checkout_qr_scanned,
                "checkout_time": booking.checkout_time.isoformat() if booking.checkout_time else None,
                "checkout_method": booking.checkout_method
            }
        }
    )

