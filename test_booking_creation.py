"""
Test script to verify booking creation works
"""
import requests
import json

# Test booking creation
base_url = "http://localhost:8000"
login_url = f"{base_url}/api/v1/auth/login"
booking_url = f"{base_url}/api/v1/bookings/create"

# First, login as admin to get token
print("Testing booking creation...")
print("=" * 50)

login_data = {
    "phone": "9876543210",
    "password": "admin123",
    "user_type": "cfs_admin"
}

try:
    # Login
    print("1. Logging in as CFS Admin...")
    login_response = requests.post(login_url, json=login_data)
    if login_response.status_code != 200:
        print(f"   Login failed: {login_response.status_code}")
        print(f"   Response: {login_response.text}")
        exit(1)
    
    token_data = login_response.json()
    access_token = token_data.get("access_token")
    if not access_token:
        print("   Login failed: No access token received")
        print(f"   Response: {token_data}")
        exit(1)
    
    print("   [OK] Login successful")
    
    # Create booking
    print("\n2. Creating test booking...")
    booking_data = {
        "consignment_type": "Export Container",
        "truck_type": "20ft Container Truck",
        "truck_capacity": "20 Ton",
        "quantity": 1,
        "weight": 15.5,
        "pickup_location": "CFS Mumbai",
        "destination_address": "Delhi Port",
        "published_rate": 25000.0,
        "base_price": 25000.0,
        "payment_terms": "immediate",
        "is_negotiable": True
    }
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    booking_response = requests.post(booking_url, json=booking_data, headers=headers)
    
    if booking_response.status_code == 200:
        result = booking_response.json()
        if result.get("success"):
            print("   [SUCCESS] Booking created successfully!")
            print(f"   Demand Number: {result['data'].get('demand_number')}")
            print(f"   Booking ID: {result['data'].get('id')}")
        else:
            print(f"   [FAILED] Booking creation failed: {result.get('message')}")
    else:
        print(f"   [FAILED] HTTP {booking_response.status_code}")
        print(f"   Response: {booking_response.text}")
        
except requests.exceptions.ConnectionError:
    print("\n[ERROR] Cannot connect to backend server.")
    print("Make sure the backend is running on http://localhost:8000")
except Exception as e:
    print(f"\n[ERROR] {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 50)

