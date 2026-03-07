"""
Webhook Signature Verification Service

Provides secure webhook signature verification for incoming webhooks
from external services (Stripe, GitHub, etc.)
import requests
"""

import hmac
import hashlib
import time
import json
from typing import Optional, Dict, Any, Tuple
from datetime import datetime, timezone
import logging

from fastapi import HTTPException, status, Request
import redis.asyncio as redis

from config.settings import settings

logger = logging.getLogger(__name__)


class WebhookVerificationService:
    """
    Service for verifying webhook signatures from external services.

    Supports multiple signature algorithms and providers:
    - HMAC-SHA256 (Stripe, SendGrid)
    - HMAC-SHA1 (GitHub)
    - Custom signatures
    """

    # Webhook provider configurations
    PROVIDERS = {
        "stripe": {
            "header": "Stripe-Signature",
            "algorithm": "sha256",
            "format": "timestamp_signature",
            "tolerance_seconds": 300,  # 5 minutes,
        },
        "github": {
            "header": "X-Hub-Signature-256",
            "algorithm": "sha256",
            "format": "sha_signature",
            "tolerance_seconds": None,  # No timestamp validation,
        },
        "sendgrid": {
            "header": "X-Twilio-Email-Event-Webhook-Signature",
            "algorithm": "sha256",
            "format": "base64_signature",
            "tolerance_seconds": None,
        },
        "custom": {
            "header": "X-Webhook-Signature",
            "algorithm": "sha256",
            "format": "hmac_signature",
            "tolerance_seconds": 300,
        },
    }

    def __init__(self, redis_client: redis.Redis = None) -> None:
        """Initialize the webhook verification service."""
        self.redis_client = redis_client
        self._secrets_cache = {}
        self._secrets_cache_ttl = 300  # 5 minutes

    async def verify_webhook(
        self,
        request: Request,
        provider: str,
        secret: Optional[str] = None,
        payload: Optional[bytes] = None,
    ) -> Tuple[bool, Optional[str]]:
        """
        Verify a webhook signature.

        Args:
            request: The incoming request
            provider: The webhook provider (stripe, github, etc.)
            secret: The webhook secret (if not in environment)
            payload: The raw request body (if not available from request)

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Get provider configuration
            if provider not in self.PROVIDERS:
                return False, f"Unknown webhook provider: {provider}"

            config = self.PROVIDERS[provider]

            # Get signature from headers
            signature_header = request.headers.get(config["header"])
            if not signature_header:
                return False, f"Missing signature header: {config['header']}"

            # Get the webhook secret
            if not secret:
                secret = await self._get_webhook_secret(provider)
                if not secret:
                    return False, f"No webhook secret configured for {provider}"

            # Get the request payload
            if payload is None:
                payload = await request.body()

            # Verify based on format
            if config["format"] == "timestamp_signature":
                return await self._verify_timestamp_signature(
                    payload,
                    signature_header,
                    secret,
                    config,
                )
            elif config["format"] == "sha_signature":
                return await self._verify_sha_signature(
                    payload,
                    signature_header,
                    secret,
                    config,
                )
            elif config["format"] == "base64_signature":
                return await self._verify_base64_signature(
                    payload,
                    signature_header,
                    secret,
                    config,
                )
            elif config["format"] == "hmac_signature":
                return await self._verify_hmac_signature(
                    payload,
                    signature_header,
                    secret,
                    config,
                )
            else:
                return False, f"Unknown signature format: {config['format']}"

        except (requests.RequestException, KeyError, IndexError) as e:
            logger.error(f"Webhook verification error: {e}")
            return False, str(e)

    async def _verify_timestamp_signature(
        self, payload: bytes, signature_header: str, secret: str, config: dict
    ) -> Tuple[bool, Optional[str]]:
        """Verify timestamp-based signatures (Stripe format)."""
        try:
            # Parse the signature header
            elements = {}
            for element in signature_header.split(","):
                key_value = element.split("=")
                if len(key_value) == 2:
                    elements[key_value[0].strip()] = key_value[1].strip()

            timestamp = elements.get("t")
            signatures = elements.get("v1", "").split(" ")

            if not timestamp or not signatures:
                return False, "Invalid signature format"

            # Check timestamp tolerance
            if config.get("tolerance_seconds"):
                current_time = int(time.time())
                webhook_time = int(timestamp)

                if abs(current_time - webhook_time) > config["tolerance_seconds"]:
                    return False, "Webhook timestamp outside tolerance window"

            # Compute expected signature
            signed_payload = f"{timestamp}.{payload.decode('utf-8')}"
            expected_signature = hmac.new(
                secret.encode("utf-8"),
                signed_payload.encode("utf-8"),
                getattr(hashlib, config["algorithm"]),
            ).hexdigest()

            # Check if any provided signature matches
            for signature in signatures:
                if hmac.compare_digest(signature, expected_signature):
                    return True, None

            return False, "Invalid signature"

        except (requests.RequestException, ValueError, KeyError) as e:
            return False, f"Signature verification failed: {e}"

    async def _verify_sha_signature(
        self, payload: bytes, signature_header: str, secret: str, config: dict
    ) -> Tuple[bool, Optional[str]]:
        """Verify SHA-based signatures (GitHub format)."""
        try:
            # Remove the algorithm prefix if present
            if "=" in signature_header:
                algorithm, signature = signature_header.split("=", 1)
            else:
                signature = signature_header

            # Compute expected signature
            expected_signature = hmac.new(
                secret.encode("utf-8"), payload, getattr(hashlib, config["algorithm"])
            ).hexdigest()

            # Compare signatures
            if hmac.compare_digest(signature, expected_signature):
                return True, None

            return False, "Invalid signature"

        except (KeyError, IndexError) as e:
            return False, f"Signature verification failed: {e}"

    async def _verify_base64_signature(
        self, payload: bytes, signature_header: str, secret: str, config: dict
    ) -> Tuple[bool, Optional[str]]:
        """Verify Base64-encoded signatures."""
        import base64

        try:
            # Decode the signature
            provided_signature = base64.b64decode(signature_header)

            # Compute expected signature
            expected_signature = hmac.new(
                secret.encode("utf-8"), payload, getattr(hashlib, config["algorithm"])
            ).digest()

            # Compare signatures
            if hmac.compare_digest(provided_signature, expected_signature):
                return True, None

            return False, "Invalid signature"

        except (KeyError, IndexError) as e:
            return False, f"Signature verification failed: {e}"

    async def _verify_hmac_signature(
        self, payload: bytes, signature_header: str, secret: str, config: dict
    ) -> Tuple[bool, Optional[str]]:
        """Verify plain HMAC signatures."""
        try:
            # Parse timestamp if included
            timestamp = None
            signature = signature_header

            if "." in signature_header:
                parts = signature_header.split(".")
                if len(parts) == 2 and parts[0].isdigit():
                    timestamp = int(parts[0])
                    signature = parts[1]

            # Check timestamp tolerance if applicable
            if timestamp and config.get("tolerance_seconds"):
                current_time = int(time.time())
                if abs(current_time - timestamp) > config["tolerance_seconds"]:
                    return False, "Webhook timestamp outside tolerance window"

            # Prepare payload with timestamp if present
            if timestamp:
                signed_payload = f"{timestamp}.{payload.decode('utf-8')}"
                payload_to_sign = signed_payload.encode("utf-8")
            else:
                payload_to_sign = payload

            # Compute expected signature
            expected_signature = hmac.new(
                secret.encode("utf-8"),
                payload_to_sign,
                getattr(hashlib, config["algorithm"]),
            ).hexdigest()

            # Compare signatures
            if hmac.compare_digest(signature, expected_signature):
                return True, None

            return False, "Invalid signature"

        except (requests.RequestException, ValueError, KeyError) as e:
            return False, f"Signature verification failed: {e}"

    async def _get_webhook_secret(self, provider: str) -> Optional[str]:
        """Get webhook secret from environment or cache."""
        # Check cache first
        cache_key = f"webhook_secret:{provider}"
        if cache_key in self._secrets_cache:
            cached_time, secret = self._secrets_cache[cache_key]
            if time.time() - cached_time < self._secrets_cache_ttl:
                return secret

        # Get from environment
        env_var = f"WEBHOOK_SECRET_{provider.upper()}"
        secret = settings.get(env_var)

        if not secret:
            # Try Doppler if configured
            try:
                import subprocess

                result = subprocess.run(
                    ["doppler", "secrets", "get", env_var, "--plain"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if result.returncode == 0:
                    secret = result.stdout.strip()
            except (KeyError, IndexError):
                pass

        # Cache the secret
        if secret:
            self._secrets_cache[cache_key] = (time.time(), secret)

        return secret

    async def generate_webhook_signature(
        self,
        payload: str,
        secret: str,
        provider: str = "custom",
        include_timestamp: bool = True,
    ) -> str:
        """
        Generate a webhook signature for outgoing webhooks.

        Args:
            payload: The webhook payload
            secret: The webhook secret
            provider: The provider format to use
            include_timestamp: Whether to include timestamp

        Returns:
            The generated signature
        """
        config = self.PROVIDERS.get(provider, self.PROVIDERS["custom"])

        if include_timestamp and config["format"] in [
            "timestamp_signature",
            "hmac_signature",
        ]:
            timestamp = int(time.time())
            signed_payload = f"{timestamp}.{payload}"
            signature = hmac.new(
                secret.encode("utf-8"),
                signed_payload.encode("utf-8"),
                getattr(hashlib, config["algorithm"]),
            ).hexdigest()

            if config["format"] == "timestamp_signature":
                return f"t={timestamp},v1={signature}"
            else:
                return f"{timestamp}.{signature}"
        else:
            signature = hmac.new(
                secret.encode("utf-8"),
                payload.encode("utf-8"),
                getattr(hashlib, config["algorithm"]),
            ).hexdigest()

            if config["format"] == "sha_signature":
                return f"sha{config['algorithm'][-3:]}={signature}"
            elif config["format"] == "base64_signature":
                import base64

                return base64.b64encode(signature.encode()).decode()
            else:
                return signature

    async def log_webhook_attempt(
        self,
        provider: str,
        endpoint: str,
        is_valid: bool,
        error: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Log webhook verification attempt."""
        if not self.redis_client:
            return

        try:
            # Create log entry
            log_entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "provider": provider,
                "endpoint": endpoint,
                "is_valid": is_valid,
                "error": error,
                "metadata": metadata or {},
            }

            # Store in Redis with expiration
            log_key = f"webhook_log:{provider}:{int(time.time())}"
            await self.redis_client.setex(
                log_key,
                86400,
                json.dumps(log_entry),  # 24 hours,
            )

            # Update metrics
            if is_valid:
                await self.redis_client.incr(f"webhook_metrics:{provider}:success")
            else:
                await self.redis_client.incr(f"webhook_metrics:{provider}:failure")

        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to log webhook attempt: {e}")


# Webhook verification dependency
async def verify_webhook_signature(
    request: Request, provider: str, secret: Optional[str] = None
) -> bool:
    """
    FastAPI dependency for webhook signature verification.

    Usage:
        @router.post("/webhook/stripe")
        async def handle_stripe_webhook(
            request: Request,
            verified: bool = Depends(lambda req: verify_webhook_signature(req, "stripe"))
        ):
            if not verified:
                raise HTTPException(status_code=400, detail="Invalid signature")
    """
    from services.redis_client import get_redis_client

    try:
        redis_client = await get_redis_client()
        service = WebhookVerificationService(redis_client)

        is_valid, error = await service.verify_webhook(
            request=request,
            provider=provider,
            secret=secret,
        )

        # Log the attempt
        await service.log_webhook_attempt(
            provider=provider,
            endpoint=str(request.url.path),
            is_valid=is_valid,
            error=error,
        )

        if not is_valid:
            logger.warning(f"Invalid webhook signature from {provider}: {error}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid webhook signature: {error}",
            )

        return True

    except HTTPException:
        raise
    except (OSError, requests.RequestException) as e:
        logger.error(f"Webhook verification error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webhook verification failed",
        )
