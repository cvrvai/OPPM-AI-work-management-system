#!/usr/bin/env python3
"""
OPPM AI System Comprehensive Testing Script - Docker Version
Tests all features from within Docker network using real example data
"""

import requests
import json
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

# Configuration - Using Docker internal URLs
CORE_SERVICE_URL = "http://core:8000"
AI_SERVICE_URL = "http://ai:8001"
GIT_SERVICE_URL = "http://git:8002"

# Test credentials
TEST_EMAIL = "testuser@mobileredesign.com"
TEST_PASSWORD = "TestPass123!"
TEST_USER_NAME = "Test User Mobile Redesign"

# Global state for tokens and IDs
access_token: Optional[str] = None
refresh_token: Optional[str] = None
user_id: Optional[str] = None
workspace_id: Optional[str] = None
project_id: Optional[str] = None

def print_section(title: str):
    """Print a formatted section header"""
    print(f"\n{'='*80}")
    print(f"  {title}")
    print(f"{'='*80}\n")

def print_test(test_name: str, status: str, details: str = ""):
    """Print test result"""
    status_symbol = "PASS" if status == "PASS" else "FAIL" if status == "FAIL" else "SKIP"
    print(f"[{status_symbol}] {test_name}")
    if details:
        print(f"   -> {details}")

def get_headers() -> Dict[str, str]:
    """Get request headers with auth token"""
    headers = {"Content-Type": "application/json"}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    return headers

def test_auth_signup() -> bool:
    """Test 1: User Signup"""
    print_section("TEST 1: AUTHENTICATION - SIGNUP")
    
    try:
        import uuid
        unique_email = f"test{uuid.uuid4().hex[:8]}@mobileredesign.com"
        
        payload = {
            "email": unique_email,
            "password": TEST_PASSWORD,
            "full_name": TEST_USER_NAME
        }
        resp = requests.post(f"{CORE_SERVICE_URL}/api/auth/signup", json=payload)
        
        if resp.status_code != 200:
            print_test("User Signup", "FAIL", f"Status {resp.status_code}: {resp.text}")
            return False
        
        data = resp.json()
        global access_token, refresh_token, user_id
        access_token = data.get("access_token")
        refresh_token = data.get("refresh_token")
        user_id = data["user"]["id"]
        
        print_test("User Signup", "PASS", f"User ID: {user_id}")
        print(f"   Email: {data['user']['email']}")
        print(f"   Token Expiry: {data['expires_in']} seconds")
        return True
    except Exception as e:
        print_test("User Signup", "FAIL", str(e))
        return False

def test_auth_login() -> bool:
    """Test 2: User Login"""
    print_section("TEST 2: AUTHENTICATION - LOGIN")
    
    try:
        payload = {
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        }
        resp = requests.post(f"{CORE_SERVICE_URL}/api/auth/login", json=payload)
        
        if resp.status_code != 200:
            print_test("User Login", "FAIL", f"Status {resp.status_code}: {resp.text}")
            return False
        
        data = resp.json()
        global access_token, refresh_token
        access_token = data.get("access_token")
        refresh_token = data.get("refresh_token")
        
        print_test("User Login", "PASS", f"Token received: {data['access_token'][:20]}...")
        print(f"   User Email: {data['user']['email']}")
        return True
    except Exception as e:
        print_test("User Login", "FAIL", str(e))
        return False

def test_auth_me() -> bool:
    """Test 3: Get Current User"""
    print_section("TEST 3: AUTHENTICATION - GET CURRENT USER")
    
    try:
        resp = requests.get(f"{CORE_SERVICE_URL}/api/auth/me", headers=get_headers())
        
        if resp.status_code != 200:
            print_test("Get Current User", "FAIL", f"Status {resp.status_code}: {resp.text}")
            return False
        
        data = resp.json()
        print_test("Get Current User", "PASS", f"User: {data['email']}")
        print(f"   Role: {data.get('role', 'N/A')}")
        return True
    except Exception as e:
        print_test("Get Current User", "FAIL", str(e))
        return False

def test_workspace_creation() -> bool:
    """Test 4: Create Workspace"""
    print_section("TEST 4: WORKSPACE CREATION")
    
    try:
        import uuid
        payload = {
            "name": "Mobile App Redesign Workspace",
            "slug": f"mobile-redesign-{uuid.uuid4().hex[:4]}",
            "description": "Workspace for Mobile App Redesign Q1 2026 project"
        }
        resp = requests.post(
            f"{CORE_SERVICE_URL}/api/v1/workspaces",
            json=payload,
            headers=get_headers()
        )
        
        if resp.status_code not in [200, 201]:
            print_test("Workspace Creation", "FAIL", f"Status {resp.status_code}: {resp.text}")
            return False
        
        data = resp.json()
        global workspace_id
        workspace_id = data.get("id")
        
        print_test("Workspace Creation", "PASS", f"Workspace ID: {workspace_id}")
        print(f"   Name: {data.get('name')}")
        return True
    except Exception as e:
        print_test("Workspace Creation", "FAIL", str(e))
        return False

