"""Trip service for handling trip tracking, ETA calculations, and delay monitoring"""
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
import json

from ..models.gate_activity import Trip
from ..models.booking import Booking, BookingStatus
from ..models.driver import Driver
from ..models.user import User


def calculate_eta(distance_km: float, average_speed_kmh: float = 40) -> datetime:
    """
    Calculate estimated time of arrival
    Args:
        distance_km: Distance in kilometers
        average_speed_kmh: Average speed (default 40 km/h for Indian highways)
    Returns:
        Estimated arrival datetime
    """
    hours = distance_km / average_speed_kmh
    return datetime.utcnow() + timedelta(hours=hours)


def calculate_delay(expected_time: datetime, current_time: datetime = None) -> Dict[str, Any]:
    """
    Calculate delay information
    Returns:
        dict with is_delayed, delay_minutes, delay_seconds
    """
    if current_time is None:
        current_time = datetime.utcnow()
    
    if current_time > expected_time:
        delay_delta = current_time - expected_time
        delay_minutes = delay_delta.total_seconds() / 60
        return {
            "is_delayed": True,
            "delay_minutes": delay_minutes,
            "delay_seconds": delay_delta.total_seconds()
        }
    else:
        return {
            "is_delayed": False,
            "delay_minutes": 0,
            "delay_seconds": 0
        }


def create_trip_from_booking(
    db: Session,
    booking: Booking,
    driver_id: str,
    truck_id: Optional[str] = None
) -> Trip:
    """
    Create a trip record when driver accepts booking
    Calculates ETA and sets up tracking
    """
    # Calculate distance if not set (simplified - in production use maps API)
    distance = booking.distance_km or 50.0  # Default 50km if not set
    
    # Calculate expected arrival time
    expected_arrival = calculate_eta(distance)
    expected_duration = distance / 40 * 60  # minutes
    
    trip = Trip(
        booking_id=booking.id,
        driver_id=driver_id,
        truck_id=truck_id,
        status="pending",
        expected_arrival_time=expected_arrival,
        expected_duration_minutes=expected_duration,
        total_distance=distance,
        distance_remaining=distance,
        progress_percentage=0.0,
        is_delayed=False,
        delay_minutes=0.0
    )
    
    # Add initial milestone
    milestones = [
        {
            "type": "booking_accepted",
            "timestamp": datetime.utcnow().isoformat(),
            "status": "Driver accepted booking"
        }
    ]
    trip.milestones = json.dumps(milestones)
    
    db.add(trip)
    return trip


def update_trip_location(
    db: Session,
    trip: Trip,
    latitude: float,
    longitude: float,
    speed: Optional[float] = None
) -> Trip:
    """Update trip location and recalculate progress"""
    trip.current_latitude = latitude
    trip.current_longitude = longitude
    trip.current_speed = speed
    trip.last_location_update = datetime.utcnow()
    
    # Calculate distance covered (simplified - use proper geolocation in production)
    # This is a placeholder calculation
    if trip.total_distance:
        # Assuming linear progress for now
        trip.progress_percentage = min(100.0, (trip.distance_covered / trip.total_distance) * 100)
        trip.distance_remaining = max(0.0, trip.total_distance - trip.distance_covered)
    
    # Check for delays
    if trip.expected_arrival_time:
        delay_info = calculate_delay(trip.expected_arrival_time)
        trip.is_delayed = delay_info["is_delayed"]
        trip.delay_minutes = delay_info["delay_minutes"]
    
    return trip


def check_and_notify_delay(db: Session, trip: Trip) -> bool:
    """
    Check if trip is delayed and needs notification
    Returns True if notification should be sent
    """
    if not trip.expected_arrival_time:
        return False
    
    delay_info = calculate_delay(trip.expected_arrival_time)
    
    # Update trip delay status
    if delay_info["is_delayed"] and not trip.is_delayed:
        trip.is_delayed = True
        trip.delay_minutes = delay_info["delay_minutes"]
        
        # Add milestone
        milestones = json.loads(trip.milestones) if trip.milestones else []
        milestones.append({
            "type": "delay_detected",
            "timestamp": datetime.utcnow().isoformat(),
            "delay_minutes": delay_info["delay_minutes"],
            "status": f"Trip delayed by {delay_info['delay_minutes']:.1f} minutes"
        })
        trip.milestones = json.dumps(milestones)
        
        # Mark when notification was sent
        if not trip.delay_notified_at:
            trip.delay_notified_at = datetime.utcnow()
            return True  # Send notification
    
    return False


