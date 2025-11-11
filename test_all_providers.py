#!/usr/bin/env python3
"""
Test All Provider Combinations
Tests OpenRouter, OpenAI, and Anthropic providers with a real PDF file
"""
import requests
import time
import json
from pathlib import Path

# Configuration
API_BASE = "http://localhost:8000"
TEST_FILE = "test_documents/amrapali_allotment_letter.pdf"
PROVIDERS = [
    {"id": "openrouter", "model": "meta-llama/llama-3.3-70b-instruct"},
    {"id": "openai", "model": "gpt-4o-mini"},
    {"id": "anthropic", "model": "claude-3-5-haiku-20241022"}
]

# Auth headers (will be set after login)
AUTH_HEADERS = {}

def print_section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")

def register_user():
    """Register a new test user"""
    print("📝 Registering new test user...")
    try:
        response = requests.post(
            f"{API_BASE}/v1/auth/register",
            json={
                "email": "test@localhost",
                "name": "Test User",
                "password": "test123"
            }
        )

        if response.status_code in [200, 201]:
            print("✅ User registered successfully")
            return True
        elif response.status_code == 400:
            print("ℹ️ User already exists")
            return True
    except Exception as e:
        print(f"⚠️ Registration failed: {e}")

    return False

def login():
    """Authenticate and get access token"""
    print("🔐 Authenticating...")

    # Register user first (in case it doesn't exist)
    register_user()

    # Try default test user credentials
    credentials = [
        {"email": "test@localhost", "password": "test123"},
        {"email": "dev@localhost", "password": "devpass123"},
        {"email": "admin@localhost", "password": "admin123"}
    ]

    for cred in credentials:
        try:
            response = requests.post(
                f"{API_BASE}/v1/auth/login",
                json=cred  # Use JSON, not form data
            )

            if response.status_code == 200:
                token = response.json()["access_token"]
                AUTH_HEADERS["Authorization"] = f"Bearer {token}"
                print(f"✅ Logged in as: {cred['email']}")
                return True
            else:
                print(f"⚠️ Login failed for {cred['email']}: {response.status_code} - {response.text[:100]}")
        except Exception as e:
            print(f"⚠️ Login attempt failed for {cred['email']}: {e}")
            continue

    # No authentication - try without
    print("❌ Authentication failed - cannot proceed with write operations")
    return False

def create_client():
    """Create a test client"""
    print("📝 Creating test client...")
    response = requests.post(
        f"{API_BASE}/v1/clients",
        json={
            "name": "Provider Test Client",
            "status": "active"
        },
        headers=AUTH_HEADERS
    )
    response.raise_for_status()
    client_id = response.json()["id"]
    print(f"✅ Client created: {client_id}")
    return client_id

def create_case(client_id):
    """Create a test case"""
    print("📁 Creating test case...")
    response = requests.post(
        f"{API_BASE}/v1/cases",
        json={
            "client_id": client_id,
            "name": f"Provider Comparison Test {int(time.time())}",
            "description": "Testing all 3 LLM providers with real PDF"
        },
        headers=AUTH_HEADERS
    )
    response.raise_for_status()
    case_id = response.json()["id"]
    print(f"✅ Case created: {case_id}")
    return case_id

def upload_document(case_id):
    """Upload test PDF temporarily"""
    print(f"📤 Uploading document: {TEST_FILE}...")

    file_path = Path(TEST_FILE)
    if not file_path.exists():
        raise FileNotFoundError(f"Test file not found: {TEST_FILE}")

    with open(file_path, "rb") as f:
        files = {"files": (file_path.name, f, "application/pdf")}

        response = requests.post(
            f"{API_BASE}/v1/upload",
            files=files,
            headers=AUTH_HEADERS
        )
        response.raise_for_status()

    upload_result = response.json()
    # Response is a list of file objects
    if isinstance(upload_result, list) and len(upload_result) > 0:
        file_id = upload_result[0].get("file_id") or upload_result[0].get("id")
    else:
        file_id = upload_result.get("file_id") or upload_result.get("id")

    print(f"✅ Document uploaded: {file_id}")
    print(f"  Upload response: {upload_result}")
    return file_id

