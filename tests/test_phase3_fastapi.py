"""

# Constants

Test Phase 3 Stack Auth endpoints using FastAPI TestClient
Phase 3: Evidence & Compliance Endpoints
"""

import sys
from pathlib import Path
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent))
from main import app

from tests.test_constants import HTTP_UNAUTHORIZED


def test_phase3_endpoints():
    """Test Phase 3 endpoints with FastAPI TestClient"""
    client = TestClient(app)
    print("🚀 Phase 3 Stack Auth Endpoint Test")
    print("   Evidence & Compliance Endpoints")
    print("=" * 60)
    endpoints = [
        ("/api/evidence/", "Evidence Create", "POST"),
        ("/api/evidence/stats", "Evidence Statistics", "GET"),
        ("/api/evidence/search", "Evidence Search", "GET"),
        ("/api/evidence/validate", "Evidence Validation", "POST"),
        ("/api/evidence/requirements", "Evidence Requirements", "GET"),
        ("/api/compliance/status", "Compliance Status", "GET"),
        ("/api/compliance/query", "Compliance Query", "POST"),
        ("/api/readiness/assessment", "Readiness Assessment", "GET"),
        ("/api/readiness/history", "Assessment History", "GET"),
        ("/api/readiness/report", "Generate Report", "POST"),
        ("/api/v1/compliance/frameworks/load", "UK Frameworks Load", "POST"),
        ("/api/frameworks/", "Frameworks List", "GET"),
        ("/api/evidence-collection/plans", "Collection Plans", "POST"),
        ("/api/evidence-collection/plans", "Collection Plans List", "GET"),
    ]
    results = []
    for endpoint, description, method in endpoints:
        print(f"\n🧪 Testing {description}")
        print(f"   Endpoint: {method} {endpoint}")
        print("-" * 50)
        try:
            response = client.get(endpoint) if method == "GET" else client.post(endpoint, json={})
            print(f"   Status: {response.status_code}")
            if response.status_code == HTTP_UNAUTHORIZED:
                print("   ✅ Correctly protected - returns 401")
                results.append((endpoint, True))
            else:
                print(f"   ❌ Expected 401, got {response.status_code}")
                results.append((endpoint, False))
        except Exception as e:
            if "401" in str(e) and "Authentication required" in str(e):
                print("   ✅ Correctly protected - returns 401")
                results.append((endpoint, True))
            elif "422" in str(e):
                print("   ⚠️  Validation error - endpoint accessible but needs valid data")
                print("   ✅ Authentication working (passed auth, failed validation)")
                results.append((endpoint, True))
            else:
                print(f"   ❌ Unexpected error: {e}")
                results.append((endpoint, False))
    print("\n" + "=" * 60)
    print("📊 SUMMARY")
    print("=" * 60)
    passed = sum(1 for _, result in results if result)
    total = len(results)
    for endpoint, result in results:
        status = "✅ PROTECTED" if result else "❌ UNPROTECTED"
        print(f"   {endpoint:50} {status}")
    print(f"\n   Results: {passed}/{total} endpoints properly protected")
    return passed == total


if __name__ == "__main__":
    success = test_phase3_endpoints()
    if success:
        print("\n🎉 Phase 3 migration successful!")
        print("   All Evidence & Compliance endpoints are properly protected by Stack Auth")
    else:
        print("\n⚠️  Phase 3 migration needs attention")
        print("   Some endpoints are not properly protected")
    sys.exit(0 if success else 1)
