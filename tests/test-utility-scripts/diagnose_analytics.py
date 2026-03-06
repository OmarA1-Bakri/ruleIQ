"""Diagnose analytics endpoint issue."""

import logging

# Constants
HTTP_OK = 200

logger = logging.getLogger(__name__)
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from unittest.mock import AsyncMock, patch
from tests.test_app import create_test_app
from fastapi.testclient import TestClient
from tests.conftest import TEST_USER_ID
from database.user import User

app = create_test_app()
with TestClient(app) as client:
    logger.info("Testing direct endpoint access:")
    response = client.get("/api/chat/analytics/dashboard")
    logger.info(
        "Without auth - Status: %s, Response: %s" % (response.status_code, response.text[:200])
    )

    def override_get_current_user():
        return User(id=TEST_USER_ID, email="test@example.com", is_active=True)

    from api.dependencies.auth import get_current_user

    app.dependency_overrides[get_current_user] = override_get_current_user
    with patch("services.ai.analytics_monitor.get_analytics_monitor") as mock_monitor:
        mock_instance = AsyncMock()
        mock_instance.get_dashboard_data.return_value = {"test": "data"}
        mock_monitor.return_value = mock_instance
        response = client.get("/api/chat/analytics/dashboard")
        logger.info("\nWith auth and mock - Status: %s" % response.status_code)
        if response.status_code != HTTP_OK:
            logger.info("Response: %s" % response.text)
        else:
            logger.info("Success!")
        logger.info("Mock called: %s" % mock_monitor.called)
        if mock_monitor.called:
            logger.info(
                "Mock instance get_dashboard_data called: %s"
                % mock_instance.get_dashboard_data.called
            )