def create_run(case_id, file_id, provider_id, model):
    """Create a processing run"""
    print(f"\n🚀 Creating run for provider: {provider_id} (model: {model})...")

    response = requests.post(
        f"{API_BASE}/v1/runs",
        json={
            "case_id": case_id,
            "provider": provider_id,
            "model": model,
            "file_ids": [file_id]  # Use file_ids for temporary uploads
        },
        headers=AUTH_HEADERS
    )
    response.raise_for_status()

    run_data = response.json()
    run_id = run_data["id"]
    print(f"✅ Run created: {run_id}")
    return run_id

def wait_for_run(run_id, timeout=300):
    """Wait for run to complete"""
    print(f"⏳ Waiting for run {run_id} to complete...")

    start_time = time.time()
    while time.time() - start_time < timeout:
        response = requests.get(f"{API_BASE}/v1/runs/{run_id}")
        response.raise_for_status()

        run = response.json()
        status = run["status"]

        if status in ["completed", "success", "partial"]:
            elapsed = time.time() - start_time
            print(f"✅ Run completed in {elapsed:.1f}s with status: {status}")
            return run
        elif status == "failed":
            print(f"❌ Run failed: {run.get('error_message', 'Unknown error')}")
            return run

        time.sleep(2)

    print(f"⏰ Timeout after {timeout}s")
    return None

def get_events(run_id):
    """Get extracted events"""
    response = requests.get(f"{API_BASE}/v1/runs/{run_id}/events")
    response.raise_for_status()
    return response.json()

def run_test():
    """Main test orchestrator"""
    print_section("Provider Comparison Test - v0.11.0")

    print(f"Testing {len(PROVIDERS)} providers:")
    for p in PROVIDERS:
        print(f"  • {p['id']} ({p['model']})")

    # Authenticate
    print_section("Authentication")
    login()

    # Setup
    print_section("Setup Phase")
    client_id = create_client()
    case_id = create_case(client_id)
    file_id = upload_document(case_id)

    # Test each provider
    results = []

    for provider in PROVIDERS:
        print_section(f"Testing {provider['id'].upper()}")

        try:
            # Create and run
            run_id = create_run(case_id, file_id, provider["id"], provider["model"])
            run_result = wait_for_run(run_id)

            if run_result:
                # Get events
                events_data = get_events(run_id)
                event_count = len(events_data.get("events", []))

                results.append({
                    "provider": provider["id"],
                    "model": provider["model"],
                    "status": run_result["status"],
                    "event_count": event_count,
                    "run_id": run_id,
                    "success": run_result["status"] in ["completed", "success", "partial"]
                })

                print(f"📊 Extracted {event_count} events")
            else:
                results.append({
                    "provider": provider["id"],
                    "model": provider["model"],
                    "status": "timeout",
                    "event_count": 0,
                    "run_id": run_id,
                    "success": False
                })

        except Exception as e:
            print(f"❌ Error: {e}")
            results.append({
                "provider": provider["id"],
                "model": provider["model"],
                "status": "error",
                "error": str(e),
                "event_count": 0,
                "success": False
            })

    # Summary
    print_section("Test Results Summary")

    print(f"{'Provider':<15} {'Model':<40} {'Status':<12} {'Events':<8} {'Result'}")
    print("-" * 100)

    for r in results:
        result_icon = "✅" if r["success"] else "❌"
        print(f"{r['provider']:<15} {r['model']:<40} {r['status']:<12} {r['event_count']:<8} {result_icon}")

    # Success rate
    success_count = sum(1 for r in results if r["success"])
    total_count = len(results)
    success_rate = (success_count / total_count) * 100 if total_count > 0 else 0

    print(f"\n📈 Success Rate: {success_count}/{total_count} ({success_rate:.0f}%)")

    # Save results
    results_file = f"test_results_{int(time.time())}.json"
    with open(results_file, "w") as f:
        json.dump({
            "test_file": TEST_FILE,
            "client_id": client_id,
            "case_id": case_id,
            "file_id": file_id,
            "results": results
        }, f, indent=2)

    print(f"\n💾 Results saved to: {results_file}")

    if success_count == total_count:
        print("\n🎉 All providers working successfully!")
        return 0
    else:
        print(f"\n⚠️ {total_count - success_count} provider(s) failed")
        return 1

if __name__ == "__main__":
    try:
        exit_code = run_test()
        exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n⚠️ Test interrupted by user")
        exit(130)
    except Exception as e:
        print(f"\n\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
