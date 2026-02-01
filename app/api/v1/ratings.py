from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel, Field
from ...database import get_db
from ...models.transaction import RatingReview
from ...models.user import User
from ...models.gate_activity import Trip
from ...schemas.response import ResponseModel
from ...core.deps import get_current_user
from ...utils.pagination import paginate_query, create_paginated_response

router = APIRouter()

class RatingCreate(BaseModel):
    trip_id: str
    rated_to: str
    rating: int = Field(..., ge=1, le=5)
    review: Optional[str] = None
    punctuality_rating: Optional[int] = Field(None, ge=1, le=5)
    professionalism_rating: Optional[int] = Field(None, ge=1, le=5)
    vehicle_condition_rating: Optional[int] = Field(None, ge=1, le=5)

@router.post("/", response_model=ResponseModel)
async def create_rating(
    rating_data: RatingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a rating and review"""
    # Verify trip exists
    trip = db.query(Trip).filter(Trip.id == rating_data.trip_id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    
    # Check if user already rated this trip
    existing_rating = db.query(RatingReview).filter(
        RatingReview.trip_id == rating_data.trip_id,
        RatingReview.rated_by == current_user.id
    ).first()
    
    if existing_rating:
        raise HTTPException(status_code=400, detail="You have already rated this trip")
    
    # Create rating
    rating = RatingReview(
        trip_id=rating_data.trip_id,
        rated_by=current_user.id,
        rated_to=rating_data.rated_to,
        rating=rating_data.rating,
        review=rating_data.review,
        punctuality_rating=rating_data.punctuality_rating,
        professionalism_rating=rating_data.professionalism_rating,
        vehicle_condition_rating=rating_data.vehicle_condition_rating
    )
    
    db.add(rating)
    db.commit()
    db.refresh(rating)
    
    # Update user rating (average)
    rated_user = db.query(User).filter(User.id == rating_data.rated_to).first()
    if rated_user:
        all_ratings = db.query(RatingReview).filter(RatingReview.rated_to == rating_data.rated_to).all()
        if all_ratings:
            avg_rating = sum(r.rating for r in all_ratings) / len(all_ratings)
            rated_user.rating = round(avg_rating, 2)
            db.commit()
    
    return ResponseModel(
        success=True,
        message="Rating submitted successfully",
        data={"rating_id": rating.id}
    )

@router.get("/", response_model=ResponseModel)
async def get_ratings(
    user_id: Optional[str] = None,
    trip_id: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db)
):
    """Get ratings with filters"""
    query = db.query(RatingReview)
    
    if user_id:
        query = query.filter(RatingReview.rated_to == user_id)
    if trip_id:
        query = query.filter(RatingReview.trip_id == trip_id)
    
    paginated_query, pagination_info = paginate_query(query, page, page_size)
    ratings = paginated_query.all()
    
    return ResponseModel(
        success=True,
        data=create_paginated_response(
            [{"id": r.id, "trip_id": r.trip_id, "rated_by": r.rated_by,
              "rated_to": r.rated_to, "rating": r.rating, "review": r.review,
              "created_at": r.created_at.isoformat()} for r in ratings],
            pagination_info["total"],
            pagination_info["page"],
            pagination_info["page_size"]
        ).model_dump()
    )

@router.get("/{rating_id}", response_model=ResponseModel)
async def get_rating(
    rating_id: str,
    db: Session = Depends(get_db)
):
    """Get a specific rating"""
    rating = db.query(RatingReview).filter(RatingReview.id == rating_id).first()
    if not rating:
        raise HTTPException(status_code=404, detail="Rating not found")
    
    return ResponseModel(
        success=True,
        data={
            "id": rating.id,
            "trip_id": rating.trip_id,
            "rated_by": rating.rated_by,
            "rated_to": rating.rated_to,
            "rating": rating.rating,
            "review": rating.review,
            "punctuality_rating": rating.punctuality_rating,
            "professionalism_rating": rating.professionalism_rating,
            "vehicle_condition_rating": rating.vehicle_condition_rating,
            "created_at": rating.created_at.isoformat()
        }
    )
