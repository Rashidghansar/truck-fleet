from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime
from pydantic import BaseModel
from ...database import get_db
from ...models.payment_transaction import PaymentTransaction, PaymentStatus, PaymentMethod
from ...models.booking import Booking
from ...models.user import User
from ...schemas.response import ResponseModel
from ...core.deps import get_current_user
from ...utils.pagination import paginate_query, create_paginated_response

router = APIRouter()

class PaymentCreate(BaseModel):
    booking_id: str
    amount: float
    payment_method: str
    transaction_id: Optional[str] = None
    reference_number: Optional[str] = None
    notes: Optional[str] = None

@router.post("/", response_model=ResponseModel)
async def create_payment(
    payment_data: PaymentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a payment transaction"""
    # Verify booking exists
    booking = db.query(Booking).filter(Booking.id == payment_data.booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    # Determine payee (usually the aggregator or owner)
    payee_id = booking.aggregator_id
    
    payment = PaymentTransaction(
        booking_id=payment_data.booking_id,
        payer_id=current_user.id,
        payee_id=payee_id,
        amount=payment_data.amount,
        payment_method=payment_data.payment_method,
        transaction_id=payment_data.transaction_id,
        reference_number=payment_data.reference_number,
        status=PaymentStatus.PENDING.value,
        notes=payment_data.notes
    )
    
    db.add(payment)
    db.commit()
    db.refresh(payment)
    
    return ResponseModel(
        success=True,
        message="Payment transaction created successfully",
        data={"payment_id": payment.id}
    )

@router.put("/{payment_id}/status", response_model=ResponseModel)
async def update_payment_status(
    payment_id: str,
    status: str,
    failure_reason: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update payment status"""
    payment = db.query(PaymentTransaction).filter(PaymentTransaction.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    
    if status not in [s.value for s in PaymentStatus]:
        raise HTTPException(status_code=400, detail="Invalid payment status")
    
    payment.status = status
    payment.processed_at = datetime.utcnow()
    
    if status == PaymentStatus.COMPLETED.value:
        payment.payment_date = datetime.utcnow()
    elif status == PaymentStatus.FAILED.value:
        payment.failure_reason = failure_reason
    
    db.commit()
    
    return ResponseModel(success=True, message="Payment status updated successfully")

@router.get("/", response_model=ResponseModel)
async def get_payments(
    booking_id: Optional[str] = None,
    status: Optional[str] = None,
    payment_method: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get payment transactions with filters"""
    query = db.query(PaymentTransaction)
    
    # Filter based on user role
    if current_user.user_type in ["aggregator", "owner", "driver"]:
        query = query.filter(
            (PaymentTransaction.payer_id == current_user.id) |
            (PaymentTransaction.payee_id == current_user.id)
        )
    elif current_user.user_type == "cfs_admin":
        # CFS admins see all payments for their bookings
        cfs_bookings = db.query(Booking.id).filter(Booking.cfs_id == current_user.id).subquery()
        query = query.filter(PaymentTransaction.booking_id.in_(cfs_bookings))
    
    if booking_id:
        query = query.filter(PaymentTransaction.booking_id == booking_id)
    if status:
        query = query.filter(PaymentTransaction.status == status)
    if payment_method:
        query = query.filter(PaymentTransaction.payment_method == payment_method)
    if date_from:
        query = query.filter(PaymentTransaction.created_at >= date_from)
    if date_to:
        query = query.filter(PaymentTransaction.created_at <= date_to)
    
    paginated_query, pagination_info = paginate_query(
        query.order_by(PaymentTransaction.created_at.desc()),
        page,
        page_size
    )
    payments = paginated_query.all()
    
    return ResponseModel(
        success=True,
        data=create_paginated_response(
            [{
                "id": p.id,
                "booking_id": p.booking_id,
                "amount": p.amount,
                "payment_method": p.payment_method,
                "status": p.status,
                "transaction_id": p.transaction_id,
                "created_at": p.created_at.isoformat()
            } for p in payments],
            pagination_info["total"],
            pagination_info["page"],
            pagination_info["page_size"]
        ).model_dump()
    )

@router.get("/{payment_id}", response_model=ResponseModel)
async def get_payment(
    payment_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific payment transaction"""
    payment = db.query(PaymentTransaction).filter(PaymentTransaction.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    
    # Check access
    booking = db.query(Booking).filter(Booking.id == payment.booking_id).first()
    if current_user.user_type not in ["cfs_admin", "security_officer"]:
        if payment.payer_id != current_user.id and payment.payee_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized to view this payment")
    
    return ResponseModel(
        success=True,
        data={
            "id": payment.id,
            "booking_id": payment.booking_id,
            "payer_id": payment.payer_id,
            "payee_id": payment.payee_id,
            "amount": payment.amount,
            "currency": payment.currency,
            "payment_method": payment.payment_method,
            "transaction_id": payment.transaction_id,
            "reference_number": payment.reference_number,
            "status": payment.status,
            "failure_reason": payment.failure_reason,
            "payment_date": payment.payment_date.isoformat() if payment.payment_date else None,
            "created_at": payment.created_at.isoformat()
        }
    )

@router.get("/booking/{booking_id}/summary", response_model=ResponseModel)
async def get_booking_payment_summary(
    booking_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get payment summary for a booking"""
    from sqlalchemy import func
    
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    payments = db.query(PaymentTransaction).filter(
        PaymentTransaction.booking_id == booking_id
    ).all()
    
    total_paid = sum(p.amount for p in payments if p.status == PaymentStatus.COMPLETED.value)
    total_pending = sum(p.amount for p in payments if p.status == PaymentStatus.PENDING.value)
    total_failed = sum(p.amount for p in payments if p.status == PaymentStatus.FAILED.value)
    
    return ResponseModel(
        success=True,
        data={
            "booking_id": booking_id,
            "agreed_rate": booking.agreed_rate or booking.published_rate,
            "total_paid": total_paid,
            "total_pending": total_pending,
            "total_failed": total_failed,
            "remaining": (booking.agreed_rate or booking.published_rate or 0) - total_paid,
            "payments": [{
                "id": p.id,
                "amount": p.amount,
                "payment_method": p.payment_method,
                "status": p.status,
                "created_at": p.created_at.isoformat()
            } for p in payments]
        }
    )
