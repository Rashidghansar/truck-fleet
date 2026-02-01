from typing import Generic, TypeVar, Optional, List
from pydantic import BaseModel
from sqlalchemy.orm import Query
from math import ceil

T = TypeVar('T')

class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T]
    total: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_prev: bool

def paginate_query(
    query: Query,
    page: int = 1,
    page_size: int = 20,
    max_page_size: int = 100
) -> tuple[Query, dict]:
    """
    Paginate a SQLAlchemy query
    
    Returns:
        tuple: (paginated_query, pagination_info)
    """
    # Validate and clamp page_size
    if page_size > max_page_size:
        page_size = max_page_size
    if page_size < 1:
        page_size = 20
    if page < 1:
        page = 1
    
    # Get total count
    total = query.count()
    
    # Calculate pagination
    total_pages = ceil(total / page_size) if total > 0 else 0
    offset = (page - 1) * page_size
    
    # Apply pagination
    paginated_query = query.offset(offset).limit(page_size)
    
    pagination_info = {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_prev": page > 1
    }
    
    return paginated_query, pagination_info

def create_paginated_response(
    items: List[T],
    total: int,
    page: int,
    page_size: int
) -> PaginatedResponse[T]:
    """Create a paginated response"""
    total_pages = ceil(total / page_size) if total > 0 else 0
    
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_prev=page > 1
    )
