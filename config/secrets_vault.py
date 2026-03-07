"""

# Constants
MAX_RETRIES = 3


🔐 RuleIQ Secure Secrets Vault - Multi-Platform Integration
Easily identifiable secure secrets vault implementation

Supports multiple deployment platforms:
- Doppler Secrets Management (Recommended for production)
- Vercel Environment Variables (Vercel deployments)
- AWS Secrets Manager (Enterprise/Self-hosted)
- Local Environment Variables (Development)
"""

import os
import json
import logging
from typing import Dict, Optional, Any
from functools import lru_cache

try:
    import boto3

    AWS_AVAILABLE = True
except ImportError:
    AWS_AVAILABLE = False
logger = logging.getLogger(__name__)


class SecretsVault:
    """
    🔐 RuleIQ Secure Secrets Vault - Multi-Platform Integration

    Easily identifiable vault for secure secrets management:
    - Vercel Environment Variables (Primary for production)
    - AWS Secrets Manager (Enterprise/Self-hosted)
    - Local Environment Variables (Development fallback)
    - Caching for performance
    - Health monitoring
    """

    def __init__(
        self,
        backend: str = "auto",
        region_name: str = "us-east-1",
        secret_name: str = "ruleiq-production-secrets",
    ) -> None:
        self.region_name = region_name
        self.secret_name = secret_name
        self.backend = self._detect_backend(backend)
        self.aws_client = None
        if self.backend == "doppler":
            logger.info("🔐 SecretsVault: Using Doppler Secrets Management")
        elif self.backend == "aws" and AWS_AVAILABLE:
            self._init_aws_backend()
        elif self.backend == "vercel":
            logger.info("🔐 SecretsVault: Using Vercel Environment Variables")
        else:
            logger.info("🔐 SecretsVault: Using Local Environment Variables")

    def _detect_backend(self, backend: str) -> str:
        """Detect the appropriate secrets backend based on environment"""
        if backend != "auto":
            return backend
        if os.getenv("DOPPLER_TOKEN") or os.getenv("DOPPLER_PROJECT"):
            logger.info("🔐 Detected Doppler secrets management")
            return "doppler"
        if os.getenv("VERCEL"):
            logger.info("🔐 Detected Vercel deployment environment - recommend using Doppler")
            return "vercel"
        aws_enabled = os.getenv("SECRETS_MANAGER_ENABLED", "false").lower() == "true"
        if aws_enabled and AWS_AVAILABLE:
            return "aws"
        return "env"

    def _init_aws_backend(self):
        """Initialize AWS Secrets Manager backend"""
        try:
            self.aws_client = boto3.client("secretsmanager", region_name=self.region_name)
            logger.info("🔐 SecretsVault: AWS Secrets Manager client initialized")
        except Exception as e:
            logger.warning(
                "⚠️ SecretsVault: AWS initialization failed, falling back to environment: %s" % e
            )
            self.backend = "env"
            self.aws_client = None

    @lru_cache(maxsize=100)
    def get_secret(self, secret_key: str) -> Optional[str]:
        """
        Retrieve secret from configured backend (Doppler, Vercel, AWS, or Environment)

        Args:
            secret_key: The secret key (e.g., 'database_url', 'openai_api_key')

        Returns:
            Secret value or None if not found
        """
        if self.backend == "doppler":
            return self._get_from_doppler(secret_key)
        elif self.backend == "aws" and self.aws_client:
            return self._get_from_aws(secret_key)
        elif self.backend == "vercel":
            return self._get_from_vercel(secret_key)
        else:
            return self._get_from_env(secret_key)

    def _get_from_aws(self, secret_key: str) -> Optional[str]:
        """Get secret from AWS Secrets Manager"""
        try:
            response = self.aws_client.get_secret_value(SecretId=self.secret_name)
            secrets = json.loads(response["SecretString"])
            if secret_key in secrets:
                logger.debug(
                    "🔐 SecretsVault: Retrieved '%s' from AWS Secrets Manager" % secret_key
                )
                return secrets[secret_key]
            else:
                logger.warning(
                    "⚠️ SecretsVault: '%s' not found in AWS vault, checking environment" % secret_key
                )
                return self._get_from_env(secret_key)
        except Exception as e:
            logger.error("❌ SecretsVault: AWS error retrieving '%s': %s" % (secret_key, e))
            return self._get_from_env(secret_key)

    def _get_from_doppler(self, secret_key: str) -> Optional[str]:
        """
        Get secret from Doppler secrets management

        Doppler automatically injects secrets as environment variables when properly configured.
        This method provides Doppler-aware logging and fallback handling.
        """
        direct_key = secret_key.upper()
        value = os.getenv(direct_key)
        if value:
            logger.debug(
                "🔐 SecretsVault: Retrieved '%s' from Doppler environment (%s)"
                % (secret_key, direct_key)
            )
            return value
        vault_env_key = f"VAULT_SECRET_{secret_key.upper()}"
        value = os.getenv(vault_env_key)
        if value:
            logger.debug(
                "🔐 SecretsVault: Retrieved '%s' from Doppler vault format (%s)"
                % (secret_key, vault_env_key)
            )
            return value
        doppler_token = os.getenv("DOPPLER_TOKEN")
        doppler_project = os.getenv("DOPPLER_PROJECT")
        if not doppler_token and not doppler_project:
            logger.warning("⚠️ SecretsVault: Doppler not configured, but backend set to 'doppler'")
            logger.info("💡 Configure Doppler: https://docs.doppler.com/docs/vercel")
        logger.warning("⚠️ SecretsVault: '%s' not found in Doppler environment" % secret_key)
        return None

    def _get_from_vercel(self, secret_key: str) -> Optional[str]:
        """
        Get secret from Vercel environment variables

        Vercel automatically makes environment variables available as os.environ,
        so we use the same logic as local environment but with Vercel-aware logging.
        """
        direct_key = secret_key.upper()
        value = os.getenv(direct_key)
        if value:
            logger.debug(
                "🔐 SecretsVault: Retrieved '%s' from Vercel environment (%s)"
                % (secret_key, direct_key)
            )
            return value
        vault_env_key = f"VAULT_SECRET_{secret_key.upper()}"
        value = os.getenv(vault_env_key)
        if value:
            logger.debug(
                "🔐 SecretsVault: Retrieved '%s' from Vercel vault format (%s)"
                % (secret_key, vault_env_key)
            )
            return value
        logger.warning("⚠️ SecretsVault: '%s' not found in Vercel environment" % secret_key)
        return None

    def _get_from_env(self, secret_key: str) -> Optional[str]:
        """Fallback to environment variables"""
        vault_env_key = f"VAULT_SECRET_{secret_key.upper()}"
        value = os.getenv(vault_env_key)
        if value:
            logger.debug(
                "🔐 SecretsVault: Retrieved '%s' from environment (%s)"
                % (secret_key, vault_env_key)
            )
            return value
        direct_key = secret_key.upper()
        value = os.getenv(direct_key)
        if value:
            logger.debug(
                "🔐 SecretsVault: Retrieved '%s' from direct environment (%s)"
                % (secret_key, direct_key)
            )
            return value
        logger.warning("⚠️ SecretsVault: '%s' not found in vault or environment" % secret_key)
        return None

    def get_all_secrets(self) -> Dict[str, str]:
        """
        Retrieve all secrets from the configured backend

        Returns:
            Dictionary of all secrets (limited for security)
        """
        if self.backend == "doppler":
            return self._get_all_secrets_doppler()
        elif self.backend == "aws" and self.aws_client:
            return self._get_all_secrets_aws()
        elif self.backend == "vercel":
            return self._get_all_secrets_vercel()
        else:
            return self._get_all_secrets_env()

    def _get_all_secrets_aws(self) -> Dict[str, str]:
        """Get all secrets from AWS Secrets Manager"""
        try:
            response = self.aws_client.get_secret_value(SecretId=self.secret_name)
            secrets = json.loads(response["SecretString"])
            logger.info(
                "🔐 SecretsVault: Retrieved %s secrets from AWS Secrets Manager" % len(secrets)
            )
            return secrets
        except Exception as e:
            logger.error("❌ SecretsVault: Error retrieving all secrets from AWS: %s" % e)
            return {}

    def _get_all_secrets_doppler(self) -> Dict[str, str]:
        """
        Get all secrets from Doppler secrets management

        Note: For security, this returns a limited set of known secret keys
        rather than all environment variables
        """
        secrets = {}
        for attr_name, key_name in vars(SecretKeys).items():
            if not attr_name.startswith("_"):
                value = self._get_from_doppler(key_name)
                if value:
                    secrets[key_name] = value
        logger.info("🔐 SecretsVault: Retrieved %s secrets from Doppler" % len(secrets))
        return secrets

    def _get_all_secrets_vercel(self) -> Dict[str, str]:
        """
        Get all secrets from Vercel environment variables

        Note: For security, this returns a limited set of known secret keys
        rather than all environment variables
        """
        secrets = {}
        for attr_name, key_name in vars(SecretKeys).items():
            if not attr_name.startswith("_"):
                value = self._get_from_vercel(key_name)
                if value:
                    secrets[key_name] = value
        logger.info("🔐 SecretsVault: Retrieved %s secrets from Vercel environment" % len(secrets))
        return secrets

    def _get_all_secrets_env(self) -> Dict[str, str]:
        """
        Get all secrets from local environment variables

        Note: For security, this returns a limited set of known secret keys
        rather than all environment variables
        """
        secrets = {}
        for attr_name, key_name in vars(SecretKeys).items():
            if not attr_name.startswith("_"):
                value = self._get_from_env(key_name)
                if value:
                    secrets[key_name] = value
        logger.info("🔐 SecretsVault: Retrieved %s secrets from local environment" % len(secrets))
        return secrets

    def health_check(self) -> Dict[str, Any]:
        """
        Health check for secrets vault connectivity

        Returns:
            Health status information
        """
        backend_map = {
            "doppler": "Doppler Secrets Management",
            "vercel": "Vercel Environment Variables",
            "aws": "AWS Secrets Manager",
            "env": "Local Environment Variables",
        }
        status = {
            "vault_type": backend_map.get(self.backend, "Unknown"),
            "backend": self.backend,
            "enabled": True,
            "region": self.region_name if self.backend == "aws" else None,
            "secret_name": self.secret_name if self.backend == "aws" else None,
            "status": "unknown",
        }
        if self.backend == "doppler":
            status.update(self._health_check_doppler())
        elif self.backend == "vercel":
            status.update(self._health_check_vercel())
        elif self.backend == "aws":
            status.update(self._health_check_aws())
        else:
            status.update(self._health_check_env())
        return status

    def _health_check_vercel(self) -> Dict[str, Any]:
        """Health check for Vercel environment"""
        vercel_env = os.getenv("VERCEL")
        vercel_url = os.getenv("VERCEL_URL")
        if vercel_env:
            return {
                "status": "healthy",
                "message": "Running on Vercel with environment variable access",
                "vercel_url": vercel_url,
                "deployment_id": os.getenv("VERCEL_GIT_COMMIT_SHA", "unknown")[:8],
            }
        else:
            return {
                "status": "healthy",
                "message": "Configured for Vercel deployment (local development mode)",
            }

    def _health_check_aws(self) -> Dict[str, Any]:
        """Health check for AWS Secrets Manager"""
        if not self.aws_client:
            return {"status": "error", "message": "AWS client not initialized"}
        try:
            self.aws_client.describe_secret(SecretId=self.secret_name)
            return {"status": "healthy", "message": "Successfully connected to AWS Secrets Manager"}
        except Exception as e:
            return {"status": "error", "message": f"AWS connection failed: {str(e)}"}

    def _health_check_env(self) -> Dict[str, Any]:
        """Health check for local environment variables"""
        return {"status": "healthy", "message": "Using local environment variables"}

    def _health_check_doppler(self) -> Dict[str, Any]:
        """Health check for Doppler secrets management"""
        doppler_token = os.getenv("DOPPLER_TOKEN")
        doppler_project = os.getenv("DOPPLER_PROJECT")
        doppler_config = os.getenv("DOPPLER_CONFIG")
        doppler_environment = os.getenv("DOPPLER_ENVIRONMENT")
        if doppler_token:
            return {
                "status": "healthy",
                "message": "Doppler secrets management active with token authentication",
                "project": doppler_project or "Not specified",
                "config": doppler_config or "default",
                "environment": doppler_environment or "Not specified",
                "token_configured": True,
            }
        elif doppler_project:
            return {
                "status": "warning",
                "message": "Doppler project configured but no token found",
                "project": doppler_project,
                "config": doppler_config or "default",
                "environment": doppler_environment or "Not specified",
                "token_configured": False,
                "setup_url": "https://docs.doppler.com/docs/vercel",
            }
        else:
            return {
                "status": "error",
                "message": "Doppler not configured - no project or token found",
                "token_configured": False,
                "setup_url": "https://docs.doppler.com/docs/vercel",
                "instructions": "Configure DOPPLER_TOKEN and DOPPLER_PROJECT environment variables",
            }

    def rotate_secret(self, secret_key: str, new_value: str) -> bool:
        """
        Rotate a specific secret in the configured backend

        Args:
            secret_key: The secret key to rotate
            new_value: The new secret value

        Returns:
            True if rotation successful, False otherwise
        """
        if self.backend == "doppler":
            return self._rotate_secret_doppler(secret_key, new_value)
        elif self.backend == "aws" and self.aws_client:
            return self._rotate_secret_aws(secret_key, new_value)
        elif self.backend == "vercel":
            return self._rotate_secret_vercel(secret_key, new_value)
        else:
            return self._rotate_secret_env(secret_key, new_value)

    def _rotate_secret_aws(self, secret_key: str, new_value: str) -> bool:
        """Rotate secret in AWS Secrets Manager"""
        try:
            current_secrets = self._get_all_secrets_aws()
            current_secrets[secret_key] = new_value
            self.aws_client.update_secret(
                SecretId=self.secret_name, SecretString=json.dumps(current_secrets)
            )
            self.get_secret.cache_clear()
            logger.info("✅ SecretsVault: Successfully rotated secret '%s' in AWS" % secret_key)
            return True
        except Exception as e:
            logger.error(
                "❌ SecretsVault: Failed to rotate secret '%s' in AWS: %s" % (secret_key, e)
            )
            return False

    def _rotate_secret_doppler(self, secret_key: str, new_value: str) -> bool:
        """
        Rotate secret in Doppler secrets management

        Note: Doppler secrets should be rotated through the Doppler CLI or Dashboard.
        This method logs the rotation request for manual action.
        """
        logger.warning("⚠️ SecretsVault: Doppler secret rotation requested for '%s'" % secret_key)
        logger.info("📝 Doppler secrets must be rotated via:")
        logger.info("   1. Doppler Dashboard: https://dashboard.doppler.com")
        logger.info("   2. Doppler CLI: doppler secrets set")
        logger.info("   3. Update the secret: %s" % secret_key.upper())
        logger.info("   4. Secrets will auto-sync to connected services (Vercel, etc.)")
        self.get_secret.cache_clear()
        return False

    def _rotate_secret_vercel(self, secret_key: str, new_value: str) -> bool:
        """
        Rotate secret in Vercel environment

        Note: Vercel environment variables cannot be programmatically updated.
        This method logs the rotation request for manual action.
        """
        logger.warning("⚠️ SecretsVault: Vercel secret rotation requested for '%s'" % secret_key)
        logger.info("📝 Vercel secrets must be rotated manually via:")
        logger.info("   1. Vercel Dashboard > Project > Settings > Environment Variables")
        logger.info("   2. Vercel CLI: vercel env add")
        logger.info("   3. Update the environment variable: %s" % secret_key.upper())
        self.get_secret.cache_clear()
        return False

    def _rotate_secret_env(self, secret_key: str, new_value: str) -> bool:
        """
        Rotate secret in local environment

        Note: Local environment variables cannot be programmatically updated.
        This method logs the rotation request for manual action.
        """
        logger.warning(
            "⚠️ SecretsVault: Local environment secret rotation requested for '%s'" % secret_key
        )
        logger.info("📝 Local environment secrets must be rotated manually:")
        logger.info("   1. Update .env file or environment variable: %s" % secret_key.upper())
        logger.info("   2. Restart the application to reload environment")
        self.get_secret.cache_clear()
        return False


