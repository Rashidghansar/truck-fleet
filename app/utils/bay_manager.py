"""Bay management utilities for automatic bay assignment"""
from typing import Optional, List
from sqlalchemy.orm import Session
from datetime import datetime

from ..models.user import CfsBay, CfsLocation
from ..models.booking import Booking


def get_available_bay(db: Session, cfs_id: str) -> Optional[CfsBay]:
    """
    Get an available bay for automatic assignment
    Returns first available bay or None
    """
    bay = db.query(CfsBay).filter(
        CfsBay.cfs_id == cfs_id,
        CfsBay.is_available == True
    ).order_by(CfsBay.bay_number).first()
    
    return bay


def assign_bay_to_booking(db: Session, booking: Booking, bay: CfsBay) -> bool:
    """Assign a bay to a booking"""
    if not bay.is_available:
        return False
    
    booking.bay_id = bay.id
    booking.bay_number = bay.bay_number
    booking.bay_contact_name = bay.supervisor_name
    booking.bay_contact_phone = bay.supervisor_phone
    
    # Mark bay as occupied
    bay.is_available = False
    
    return True


def release_bay(db: Session, booking: Booking) -> bool:
    """Release bay after checkout"""
    if booking.bay_id:
        bay = db.query(CfsBay).filter(CfsBay.id == booking.bay_id).first()
        if bay:
            bay.is_available = True
            return True
    return False


def get_bay_occupancy_stats(db: Session, cfs_id: str) -> dict:
    """Get real-time bay occupancy statistics"""
    total_bays = db.query(CfsBay).filter(CfsBay.cfs_id == cfs_id).count()
    occupied_bays = db.query(CfsBay).filter(
        CfsBay.cfs_id == cfs_id,
        CfsBay.is_available == False
    ).count()
    available_bays = total_bays - occupied_bays
    
    return {
        "total": total_bays,
        "occupied": occupied_bays,
        "available": available_bays,
        "occupancy_percentage": (occupied_bays / total_bays * 100) if total_bays > 0 else 0
    }


def get_bay_list(db: Session, cfs_id: str) -> List[dict]:
    """Get list of all bays with status"""
    bays = db.query(CfsBay).filter(CfsBay.cfs_id == cfs_id).order_by(CfsBay.bay_number).all()
    
    result = []
    for bay in bays:
        # Find current booking for this bay
        current_booking = None
        if not bay.is_available:
            booking = db.query(Booking).filter(
                Booking.bay_id == bay.id,
                Booking.status.in_(["confirmed", "in_progress"])
            ).first()
            
            if booking:
                current_booking = {
                    "booking_id": booking.id,
                    "demand_number": booking.demand_number,
                    "consignment_type": booking.consignment_type,
                    "checked_in_at": booking.checkin_time.isoformat() if booking.checkin_time else None
                }
        
        result.append({
            "id": bay.id,
            "bay_number": bay.bay_number,
            "supervisor_name": bay.supervisor_name,
            "supervisor_phone": bay.supervisor_phone,
            "is_available": bay.is_available,
            "current_booking": current_booking
        })
    
    return result

