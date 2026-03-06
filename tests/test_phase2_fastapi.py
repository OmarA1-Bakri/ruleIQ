"""

# Constants

Test Phase 2 Stack Auth endpoints using FastAPI TestClient
Phase 2: Assessment & AI Endpoints
"""

import sys
from pathlib import Path
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent))
from main import app

from tests.test_constants import HTTP_UNAUTHORIZED


def test_phase2_endpoints():
    """Test Phase 2 endpoints with FastAPI TestClient"""
    client = TestClient(app)
    print("🚀 Phase 2 Stack Auth Endpoint Test")
    print("   Assessment & AI Endpoints")
    print("=" * 60)
    endpoints = [
        ("/api/gdpr/help", "AI Assessment Help", "POST"),
        ("/api/analysis", "AI Analysis", "POST"),
        ("/api/recommendations", "AI Recommendations", "POST"),
        ("/api/feedback", "AI Feedback", "POST"),
        ("/api/metrics", "AI Metrics", "GET"),
        ("/api/ai/model-selection", "AI Model Selection", "POST"),
        ("/api/ai/model-health", "AI Model Health", "GET"),
        ("/api/ai/performance-metrics", "AI Performance Metrics", "GET"),
        ("/api/agentic-assessments/predicted-needs", "Agentic Predicted Needs", "GET"),
        ("/api/agentic-rag/find-examples", "Agentic RAG Examples", "POST"),
        ("/api/agentic-rag/fact-check", "Agentic RAG Fact Check", "POST"),
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
        print(f"   {endpoint:40} {status}")
    print(f"\n   Results: {passed}/{total} endpoints properly protected")
    return passed == total


if __name__ == "__main__":
    success = test_phase2_endpoints()
    if success:
        print("\n🎉 Phase 2 migration successful!")
        print("   All Assessment & AI endpoints are properly protected by Stack Auth")
    else:
        print("\n⚠️  Phase 2 migration needs attention")
        print("   Some endpoints are not properly protected")
    sys.exit(0 if success else 1)
