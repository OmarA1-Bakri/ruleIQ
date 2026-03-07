"""
Unit tests for services/webhook_verification.py — WebhookVerificationService.

Tests signature generation and provider configuration. Verification tests
use mocked Request objects.
"""

import os
import hmac
import hashlib
import time
import base64
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault("TESTING", "true")
os.environ.setdefault("ENVIRONMENT", "testing")

from services.webhook_verification import WebhookVerificationService


# ---------------------------------------------------------------------------
# Provider Configuration
# ---------------------------------------------------------------------------

class TestProviderConfig:
    """Tests for PROVIDERS class attribute."""

    def test_has_stripe_provider(self):
        assert "stripe" in WebhookVerificationService.PROVIDERS

    def test_has_github_provider(self):
        assert "github" in WebhookVerificationService.PROVIDERS

    def test_has_sendgrid_provider(self):
        assert "sendgrid" in WebhookVerificationService.PROVIDERS

    def test_has_custom_provider(self):
        assert "custom" in WebhookVerificationService.PROVIDERS

    def test_provider_has_required_fields(self):
        for name, config in WebhookVerificationService.PROVIDERS.items():
            assert "header" in config, f"{name} missing 'header'"
            assert "algorithm" in config, f"{name} missing 'algorithm'"
            assert "format" in config, f"{name} missing 'format'"

    def test_stripe_config(self):
        cfg = WebhookVerificationService.PROVIDERS["stripe"]
        assert cfg["header"] == "Stripe-Signature"
        assert cfg["algorithm"] == "sha256"
        assert cfg["format"] == "timestamp_signature"
        assert cfg["tolerance_seconds"] == 300

    def test_github_config(self):
        cfg = WebhookVerificationService.PROVIDERS["github"]
        assert cfg["header"] == "X-Hub-Signature-256"
        assert cfg["format"] == "sha_signature"


# ---------------------------------------------------------------------------
# generate_webhook_signature
# ---------------------------------------------------------------------------

class TestGenerateSignature:
    """Tests for WebhookVerificationService.generate_webhook_signature()."""

    @pytest.mark.asyncio
    async def test_custom_with_timestamp(self):
        svc = WebhookVerificationService()
        sig = await svc.generate_webhook_signature(
            payload="test-payload",
            secret="my-secret",
            provider="custom",
            include_timestamp=True,
        )
        # Should be in format: <timestamp>.<hex>
        parts = sig.split(".")
        assert len(parts) == 2
        assert parts[0].isdigit()
        assert len(parts[1]) == 64  # sha256 hex

    @pytest.mark.asyncio
    async def test_stripe_format(self):
        svc = WebhookVerificationService()
        sig = await svc.generate_webhook_signature(
            payload="test-payload",
            secret="my-secret",
            provider="stripe",
            include_timestamp=True,
        )
        assert sig.startswith("t=")
        assert ",v1=" in sig

    @pytest.mark.asyncio
    async def test_github_format(self):
        svc = WebhookVerificationService()
        sig = await svc.generate_webhook_signature(
            payload="test-payload",
            secret="my-secret",
            provider="github",
            include_timestamp=False,
        )
        assert sig.startswith("sha256=")

    @pytest.mark.asyncio
    async def test_custom_without_timestamp(self):
        svc = WebhookVerificationService()
        sig = await svc.generate_webhook_signature(
            payload="test",
            secret="secret",
            provider="custom",
            include_timestamp=False,
        )
        # Plain hex signature
        assert len(sig) == 64  # sha256 hex
        assert "." not in sig

    @pytest.mark.asyncio
    async def test_signature_is_deterministic(self):
        svc = WebhookVerificationService()
        sig1 = await svc.generate_webhook_signature(
            payload="same",
            secret="same",
            provider="github",
            include_timestamp=False,
        )
        sig2 = await svc.generate_webhook_signature(
            payload="same",
            secret="same",
            provider="github",
            include_timestamp=False,
        )
        assert sig1 == sig2

    @pytest.mark.asyncio
    async def test_different_secrets_produce_different_signatures(self):
        svc = WebhookVerificationService()
        sig1 = await svc.generate_webhook_signature(
            payload="data", secret="secret-a", provider="github", include_timestamp=False
        )
        sig2 = await svc.generate_webhook_signature(
            payload="data", secret="secret-b", provider="github", include_timestamp=False
        )
        assert sig1 != sig2


