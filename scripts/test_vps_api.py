#!/usr/bin/env python3
"""
Test VPS API functionality
"""
import requests
import json

def test_vps_api():
    """Test VPS API endpoints"""
    base_url = "http://localhost:8000"
    
    # Login first
    login_response = requests.post(
        f"{base_url}/api/v1/auth/login",
        data={"username": "admin", "password": "admin"},
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    
    if login_response.status_code != 200:
        print(f"Login failed: {login_response.text}")
        return False
    
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    print("1. Testing VPS list endpoint...")
    list_response = requests.get(f"{base_url}/api/v1/vps", headers=headers)
    print(f"   Status: {list_response.status_code}")
    print(f"   Response: {list_response.json()}")
    
    print("\n2. Testing VPS onboard validation...")
    # Test with missing data to see validation
    onboard_response = requests.post(
        f"{base_url}/api/v1/vps/onboard",
        json={
            "name": "Test VPS",
            "hostname": "test.example.com",
            "ip_address": "192.168.1.100",
            "username": "root"
            # Missing password or private_key - should fail
        },
        headers=headers
    )
    print(f"   Status: {onboard_response.status_code}")
    print(f"   Response: {onboard_response.text}")
    
    return True

if __name__ == "__main__":
    test_vps_api()