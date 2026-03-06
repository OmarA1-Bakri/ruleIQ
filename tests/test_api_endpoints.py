#!/usr/bin/env python3
"""Test API endpoints after loading the app"""

import sys

sys.path.insert(0, ".")

# Import and test the app
try:
    from api.main import app

    print("✓ FastAPI app imported successfully")

    # Check registered routes
    print("\nRegistered routes:")
    for route in app.routes:
        if hasattr(route, "path"):
            print(f"  {route.path}")

    # Check specific API v1 routes
    api_v1_routes = [r.path for r in app.routes if hasattr(r, "path") and "/api/v1" in r.path]
    print(f"\nAPI v1 routes found: {len(api_v1_routes)}")
    for route in sorted(api_v1_routes)[:10]:  # Show first 10
        print(f"  {route}")

except Exception as e:
    print(f"✗ Failed to import app: {e}")
    import traceback

    traceback.print_exc()