# ---------------------------------------------------------------------------
# verify_webhook — unknown provider
# ---------------------------------------------------------------------------

class TestVerifyWebhookUnknown:
    """Tests for verify_webhook with unknown provider."""

    @pytest.mark.asyncio
    async def test_unknown_provider(self):
        svc = WebhookVerificationService()
        mock_request = MagicMock()
        mock_request.headers = {}
        is_valid, error = await svc.verify_webhook(mock_request, provider="nonexistent")
        assert is_valid is False
        assert "Unknown" in error

    @pytest.mark.asyncio
    async def test_missing_signature_header(self):
        svc = WebhookVerificationService()
        mock_request = MagicMock()
        mock_request.headers = {}
        is_valid, error = await svc.verify_webhook(
            mock_request, provider="github", secret="test"
        )
        assert is_valid is False
        assert "Missing signature" in error


# ---------------------------------------------------------------------------
# _verify_sha_signature (GitHub format)
# ---------------------------------------------------------------------------

class TestVerifyShaSignature:
    """Tests for _verify_sha_signature (GitHub format)."""

    @pytest.mark.asyncio
    async def test_valid_github_signature(self):
        svc = WebhookVerificationService()
        payload = b'{"action": "push"}'
        secret = "webhook-secret"
        config = WebhookVerificationService.PROVIDERS["github"]

        expected_sig = hmac.new(
            secret.encode("utf-8"), payload, hashlib.sha256
        ).hexdigest()
        signature_header = f"sha256={expected_sig}"

        is_valid, error = await svc._verify_sha_signature(
            payload, signature_header, secret, config
        )
        assert is_valid is True
        assert error is None

    @pytest.mark.asyncio
    async def test_invalid_github_signature(self):
        svc = WebhookVerificationService()
        payload = b'{"action": "push"}'
        secret = "webhook-secret"
        config = WebhookVerificationService.PROVIDERS["github"]

        is_valid, error = await svc._verify_sha_signature(
            payload, "sha256=invalid", secret, config
        )
        assert is_valid is False
        assert "Invalid signature" in error


# ---------------------------------------------------------------------------
# _verify_hmac_signature (custom format)
# ---------------------------------------------------------------------------

