"""

Authentication utilities for testing.
"""

import uuid
from datetime import timedelta
from typing import Optional, Dict, Any

import pytest

from database.user import User
from api.dependencies.auth import oauth2_scheme, create_access_token


class TestAuthManager:
    """Manages authentication for tests."""

    @pytest.fixture(autouse=True)
    def setup_method(self):
        """Set up test auth manager before each test method."""
        self.test_users = {}
        self.active_tokens = {}
        self.blacklisted_tokens = set()

    def create_test_user(
        self,
        email: str = "test@example.com",
        user_id: Optional[str] = None,
        is_active: bool = True,
    ) -> User:
        """Create a test user."""
        if user_id is None:
            user_id = str(uuid.uuid4())

        user = User(
            id=user_id,
            email=email,
            hashed_password="fake_password_hash",
            is_active=is_active,
        )

        self.test_users[user_id] = user
        return user

    def create_test_token(self, user: User, expires_delta: Optional[timedelta] = None) -> str:
        """Create a test JWT token."""
        if expires_delta is None:
            expires_delta = timedelta(minutes=30)

        token_data = {"sub": str(user.id)}
        token = create_access_token(data=token_data, expires_delta=expires_delta)

        self.active_tokens[token] = user
        return token

    def blacklist_token(self, token: str):
        """Blacklist a token."""
        self.blacklisted_tokens.add(token)
        if token in self.active_tokens:
            del self.active_tokens[token]

    def is_token_blacklisted(self, token: str) -> bool:
        """Check if token is blacklisted."""
        return token in self.blacklisted_tokens

    def get_user_from_token(self, token: str) -> Optional[User]:
        """Get user from token."""
        if token in self.blacklisted_tokens:
            return None
        return self.active_tokens.get(token)

    def clear_all(self):
        """Clear all test data."""
        self.test_users.clear()
        self.active_tokens.clear()
        self.blacklisted_tokens.clear()


# Create a class for the global auth manager that doesn't have __init__
class GlobalTestAuthManager:
    """Global test auth manager for utility functions."""

    def __init__(self):
        """Initialize the global auth manager."""
        self.test_users = {}
        self.active_tokens = {}
        self.blacklisted_tokens = set()

    def create_test_user(
        self,
        email: str = "test@example.com",
        user_id: Optional[str] = None,
        is_active: bool = True,
    ) -> User:
        """Create a test user."""
        if user_id is None:
            user_id = str(uuid.uuid4())

        user = User(
            id=user_id,
            email=email,
            hashed_password="fake_password_hash",
            is_active=is_active,
        )

        self.test_users[user_id] = user
        return user

    def create_test_token(self, user: User, expires_delta: Optional[timedelta] = None) -> str:
        """Create a test JWT token."""
        if expires_delta is None:
            expires_delta = timedelta(minutes=30)

        token_data = {"sub": str(user.id)}
        token = create_access_token(data=token_data, expires_delta=expires_delta)

        self.active_tokens[token] = user
        return token

    def blacklist_token(self, token: str):
        """Blacklist a token."""
        self.blacklisted_tokens.add(token)
        if token in self.active_tokens:
            del self.active_tokens[token]

    def is_token_blacklisted(self, token: str) -> bool:
        """Check if token is blacklisted."""
        return token in self.blacklisted_tokens

    def get_user_from_token(self, token: str) -> Optional[User]:
        """Get user from token."""
        if token in self.blacklisted_tokens:
            return None
        return self.active_tokens.get(token)

    def clear_all(self):
        """Clear all test data."""
        self.test_users.clear()
        self.active_tokens.clear()
        self.blacklisted_tokens.clear()


# Global test auth manager
_test_auth_manager = GlobalTestAuthManager()


def get_test_auth_manager() -> GlobalTestAuthManager:
    """Get the global test auth manager."""
    return _test_auth_manager


def override_get_current_user() -> User:
    """Override for get_current_user in tests."""
    # Always return test user for tests - ignore token validation
    # Use synchronous version to avoid event loop conflicts with TestClient
    user = _test_auth_manager.create_test_user()
    return user


def override_get_current_active_user() -> User:
    """Override for get_current_active_user in tests."""
    # Always return active test user for tests
    # Use synchronous version to avoid event loop conflicts with TestClient
    user = _test_auth_manager.create_test_user()
    return user


def create_auth_headers(user: Optional[User] = None) -> Dict[str, str]:
    """Create authentication headers for tests."""
    if user is None:
        user = _test_auth_manager.create_test_user()

    token = _test_auth_manager.create_test_token(user)
    return {"Authorization": f"Bearer {token}"}


def create_test_user_with_permissions() -> User:
    """Create test user with specific permissions."""
    return _test_auth_manager.create_test_user()


def setup_auth_mocks():
    """Set up authentication mocks for tests."""
    # Mock AI services to prevent external API calls
    import unittest.mock

    # Mock Google Generative AI
    mock_genai = unittest.mock.MagicMock()
    mock_response = unittest.mock.MagicMock()
    mock_response.text = "Mock AI response for testing"
    mock_response.parts = [unittest.mock.MagicMock()]
    mock_response.parts[0].text = "Mock AI response for testing"

    mock_model = unittest.mock.MagicMock()
    mock_model.generate_content.return_value = mock_response
    mock_genai.GenerativeModel.return_value = mock_model

    # Apply mocks
    import sys

    sys.modules["google.generativeai"] = mock_genai
    sys.modules["google.generativeai.types"] = unittest.mock.MagicMock()

    return mock_genai


def cleanup_auth_mocks():
    """Clean up authentication mocks."""
    _test_auth_manager.clear_all()


# Context manager for test authentication
class TestAuthContext:
    """Context manager for test authentication setup."""

    def __init__(self, app, user: Optional[User] = None):
        self.app = app
        self.user = user or _test_auth_manager.create_test_user()
        self.original_overrides = {}

    def __enter__(self):
        """Enter context and set up auth overrides."""
        from api.dependencies.auth import get_current_user, get_current_active_user
        from database.db_setup import get_async_db

        # Store original overrides
        self.original_overrides = self.app.dependency_overrides.copy()

        # Set up auth overrides
        self.app.dependency_overrides[get_current_user] = lambda: self.user
        self.app.dependency_overrides[get_current_active_user] = lambda: self.user

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context and restore original overrides."""
        # Restore original overrides
        self.app.dependency_overrides.clear()
        self.app.dependency_overrides.update(self.original_overrides)


def with_test_auth(app, user: Optional[User] = None):
    """Context manager for test authentication."""
    return TestAuthContext(app, user)
