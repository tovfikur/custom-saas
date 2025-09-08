#!/usr/bin/env python3
"""
Comprehensive login tests using Docker test environment.
Tests login functionality without hardcoded demo credentials.
"""
import asyncio
import httpx
import json
import sys
import os
from datetime import datetime
import pytest

# Test configuration
TEST_API_URL = "http://localhost:8001"
TEST_USERS = {
    "default_admin": {
        "username": "admin",
        "password": "admin",
        "expected_superuser": True
    },
    "super_admin": {
        "username": "test.admin@example.com",
        "password": "test123456",
        "expected_superuser": True
    },
    "regular_admin": {
        "username": "regular.admin@example.com", 
        "password": "regular123456",
        "expected_superuser": False
    }
}

class LoginTester:
    def __init__(self, base_url: str = TEST_API_URL):
        self.base_url = base_url
        self.session = None
    
    async def __aenter__(self):
        self.session = httpx.AsyncClient(base_url=self.base_url)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.aclose()
    
    async def test_login(self, username: str, password: str) -> dict:
        """Test login endpoint"""
        login_data = {
            "username": username,
            "password": password
        }
        
        response = await self.session.post(
            "/api/v1/auth/login",
            data=login_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        
        return {
            "status_code": response.status_code,
            "response": response.json() if response.headers.get("content-type", "").startswith("application/json") else response.text,
            "headers": dict(response.headers)
        }
    
    async def test_get_current_user(self, token: str) -> dict:
        """Test /me endpoint with token"""
        headers = {"Authorization": f"Bearer {token}"}
        response = await self.session.get("/api/v1/auth/me", headers=headers)
        
        return {
            "status_code": response.status_code,
            "response": response.json() if response.headers.get("content-type", "").startswith("application/json") else response.text
        }

async def run_login_tests():
    """Run comprehensive login tests"""
    print("🔐 Starting Login Tests with Docker Environment")
    print("=" * 50)
    
    async with LoginTester() as tester:
        all_tests_passed = True
        
        for test_name, user_data in TEST_USERS.items():
            print(f"\n🧪 Testing {test_name}...")
            
            try:
                # Test login
                result = await tester.test_login(
                    user_data["username"],
                    user_data["password"]
                )
                
                should_fail = user_data.get("should_fail", False)
                
                if should_fail:
                    # This user should fail to login
                    if result["status_code"] == 401:
                        print(f"✅ {test_name}: Login correctly rejected (status: {result['status_code']})")
                    else:
                        print(f"❌ {test_name}: Expected login to fail but got status: {result['status_code']}")
                        all_tests_passed = False
                else:
                    # This user should successfully login
                    if result["status_code"] == 200:
                        print(f"✅ {test_name}: Login successful (status: {result['status_code']})")
                        
                        # Test token validity
                        token = result["response"].get("access_token")
                        if token:
                            user_info = await tester.test_get_current_user(token)
                            
                            if user_info["status_code"] == 200:
                                user_details = user_info["response"]
                                expected_superuser = user_data.get("expected_superuser", False)
                                
                                if user_details.get("is_superuser") == expected_superuser:
                                    print(f"✅ {test_name}: User permissions correct (superuser: {expected_superuser})")
                                else:
                                    print(f"❌ {test_name}: User permissions incorrect. Expected superuser: {expected_superuser}, got: {user_details.get('is_superuser')}")
                                    all_tests_passed = False
                                
                                print(f"   📧 Email: {user_details.get('email')}")
                                print(f"   👤 Name: {user_details.get('full_name')}")
                                print(f"   🔑 Super Admin: {user_details.get('is_superuser')}")
                            else:
                                print(f"❌ {test_name}: Failed to get user info with token (status: {user_info['status_code']})")
                                all_tests_passed = False
                        else:
                            print(f"❌ {test_name}: No access token in response")
                            all_tests_passed = False
                    else:
                        print(f"❌ {test_name}: Login failed (status: {result['status_code']})")
                        print(f"   Response: {result['response']}")
                        all_tests_passed = False
                        
            except Exception as e:
                print(f"❌ {test_name}: Test failed with exception: {e}")
                all_tests_passed = False
        
        print("\n" + "=" * 50)
        if all_tests_passed:
            print("🎉 All login tests passed!")
        else:
            print("⚠️  Some login tests failed!")
        
        return all_tests_passed

async def test_invalid_credentials():
    """Test login with invalid credentials"""
    print("\n🔒 Testing Invalid Credentials...")
    
    async with LoginTester() as tester:
        # Test with wrong password
        result = await tester.test_login("admin", "wrongpassword")
        if result["status_code"] == 401:
            print("✅ Wrong password correctly rejected")
        else:
            print(f"❌ Wrong password not rejected (status: {result['status_code']})")
            return False
        
        # Test with non-existent user
        result = await tester.test_login("nonexistent@example.com", "anypassword")
        if result["status_code"] == 401:
            print("✅ Non-existent user correctly rejected")
        else:
            print(f"❌ Non-existent user not rejected (status: {result['status_code']})")
            return False
        
        return True

async def main():
    """Main test runner"""
    print("🐳 Docker-based Login Testing Suite")
    print("🔧 Make sure test services are running with:")
    print("   docker-compose --profile test up test-postgres test-backend")
    print()
    
    try:
        # Wait for services to be ready
        print("⏳ Waiting for test services to be ready...")
        await asyncio.sleep(3)
        
        # Run main login tests
        login_tests_passed = await run_login_tests()
        
        # Run invalid credential tests
        invalid_tests_passed = await test_invalid_credentials()
        
        if login_tests_passed and invalid_tests_passed:
            print("\n🎉 All tests completed successfully!")
            sys.exit(0)
        else:
            print("\n❌ Some tests failed!")
            sys.exit(1)
            
    except Exception as e:
        print(f"❌ Test suite failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())