class TestVerifyHmacSignature:
    """Tests for _verify_hmac_signature (custom format)."""

    @pytest.mark.asyncio
    async def test_valid_plain_hmac(self):
        svc = WebhookVerificationService()
        payload = b"test-payload"
        secret = "my-secret"
        config = WebhookVerificationService.PROVIDERS["custom"]

        expected = hmac.new(
            secret.encode("utf-8"), payload, hashlib.sha256
        ).hexdigest()

        is_valid, error = await svc._verify_hmac_signature(
            payload, expected, secret, config
        )
        assert is_valid is True

    @pytest.mark.asyncio
    async def test_valid_timestamped_hmac(self):
        svc = WebhookVerificationService()
        payload = b"test-payload"
        secret = "my-secret"
        timestamp = str(int(time.time()))
        config = {"algorithm": "sha256", "tolerance_seconds": 300}

        signed_payload = f"{timestamp}.{payload.decode('utf-8')}"
        expected = hmac.new(
            secret.encode("utf-8"),
            signed_payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        signature_header = f"{timestamp}.{expected}"

        is_valid, error = await svc._verify_hmac_signature(
            payload, signature_header, secret, config
        )
        assert is_valid is True

    @pytest.mark.asyncio
    async def test_invalid_hmac(self):
        svc = WebhookVerificationService()
        payload = b"test-payload"
        config = WebhookVerificationService.PROVIDERS["custom"]
        is_valid, error = await svc._verify_hmac_signature(
            payload, "bogus-signature", "secret", config
        )
        assert is_valid is False


# ---------------------------------------------------------------------------
# _verify_base64_signature (SendGrid format)
# ---------------------------------------------------------------------------

class TestVerifyBase64Signature:
    """Tests for _verify_base64_signature (SendGrid format)."""

    @pytest.mark.asyncio
    async def test_valid_base64_signature(self):
        svc = WebhookVerificationService()
        payload = b"sendgrid-payload"
        secret = "sg-secret"
        config = WebhookVerificationService.PROVIDERS["sendgrid"]

        raw_sig = hmac.new(
            secret.encode("utf-8"), payload, hashlib.sha256
        ).digest()
        sig_header = base64.b64encode(raw_sig).decode()

        is_valid, error = await svc._verify_base64_signature(
            payload, sig_header, secret, config
        )
        assert is_valid is True

    @pytest.mark.asyncio
    async def test_invalid_base64_signature(self):
        svc = WebhookVerificationService()
        payload = b"sendgrid-payload"
        config = WebhookVerificationService.PROVIDERS["sendgrid"]

        # Valid base64 but wrong signature
        fake_sig = base64.b64encode(b"wrong-signature").decode()
        is_valid, error = await svc._verify_base64_signature(
            payload, fake_sig, "sg-secret", config
        )
        assert is_valid is False


# ---------------------------------------------------------------------------
# log_webhook_attempt
# ---------------------------------------------------------------------------

class TestLogWebhookAttempt:
    """Tests for log_webhook_attempt with mocked Redis."""

    @pytest.mark.asyncio
    async def test_logs_when_redis_available(self):
        mock_redis = AsyncMock()
        svc = WebhookVerificationService(redis_client=mock_redis)
        await svc.log_webhook_attempt(
            provider="stripe",
            endpoint="/webhook/stripe",
            is_valid=True,
        )
        mock_redis.setex.assert_awaited_once()
        mock_redis.incr.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_logs_failure_metric(self):
        mock_redis = AsyncMock()
        svc = WebhookVerificationService(redis_client=mock_redis)
        await svc.log_webhook_attempt(
            provider="github",
            endpoint="/webhook/github",
            is_valid=False,
            error="Invalid signature",
        )
        mock_redis.incr.assert_awaited_once_with("webhook_metrics:github:failure")

    @pytest.mark.asyncio
    async def test_logs_success_metric(self):
        mock_redis = AsyncMock()
        svc = WebhookVerificationService(redis_client=mock_redis)
        await svc.log_webhook_attempt(
            provider="stripe",
            endpoint="/webhook/stripe",
            is_valid=True,
        )
        mock_redis.incr.assert_awaited_once_with("webhook_metrics:stripe:success")

    @pytest.mark.asyncio
    async def test_no_redis_does_nothing(self):
        svc = WebhookVerificationService(redis_client=None)
        # Should not raise
        await svc.log_webhook_attempt(
            provider="stripe",
            endpoint="/webhook/stripe",
            is_valid=True,
        )


# ---------------------------------------------------------------------------
# _get_webhook_secret — caching behavior
# ---------------------------------------------------------------------------

class TestGetWebhookSecret:
    """Tests for _get_webhook_secret cache."""

    @pytest.mark.asyncio
    async def test_cache_hit(self):
        svc = WebhookVerificationService()
        svc._secrets_cache["webhook_secret:stripe"] = (time.time(), "cached-secret")
        result = await svc._get_webhook_secret("stripe")
        assert result == "cached-secret"

    @pytest.mark.asyncio
    async def test_cache_expired(self):
        svc = WebhookVerificationService()
        # Set expired cache entry
        svc._secrets_cache["webhook_secret:stripe"] = (
            time.time() - 600,  # 10 min ago, TTL is 5 min
            "old-secret",
        )
        # Without env var set, should return None
        with patch("services.webhook_verification.settings") as mock_settings:
            mock_settings.get.return_value = None
            result = await svc._get_webhook_secret("stripe")
            assert result is None
