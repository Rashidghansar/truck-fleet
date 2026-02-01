from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from typing import Dict, List, Optional
import json
from datetime import datetime
from sqlalchemy.orm import Session
from ...database import get_db
from ...core.security import decode_token

router = APIRouter()

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.user_connections: Dict[str, List[str]] = {}  # user_id -> [connection_ids]
    
    async def connect(self, websocket: WebSocket, user_id: str, connection_id: str):
        await websocket.accept()
        self.active_connections[connection_id] = websocket
        if user_id not in self.user_connections:
            self.user_connections[user_id] = []
        self.user_connections[user_id].append(connection_id)
    
    def disconnect(self, connection_id: str, user_id: str):
        if connection_id in self.active_connections:
            del self.active_connections[connection_id]
        if user_id in self.user_connections:
            if connection_id in self.user_connections[user_id]:
                self.user_connections[user_id].remove(connection_id)
            if not self.user_connections[user_id]:
                del self.user_connections[user_id]
    
    async def send_personal_message(self, message: dict, user_id: str):
        if user_id in self.user_connections:
            for conn_id in self.user_connections[user_id]:
                if conn_id in self.active_connections:
                    try:
                        await self.active_connections[conn_id].send_text(json.dumps(message))
                    except:
                        pass
    
    async def broadcast(self, message: dict, user_ids: List[str] = None):
        if user_ids:
            for user_id in user_ids:
                await self.send_personal_message(message, user_id)
        else:
            for connection in self.active_connections.values():
                try:
                    await connection.send_text(json.dumps(message))
                except:
                    pass

manager = ConnectionManager()

def get_manager() -> ConnectionManager:
    return manager

@router.websocket("/{user_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    user_id: str,
    token: Optional[str] = Query(None)
):
    # Verify token
    if token:
        payload = decode_token(token)
        if not payload or payload.get("sub") != user_id:
            await websocket.close(code=4001, reason="Invalid token")
            return
    
    import uuid
    connection_id = str(uuid.uuid4())
    
    await manager.connect(websocket, user_id, connection_id)
    
    try:
        # Send connection confirmation
        await websocket.send_text(json.dumps({
            "type": "connected",
            "message": "WebSocket connected successfully",
            "connection_id": connection_id,
            "timestamp": datetime.utcnow().isoformat()
        }))
        
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            # Handle different message types
            msg_type = message.get("type")
            
            if msg_type == "ping":
                await websocket.send_text(json.dumps({
                    "type": "pong",
                    "timestamp": datetime.utcnow().isoformat()
                }))
            
            elif msg_type == "location_update":
                # Handle location updates from drivers
                await handle_location_update(message, user_id)
            
            elif msg_type == "subscribe":
                # Subscribe to specific channels
                channel = message.get("channel")
                # Store subscription
                pass
            
    except WebSocketDisconnect:
        manager.disconnect(connection_id, user_id)
    except Exception as e:
        manager.disconnect(connection_id, user_id)

async def handle_location_update(message: dict, user_id: str):
    """Handle location updates from drivers"""
    location = message.get("location", {})
    trip_id = message.get("trip_id")
    
    if trip_id:
        # Broadcast to interested parties (CFS admin, aggregator)
        await manager.broadcast({
            "type": "location_update",
            "trip_id": trip_id,
            "driver_id": user_id,
            "location": location,
            "timestamp": datetime.utcnow().isoformat()
        })

# Helper functions for sending notifications
async def send_notification(user_ids: List[str], notification_type: str, data: dict):
    """Send notification to specific users"""
    message = {
        "type": notification_type,
        "data": data,
        "timestamp": datetime.utcnow().isoformat()
    }
    await manager.broadcast(message, user_ids)

async def notify_new_opportunity(booking_data: dict, user_ids: List[str]):
    """Notify users about new booking opportunity"""
    await send_notification(user_ids, "new_opportunity", {
        "booking_id": booking_data.get("id"),
        "demand_number": booking_data.get("demand_number"),
        "truck_type": booking_data.get("truck_type"),
        "rate": booking_data.get("published_rate"),
        "pickup_time": booking_data.get("gate_in_time")
    })

async def notify_booking_accepted(booking_id: str, user_ids: List[str]):
    """Notify that a booking was accepted"""
    await send_notification(user_ids, "booking_accepted", {
        "booking_id": booking_id,
        "message": "Your booking has been accepted"
    })

async def notify_negotiation_update(booking_id: str, offer_data: dict, user_ids: List[str]):
    """Notify about negotiation updates"""
    await send_notification(user_ids, "negotiation_update", {
        "booking_id": booking_id,
        **offer_data
    })

async def notify_trip_started(trip_data: dict, user_ids: List[str]):
    """Notify that a trip has started"""
    await send_notification(user_ids, "trip_started", trip_data)

async def notify_trip_completed(trip_data: dict, user_ids: List[str]):
    """Notify that a trip has been completed"""
    await send_notification(user_ids, "trip_completed", trip_data)