_vault_instance: Optional[SecretsVault] = None


def get_secrets_vault() -> SecretsVault:
    """
    🔐 Get the global SecretsVault instance (Singleton Pattern)

    Returns:
        SecretsVault: The global secrets vault instance
    """
    global _vault_instance
    if _vault_instance is None:
        region = os.getenv("SECRETS_MANAGER_REGION", "us-east-1")
        secret_name = os.getenv("SECRETS_MANAGER_SECRET_NAME", "ruleiq-production-secrets")
        _vault_instance = SecretsVault(region_name=region, secret_name=secret_name)
        logger.info("🔐 SecretsVault: Global instance initialized")
    return _vault_instance


def get_secret(key: str) -> Optional[str]:
    """🔐 Convenience function to get a secret from the vault"""
    return get_secrets_vault().get_secret(key)


def vault_health_check() -> Dict[str, Any]:
    """🔐 Convenience function to check vault health"""
    return get_secrets_vault().health_check()


class SecretKeys:
    """🔐 Easily identifiable secret keys used in RuleIQ"""

    DATABASE_URL = "database_url"
    TEST_DATABASE_URL = "test_database_url"
    REDIS_URL = "redis_url"
    CACHE_REDIS_URL = "cache_redis_url"
    SESSION_REDIS_URL = "session_redis_url"
    JWT_SECRET = "jwt_secret"
    SECRET_KEY = "secret_key"
    ENCRYPTION_KEY = "encryption_key"
    FERNET_KEY = "fernet_key"
    CREDENTIAL_MASTER_KEY = "credential_master_key"
    STACK_PROJECT_ID = "stack_project_id"
    STACK_CLIENT_KEY = "stack_client_key"
    STACK_SERVER_KEY = "stack_server_key"
    GOOGLE_CLIENT_ID = "google_client_id"
    GOOGLE_CLIENT_SECRET = "google_client_secret"
    MICROSOFT_CLIENT_ID = "microsoft_client_id"
    MICROSOFT_CLIENT_SECRET = "microsoft_client_secret"
    OPENAI_API_KEY = "openai_api_key"
    ANTHROPIC_API_KEY = "anthropic_api_key"
    GOOGLE_AI_API_KEY = "google_ai_api_key"
    MISTRAL_API_KEY = "mistral_api_key"
    SMTP_HOST = "smtp_host"
    SMTP_USERNAME = "smtp_username"
    SMTP_PASSWORD = "smtp_password"
    AWS_ACCESS_KEY_ID = "aws_access_key_id"
    AWS_SECRET_ACCESS_KEY = "aws_secret_access_key"
    STRIPE_PUBLISHABLE_KEY = "stripe_publishable_key"
    STRIPE_SECRET_KEY = "stripe_secret_key"
    STRIPE_WEBHOOK_SECRET = "stripe_webhook_secret"
    SENTRY_DSN = "sentry_dsn"
    SENTRY_RELEASE = "sentry_release"


if __name__ == "__main__":
    """
    🔐 SecretsVault CLI for testing and management
    """
    import sys

    vault = get_secrets_vault()
    if len(sys.argv) < 2:
        logger.info("🔐 SecretsVault CLI")
        logger.info("Usage:")
        logger.info("  python secrets_vault.py health")
        logger.info("  python secrets_vault.py get <secret_key>")
        logger.info("  python secrets_vault.py list")
        sys.exit(1)
    command = sys.argv[1]
    if command == "health":
        health = vault_health_check()
        logger.info("🔐 Vault Health: %s" % json.dumps(health, indent=2))
    elif command == "get" and len(sys.argv) == MAX_RETRIES:
        secret_key = sys.argv[2]
        value = vault.get_secret(secret_key)
        if value:
            logger.info("🔐 Secret '%s': %s... (hidden)" % (secret_key, "*" * min(len(value), 10)))
        else:
            logger.info("❌ Secret '%s' not found" % secret_key)
    elif command == "list":
        secrets = vault.get_all_secrets()
        logger.info("🔐 Found %s secrets:" % len(secrets))
        for key in secrets:
            logger.info("  - %s" % key)
    else:
        logger.info("❌ Invalid command")
        sys.exit(1)
