"""
Comprehensive mock fixtures for all external services.
Task 799f27b3: Fix failing fixtures & mocks.
Provides mocks for all external APIs to ensure test isolation.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import json
from typing import Dict, Any, Optional


# ==================== AI Service Mocks ====================


@pytest.fixture
def mock_openai():
    """Mock OpenAI API client."""
    mock = MagicMock()

    # Mock chat completions
    mock.chat.completions.create = MagicMock()
    mock.chat.completions.create.return_value = MagicMock(
        choices=[
            MagicMock(
                message=MagicMock(
                    content="This is a mock OpenAI response for compliance analysis.",
                    role="assistant",
                ),
                finish_reason="stop",
            )
        ],
        usage=MagicMock(prompt_tokens=100, completion_tokens=50, total_tokens=150),
        model="gpt-4",
        id="mock-response-id",
    )

    # Mock embeddings
    mock.embeddings.create = MagicMock()
    mock.embeddings.create.return_value = MagicMock(
        data=[
            MagicMock(
                embedding=[0.1, 0.2, 0.3] * 512  # Mock 1536-dim embedding
            )
        ],
        usage=MagicMock(total_tokens=10),
    )

    return mock


@pytest.fixture
def mock_anthropic():
    """Mock Anthropic Claude API client."""
    mock = MagicMock()

    mock.messages.create = MagicMock()
    mock.messages.create.return_value = MagicMock(
        content=[
            MagicMock(
                text="This is a mock Claude response for compliance requirements.", type="text"
            )
        ],
        id="mock-message-id",
        model="claude-3-opus-20240229",
        role="assistant",
        stop_reason="end_turn",
        usage=MagicMock(input_tokens=100, output_tokens=50),
    )

    # Async version
    mock.messages.create_async = AsyncMock()
    mock.messages.create_async.return_value = mock.messages.create.return_value

    return mock


@pytest.fixture
def mock_google_ai():
    """Mock Google Gemini AI client."""
    mock = MagicMock()

    # Mock model
    mock_model = MagicMock()
    mock_model.generate_content = MagicMock()
    mock_model.generate_content.return_value = MagicMock(
        text="This is a mock Gemini response for compliance framework analysis.",
        parts=[MagicMock(text="This is a mock Gemini response for compliance framework analysis.")],
        candidates=[
            MagicMock(
                content=MagicMock(
                    parts=[
                        MagicMock(
                            text="This is a mock Gemini response for compliance framework analysis."
                        )
                    ]
                ),
                finish_reason="STOP",
            )
        ],
    )

    # Async version
    mock_model.generate_content_async = AsyncMock()
    mock_model.generate_content_async.return_value = mock_model.generate_content.return_value

    mock.GenerativeModel = MagicMock(return_value=mock_model)

    return mock


# ==================== Email Service Mocks ====================


@pytest.fixture
def mock_sendgrid():
    """Mock SendGrid email service."""
    mock = MagicMock()

    mock.send = MagicMock()
    mock.send.return_value = MagicMock(
        status_code=202, body="", headers={"X-Message-Id": "mock-message-id"}
    )

    return mock


@pytest.fixture
def mock_smtp():
    """Mock SMTP email service."""
    with patch("smtplib.SMTP") as mock_smtp:
        instance = MagicMock()
        mock_smtp.return_value.__enter__.return_value = instance

        instance.starttls = MagicMock()
        instance.login = MagicMock()
        instance.send_message = MagicMock()
        instance.sendmail = MagicMock()
        instance.quit = MagicMock()

        yield instance


# ==================== AWS Service Mocks ====================


@pytest.fixture
def mock_s3():
    """Mock AWS S3 client."""
    mock = MagicMock()

    # Mock bucket operations
    mock.create_bucket = MagicMock(return_value={"Location": "/test-bucket"})
    mock.list_buckets = MagicMock(return_value={"Buckets": []})

    # Mock object operations
    mock.put_object = MagicMock(return_value={"ETag": '"mock-etag"'})
    mock.get_object = MagicMock(
        return_value={
            "Body": MagicMock(read=lambda: b"mock file content"),
            "ContentType": "application/pdf",
            "ContentLength": 1024,
        }
    )
    mock.delete_object = MagicMock(return_value={"DeleteMarker": True})
    mock.list_objects_v2 = MagicMock(return_value={"Contents": []})

    # Mock presigned URLs
    mock.generate_presigned_url = MagicMock(
        return_value="https://s3.amazonaws.com/test-bucket/test-key?signature=mock"
    )
    mock.generate_presigned_post = MagicMock(
        return_value={
            "url": "https://s3.amazonaws.com/test-bucket",
            "fields": {"key": "test-key", "signature": "mock"},
        }
    )

    return mock


@pytest.fixture
def mock_secrets_manager():
    """Mock AWS Secrets Manager client."""
    mock = MagicMock()

    mock.get_secret_value = MagicMock(
        return_value={
            "SecretString": json.dumps(
                {
                    "database_url": "postgresql://test@localhost/test",
                    "jwt_secret": "test-jwt-secret-key",
                    "api_key": "test-api-key",
                }
            ),
            "Name": "test-secret",
            "VersionId": "mock-version-id",
        }
    )

    mock.create_secret = MagicMock(
        return_value={
            "ARN": "arn:aws:secretsmanager:us-east-1:123456789:secret:test",
            "Name": "test-secret",
            "VersionId": "mock-version-id",
        }
    )

    mock.update_secret = MagicMock(
        return_value={
            "ARN": "arn:aws:secretsmanager:us-east-1:123456789:secret:test",
            "Name": "test-secret",
            "VersionId": "mock-version-id-2",
        }
    )

    return mock


@pytest.fixture
def mock_cloudwatch():
    """Mock AWS CloudWatch client."""
    mock = MagicMock()

    mock.put_metric_data = MagicMock()
    mock.get_metric_statistics = MagicMock(return_value={"Datapoints": [], "Label": "TestMetric"})
    mock.put_metric_alarm = MagicMock()
    mock.describe_alarms = MagicMock(return_value={"MetricAlarms": []})

    return mock


# ==================== Payment Service Mocks ====================


@pytest.fixture
def mock_stripe():
    """Mock Stripe payment service."""
    mock = MagicMock()

    # Mock customer operations
    mock.Customer.create = MagicMock(
        return_value=MagicMock(id="cus_mock123", email="test@example.com", created=1234567890)
    )

    # Mock payment intent
    mock.PaymentIntent.create = MagicMock(
        return_value=MagicMock(
            id="pi_mock123",
            amount=1000,
            currency="usd",
            status="requires_payment_method",
            client_secret="pi_mock123_secret_mock",
        )
    )

    # Mock subscription
    mock.Subscription.create = MagicMock(
        return_value=MagicMock(
            id="sub_mock123", customer="cus_mock123", status="active", current_period_end=1234567890
        )
    )

    # Mock webhook
    mock.Webhook.construct_event = MagicMock(
        return_value={"type": "payment_intent.succeeded", "data": {"object": {"id": "pi_mock123"}}}
    )

    return mock


# ==================== OAuth Service Mocks ====================


@pytest.fixture
def mock_google_oauth():
    """Mock Google OAuth client."""
    mock = MagicMock()

    # Mock OAuth flow
    mock.Flow.from_client_config = MagicMock()
    flow_instance = MagicMock()
    flow_instance.authorization_url = MagicMock(
        return_value=("https://accounts.google.com/oauth/authorize?mock=true", "mock-state")
    )
    flow_instance.fetch_token = MagicMock(
        return_value={
            "access_token": "mock-access-token",
            "refresh_token": "mock-refresh-token",
            "token_type": "Bearer",
            "expires_in": 3600,
        }
    )
    mock.Flow.from_client_config.return_value = flow_instance

    # Mock ID token verification
    mock.id_token.verify_oauth2_token = MagicMock(
        return_value={
            "sub": "mock-user-id",
            "email": "test@example.com",
            "email_verified": True,
            "name": "Test User",
            "picture": "https://example.com/photo.jpg",
        }
    )

    return mock


# ==================== Database/Cache Mocks ====================


@pytest.fixture
def mock_neo4j():
    """Mock Neo4j graph database driver."""
    mock = MagicMock()

    # Mock session
    session = MagicMock()
    session.run = MagicMock(
        return_value=MagicMock(
            data=MagicMock(return_value=[{"id": 1, "name": "Test Node", "properties": {}}])
        )
    )
    session.close = MagicMock()

    # Mock transaction
    tx = MagicMock()
    tx.run = session.run
    session.begin_transaction = MagicMock(return_value=tx)

    mock.session = MagicMock(return_value=session)
    mock.close = MagicMock()

    return mock


@pytest.fixture
def mock_elasticsearch():
    """Mock Elasticsearch client."""
    mock = MagicMock()

    # Mock index operations
    mock.index = MagicMock(
        return_value={"_index": "test-index", "_id": "mock-id", "_version": 1, "result": "created"}
    )

    # Mock search
    mock.search = MagicMock(
        return_value={"hits": {"total": {"value": 0, "relation": "eq"}, "hits": []}}
    )

    # Mock bulk operations
    mock.bulk = MagicMock(return_value={"took": 5, "errors": False, "items": []})

    return mock


# ==================== Monitoring Service Mocks ====================


@pytest.fixture
def mock_sentry():
    """Mock Sentry error tracking."""
    with patch("sentry_sdk.init") as mock_init:
        with patch("sentry_sdk.capture_exception") as mock_capture:
            with patch("sentry_sdk.capture_message") as mock_message:
                yield {
                    "init": mock_init,
                    "capture_exception": mock_capture,
                    "capture_message": mock_message,
                }


@pytest.fixture
def mock_datadog():
    """Mock Datadog monitoring."""
    mock = MagicMock()

    # Mock metrics
    mock.statsd.increment = MagicMock()
    mock.statsd.decrement = MagicMock()
    mock.statsd.gauge = MagicMock()
    mock.statsd.histogram = MagicMock()
    mock.statsd.timing = MagicMock()

    # Mock APM
    mock.tracer.trace = MagicMock()
    mock.tracer.current_span = MagicMock()

    return mock


# ==================== External API Mocks ====================


@pytest.fixture
def mock_http_client():
    """Mock HTTP client for external API calls."""
    mock = MagicMock()

    # Default successful response
    mock.get = MagicMock(
        return_value=MagicMock(
            status_code=200,
            json=lambda: {"status": "success", "data": {}},
            text='{"status": "success"}',
            headers={"Content-Type": "application/json"},
        )
    )

    mock.post = MagicMock(
        return_value=MagicMock(
            status_code=201,
            json=lambda: {"id": "mock-id", "status": "created"},
            text='{"id": "mock-id"}',
            headers={"Content-Type": "application/json"},
        )
    )

    mock.put = MagicMock(
        return_value=MagicMock(
            status_code=200,
            json=lambda: {"status": "updated"},
            text='{"status": "updated"}',
            headers={"Content-Type": "application/json"},
        )
    )

    mock.delete = MagicMock(return_value=MagicMock(status_code=204, text="", headers={}))

    return mock


@pytest.fixture
def mock_webhook_client():
    """Mock webhook client for external notifications."""
    mock = MagicMock()

    mock.send = MagicMock(
        return_value=MagicMock(
            status_code=200, json=lambda: {"delivered": True}, text='{"delivered": true}'
        )
    )

    mock.verify_signature = MagicMock(return_value=True)

    return mock


# ==================== Celery/Background Task Mocks ====================


@pytest.fixture
def mock_celery_task():
    """Mock Celery task execution."""
    mock = MagicMock()

    mock.delay = MagicMock(return_value=MagicMock(id="mock-task-id", state="PENDING", result=None))

    mock.apply_async = MagicMock(
        return_value=MagicMock(id="mock-task-id", state="PENDING", result=None)
    )

    mock.apply = MagicMock(
        return_value=MagicMock(id="mock-task-id", state="SUCCESS", result={"status": "completed"})
    )

    return mock


# ==================== File Storage Mocks ====================


@pytest.fixture
def mock_file_storage():
    """Mock file storage operations."""
    mock = MagicMock()

    mock.save = MagicMock(return_value="path/to/saved/file.pdf")
    mock.load = MagicMock(return_value=b"mock file content")
    mock.delete = MagicMock(return_value=True)
    mock.exists = MagicMock(return_value=True)
    mock.list_files = MagicMock(return_value=["file1.pdf", "file2.docx"])
    mock.get_url = MagicMock(return_value="https://storage.example.com/file.pdf")

    return mock


# ==================== Auto-patching Fixture ====================


@pytest.fixture(autouse=True)
def auto_mock_external_services(monkeypatch):
    """
    Automatically mock all external services for all tests.
    This ensures no test accidentally makes real external API calls.
    """
    # Mock environment variables for external services
    monkeypatch.setenv("DISABLE_EXTERNAL_SERVICES", "true")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("GOOGLE_AI_API_KEY", "test-key")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test-key")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test-secret")
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_mock")
    monkeypatch.setenv("SENDGRID_API_KEY", "test-key")
    monkeypatch.setenv("SENTRY_DSN", "")  # Disable Sentry in tests

    # Patch common external service imports
    with patch("openai.OpenAI") as mock_openai:
        with patch("anthropic.Anthropic") as mock_anthropic:
            with patch("config.ai_config.AIConfig.get_model") as mock_gemini:
                with patch("boto3.client") as mock_boto:
                    with patch("stripe.api_key") as mock_stripe_key:
                        # Set up basic returns
                        mock_openai.return_value = MagicMock()
                        mock_anthropic.return_value = MagicMock()
                        mock_gemini.return_value = MagicMock()
                        mock_boto.return_value = MagicMock()
                        mock_stripe_key = "sk_test_mock"

                        yield {
                            "openai": mock_openai,
                            "anthropic": mock_anthropic,
                            "gemini": mock_gemini,
                            "boto": mock_boto,
                            "stripe": mock_stripe_key,
                        }


# ==================== Helper Functions ====================


def create_mock_response(
    status_code: int = 200, json_data: Optional[Dict[str, Any]] = None, text: str = ""
):
    """Helper to create mock HTTP responses."""
    mock_response = MagicMock()
    mock_response.status_code = status_code
    mock_response.text = text or json.dumps(json_data or {})
    mock_response.json = MagicMock(return_value=json_data or {})
    mock_response.headers = {"Content-Type": "application/json"}
    mock_response.raise_for_status = MagicMock()

    if status_code >= 400:
        mock_response.raise_for_status.side_effect = Exception(f"HTTP {status_code} Error")

    return mock_response


def create_mock_async_response(status_code: int = 200, json_data: Optional[Dict[str, Any]] = None):
    """Helper to create mock async HTTP responses."""
    mock_response = AsyncMock()
    mock_response.status = status_code
    mock_response.json = AsyncMock(return_value=json_data or {})
    mock_response.text = AsyncMock(return_value=json.dumps(json_data or {}))
    mock_response.headers = {"Content-Type": "application/json"}

    return mock_response
