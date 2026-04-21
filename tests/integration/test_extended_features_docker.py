#!/usr/bin/env python3
"""
OPPM AI System - Extended Feature Testing (Tasks & Notifications)
Tests additional features using Mobile App Redesign project
"""

import requests
import json
from datetime import datetime, timedelta
from typing import Optional

# Configuration - Using Docker internal URLs
CORE_SERVICE_URL = "http://core:8000"

# Test credentials
TEST_EMAIL = "testuser@mobileredesign.com"
TEST_PASSWORD = "TestPass123!"

# Global state
access_token: Optional[str] = None
workspace_id: Optional[str] = None
project_id: Optional[str] = None
task_id: Optional[str] = None

def print_section(title: str):
    print(f"\n{'='*80}")
    print(f"  {title}")
    print(f"{'='*80}\n")

def print_test(test_name: str, status: str, details: str = ""):
    status_symbol = "[PASS]" if status == "PASS" else "[FAIL]" if status == "FAIL" else "[SKIP]"
    print(f"{status_symbol} {test_name}")
    if details:
        print(f"   -> {details}")

def get_headers() -> dict:
    headers = {"Content-Type": "application/json"}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    return headers

def setup_test_data() -> bool:
    """Setup: Login and get/create workspace/project IDs"""
    print_section("SETUP: RETRIEVING TEST DATA")
    
    global access_token, workspace_id, project_id
    
    try:
        # Login
        resp = requests.post(
            f"{CORE_SERVICE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        if resp.status_code != 200:
            print_test("Login", "FAIL", f"Status {resp.status_code}")
            return False
        
        access_token = resp.json()["access_token"]
        print_test("Login", "PASS", "Authenticated")
        
        # Get first workspace
        resp = requests.get(f"{CORE_SERVICE_URL}/api/v1/workspaces", headers=get_headers())
        if resp.status_code != 200:
            print_test("List Workspaces", "FAIL", f"Status {resp.status_code}")
            return False
        
        workspaces = resp.json()
        if not workspaces:
            print_test("Get Workspace", "FAIL", "No workspaces found")
            return False
        
        workspace_id = workspaces[0]["id"]
        print_test("Get Workspace", "PASS", f"ID: {workspace_id}")
        
        # Get first project or create one
        resp = requests.get(
            f"{CORE_SERVICE_URL}/api/v1/workspaces/{workspace_id}/projects",
            headers=get_headers()
        )
        if resp.status_code != 200:
            print_test("List Projects", "FAIL", f"Status {resp.status_code}")
            return False
        
        data = resp.json()
        projects = data.get("items", [])
        
        if not projects:
            # Create a project for testing
            import uuid
            from datetime import datetime, timedelta
            start_date = datetime.now().date()
            
            payload = {
                "title": "Mobile App Redesign Q1 2026",
                "code": "PRJ-2026-001",
                "objective_summary": "Redesign and rebuild the mobile app with improved UX and 30% faster performance",
                "description": "Complete redesign of iOS and Android apps with focus on accessibility, modern design system, and performance optimization.",
                "start_date": start_date.isoformat(),
                "deadline_date": (start_date + timedelta(days=56)).isoformat(),
                "end_date": (start_date + timedelta(days=77)).isoformat(),
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
                print_test("Create Project", "FAIL", f"Status {resp.status_code}")
                return False
            
            project_id = resp.json()["id"]
            print_test("Create Project", "PASS", f"ID: {project_id}")
        else:
            project_id = projects[0]["id"]
            print_test("Get Project", "PASS", f"ID: {project_id}")
        
        return True
    except Exception as e:
        print_test("Setup", "FAIL", str(e))
        import traceback
        traceback.print_exc()
        return False

def test_task_creation() -> bool:
    """Test: Create Task"""
    print_section("TEST 9: TASK CREATION")
    
    if not workspace_id or not project_id:
        print_test("Task Creation", "SKIP", "No workspace/project")
        return False
    
    try:
        payload = {
            "title": "Design System - Mobile Components",
            "description": "Create reusable component library for mobile redesign including buttons, forms, modals, and navigation patterns",
            "project_id": project_id,
            "priority": "high",
            "due_date": (datetime.now().date() + timedelta(days=14)).isoformat(),
            "project_contribution": 25
        }
        
        resp = requests.post(
            f"{CORE_SERVICE_URL}/api/v1/workspaces/{workspace_id}/tasks",
            json=payload,
            headers=get_headers()
        )
        
        if resp.status_code not in [200, 201]:
            print_test("Task Creation", "FAIL", f"Status {resp.status_code}: {resp.text[:100]}")
            return False
        
        data = resp.json()
        global task_id
        task_id = data.get("id")
        
        print_test("Task Creation", "PASS", f"Task ID: {task_id}")
        print(f"   Title: {data.get('title')}")
        print(f"   Priority: {data.get('priority')}")
        return True
    except Exception as e:
        print_test("Task Creation", "FAIL", str(e))
        return False

def test_task_retrieval() -> bool:
    """Test: Retrieve Task"""
    print_section("TEST 10: TASK RETRIEVAL")
    
    if not workspace_id or not task_id:
        print_test("Task Retrieval", "SKIP", "No workspace/task")
        return False
    
    try:
        resp = requests.get(
            f"{CORE_SERVICE_URL}/api/v1/workspaces/{workspace_id}/tasks/{task_id}",
            headers=get_headers()
        )
        
        if resp.status_code != 200:
            print_test("Task Retrieval", "FAIL", f"Status {resp.status_code}")
            return False
        
        data = resp.json()
        print_test("Task Retrieval", "PASS", f"Task: {data.get('title')}")
        return True
    except Exception as e:
        print_test("Task Retrieval", "FAIL", str(e))
        return False

def test_task_update() -> bool:
    """Test: Update Task"""
    print_section("TEST 11: TASK UPDATE")
    
    if not workspace_id or not task_id:
        print_test("Task Update", "SKIP", "No workspace/task")
        return False
    
    try:
        payload = {
            "status": "in_progress",
            "progress": 25
        }
        
        resp = requests.put(
            f"{CORE_SERVICE_URL}/api/v1/workspaces/{workspace_id}/tasks/{task_id}",
            json=payload,
            headers=get_headers()
        )
        
        if resp.status_code != 200:
            print_test("Task Update", "FAIL", f"Status {resp.status_code}")
            return False
        
        data = resp.json()
        print_test("Task Update", "PASS", f"Status: {data.get('status')}")
        return True
    except Exception as e:
        print_test("Task Update", "FAIL", str(e))
        return False

def test_task_list() -> bool:
    """Test: List Tasks"""
    print_section("TEST 12: LIST TASKS")
    
    if not workspace_id:
        print_test("List Tasks", "SKIP", "No workspace")
        return False
    
    try:
        resp = requests.get(
            f"{CORE_SERVICE_URL}/api/v1/workspaces/{workspace_id}/tasks",
            headers=get_headers()
        )
        
        if resp.status_code != 200:
            print_test("List Tasks", "FAIL", f"Status {resp.status_code}")
            return False
        
        tasks = resp.json()
        print_test("List Tasks", "PASS", f"Found {len(tasks)} tasks")
        return True
    except Exception as e:
        print_test("List Tasks", "FAIL", str(e))
        return False

def test_notifications_list() -> bool:
    """Test: List Notifications"""
    print_section("TEST 13: LIST NOTIFICATIONS")
    
    try:
        resp = requests.get(
            f"{CORE_SERVICE_URL}/api/v1/notifications",
            headers=get_headers()
        )
        
        if resp.status_code != 200:
            print_test("List Notifications", "FAIL", f"Status {resp.status_code}")
            return False
        
        notifications = resp.json()
        print_test("List Notifications", "PASS", f"Found {len(notifications)} notifications")
        return True
    except Exception as e:
        print_test("List Notifications", "FAIL", str(e))
        return False

def test_unread_count() -> bool:
    """Test: Get Unread Notification Count"""
    print_section("TEST 14: UNREAD NOTIFICATION COUNT")
    
    try:
        resp = requests.get(
            f"{CORE_SERVICE_URL}/api/v1/notifications/unread-count",
            headers=get_headers()
        )
        
        if resp.status_code != 200:
            print_test("Unread Count", "FAIL", f"Status {resp.status_code}")
            return False
        
        data = resp.json()
        print_test("Unread Count", "PASS", f"Unread: {data.get('count', 0)}")
        return True
    except Exception as e:
        print_test("Unread Count", "FAIL", str(e))
        return False

def run_extended_tests():
    """Run extended tests"""
    print("\n" + "="*80)
    print("  EXTENDED FEATURE TESTING")
    print("  Project: Mobile App Redesign Q1 2026")
    print("="*80)
    
    if not setup_test_data():
        print("\n[ERROR] Setup failed - cannot continue")
        return
    
    tests = [
        ("Task Creation", test_task_creation),
        ("Task Retrieval", test_task_retrieval),
        ("Task Update", test_task_update),
        ("List Tasks", test_task_list),
        ("List Notifications", test_notifications_list),
        ("Unread Notification Count", test_unread_count),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            if result:
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"[ERROR] {test_name}: {str(e)}")
            failed += 1
    
    print_section("EXTENDED TEST SUMMARY")
    print(f"PASSED:  {passed}")
    print(f"FAILED:  {failed}")
    print(f"TOTAL:   {passed + failed}")
    
    if (passed + failed) > 0:
        print(f"SUCCESS RATE: {passed}/{passed + failed} ({100*passed/(passed+failed):.1f}%)")
    
    print("\n" + "="*80 + "\n")

if __name__ == "__main__":
    run_extended_tests()
