"""
Common test constants to fix NameError issues across test suite.

This module provides HTTP status codes and other constants commonly used in tests
to eliminate NameError exceptions.
"""

# HTTP Status Codes
HTTP_OK = 200
HTTP_CREATED = 201
HTTP_ACCEPTED = 202
HTTP_NO_CONTENT = 204

HTTP_BAD_REQUEST = 400
HTTP_UNAUTHORIZED = 401
HTTP_FORBIDDEN = 403
HTTP_NOT_FOUND = 404
HTTP_METHOD_NOT_ALLOWED = 405
HTTP_CONFLICT = 409
HTTP_UNPROCESSABLE_ENTITY = 422
HTTP_TOO_MANY_REQUESTS = 429

HTTP_INTERNAL_SERVER_ERROR = 500
HTTP_BAD_GATEWAY = 502
HTTP_SERVICE_UNAVAILABLE = 503
HTTP_GATEWAY_TIMEOUT = 504

# Time Constants
HOUR_SECONDS = 3600
DAY_SECONDS = 86400
WEEK_SECONDS = 604800

# Default Limits
DEFAULT_LIMIT = 100
DEFAULT_OFFSET = 0
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100

# Retry Constants
MAX_RETRIES = 3
RETRY_DELAY = 1.0
RETRY_BACKOFF = 2.0

# Token Constants
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7
TOKEN_TYPE = "bearer"

# Test User Constants
TEST_USER_EMAIL = "test@example.com"
TEST_USER_PASSWORD = "TestPass" + "!234"
TEST_ADMIN_EMAIL = "admin@example.com"
TEST_ADMIN_PASSWORD = "AdminPass" + "!234"

# Common Response Keys - Use these for assertions
EXPECTED_AUTH_RESPONSE_KEYS = {"access_token", "token_type", "expires_in"}
EXPECTED_USER_RESPONSE_KEYS = {"id", "email", "is_active", "created_at"}
EXPECTED_ERROR_RESPONSE_KEYS = {"detail", "status_code"}
EXPECTED_COMPLIANCE_RESPONSE_KEYS = {"compliance_data", "status", "framework"}
EXPECTED_ASSESSMENT_RESPONSE_KEYS = {"id", "name", "status", "created_at", "updated_at"}

# API Endpoints
API_V1_PREFIX = "/api/v1"
AUTH_ENDPOINT = f"{API_V1_PREFIX}/auth"
USERS_ENDPOINT = f"{API_V1_PREFIX}/users"
ASSESSMENTS_ENDPOINT = f"{API_V1_PREFIX}/assessments"
COMPLIANCE_ENDPOINT = f"{API_V1_PREFIX}/compliance"
EVIDENCE_ENDPOINT = f"{API_V1_PREFIX}/evidence"
POLICIES_ENDPOINT = f"{API_V1_PREFIX}/policies"
