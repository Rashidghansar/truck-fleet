#!/usr/bin/env python3
"""Comprehensive API test script for CFS Transport System"""
import requests
import json
import time
from datetime import datetime, timedelta

BASE_URL = "http://localhost:8000"
API_BASE = f"{BASE_URL}/api/v1"

# Test data storage
test_data = {
    "tokens": {},
    "users": {},
    "bookings": [],
    "trucks": [],
    "drivers": [],
    "opportunities": []
}

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'

def log(message, color=Colors.BLUE):
    print(f"{color}{message}{Colors.END}")

def log_success(message):
    log(f"[+] {message}", Colors.GREEN)

def log_error(message):
    log(f"[-] {message}", Colors.RED)

def log_info(message):
    log(f"[i] {message}", Colors.YELLOW)

def test_health_check():
    """Test health check endpoint"""
    log_info("Testing health check...")
    try:
        response = requests.get(f"{BASE_URL}/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        log_success("Health check passed")
        return True
    except Exception as e:
        log_error(f"Health check failed: {e}")
        return False

def test_register_cfs_admin():
    """Test CFS Admin registration"""
    log_info("Testing CFS Admin registration...")
    try:
        timestamp = str(int(time.time()))
        data = {
            "name": "Test CFS Admin",
            "phone": f"987654{timestamp[-4:]}",
            "email": f"admin{timestamp[-4:]}@testcfs.com",
            "password": "password123",
            "user_type": "cfs_admin",
            "cfs_name": "Test CFS Container Facility",
            "cfs_address": "123 Port Road, Mumbai",
            "cfs_license": "CFS/MUM/2024/001"
        }
        response = requests.post(f"{API_BASE}/auth/register", json=data)
        if response.status_code != 200:
            log_error(f"Registration failed: {response.status_code} - {response.text}")
            return False
        result = response.json()
        assert result["success"] == True
        test_data["users"]["cfs_admin"] = data
        log_success("CFS Admin registered successfully")
        return True
    except Exception as e:
        log_error(f"CFS Admin registration failed: {e}")
        return False

def test_register_aggregator():
    """Test Aggregator registration"""
    log_info("Testing Aggregator registration...")
    try:
        timestamp = str(int(time.time()))
        data = {
            "name": "Test Aggregator",
            "phone": f"987655{timestamp[-4:]}",
            "email": f"aggregator{timestamp[-4:]}@test.com",
            "password": "password123",
            "user_type": "aggregator",
            "address": "456 Transport Nagar, Mumbai"
        }
        response = requests.post(f"{API_BASE}/auth/register", json=data)
        if response.status_code != 200:
            log_error(f"Registration failed: {response.status_code} - {response.text}")
            return False
        result = response.json()
        assert result["success"] == True
        test_data["users"]["aggregator"] = data
        log_success("Aggregator registered successfully")
        return True
    except Exception as e:
        log_error(f"Aggregator registration failed: {e}")
        return False

def test_register_driver():
    """Test Driver registration"""
    log_info("Testing Driver registration...")
    try:
        timestamp = str(int(time.time()))
        data = {
            "name": "Test Driver",
            "phone": f"987656{timestamp[-4:]}",
            "email": f"driver{timestamp[-4:]}@test.com",
            "password": "password123",
            "user_type": "driver",
            "address": "789 Driver Colony, Mumbai",
            "emergency_contact_name": "Emergency Contact",
            "emergency_contact_phone": "9876543213"
        }
        response = requests.post(f"{API_BASE}/auth/register", json=data)
        if response.status_code != 200:
            log_error(f"Registration failed: {response.status_code} - {response.text}")
            return False
        result = response.json()
        assert result["success"] == True
        test_data["users"]["driver"] = data
        log_success("Driver registered successfully")
        return True
    except Exception as e:
        log_error(f"Driver registration failed: {e}")
        return False

def test_login(user_type):
    """Test login for a user type"""
    log_info(f"Testing {user_type} login...")
    try:
        user = test_data["users"][user_type]
        data = {
            "phone": user["phone"],
            "password": user["password"],
            "user_type": user["user_type"]
        }
        response = requests.post(f"{API_BASE}/auth/login", json=data)
        assert response.status_code == 200
        result = response.json()
        assert "access_token" in result
        test_data["tokens"][user_type] = result["access_token"]
        test_data["users"][f"{user_type}_id"] = result["user"]["id"]
        log_success(f"{user_type} login successful")
        return True
    except Exception as e:
        log_error(f"{user_type} login failed: {e}")
        return False

def get_headers(user_type):
    """Get authorization headers for a user type"""
    return {
        "Authorization": f"Bearer {test_data['tokens'][user_type]}",
        "Content-Type": "application/json"
    }

def test_create_booking():
    """Test creating a booking as CFS Admin"""
    log_info("Testing booking creation...")
    try:
        gate_in = datetime.now() + timedelta(hours=2)
        gate_out = gate_in + timedelta(hours=4)
        
        data = {
            "consignment_type": "Container",
            "container_number": "ABCD1234567",
            "container_type": "20ft",
            "container_size": "20",
            "weight": 15000.0,
            "truck_type": "20ft Flatbed",
            "truck_capacity": "20",
            "quantity": 1,
            "gate_in_time": gate_in.isoformat(),
            "gate_out_time": gate_out.isoformat(),
            "bay_number": "Bay-A1",
            "bay_contact_name": "Supervisor",
            "bay_contact_phone": "9876543214",
            "pickup_location": "Test CFS, Mumbai Port",
            "pickup_lat": 18.9220,
            "pickup_lng": 72.8347,
            "delivery_location": "Warehouse XYZ, Pune",
            "delivery_lat": 18.5204,
            "delivery_lng": 73.8567,
            "destination_address": "Warehouse XYZ, Pune",
            "destination_lat": 18.5204,
            "destination_lng": 73.8567,
            "base_price": 12000.0,
            "published_rate": 12000.0,
            "payment_terms": "30 days",
            "is_negotiable": True,
            "notes": "Test booking for container transport",
            "special_instructions": "Handle with care"
        }
        
        response = requests.post(
            f"{API_BASE}/bookings/create",
            json=data,
            headers=get_headers("cfs_admin")
        )
        if response.status_code != 200:
            log_error(f"Booking creation failed: {response.status_code} - {response.text}")
            return False
        result = response.json()
        assert result["success"] == True
        test_data["bookings"].append(result["data"])
        log_success(f"Booking created: {result['data']['demand_number']}")
        return True
    except Exception as e:
        log_error(f"Booking creation failed: {e}")
        return False

def test_get_opportunities():
    """Test getting opportunities as aggregator"""
    log_info("Testing get opportunities...")
    try:
        response = requests.get(
            f"{API_BASE}/opportunities",
            headers=get_headers("aggregator")
        )
        assert response.status_code == 200
        result = response.json()
        assert result["success"] == True
        test_data["opportunities"] = result["data"]["opportunities"]
        log_success(f"Found {len(test_data['opportunities'])} opportunities")
        return True
    except Exception as e:
        log_error(f"Get opportunities failed: {e}")
        return False

def test_add_truck():
    """Test adding a truck as aggregator"""
    log_info("Testing add truck...")
    try:
        timestamp = str(int(time.time()))
        data = {
            "truck_number": f"MH01AB{timestamp[-4:]}",
            "truck_type": "20ft Flatbed",
            "capacity": "20",
            "truck_make": "Tata",
            "model_year": 2022,
            "insurance_expiry": (datetime.now() + timedelta(days=180)).strftime("%Y-%m-%d"),
            "fitness_expiry": (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%d"),
            "permit_expiry": (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%d")
        }
        
        response = requests.post(
            f"{API_BASE}/trucks/add",
            json=data,
            headers=get_headers("aggregator")
        )
        if response.status_code != 200:
            log_error(f"Add truck failed: {response.status_code} - {response.text}")
            return False
        result = response.json()
        assert result["success"] == True
        test_data["trucks"].append(result["data"])
        log_success(f"Truck added: {data['truck_number']}")
        return True
    except Exception as e:
        log_error(f"Add truck failed: {e}")
        return False

def test_add_driver():
    """Test adding a driver as aggregator"""
    log_info("Testing add driver...")
    try:
        timestamp = str(int(time.time()))
        data = {
            "name": "Test Driver 2",
            "phone": f"987657{timestamp[-4:]}",
            "email": f"driver2{timestamp[-4:]}@test.com",
            "license_number": f"MH{timestamp[-10:]}",
            "license_type": "HMV",
            "license_expiry": (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%d"),
            "address": "Test Address",
            "emergency_contact_name": "Emergency",
            "emergency_contact_phone": "9876543216"
        }
        
        response = requests.post(
            f"{API_BASE}/drivers/add",
            json=data,
            headers=get_headers("aggregator")
        )
        if response.status_code != 200:
            log_error(f"Add driver failed: {response.status_code} - {response.text}")
            return False
        result = response.json()
        assert result["success"] == True
        test_data["drivers"].append(result["data"])
        log_success(f"Driver added: {data['name']}")
        return True
    except Exception as e:
        log_error(f"Add driver failed: {e}")
        return False

def test_accept_opportunity():
    """Test accepting an opportunity"""
    log_info("Testing accept opportunity...")
    try:
        if not test_data["opportunities"]:
            log_error("No opportunities available to accept")
            return False
        
        if not test_data["trucks"]:
            log_error("No trucks available")
            return False
        
        opportunity_id = test_data["opportunities"][0]["id"]
        truck_id = test_data["trucks"][0]["id"]
        
        response = requests.post(
            f"{API_BASE}/opportunities/{opportunity_id}/accept",
            params={"truck_id": truck_id, "auto_assign_driver": True},
            headers=get_headers("aggregator")
        )
        assert response.status_code == 200
        result = response.json()
        assert result["success"] == True
        log_success(f"Opportunity accepted: {result['data']['demand_number']}")
        return True
    except Exception as e:
        log_error(f"Accept opportunity failed: {e}")
        return False

def test_dashboard_stats():
    """Test dashboard stats for CFS admin"""
    log_info("Testing dashboard stats...")
    try:
        response = requests.get(
            f"{API_BASE}/dashboard/stats",
            headers=get_headers("cfs_admin")
        )
        assert response.status_code == 200
        result = response.json()
        assert result["success"] == True
        log_success(f"Dashboard stats retrieved: {result['data']}")
        return True
    except Exception as e:
        log_error(f"Dashboard stats failed: {e}")
        return False

def test_get_bookings():
    """Test getting bookings"""
    log_info("Testing get bookings for CFS admin...")
    try:
        response = requests.get(
            f"{API_BASE}/bookings",
            headers=get_headers("cfs_admin")
        )
        assert response.status_code == 200
        result = response.json()
        assert result["success"] == True
        log_success(f"Retrieved {result['data']['total']} bookings")
        return True
    except Exception as e:
        log_error(f"Get bookings failed: {e}")
        return False

def run_all_tests():
    """Run all tests in sequence"""
    log("\n" + "="*60, Colors.BLUE)
    log("CFS TRANSPORT SYSTEM - COMPREHENSIVE API TESTS", Colors.BLUE)
    log("="*60 + "\n", Colors.BLUE)
    
    tests = [
        ("Health Check", test_health_check),
        ("Register CFS Admin", test_register_cfs_admin),
        ("Register Aggregator", test_register_aggregator),
        ("Register Driver", test_register_driver),
        ("Login CFS Admin", lambda: test_login("cfs_admin")),
        ("Login Aggregator", lambda: test_login("aggregator")),
        ("Login Driver", lambda: test_login("driver")),
        ("Create Booking", test_create_booking),
        ("Add Truck", test_add_truck),
        ("Add Driver", test_add_driver),
        ("Get Opportunities", test_get_opportunities),
        ("Accept Opportunity", test_accept_opportunity),
        ("Get Bookings", test_get_bookings),
        ("Dashboard Stats", test_dashboard_stats),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            log_error(f"{test_name} crashed: {e}")
            failed += 1
        time.sleep(0.5)  # Small delay between tests
    
    log("\n" + "="*60, Colors.BLUE)
    log(f"TEST SUMMARY: {passed} passed, {failed} failed", 
        Colors.GREEN if failed == 0 else Colors.RED)
    log("="*60 + "\n", Colors.BLUE)
    
    return failed == 0

if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)

