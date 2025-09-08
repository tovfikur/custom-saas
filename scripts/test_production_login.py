#!/usr/bin/env python3
"""
Test production login with auto-created admin user
"""
import requests
import json

def test_login(username, password, description):
    """Test login with given credentials"""
    base_url = "http://localhost:8000"
    
    print(f"\nTesting {description}...")
    
    try:
        # Test login
        response = requests.post(
            f"{base_url}/api/v1/auth/login",
            data={"username": username, "password": password},
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        
        if response.status_code == 200:
            print(f"SUCCESS: {description}")
            token_data = response.json()
            access_token = token_data.get("access_token")
            
            # Get user info
            user_response = requests.get(
                f"{base_url}/api/v1/auth/me",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            
            if user_response.status_code == 200:
                user_info = user_response.json()
                print(f"   Email: {user_info.get('email')}")
                print(f"   Full Name: {user_info.get('full_name')}")
                print(f"   Super Admin: {user_info.get('is_superuser')}")
                return True
            else:
                print(f"FAILED: Could not get user info")
                return False
                
        else:
            print(f"FAILED: {description} (status: {response.status_code})")
            print(f"   Response: {response.text}")
            return False
            
    except requests.exceptions.ConnectionError:
        print(f"FAILED: Cannot connect to backend. Make sure it's running:")
        print("   docker-compose up -d backend")
        return False
    except Exception as e:
        print(f"FAILED: {e}")
        return False

def main():
    """Test all login methods"""
    print("Production Login Test - Auto-Created Admin User")
    print("=" * 55)
    
    # Test both login methods
    tests = [
        ("admin", "admin", "Username login (admin/admin)"),
        ("admin@domain.com", "admin", "Email login (admin@domain.com/admin)")
    ]
    
    all_passed = True
    for username, password, description in tests:
        success = test_login(username, password, description)
        if not success:
            all_passed = False
    
    print("\n" + "=" * 55)
    if all_passed:
        print("All tests passed! Auto-admin creation is working perfectly!")
        print("\nLogin Options:")
        print("   - Username: admin / Password: admin")
        print("   - Email: admin@domain.com / Password: admin")
    else:
        print("Some tests failed!")

if __name__ == "__main__":
    main()