def start_trip(db: Session, trip: Trip, gate_in_id: str = None) -> Trip:
    """Start the trip after gate check-in"""
    trip.status = "en_route_to_pickup"
    trip.start_time = datetime.utcnow()
    
    if gate_in_id:
        trip.gate_in_id = gate_in_id
    
    # Add milestone
    milestones = json.loads(trip.milestones) if trip.milestones else []
    milestones.append({
        "type": "trip_started",
        "timestamp": datetime.utcnow().isoformat(),
        "status": "Trip started - en route to pickup location"
    })
    trip.milestones = json.dumps(milestones)
    
    return trip


def complete_trip(db: Session, trip: Trip, gate_out_id: str = None) -> Trip:
    """Complete the trip after delivery and update driver statistics"""
    trip.status = "completed"
    trip.end_time = datetime.utcnow()
    trip.completed_at = datetime.utcnow()
    trip.actual_arrival_time = datetime.utcnow()
    trip.progress_percentage = 100.0
    trip.distance_remaining = 0.0
    
    if gate_out_id:
        trip.gate_out_id = gate_out_id
    
    # Add milestone
    milestones = json.loads(trip.milestones) if trip.milestones else []
    milestones.append({
        "type": "trip_completed",
        "timestamp": datetime.utcnow().isoformat(),
        "status": "Trip completed successfully"
    })
    trip.milestones = json.dumps(milestones)
    
    # Update driver statistics - ACTUAL DATA FROM DB
    driver = db.query(Driver).filter(Driver.id == trip.driver_id).first()
    if driver:
        # Increment trip count
        driver.total_trips += 1
        
        # Update status
        driver.current_status = "available"
        driver.is_available = True
        
        # Calculate earnings if booking has agreed_rate
        booking = db.query(Booking).filter(Booking.id == trip.booking_id).first()
        if booking and booking.agreed_rate:
            driver.total_earnings += booking.agreed_rate
    
    # Update truck statistics
    if trip.truck_id:
        from ..models.truck import Truck
        truck = db.query(Truck).filter(Truck.id == trip.truck_id).first()
        if truck:
            truck.total_trips += 1
            truck.is_available = True
            truck.current_status = "available"
            if booking and booking.agreed_rate:
                truck.total_earnings += booking.agreed_rate
    
    # Update booking status
    if booking:
        booking.status = BookingStatus.COMPLETED.value
    
    return trip


def get_trip_details(db: Session, trip: Trip) -> Dict[str, Any]:
    """Get complete trip details with all related information"""
    booking = db.query(Booking).filter(Booking.id == trip.booking_id).first()
    driver = db.query(Driver).filter(Driver.id == trip.driver_id).first()
    
    # Get CFS info
    cfs = None
    bay_info = None
    if booking:
        cfs = db.query(User).filter(User.id == booking.cfs_id).first()
        if booking.bay_number:
            bay_info = {
                "bay_number": booking.bay_number,
                "bay_contact_name": booking.bay_contact_name,
                "bay_contact_phone": booking.bay_contact_phone
            }
    
    # Parse milestones
    milestones = json.loads(trip.milestones) if trip.milestones else []
    
    # Calculate remaining time
    time_remaining = None
    if trip.expected_arrival_time:
        remaining_delta = trip.expected_arrival_time - datetime.utcnow()
        time_remaining = max(0, int(remaining_delta.total_seconds() / 60))  # minutes
    
    return {
        "trip_id": trip.id,
        "booking_id": trip.booking_id,
        "status": trip.status,
        "driver": {
            "id": driver.id if driver else None,
            "name": driver.name if driver else None,
            "phone": driver.phone if driver else None,
            "profile_image": driver.profile_image if driver else None
        },
        "pickup_location": booking.pickup_location if booking else None,
        "destination": booking.destination_address if booking else None,
        "cfs_info": {
            "name": cfs.cfs_name or cfs.name if cfs else None,
            "address": cfs.cfs_address or cfs.address if cfs else None,
            "phone": cfs.phone if cfs else None
        } if cfs else None,
        "bay_info": bay_info,
        "timing": {
            "start_time": trip.start_time.isoformat() if trip.start_time else None,
            "expected_arrival": trip.expected_arrival_time.isoformat() if trip.expected_arrival_time else None,
            "expected_duration_minutes": trip.expected_duration_minutes,
            "time_remaining_minutes": time_remaining,
            "is_delayed": trip.is_delayed,
            "delay_minutes": trip.delay_minutes
        },
        "progress": {
            "distance_covered": trip.distance_covered,
            "distance_remaining": trip.distance_remaining,
            "total_distance": trip.total_distance,
            "progress_percentage": trip.progress_percentage
        },
        "current_location": {
            "latitude": trip.current_latitude,
            "longitude": trip.current_longitude,
            "speed": trip.current_speed,
            "last_update": trip.last_location_update.isoformat() if trip.last_location_update else None
        },
        "milestones": milestones,
        "codes": {
            "qr_code": booking.gate_qr_code if booking else None,
            "numeric_code": booking.gate_numeric_code if booking else None
        }
    }

