#!/usr/bin/env python3
"""
Quick login test for admin/admin credentials
"""
import requests
import json

def test_login():
    """Test admin/admin login"""
    # Test API URL
    base_url = "http://localhost:8001"
    
    print("Testing admin/admin login...")
    
    try:
        # Test login
        login_response = requests.post(
            f"{base_url}/api/v1/auth/login",
            data={"username": "admin", "password": "admin"},
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        
        if login_response.status_code == 200:
            print("SUCCESS: Login successful!")
            token_data = login_response.json()
            access_token = token_data.get("access_token")
            
            # Test user info
            user_response = requests.get(
                f"{base_url}/api/v1/auth/me",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            
            if user_response.status_code == 200:
                user_info = user_response.json()
                print(f"User Email: {user_info.get('email')}")
                print(f"Full Name: {user_info.get('full_name')}")
                print(f"Is Super Admin: {user_info.get('is_superuser')}")
                print(f"Is Active: {user_info.get('is_active')}")
                return True
            else:
                print(f"FAILED: Could not get user info (status: {user_response.status_code})")
                return False
                
        else:
            print(f"FAILED: Login failed (status: {login_response.status_code})")
            print(f"Response: {login_response.text}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("FAILED: Cannot connect to test backend. Make sure it's running:")
        print("  docker-compose --profile test up -d test-backend")
        return False
    except Exception as e:
        print(f"FAILED: {e}")
        return False

if __name__ == "__main__":
    success = test_login()
    if success:
        print("\nAll tests passed! admin/admin login is working.")
    else:
        print("\nLogin test failed!")