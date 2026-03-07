"""Direct test of analytics endpoints."""

import traceback
import sys
import os

from tests.test_constants import HTTP_OK

# Constants

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["DATABASE_URL"] = "sqlite:///./test.db"
os.environ["TESTING"] = "true"
try:
    from tests.conftest import (
        client,
        authenticated_headers,
        sample_user,
        sample_business_profile,
        db_session,
    )
    from unittest.mock import AsyncMock, patch
    import pytest

    @pytest.fixture(scope="module")
    def event_loop():
        import asyncio

        loop = asyncio.get_event_loop_policy().new_event_loop()
        yield loop
        loop.close()

    def test_analytics_dashboard():
        print("Creating test fixtures...")
        from _pytest.config import get_config
        from _pytest.fixtures import FixtureManager

        config = get_config()
        from tests.conftest import TestSessionLocal

        session = TestSessionLocal()
        from tests.conftest import sample_user as create_user

        user = create_user(session)
        print(f"Created user: {user.email}")
        from tests.conftest import auth_token as create_token

        token = create_token(user)
        headers = {"Authorization": f"Bearer {token}"}
        print("Created auth headers")
        from tests.conftest import client as create_client

        test_client = create_client(session, user)
        print("\nTesting analytics dashboard endpoint...")
        with patch("services.ai.analytics_monitor.get_analytics_monitor") as mock_monitor:
            mock_instance = AsyncMock()
            mock_instance.get_dashboard_data.return_value = {
                "real_time": {"test": "data"},
                "usage_analytics": {},
                "cost_analytics": {},
                "quality_metrics": {},
                "system_health": {},
            }
            mock_monitor.return_value = mock_instance
            response = test_client.get("/api/chat/analytics/dashboard", headers=headers)
            print(f"Response status: {response.status_code}")
            print(f"Response headers: {dict(response.headers)}")
            if response.status_code != HTTP_OK:
                print(f"Response content: {response.text}")
            else:
                print("Success! Response data keys:", list(response.json().keys()))
            assert response.status_code == HTTP_OK
            data = response.json()
            assert "real_time" in data
            print("\nTest passed!")
        session.close()

    if __name__ == "__main__":
        test_analytics_dashboard()
except Exception as e:
    print(f"\nError: {type(e).__name__}: {e}")
    traceback.print_exc()
