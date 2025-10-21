#!/usr/bin/env python3
"""
Test script for Legal Events v2 API
Verifies that all components are working correctly
"""

import requests
import time
import sys
import json
from datetime import datetime

API_URL = "http://localhost:8000"

def colored_print(text, color="default"):
    """Print colored text"""
    colors = {
        "red": "\033[91m",
        "green": "\033[92m",
        "yellow": "\033[93m",
        "blue": "\033[94m",
        "default": "\033[0m"
    }
    print(f"{colors.get(color, colors['default'])}{text}{colors['default']}")

def test_health():
    """Test health endpoint"""
    print("\n1. Testing Health Endpoint...")
    try:
        response = requests.get(f"{API_URL}/health")
        if response.status_code == 200:
            health = response.json()
            if health["status"] == "healthy":
                colored_print("✅ Health check passed", "green")
                for component, status in health["components"].items():
                    icon = "✅" if status == "healthy" else "❌"
                    colored_print(f"   {icon} {component}: {status}", 
                                "green" if status == "healthy" else "red")
                return True
            else:
                colored_print(f"⚠️  System degraded: {health['status']}", "yellow")
                return False
        else:
            colored_print(f"❌ Health check failed: {response.status_code}", "red")
            return False
    except Exception as e:
        colored_print(f"❌ Cannot connect to API: {e}", "red")
        return False

def test_client_creation():
    """Test client creation"""
    print("\n2. Testing Client Creation...")
    try:
        data = {
            "name": f"Test Client {datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "reference_code": f"TEST-{int(time.time())}"
        }
        response = requests.post(f"{API_URL}/v1/clients", json=data)
        
        if response.status_code == 200:
            client = response.json()
            colored_print(f"✅ Created client: ID={client['id']}, Name={client['name']}", "green")
            return client["id"]
        else:
            colored_print(f"❌ Failed to create client: {response.text}", "red")
            return None
    except Exception as e:
        colored_print(f"❌ Error creating client: {e}", "red")
        return None

def test_case_creation(client_id):
    """Test case creation"""
    print("\n3. Testing Case Creation...")
    try:
        data = {
            "client_id": client_id,
            "name": f"Test Case {datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "description": "Automated test case"
        }
        response = requests.post(f"{API_URL}/v1/cases", json=data)
        
        if response.status_code == 200:
            case = response.json()
            colored_print(f"✅ Created case: ID={case['id']}, Name={case['name']}", "green")
            return case["id"]
        else:
            colored_print(f"❌ Failed to create case: {response.text}", "red")
            return None
    except Exception as e:
        colored_print(f"❌ Error creating case: {e}", "red")
        return None

def test_run_creation(case_id):
    """Test run creation"""
    print("\n4. Testing Run Creation...")
    try:
        data = {
            "case_id": case_id,
            "provider": "openrouter",
            "model": "meta-llama/llama-3.3-70b-instruct",
            "file_count": 1
        }
        response = requests.post(f"{API_URL}/v1/runs", json=data)
        
        if response.status_code == 200:
            run = response.json()
            colored_print(f"✅ Created run: ID={run['run_id']}, Status={run['status']}", "green")
            colored_print(f"   Upload URLs: {len(run['upload_urls'])} generated", "blue")
            return run["run_id"]
        else:
            colored_print(f"❌ Failed to create run: {response.text}", "red")
            return None
    except Exception as e:
        colored_print(f"❌ Error creating run: {e}", "red")
        return None

def test_run_status(run_id):
    """Test run status endpoint"""
    print("\n5. Testing Run Status...")
    try:
        response = requests.get(f"{API_URL}/v1/runs/{run_id}")
        
        if response.status_code == 200:
            run = response.json()
            colored_print(f"✅ Run status retrieved: {run['status']}", "green")
            colored_print(f"   Documents: {run['counts']}", "blue")
            return True
        else:
            colored_print(f"❌ Failed to get run status: {response.text}", "red")
            return False
    except Exception as e:
        colored_print(f"❌ Error getting run status: {e}", "red")
        return False

def test_models_endpoint():
    """Test models catalog endpoint"""
    print("\n6. Testing Models Catalog...")
    try:
        response = requests.get(f"{API_URL}/v1/models")
        
        if response.status_code == 200:
            models = response.json()
            colored_print(f"✅ Models catalog retrieved: {len(models['models'])} models", "green")
            for model in models['models'][:3]:  # Show first 3
                colored_print(f"   • {model['provider']}: {model['display_name']}", "blue")
            return True
        else:
            colored_print(f"❌ Failed to get models: {response.text}", "red")
            return False
    except Exception as e:
        colored_print(f"❌ Error getting models: {e}", "red")
        return False

def test_database_connection():
    """Test database by listing clients"""
    print("\n7. Testing Database Connection...")
    try:
        response = requests.get(f"{API_URL}/v1/clients")
        
        if response.status_code == 200:
            clients = response.json()
            colored_print(f"✅ Database connected: {len(clients)} clients found", "green")
            return True
        else:
            colored_print(f"❌ Database error: {response.text}", "red")
            return False
    except Exception as e:
        colored_print(f"❌ Error testing database: {e}", "red")
        return False

def run_all_tests():
    """Run all tests"""
    colored_print("\n" + "="*60, "blue")
    colored_print("       Legal Events v2 - System Test Suite", "blue")
    colored_print("="*60, "blue")
    
    # Track results
    results = []
    
    # Run tests
    results.append(("Health Check", test_health()))
    
    if not results[-1][1]:
        colored_print("\n⚠️  API is not responding. Is the system running?", "yellow")
        colored_print("Run: ./start.sh start", "yellow")
        return False
    
    results.append(("Database", test_database_connection()))
    
    # Create test data
    client_id = test_client_creation()
    results.append(("Client Creation", client_id is not None))
    
    if client_id:
        case_id = test_case_creation(client_id)
        results.append(("Case Creation", case_id is not None))
        
        if case_id:
            run_id = test_run_creation(case_id)
            results.append(("Run Creation", run_id is not None))
            
            if run_id:
                results.append(("Run Status", test_run_status(run_id)))
    
    results.append(("Models Catalog", test_models_endpoint()))
    
    # Summary
    colored_print("\n" + "="*60, "blue")
    colored_print("                    Test Summary", "blue")
    colored_print("="*60, "blue")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        icon = "✅" if result else "❌"
        color = "green" if result else "red"
        colored_print(f"{icon} {test_name}: {'PASSED' if result else 'FAILED'}", color)
    
    colored_print("\n" + "-"*60, "blue")
    success_rate = (passed / total) * 100
    
    if success_rate == 100:
        colored_print(f"🎉 All tests passed! ({passed}/{total})", "green")
    elif success_rate >= 70:
        colored_print(f"⚠️  Most tests passed ({passed}/{total})", "yellow")
    else:
        colored_print(f"❌ Tests failed ({passed}/{total})", "red")
    
    colored_print("="*60 + "\n", "blue")
    
    return success_rate == 100

if __name__ == "__main__":
    success = run_all_tests()
    
    if success:
        colored_print("✅ System is ready for use!", "green")
        colored_print("\nNext steps:", "blue")
        colored_print("1. Open the web UI: http://localhost:3000", "blue")
        colored_print("2. Check API docs: http://localhost:8000/docs", "blue")
        colored_print("3. View MinIO console: http://localhost:9001", "blue")
        sys.exit(0)
    else:
        colored_print("❌ Some tests failed. Check the errors above.", "red")
        sys.exit(1)
