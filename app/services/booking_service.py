from sqlalchemy.orm import Session
from typing import List, Optional
from ..models.booking import Booking, BookingStatus

class BookingService:
    def __init__(self, db: Session):
        self.db = db
    
    def get_bookings_for_cfs(self, cfs_id: str, status: Optional[str] = None) -> List[Booking]:
        query = self.db.query(Booking).filter(Booking.cfs_id == cfs_id)
        if status:
            query = query.filter(Booking.status == BookingStatus(status))
        return query.order_by(Booking.created_at.desc()).all()
    
    def get_available_opportunities(self) -> List[Booking]:
        return self.db.query(Booking).filter(
            Booking.status.in_([BookingStatus.PENDING, BookingStatus.NEGOTIATING])
        ).order_by(Booking.created_at.desc()).all()
    
    def accept_booking(self, booking_id: str, aggregator_id: str, truck_id: str, driver_id: str) -> Booking:
        booking = self.db.query(Booking).filter(Booking.id == booking_id).first()
        if booking:
            booking.aggregator_id = aggregator_id
            booking.truck_id = truck_id
            booking.driver_id = driver_id
            booking.agreed_price = booking.base_price
            booking.status = BookingStatus.CONFIRMED
            self.db.commit()
            self.db.refresh(booking)
        return booking

