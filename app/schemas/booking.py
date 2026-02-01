from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class BookingCreate(BaseModel):
    consignment_type: Optional[str] = None  # Will be validated in endpoint
    container_number: Optional[str] = None
    weight: Optional[float] = None
    special_instructions: Optional[str] = None
    
    truck_type: Optional[str] = None  # Will be validated in endpoint
    truck_capacity: Optional[str] = None
    quantity: int = 1
    
    gate_in_time: Optional[datetime] = None
    gate_out_time: Optional[datetime] = None
    bay_number: Optional[str] = None
    bay_contact_name: Optional[str] = None
    bay_contact_phone: Optional[str] = None
    
    pickup_location: Optional[str] = None
    pickup_lat: Optional[float] = None
    pickup_lng: Optional[float] = None
    
    destination_address: Optional[str] = None
    destination_lat: Optional[float] = None
    destination_lng: Optional[float] = None
    destination_gate_in_time: Optional[datetime] = None
    destination_contact_name: Optional[str] = None
    destination_contact_phone: Optional[str] = None
    
    # Legacy support
    container_type: Optional[str] = None
    container_size: Optional[str] = None
    delivery_location: Optional[str] = None
    delivery_lat: Optional[float] = None
    delivery_lng: Optional[float] = None
    pickup_date: Optional[datetime] = None
    pickup_time_slot: Optional[str] = None
    
    base_price: Optional[float] = None
    published_rate: Optional[float] = None
    payment_terms: str = "immediate"
    is_negotiable: bool = False
    notes: Optional[str] = None

class BookingResponse(BaseModel):
    id: str
    demand_number: str
    cfs_id: str
    aggregator_id: Optional[str] = None
    driver_id: Optional[str] = None
    truck_id: Optional[str] = None
    
    consignment_type: Optional[str] = None
    container_number: Optional[str] = None
    weight: Optional[float] = None
    special_instructions: Optional[str] = None
    
    truck_type: Optional[str] = None
    truck_capacity: Optional[str] = None
    quantity: int = 1
    
    gate_in_time: Optional[datetime] = None
    gate_out_time: Optional[datetime] = None
    bay_number: Optional[str] = None
    
    pickup_location: str
    pickup_lat: Optional[float] = None
    pickup_lng: Optional[float] = None
    
    destination_address: Optional[str] = None
    destination_lat: Optional[float] = None
    destination_lng: Optional[float] = None
    
    # Legacy
    container_type: Optional[str] = None
    container_size: Optional[str] = None
    delivery_location: Optional[str] = None
    pickup_date: Optional[datetime] = None
    
    base_price: Optional[float] = None
    published_rate: Optional[float] = None
    agreed_rate: Optional[float] = None
    payment_terms: Optional[str] = None
    is_negotiable: bool = False
    
    status: str
    notes: Optional[str] = None
    distance_km: Optional[float] = None
    
    # CFS Location Info
    cfs_location_id: Optional[str] = None
    cfs_location_name: Optional[str] = None
    
    # Gate codes
    gate_qr_code: Optional[str] = None
    gate_numeric_code: Optional[str] = None
    
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class BookingUpdate(BaseModel):
    consignment_type: Optional[str] = None
    container_number: Optional[str] = None
    weight: Optional[float] = None
    special_instructions: Optional[str] = None
    truck_type: Optional[str] = None
    truck_capacity: Optional[str] = None
    quantity: Optional[int] = None
    gate_in_time: Optional[datetime] = None
    gate_out_time: Optional[datetime] = None
    bay_number: Optional[str] = None
    destination_address: Optional[str] = None
    agreed_rate: Optional[float] = None
    status: Optional[str] = None
    notes: Optional[str] = None
    aggregator_id: Optional[str] = None
    driver_id: Optional[str] = None
    truck_id: Optional[str] = None

class NegotiationCreate(BaseModel):
    booking_id: Optional[str] = None  # Optional since it comes from URL path
    offered_rate: float
    justification: Optional[str] = None
    payment_terms: Optional[str] = None
    truck_id: Optional[str] = None
    driver_id: Optional[str] = None

class NegotiationResponse(BaseModel):
    id: str
    booking_id: str
    offered_by: str
    offered_rate: float
    justification: Optional[str] = None
    payment_terms: Optional[str] = None
    status: str
    created_at: datetime
    
    class Config:
        from_attributes = True
