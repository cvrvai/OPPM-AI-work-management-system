#!/usr/bin/env python3
"""
Frontend UI Testing Script - Runs inside Docker environment
Tests the frontend application through the gateway by simulating browser interactions
"""

import requests
import json
import time
from datetime import datetime, timedelta

# Configure for Docker environment (frontend container has network access)
BASE_URL = "http://localhost"  # Frontend running on same network as gateway
GATEWAY_URL = "http://gateway"  # Direct gateway access from Docker network

class UITester:
    def __init__(self):
        self.session = requests.Session()
        self.base_url = GATEWAY_URL
        self.user_data = None
        self.workspace_data = None
        self.project_data = None
        self.task_data = None
        
    def test_1_signup(self):
        """Test 1: User signup through gateway"""
        print("\n" + "="*60)
        print("TEST 1: User Signup (UI → Gateway → Core Auth)")
        print("="*60)
        
        payload = {
            "email": f"ui_test_{datetime.now().timestamp()}@example.com",
            "password": "UITestPass123!@#",
            "first_name": "UI",
            "last_name": "Tester"
        }
        
        try:
            response = self.session.post(
                f"{self.base_url}/api/auth/signup",
                json=payload,
                timeout=10
            )
            print(f"Status: {response.status_code}")
            
            if response.status_code in [200, 201]:
                self.user_data = response.json()
                print(f"✅ PASS - User created")
                print(f"   User ID: {self.user_data.get('id')}")
                print(f"   Email: {self.user_data.get('email')}")
                print(f"   Token: {self.user_data.get('access_token')[:20]}...")
                
                # Store tokens for subsequent requests
                self.session.headers.update({
                    "Authorization": f"Bearer {self.user_data.get('access_token')}"
                })
                return True
            else:
                print(f"❌ FAIL - Status {response.status_code}")
                print(f"   Response: {response.text[:200]}")
                return False
        except Exception as e:
            print(f"❌ ERROR - {str(e)}")
            return False
    
    def test_2_workspace_creation(self):
        """Test 2: Workspace creation through UI"""
        print("\n" + "="*60)
        print("TEST 2: Workspace Creation (UI → Gateway → Core)")
        print("="*60)
        
        if not self.user_data:
            print("⚠️  SKIPPED - No user data from previous test")
            return False
        
        import uuid
        slug = f"ui-test-ws-{uuid.uuid4().hex[:8]}"
        
        payload = {
            "name": f"UI Test Workspace {datetime.now().isoformat()}",
            "slug": slug,
            "description": "Test workspace created through UI layer"
        }
        
        try:
            response = self.session.post(
                f"{self.base_url}/api/v1/workspaces",
                json=payload,
                timeout=10
            )
            print(f"Status: {response.status_code}")
            
            if response.status_code in [200, 201]:
                self.workspace_data = response.json()
                print(f"✅ PASS - Workspace created")
                print(f"   Workspace ID: {self.workspace_data.get('id')}")
                print(f"   Name: {self.workspace_data.get('name')}")
                print(f"   Slug: {self.workspace_data.get('slug')}")
                return True
            else:
                print(f"❌ FAIL - Status {response.status_code}")
                print(f"   Response: {response.text[:200]}")
                return False
        except Exception as e:
            print(f"❌ ERROR - {str(e)}")
            return False
    
    def test_3_project_creation_with_real_data(self):
        """Test 3: Project creation with real Mobile App Redesign data"""
        print("\n" + "="*60)
        print("TEST 3: Project Creation - Mobile App Redesign (Real Data)")
        print("="*60)
        
        if not self.workspace_data:
            print("⚠️  SKIPPED - No workspace data from previous test")
            return False
        
        workspace_id = self.workspace_data.get('id')
        
        # Real example data: Mobile App Redesign Q1 2026
        payload = {
            "title": "Mobile App Redesign Q1 2026",
            "code": "PRJ-2026-001",
            "objective_summary": "Redesign and rebuild the mobile app with improved UX and 30% faster performance",
            "description": "Complete redesign of iOS and Android apps with improved UX, performance improvements, and enhanced user engagement features. New design system, component library, and accessibility compliance throughout. Success metrics: 30% faster load times, improved user satisfaction scores, platform support expansion.",
            "start_date": "2026-04-20",
            "deadline_date": "2026-06-15",
            "end_date": "2026-07-06",
            "budget": 50000.00,
            "budget_currency": "USD",
            "planning_hours": 200,
            "priority": "high",
            "methodology": "oppm"
        }
        
        try:
            response = self.session.post(
                f"{self.base_url}/api/v1/workspaces/{workspace_id}/projects",
                json=payload,
                timeout=10
            )
            print(f"Status: {response.status_code}")
            
            if response.status_code in [200, 201]:
                self.project_data = response.json()
                print(f"✅ PASS - Project created with real data")
                print(f"   Project ID: {self.project_data.get('id')}")
                print(f"   Title: {self.project_data.get('title')}")
                print(f"   Code: {self.project_data.get('code')}")
                print(f"   Budget: ${self.project_data.get('budget')}")
                print(f"   Timeline: {self.project_data.get('start_date')} → {self.project_data.get('end_date')}")
                print(f"   Methodology: {self.project_data.get('methodology')}")
                return True
            else:
                print(f"❌ FAIL - Status {response.status_code}")
                print(f"   Response: {response.text[:200]}")
                return False
        except Exception as e:
            print(f"❌ ERROR - {str(e)}")
            return False
    
    def test_4_task_creation(self):
        """Test 4: Task creation linked to project"""
        print("\n" + "="*60)
        print("TEST 4: Task Creation (Linked to Project)")
        print("="*60)
        
        if not self.workspace_data or not self.project_data:
            print("⚠️  SKIPPED - No workspace/project data from previous tests")
            return False
        
        workspace_id = self.workspace_data.get('id')
        project_id = self.project_data.get('id')
        
        payload = {
            "title": "Design System - Mobile Components",
            "description": "Create reusable component library for mobile redesign",
            "project_id": project_id,
            "priority": "high",
            "due_date": "2026-05-04",
            "project_contribution": 25
        }
        
        try:
            response = self.session.post(
                f"{self.base_url}/api/v1/workspaces/{workspace_id}/tasks",
                json=payload,
                timeout=10
            )
            print(f"Status: {response.status_code}")
            
            if response.status_code in [200, 201]:
                self.task_data = response.json()
                print(f"✅ PASS - Task created")
                print(f"   Task ID: {self.task_data.get('id')}")
                print(f"   Title: {self.task_data.get('title')}")
                print(f"   Project ID: {self.task_data.get('project_id')}")
                print(f"   Priority: {self.task_data.get('priority')}")
                print(f"   Contribution: {self.task_data.get('project_contribution')}%")
                return True
            else:
                print(f"❌ FAIL - Status {response.status_code}")
                print(f"   Response: {response.text[:200]}")
                return False
        except Exception as e:
            print(f"❌ ERROR - {str(e)}")
            return False
    
    def test_5_task_list(self):
        """Test 5: Retrieve task list through UI"""
        print("\n" + "="*60)
        print("TEST 5: Task List Retrieval (Pagination)")
        print("="*60)
        
        if not self.workspace_data:
            print("⚠️  SKIPPED - No workspace data from previous tests")
            return False
        
        workspace_id = self.workspace_data.get('id')
        
        try:
            response = self.session.get(
                f"{self.base_url}/api/v1/workspaces/{workspace_id}/tasks?page=1&limit=10",
                timeout=10
            )
            print(f"Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                
                # Handle both list and dict responses
                if isinstance(data, list):
                    items = data
                    total = len(data)
                else:
                    items = data.get('items', [])
                    total = data.get('total', len(items))
                
                print(f"✅ PASS - Task list retrieved")
                print(f"   Total tasks: {total}")
                print(f"   Returned items: {len(items)}")
                if items:
                    first_task = items[0] if isinstance(items[0], dict) else {}
                    print(f"   First task: {first_task.get('title', 'N/A')}")
                return True
            else:
                print(f"❌ FAIL - Status {response.status_code}")
                print(f"   Response: {response.text[:200]}")
                return False
        except Exception as e:
            print(f"❌ ERROR - {str(e)}")
            import traceback
            traceback.print_exc()
            return False
    
    def test_6_notifications(self):
        """Test 6: Notifications through UI"""
        print("\n" + "="*60)
        print("TEST 6: Notifications Display")
        print("="*60)
        
        try:
            response = self.session.get(
                f"{self.base_url}/api/v1/notifications",
                timeout=10
            )
            print(f"Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                items = data.get('items', []) if isinstance(data, dict) else data
                print(f"✅ PASS - Notifications endpoint accessible")
                print(f"   Notification count: {len(items) if isinstance(items, list) else 'N/A'}")
                return True
            else:
                print(f"❌ FAIL - Status {response.status_code}")
                print(f"   Response: {response.text[:200]}")
                return False
        except Exception as e:
            print(f"❌ ERROR - {str(e)}")
            return False
    
    def run_all_tests(self):
        """Run all UI tests in sequence"""
        print("\n")
        print("#" * 60)
        print("# OPPM AI SYSTEM - FRONTEND UI TESTING")
        print("# Test Environment: Docker Network")
        print("# Backend Access: Gateway → Core Services")
        print("# Real Example Data: Mobile App Redesign Q1 2026")
        print("#" * 60)
        
        results = {}
        
        results['signup'] = self.test_1_signup()
        time.sleep(0.5)
        
        results['workspace'] = self.test_2_workspace_creation()
        time.sleep(0.5)
        
        results['project'] = self.test_3_project_creation_with_real_data()
        time.sleep(0.5)
        
        results['task'] = self.test_4_task_creation()
        time.sleep(0.5)
        
        results['task_list'] = self.test_5_task_list()
        time.sleep(0.5)
        
        results['notifications'] = self.test_6_notifications()
        
        # Print summary
        print("\n" + "="*60)
        print("TEST SUMMARY")
        print("="*60)
        
        passed = sum(1 for v in results.values() if v)
        failed = len(results) - passed
        
        for test, result in results.items():
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"{status} - {test}")
        
        print(f"\nTotal: {passed}/{len(results)} passed")
        print("="*60 + "\n")
        
        return results

if __name__ == "__main__":
    tester = UITester()
    tester.run_all_tests()