def test_project_creation() -> bool:
    """Test 5: Create Project with Real Example Data"""
    print_section("TEST 5: PROJECT CREATION - REAL EXAMPLE DATA")
    
    if not workspace_id:
        print_test("Project Creation", "SKIP", "No workspace ID")
        return False
    
    try:
        start_date = datetime.now().date()
        end_date = start_date + timedelta(days=77)  # 11 weeks
        
        payload = {
            "title": "Mobile App Redesign Q1 2026",
            "code": "PRJ-2026-001",
            "objective_summary": "Redesign and rebuild the mobile app with improved UX and 30% faster performance",
            "description": "Complete redesign of iOS and Android apps with focus on accessibility, modern design system, and performance optimization. Key deliverables: new design system, feature parity with web app, push notifications, offline mode, and comprehensive testing suite. Success metric: 30% faster load times, 4.5+ app store rating, zero critical bugs in first month.",
            "start_date": start_date.isoformat(),
            "deadline_date": (start_date + timedelta(days=56)).isoformat(),  # 8 weeks
            "end_date": end_date.isoformat(),
            "budget": 50000.00,
            "budget_currency": "USD",
            "planning_hours": 200,
            "priority": "high",
            "methodology": "oppm"
        }
        
        resp = requests.post(
            f"{CORE_SERVICE_URL}/api/v1/workspaces/{workspace_id}/projects",
            json=payload,
            headers=get_headers()
        )
        
        if resp.status_code not in [200, 201]:
            print_test("Project Creation", "FAIL", f"Status {resp.status_code}: {resp.text}")
            return False
        
        data = resp.json()
        global project_id
        project_id = data.get("id")
        
        print_test("Project Creation", "PASS", f"Project ID: {project_id}")
        print(f"   Code: {data.get('code')}")
        print(f"   Budget: ${data.get('budget'):,.2f}")
        print(f"   Priority: {data.get('priority')}")
        print(f"   Planning Hours: {data.get('planning_hours')}")
        return True
    except Exception as e:
        print_test("Project Creation", "FAIL", str(e))
        return False

def test_project_retrieval() -> bool:
    """Test 6: Retrieve Project"""
    print_section("TEST 6: PROJECT RETRIEVAL")
    
    if not workspace_id or not project_id:
        print_test("Project Retrieval", "SKIP", "No workspace or project ID")
        return False
    
    try:
        resp = requests.get(
            f"{CORE_SERVICE_URL}/api/v1/workspaces/{workspace_id}/projects/{project_id}",
            headers=get_headers()
        )
        
        if resp.status_code != 200:
            print_test("Project Retrieval", "FAIL", f"Status {resp.status_code}: {resp.text}")
            return False
        
        data = resp.json()
        print_test("Project Retrieval", "PASS", f"Project: {data.get('name')}")
        print(f"   Objective: {data.get('objective_summary')}")
        return True
    except Exception as e:
        print_test("Project Retrieval", "FAIL", str(e))
        return False

def test_project_update() -> bool:
    """Test 7: Update Project"""
    print_section("TEST 7: PROJECT UPDATE")
    
    if not workspace_id or not project_id:
        print_test("Project Update", "SKIP", "No workspace or project ID")
        return False
    
    try:
        payload = {
            "priority": "critical"
        }
        resp = requests.put(
            f"{CORE_SERVICE_URL}/api/v1/workspaces/{workspace_id}/projects/{project_id}",
            json=payload,
            headers=get_headers()
        )
        
        if resp.status_code != 200:
            print_test("Project Update", "FAIL", f"Status {resp.status_code}: {resp.text}")
            return False
        
        data = resp.json()
        print_test("Project Update", "PASS", f"Project updated")
        print(f"   New Priority: {data.get('priority')}")
        return True
    except Exception as e:
        print_test("Project Update", "FAIL", str(e))
        return False

def test_health_checks() -> bool:
    """Test 8: Service Health Checks"""
    print_section("TEST 8: SERVICE HEALTH CHECKS")
    
    all_healthy = True
    services = [
        ("Core", CORE_SERVICE_URL),
        ("AI", AI_SERVICE_URL),
        ("Git", GIT_SERVICE_URL),
    ]
    
    for service_name, service_url in services:
        try:
            resp = requests.get(f"{service_url}/health", timeout=5)
            if resp.status_code == 200:
                print_test(f"{service_name} Service Health", "PASS", resp.json().get("status", "unknown"))
            else:
                print_test(f"{service_name} Service Health", "FAIL", f"Status {resp.status_code}")
                all_healthy = False
        except Exception as e:
            print_test(f"{service_name} Service Health", "FAIL", str(e))
            all_healthy = False
    
    return all_healthy

def run_all_tests():
    """Run all feature tests"""
    print("\n" + "="*80)
    print("  OPPM AI SYSTEM - COMPREHENSIVE FEATURE TESTING")
    print("  Real Example Data: Mobile App Redesign Q1 2026 (PRJ-2026-001)")
    print("  Budget: $50,000 | Timeline: 11 weeks | Planning Hours: 200")
    print("="*80)
    
    tests = [
        ("Service Health Checks", test_health_checks),
        ("User Signup", test_auth_signup),
        ("User Login", test_auth_login),
        ("Get Current User", test_auth_me),
        ("Workspace Creation", test_workspace_creation),
        ("Project Creation (Real Data)", test_project_creation),
        ("Project Retrieval", test_project_retrieval),
        ("Project Update", test_project_update),
    ]
    
    passed = 0
    failed = 0
    skipped = 0
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            if result is None:
                skipped += 1
            elif result:
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"[ERROR] {test_name}: {str(e)}")
            failed += 1
        
        time.sleep(0.5)  # Small delay between tests
    
    # Summary
    print_section("TEST SUMMARY")
    print(f"PASSED:  {passed}")
    print(f"FAILED:  {failed}")
    print(f"SKIPPED: {skipped}")
    print(f"TOTAL:   {passed + failed + skipped}")
    
    if (passed + failed) > 0:
        success_rate = 100 * passed / (passed + failed)
        print(f"\nSUCCESS RATE: {passed}/{passed + failed} ({success_rate:.1f}%)")
    
    print("\n" + "="*80 + "\n")
    
    return passed, failed, skipped

if __name__ == "__main__":
    run_all_tests()
