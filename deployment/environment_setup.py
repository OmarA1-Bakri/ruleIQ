#!/usr/bin/env python3
"""
Environment configuration and setup script for ruleIQ deployment.
Sets up and validates environment configurations for different deployment targets.
"""

import argparse
import os
import secrets
import subprocess
import sys
from pathlib import Path
from typing import Dict, List

from dotenv import dotenv_values


class EnvironmentSetup:
    """Environment configuration manager for deployment."""

    def __init__(self, environment: str = "staging") -> None:
        """Initialize environment setup.

        Args:
            environment: Target environment (staging, production)
        """
        self.environment = environment
        self.env_file = f".env.{environment}"
        self.env_example = ".env.example"
        self.config: Dict[str, str] = {}
        self.secrets_to_generate: List[str] = []

    def log(self, message: str, level: str = "info"):
        """Log messages with formatting.

        Args:
            message: Message to log
            level: Log level
        """
        symbols = {"info": "ℹ️", "success": "✅", "warning": "⚠️", "error": "❌", "config": "⚙️"}

        colors = {
            "info": "\033[94m",
            "success": "\033[92m",
            "warning": "\033[93m",
            "error": "\033[91m",
            "config": "\033[95m",
            "reset": "\033[0m",
        }

        symbol = symbols.get(level, "ℹ️")
        color = colors.get(level, colors["info"])
        print(f"{color}{symbol} {message}{colors['reset']}")

    def load_example_config(self) -> Dict[str, str]:
        """Load configuration from .env.example.

        Returns:
            Dictionary of environment variables
        """
        if not Path(self.env_example).exists():
            self.log(f"{self.env_example} not found", "error")
            return {}

        example_config = dotenv_values(self.env_example)
        self.log(f"Loaded {len(example_config)} variables from {self.env_example}", "info")
        return example_config

    def load_existing_config(self) -> Dict[str, str]:
        """Load existing environment configuration.

        Returns:
            Dictionary of existing environment variables
        """
        if Path(self.env_file).exists():
            existing_config = dotenv_values(self.env_file)
            self.log(
                f"Loaded {len(existing_config)} existing variables from {self.env_file}", "info"
            )
            return existing_config

        # Try loading base .env file
        if Path(".env").exists():
            existing_config = dotenv_values(".env")
            self.log(f"Loaded {len(existing_config)} variables from .env", "info")
            return existing_config

        return {}

    def generate_secret(self, length: int = 32) -> str:
        """Generate a secure random secret.

        Args:
            length: Length of the secret

        Returns:
            Generated secret string
        """
        return secrets.token_urlsafe(length)

    def setup_core_variables(self):
        """Set up core environment variables."""
        self.log("Setting up core environment variables...", "config")

        # Database configuration
        if self.environment == "production":
            self.config["DATABASE_URL"] = self.config.get(
                "DATABASE_URL", "postgresql://ruleiq_user:secure_password@db:5432/ruleiq_prod"
            )
            self.config["DATABASE_POOL_SIZE"] = "20"
            self.config["DATABASE_MAX_OVERFLOW"] = "40"
        else:
            self.config["DATABASE_URL"] = self.config.get(
                "DATABASE_URL", "postgresql://ruleiq_user:password@localhost:5432/ruleiq_dev"
            )
            self.config["DATABASE_POOL_SIZE"] = "5"
            self.config["DATABASE_MAX_OVERFLOW"] = "10"

        # Redis configuration
        if self.environment == "production":
            self.config["REDIS_URL"] = self.config.get("REDIS_URL", "redis://redis:6379/0")
        else:
            self.config["REDIS_URL"] = self.config.get("REDIS_URL", "redis://localhost:6379/0")

        # Application URLs
        if self.environment == "production":
            self.config["FRONTEND_URL"] = self.config.get("FRONTEND_URL", "https://ruleiq.com")
            self.config["BACKEND_URL"] = self.config.get("BACKEND_URL", "https://api.ruleiq.com")
        else:
            self.config["FRONTEND_URL"] = self.config.get("FRONTEND_URL", "http://localhost:3000")
            self.config["BACKEND_URL"] = self.config.get("BACKEND_URL", "http://localhost:8000")

        # Environment settings
        self.config["ENVIRONMENT"] = self.environment
        self.config["DEBUG"] = "false" if self.environment == "production" else "true"
        self.config["LOG_LEVEL"] = "INFO" if self.environment == "production" else "DEBUG"

    def setup_security_variables(self):
        """Set up security-related environment variables."""
        self.log("Setting up security variables...", "config")

        # JWT Secret
        if "JWT_SECRET" not in self.config or not self.config["JWT_SECRET"]:
            self.config["JWT_SECRET"] = self.generate_secret(64)
            self.log("Generated new JWT_SECRET", "success")
            self.secrets_to_generate.append("JWT_SECRET")

        # API Key
        if "API_KEY" not in self.config or not self.config["API_KEY"]:
            self.config["API_KEY"] = self.generate_secret(32)
            self.log("Generated new API_KEY", "success")
            self.secrets_to_generate.append("API_KEY")

        # Encryption key
        if "ENCRYPTION_KEY" not in self.config or not self.config["ENCRYPTION_KEY"]:
            self.config["ENCRYPTION_KEY"] = self.generate_secret(32)
            self.log("Generated new ENCRYPTION_KEY", "success")
            self.secrets_to_generate.append("ENCRYPTION_KEY")

        # CORS settings
        self.config["CORS_ORIGINS"] = self.config.get("CORS_ORIGINS", self.config["FRONTEND_URL"])

        # Security headers
        self.config["SECURE_HEADERS"] = "true" if self.environment == "production" else "false"
        self.config["HTTPS_ONLY"] = "true" if self.environment == "production" else "false"

    def setup_api_keys(self):
        """Set up external API keys and integrations."""
        self.log("Setting up API integrations...", "config")

        # OpenAI API Key (required)
        if "OPENAI_API_KEY" not in self.config:
            self.log("OPENAI_API_KEY not set - AI features will be disabled", "warning")
            self.config["OPENAI_API_KEY"] = ""

        # AWS Configuration (optional)
        aws_keys = ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_REGION"]
        for key in aws_keys:
            if key not in self.config:
                self.config[key] = ""

        # Google Workspace (optional)
        if "GOOGLE_WORKSPACE_CREDENTIALS" not in self.config:
            self.config["GOOGLE_WORKSPACE_CREDENTIALS"] = ""

        # Microsoft Azure (optional)
        if "AZURE_CLIENT_ID" not in self.config:
            self.config["AZURE_CLIENT_ID"] = ""
            self.config["AZURE_CLIENT_SECRET"] = ""
            self.config["AZURE_TENANT_ID"] = ""

        # Okta (optional)
        if "OKTA_DOMAIN" not in self.config:
            self.config["OKTA_DOMAIN"] = ""
            self.config["OKTA_CLIENT_ID"] = ""
            self.config["OKTA_CLIENT_SECRET"] = ""

    def setup_monitoring(self):
        """Set up monitoring and observability configuration."""
        self.log("Setting up monitoring configuration...", "config")

        # Sentry configuration
        if self.environment == "production":
            if "SENTRY_DSN" not in self.config:
                self.log("SENTRY_DSN not set - error tracking disabled", "warning")
                self.config["SENTRY_DSN"] = ""

            self.config["SENTRY_ENVIRONMENT"] = self.environment
            self.config["SENTRY_TRACES_SAMPLE_RATE"] = "0.1"
        else:
            self.config["SENTRY_DSN"] = ""

        # Metrics configuration
        self.config["ENABLE_METRICS"] = "true" if self.environment == "production" else "false"
        self.config["METRICS_PORT"] = "9090"

        # Health check configuration
        self.config["HEALTH_CHECK_PATH"] = "/health"
        self.config["HEALTH_CHECK_INTERVAL"] = "30"

    def setup_feature_flags(self):
        """Set up feature flags and configuration toggles."""
        self.log("Setting up feature flags...", "config")

        # Feature flags
        self.config["ENABLE_AI_FEATURES"] = "true"
        self.config["ENABLE_CACHING"] = "true"
        self.config["ENABLE_RATE_LIMITING"] = (
            "true" if self.environment == "production" else "false"
        )
        self.config["ENABLE_AUDIT_LOGGING"] = "true"

        # Rate limiting configuration
        if self.environment == "production":
            self.config["RATE_LIMIT_REQUESTS"] = "100"
            self.config["RATE_LIMIT_WINDOW"] = "60"
        else:
            self.config["RATE_LIMIT_REQUESTS"] = "1000"
            self.config["RATE_LIMIT_WINDOW"] = "60"

    def setup_email_configuration(self):
        """Set up email/SMTP configuration."""
        self.log("Setting up email configuration...", "config")

        # SMTP settings
        if self.environment == "production":
            smtp_required = ["SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD"]
            for key in smtp_required:
                if key not in self.config:
                    self.log(f"{key} not set - email notifications disabled", "warning")
                    self.config[key] = ""

            self.config["SMTP_USE_TLS"] = "true"
            self.config["EMAIL_FROM"] = self.config.get("EMAIL_FROM", "noreply@ruleiq.com")
        else:
            # Use local mail server or mock
            self.config["SMTP_HOST"] = "localhost"
            self.config["SMTP_PORT"] = "1025"
            self.config["SMTP_USE_TLS"] = "false"
            self.config["EMAIL_FROM"] = "dev@ruleiq.local"

    def validate_configuration(self) -> bool:
        """Validate the complete configuration.

        Returns:
            Boolean indicating if configuration is valid
        """
        self.log("Validating configuration...", "info")

        required_vars = [
            "DATABASE_URL",
            "REDIS_URL",
            "JWT_SECRET",
            "API_KEY",
            "FRONTEND_URL",
            "BACKEND_URL",
            "ENVIRONMENT",
        ]

        missing_vars = []
        for var in required_vars:
            if var not in self.config or not self.config[var]:
                missing_vars.append(var)

        if missing_vars:
            self.log(f"Missing required variables: {', '.join(missing_vars)}", "error")
            return False

        # Validate OpenAI API key for AI features
        if self.config.get("ENABLE_AI_FEATURES") == "true" and not self.config.get(
            "OPENAI_API_KEY"
        ):
            self.log("AI features enabled but OPENAI_API_KEY not set", "warning")

        self.log("Configuration validated successfully", "success")
        return True

    def write_configuration(self):
        """Write configuration to environment file."""
        self.log(f"Writing configuration to {self.env_file}...", "config")

        # Sort configuration keys
        sorted_config = dict(sorted(self.config.items()))

        # Group configuration by category
        categories = {
            "Core Configuration": ["ENVIRONMENT", "DEBUG", "LOG_LEVEL"],
            "Database": ["DATABASE_URL", "DATABASE_POOL_SIZE", "DATABASE_MAX_OVERFLOW"],
            "Redis": ["REDIS_URL"],
            "URLs": ["FRONTEND_URL", "BACKEND_URL"],
            "Security": [
                "JWT_SECRET",
                "API_KEY",
                "ENCRYPTION_KEY",
                "CORS_ORIGINS",
                "SECURE_HEADERS",
                "HTTPS_ONLY",
            ],
            "API Keys": [
                "OPENAI_API_KEY",
                "AWS_ACCESS_KEY_ID",
                "AWS_SECRET_ACCESS_KEY",
                "GOOGLE_WORKSPACE_CREDENTIALS",
                "AZURE_CLIENT_ID",
                "OKTA_DOMAIN",
            ],
            "Monitoring": ["SENTRY_DSN", "ENABLE_METRICS", "HEALTH_CHECK_PATH"],
            "Feature Flags": ["ENABLE_AI_FEATURES", "ENABLE_CACHING", "ENABLE_RATE_LIMITING"],
            "Email": ["SMTP_HOST", "SMTP_PORT", "EMAIL_FROM"],
            "Other": [],
        }

        # Write to file
        with open(self.env_file, "w") as f:
            f.write("# ruleIQ Environment Configuration\n")
            f.write(f"# Environment: {self.environment}\n")
            f.write(f"# Generated: {os.popen('date').read().strip()}\n\n")

            for category, keys in categories.items():
                # Find keys in this category
                category_vars = {k: v for k, v in sorted_config.items() if k in keys}

                if category_vars:
                    f.write(f"# {category}\n")
                    for key, value in category_vars.items():
                        if key in self.secrets_to_generate:
                            f.write(f"# {key} was auto-generated - store securely!\n")
                        f.write(f"{key}={value}\n")
                    f.write("\n")

            # Write any remaining variables
            written_keys = set()
            for keys in categories.values():
                written_keys.update(keys)

            remaining = {k: v for k, v in sorted_config.items() if k not in written_keys}
            if remaining:
                f.write("# Additional Configuration\n")
                for key, value in remaining.items():
                    f.write(f"{key}={value}\n")

        self.log(f"Configuration written to {self.env_file}", "success")

        # Set file permissions (readable only by owner)
        os.chmod(self.env_file, 0o600)
        self.log(f"Set secure permissions on {self.env_file}", "success")

    def backup_existing_config(self):
        """Backup existing configuration file."""
        if Path(self.env_file).exists():
            backup_file = f"{self.env_file}.backup.{os.popen('date +%Y%m%d_%H%M%S').read().strip()}"
            subprocess.run(["cp", self.env_file, backup_file])
            self.log(f"Backed up existing config to {backup_file}", "info")

    def setup(self) -> bool:
        """Execute complete environment setup.

        Returns:
            Boolean indicating setup success
        """
        self.log("=" * 60)
        self.log(f"⚙️ ENVIRONMENT SETUP - {self.environment.upper()}", "config")
        self.log("=" * 60)

        # Load configurations
        example_config = self.load_example_config()
        existing_config = self.load_existing_config()

        # Merge configurations (existing takes precedence)
        self.config = {**example_config, **existing_config}

        # Backup existing configuration
        self.backup_existing_config()

        # Set up all configuration categories
        self.setup_core_variables()
        self.setup_security_variables()
        self.setup_api_keys()
        self.setup_monitoring()
        self.setup_feature_flags()
        self.setup_email_configuration()

        # Validate configuration
        if not self.validate_configuration():
            self.log("Configuration validation failed", "error")
            return False

        # Write configuration to file
        self.write_configuration()

        # Display summary
        self.log("=" * 60)
        self.log("📋 CONFIGURATION SUMMARY", "info")
        self.log("=" * 60)
        self.log(f"Environment: {self.environment}")
        self.log(f"Configuration file: {self.env_file}")
        self.log(f"Total variables: {len(self.config)}")

        if self.secrets_to_generate:
            self.log("\n🔑 Auto-generated secrets:", "warning")
            for secret in self.secrets_to_generate:
                self.log(f"  • {secret} - Store this securely!", "warning")

        # Check for missing optional configurations
        optional_missing = []
        if not self.config.get("OPENAI_API_KEY"):
            optional_missing.append("OPENAI_API_KEY (AI features)")
        if not self.config.get("SENTRY_DSN"):
            optional_missing.append("SENTRY_DSN (error tracking)")
        if not self.config.get("SMTP_HOST"):
            optional_missing.append("SMTP configuration (email)")

        if optional_missing:
            self.log("\n⚠️ Optional configurations not set:", "warning")
            for item in optional_missing:
                self.log(f"  • {item}", "warning")

        self.log("\n✅ Environment setup completed successfully!", "success")
        return True


def main():
    """Main entry point for environment setup."""
    parser = argparse.ArgumentParser(description="Environment setup for ruleIQ deployment")
    parser.add_argument(
        "--env", choices=["staging", "production"], default="staging", help="Target environment"
    )
    parser.add_argument(
        "--validate-only", action="store_true", help="Only validate existing configuration"
    )

    args = parser.parse_args()

    setup = EnvironmentSetup(environment=args.env)

    if args.validate_only:
        # Just validate existing configuration
        setup.config = setup.load_existing_config()
        success = setup.validate_configuration()
    else:
        # Full setup
        success = setup.setup()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
