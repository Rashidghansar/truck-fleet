from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
from ...database import get_db
from ...models.booking import Booking, BookingStatus
from ...models.gate_activity import GateActivity, Trip
from ...models.truck import Truck
from ...models.driver import Driver
from ...models.user import User, UserType
from ...models.transaction import Payment
from ...schemas.response import ResponseModel
from ...core.deps import get_current_user

router = APIRouter()

@router.get("/stats", response_model=ResponseModel)
async def get_dashboard_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get dashboard statistics based on user type"""
    today = datetime.utcnow().date()
    today_start = datetime.combine(today, datetime.min.time())
    today_end = datetime.combine(today, datetime.max.time())
    
    if current_user.user_type == UserType.CFS_ADMIN.value:
        return await get_cfs_admin_stats(db, current_user, today_start, today_end)
    elif current_user.user_type == UserType.SECURITY_OFFICER.value:
        return await get_security_stats(db, current_user, today_start, today_end)
    elif current_user.user_type == UserType.AGGREGATOR.value:
        return await get_aggregator_stats(db, current_user, today_start, today_end)
    elif current_user.user_type == UserType.OWNER.value:
        return await get_owner_stats(db, current_user, today_start, today_end)
    elif current_user.user_type == UserType.DRIVER.value:
        return await get_driver_stats(db, current_user, today_start, today_end)
    
    return ResponseModel(success=True, data={})

async def get_cfs_admin_stats(db: Session, user: User, today_start, today_end):
    # Active bookings
    active_bookings = db.query(Booking).filter(
        Booking.cfs_id == user.id,
        Booking.status.in_([BookingStatus.PENDING.value, BookingStatus.CONFIRMED.value, BookingStatus.IN_PROGRESS.value])
    ).count()
    
    # Pending approvals
    pending_approvals = db.query(Booking).filter(
        Booking.cfs_id == user.id,
        Booking.status == BookingStatus.PENDING.value
    ).count()
    
    # Today's deliveries
    todays_deliveries = db.query(Booking).filter(
        Booking.cfs_id == user.id,
        Booking.status == BookingStatus.COMPLETED.value,
        Booking.actual_delivery_time >= today_start,
        Booking.actual_delivery_time <= today_end
    ).count()
    
    # Today's revenue
    todays_revenue = db.query(func.sum(Booking.agreed_rate)).filter(
        Booking.cfs_id == user.id,
        Booking.status == BookingStatus.COMPLETED.value,
        Booking.actual_delivery_time >= today_start,
        Booking.actual_delivery_time <= today_end
    ).scalar() or 0
    
    # Gate activities
    gate_in_today = db.query(GateActivity).filter(
        GateActivity.activity_type == "gate_in",
        GateActivity.gate_time >= today_start,
        GateActivity.gate_time <= today_end
    ).count()
    
    gate_out_today = db.query(GateActivity).filter(
        GateActivity.activity_type == "gate_out",
        GateActivity.gate_time >= today_start,
        GateActivity.gate_time <= today_end
    ).count()
    
    currently_inside = gate_in_today - gate_out_today
    
    # Recent bookings
    recent_bookings = db.query(Booking).filter(
        Booking.cfs_id == user.id
    ).order_by(Booking.created_at.desc()).limit(5).all()
    
    from ...schemas.booking import BookingResponse
    
    return ResponseModel(
        success=True,
        data={
            "active_bookings": active_bookings,
            "pending_approvals": pending_approvals,
            "todays_deliveries": todays_deliveries,
            "todays_revenue": todays_revenue,
            "gate_activities": {
                "gate_in_today": gate_in_today,
                "gate_out_today": gate_out_today,
                "currently_inside": max(0, currently_inside)
            },
            "recent_bookings": [BookingResponse.model_validate(b) for b in recent_bookings]
        }
    )

async def get_security_stats(db: Session, user: User, today_start, today_end):
    gate_in_today = db.query(GateActivity).filter(
        GateActivity.activity_type == "gate_in",
        GateActivity.gate_time >= today_start,
        GateActivity.gate_time <= today_end
    ).count()
    
    gate_out_today = db.query(GateActivity).filter(
        GateActivity.activity_type == "gate_out",
        GateActivity.gate_time >= today_start,
        GateActivity.gate_time <= today_end
    ).count()
    
    currently_inside = max(0, gate_in_today - gate_out_today)
    
    # Pending gate-ins (bookings confirmed but not yet entered)
    pending_gate_ins = db.query(Booking).filter(
        Booking.status == BookingStatus.CONFIRMED.value,
        Booking.actual_gate_in_time == None
    ).count()
    
    # Recent activities
    recent_activities = db.query(GateActivity).order_by(
        GateActivity.gate_time.desc()
    ).limit(10).all()
    
    activities_data = []
    for activity in recent_activities:
        driver = db.query(Driver).filter(Driver.id == activity.driver_id).first()
        truck = db.query(Truck).filter(Truck.id == activity.truck_id).first() if activity.truck_id else None
        activities_data.append({
            "id": activity.id,
            "type": activity.activity_type,
            "time": activity.gate_time.isoformat(),
            "driver_name": driver.name if driver else "Unknown",
            "truck_number": truck.truck_number if truck else "Unknown",
            "bay": activity.bay_number
        })
    
    return ResponseModel(
        success=True,
        data={
            "gate_in_today": gate_in_today,
            "gate_out_today": gate_out_today,
            "currently_inside": currently_inside,
            "pending_gate_ins": pending_gate_ins,
            "recent_activities": activities_data
        }
    )

async def get_aggregator_stats(db: Session, user: User, today_start, today_end):
    # Active trips
    active_trips = db.query(Booking).filter(
        Booking.aggregator_id == user.id,
        Booking.status == BookingStatus.IN_PROGRESS.value
    ).count()
    
    # Available trucks
    available_trucks = db.query(Truck).filter(
        Truck.owner_id == user.id,
        Truck.is_available == True,
        Truck.is_active == True
    ).count()
    
    total_trucks = db.query(Truck).filter(
        Truck.owner_id == user.id,
        Truck.is_active == True
    ).count()
    
    # Today's earnings
    todays_earnings = db.query(func.sum(Booking.agreed_rate)).filter(
        Booking.aggregator_id == user.id,
        Booking.status == BookingStatus.COMPLETED.value,
        Booking.actual_delivery_time >= today_start,
        Booking.actual_delivery_time <= today_end
    ).scalar() or 0
    
    # Pending payments
    pending_payments = db.query(func.sum(Payment.amount)).filter(
        Payment.payee_id == user.id,
        Payment.payment_status == "pending"
    ).scalar() or 0
    
    # Driver stats
    total_drivers = db.query(Driver).filter(Driver.owner_id == user.id).count()
    drivers_on_trip = db.query(Driver).filter(
        Driver.owner_id == user.id,
        Driver.current_status == "on_trip"
    ).count()
    
    # New opportunities
    new_opportunities = db.query(Booking).filter(
        Booking.status == BookingStatus.PENDING.value
    ).count()
    
    return ResponseModel(
        success=True,
        data={
            "active_trips": active_trips,
            "available_trucks": available_trucks,
            "todays_earnings": todays_earnings,
            "pending_payments": pending_payments,
            "fleet_stats": {
                "total_trucks": total_trucks,
                "active_now": total_trucks - available_trucks,
                "available": available_trucks
            },
            "driver_stats": {
                "total_drivers": total_drivers,
                "on_trip": drivers_on_trip,
                "available": total_drivers - drivers_on_trip
            },
            "new_opportunities": new_opportunities
        }
    )

async def get_owner_stats(db: Session, user: User, today_start, today_end):
    # Similar to aggregator but simpler
    my_trucks = db.query(Truck).filter(
        Truck.owner_id == user.id,
        Truck.is_active == True
    ).count()
    
    active_trips = db.query(Booking).filter(
        Booking.aggregator_id == user.id,
        Booking.status == BookingStatus.IN_PROGRESS.value
    ).count()
    
    this_month_start = today_start.replace(day=1)
    monthly_earnings = db.query(func.sum(Booking.agreed_rate)).filter(
        Booking.aggregator_id == user.id,
        Booking.status == BookingStatus.COMPLETED.value,
        Booking.actual_delivery_time >= this_month_start
    ).scalar() or 0
    
    pending_payments = db.query(func.sum(Payment.amount)).filter(
        Payment.payee_id == user.id,
        Payment.payment_status == "pending"
    ).scalar() or 0
    
    return ResponseModel(
        success=True,
        data={
            "my_trucks": my_trucks,
            "active_trips": active_trips,
            "monthly_earnings": monthly_earnings,
            "pending_payments": pending_payments
        }
    )

async def get_driver_stats(db: Session, user: User, today_start, today_end):
    # Get driver profile
    driver = db.query(Driver).filter(Driver.user_id == user.id).first()
    
    if not driver:
        return ResponseModel(success=True, data={})
    
    # Today's trips
    trips_today = db.query(Booking).filter(
        Booking.driver_id == driver.id,
        Booking.status == BookingStatus.COMPLETED.value,
        Booking.actual_delivery_time >= today_start,
        Booking.actual_delivery_time <= today_end
    ).count()
    
    # Today's earnings
    earnings_today = db.query(func.sum(Booking.agreed_rate)).filter(
        Booking.driver_id == driver.id,
        Booking.status == BookingStatus.COMPLETED.value,
        Booking.actual_delivery_time >= today_start,
        Booking.actual_delivery_time <= today_end
    ).scalar() or 0
    
    # Current trip
    current_trip = db.query(Booking).filter(
        Booking.driver_id == driver.id,
        Booking.status == BookingStatus.IN_PROGRESS.value
    ).first()
    
    # Weekly earnings
    week_start = today_start - timedelta(days=today_start.weekday())
    weekly_earnings = db.query(func.sum(Booking.agreed_rate)).filter(
        Booking.driver_id == driver.id,
        Booking.status == BookingStatus.COMPLETED.value,
        Booking.actual_delivery_time >= week_start
    ).scalar() or 0
    
    # Monthly earnings
    month_start = today_start.replace(day=1)
    monthly_earnings = db.query(func.sum(Booking.agreed_rate)).filter(
        Booking.driver_id == driver.id,
        Booking.status == BookingStatus.COMPLETED.value,
        Booking.actual_delivery_time >= month_start
    ).scalar() or 0
    
    from ...schemas.booking import BookingResponse
    
    return ResponseModel(
        success=True,
        data={
            "trips_today": trips_today,
            "earnings_today": earnings_today,
            "current_trip": BookingResponse.model_validate(current_trip) if current_trip else None,
            "weekly_earnings": weekly_earnings,
            "monthly_earnings": monthly_earnings,
            "rating": driver.rating,
            "total_trips": driver.total_trips,
            "is_available": driver.is_available,
            "current_status": driver.current_status
        }
    )

@router.get("/trips", response_model=ResponseModel)
async def get_my_trips(
    status: str = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get trips for current user"""
    query = db.query(Booking)
    
    if current_user.user_type == UserType.CFS_ADMIN.value:
        query = query.filter(Booking.cfs_id == current_user.id)
    elif current_user.user_type in [UserType.AGGREGATOR.value, UserType.OWNER.value]:
        query = query.filter(Booking.aggregator_id == current_user.id)
    elif current_user.user_type == UserType.DRIVER.value:
        driver = db.query(Driver).filter(Driver.user_id == current_user.id).first()
        if driver:
            query = query.filter(Booking.driver_id == driver.id)
    
    if status:
        query = query.filter(Booking.status == status)
    
    total = query.count()
    query = query.order_by(Booking.created_at.desc())
    offset = (page - 1) * page_size
    trips = query.offset(offset).limit(page_size).all()
    
    from ...schemas.booking import BookingResponse
    
    return ResponseModel(
        success=True,
        data={
            "trips": [BookingResponse.model_validate(t) for t in trips],
            "total": total,
            "page": page
        }
    )
