#!/usr/bin/env python3
"""
Smoke Test for Relab Chatbot API
Tests all critical bug fixes and validates API stability
"""
import requests
import json
import sys

BASE_URL = "http://localhost:8000"

def test_health():
    """Test 1: Basic health check"""
    print("\n🔍 Test 1: Health Check")
    try:
        response = requests.get(f"{BASE_URL}/health")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✅ PASS: Health check OK")
        return True
    except Exception as e:
        print(f"❌ FAIL: {e}")
        return False

def test_chat_with_identifier():
    """Test 2: POST /chat with 'identifier' field"""
    print("\n🔍 Test 2: POST /chat with 'identifier'")
    try:
        payload = {
            "message": "Bonjour",
            "channel": "web",
            "identifier": "test_user_123"
        }
        response = requests.post(f"{BASE_URL}/chat", json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "conversation_id" in data, "Missing conversation_id"
        # message can be None in TEST_MODE, so just check it exists
        assert "message" in data, "Missing message field"
        print(f"✅ PASS: Received response with conversation_id={data['conversation_id']}")
        return True
    except Exception as e:
        print(f"❌ FAIL: {e}")
        return False

def test_chat_with_user_id():
    """Test 3: POST /chat with 'user_id' (alias)"""
    print("\n🔍 Test 3: POST /chat with 'user_id' (alias)")
    try:
        payload = {
            "message": "Hello",
            "channel": "web",
            "user_id": "test_user_456"  # Using alias instead of identifier
        }
        response = requests.post(f"{BASE_URL}/chat", json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "conversation_id" in data, "Missing conversation_id"
        print(f"✅ PASS: user_id alias works! conversation_id={data['conversation_id']}")
        return True
    except Exception as e:
        print(f"❌ FAIL: {e}")
        return False

def test_chat_missing_identifier():
    """Test 4: POST /chat without identifier (should fail validation)"""
    print("\n🔍 Test 4: POST /chat missing identifier/user_id")
    try:
        payload = {
            "message": "Test",
            "channel": "web"
            # Missing both identifier and user_id
        }
        response = requests.post(f"{BASE_URL}/chat", json=payload)
        assert response.status_code == 422, f"Expected 422, got {response.status_code}"
        print("✅ PASS: Proper validation error (422) for missing identifier")
        return True
    except Exception as e:
        print(f"❌ FAIL: {e}")
        return False

def test_dashboard_route():
    """Test 5: GET /dashboard.html exists"""
    print("\n🔍 Test 5: GET /dashboard.html")
    try:
        response = requests.get(f"{BASE_URL}/dashboard.html")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✅ PASS: Dashboard route works")
        return True
    except Exception as e:
        print(f"❌ FAIL: {e}")
        return False

def test_simulator_route_removed():
    """Test 6: GET /simulator.html should 404 (route removed)"""
    print("\n🔍 Test 6: GET /simulator.html (should be removed)")
    try:
        response = requests.get(f"{BASE_URL}/simulator.html")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✅ PASS: Simulator route properly removed (404)")
        return True
    except Exception as e:
        print(f"❌ FAIL: {e}")
        return False

def run_all_tests():
    """Run all smoke tests"""
    print("=" * 60)
    print("🚀 RELAB CHATBOT API - SMOKE TEST SUITE")
    print("=" * 60)
    
    tests = [
        test_health,
        test_chat_with_identifier,
        test_chat_with_user_id,
        test_chat_missing_identifier,
        test_dashboard_route,
        test_simulator_route_removed
    ]
    
    results = []
    for test_func in tests:
        results.append(test_func())
    
    print("\n" + "=" * 60)
    print(f"📊 RESULTS: {sum(results)}/{len(results)} tests passed")
    print("=" * 60)
    
    if all(results):
        print("✅ ALL TESTS PASSED!")
        return 0
    else:
        print("❌ SOME TESTS FAILED")
        return 1

if __name__ == "__main__":
    exit_code = run_all_tests()
    sys.exit(exit_code)
