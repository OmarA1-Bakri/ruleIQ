"""
Monitoring security configuration for Grafana and Prometheus.

This module provides secure defaults and credential management for monitoring services.
"""

import os
import secrets
from typing import Dict, Any
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def generate_secure_password(length: int = 24) -> str:
    """
    Generate a cryptographically secure password.

    Args:
        length: Password length (minimum 16)

    Returns:
        str: Secure random password
    """
    length = max(length, 16)

    # Use a mix of characters for strong passwords
    alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*()_+-="
    password = "".join(secrets.choice(alphabet) for _ in range(length))

    # Ensure password has at least one of each type
    if not any(c.islower() for c in password):
        password = password[:-1] + secrets.choice("abcdefghijklmnopqrstuvwxyz")
    if not any(c.isupper() for c in password):
        password = password[:-1] + secrets.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    if not any(c.isdigit() for c in password):
        password = password[:-1] + secrets.choice("0123456789")
    if not any(c in "!@#$%^&*()_+-=" for c in password):
        password = password[:-1] + secrets.choice("!@#$%^&*()_+-=")

    return password


def get_grafana_credentials() -> Dict[str, str]:
    """
    Get secure Grafana admin credentials.

    Returns credentials from environment or generates secure defaults.

    Returns:
        Dict with 'username' and 'password'
    """
    # Check for production environment
    is_production = os.getenv("ENVIRONMENT", "development").lower() == "production"

    # Get credentials from environment
    username = os.getenv("GRAFANA_ADMIN_USER")
    password = os.getenv("GRAFANA_ADMIN_PASSWORD")

    # Validate credentials
    if not username or username == "admin":
        if is_production:
            logger.error("CRITICAL: Grafana admin username not configured for production")
            username = f"ruleiq_admin_{secrets.token_hex(4)}"
        else:
            username = "ruleiq_admin"
            logger.warning("Using default Grafana admin username for development")

    if not password or password == "admin":
        if is_production:
            logger.error("CRITICAL: Grafana admin password not configured for production")
            password = generate_secure_password(32)
            logger.info(f"Generated secure Grafana password. Save this: {password}")
        else:
            # Use a secure but memorable password for development
            password = generate_secure_password(20)
            logger.warning(f"Generated Grafana development password: {password}")

    # Validate password strength
    if len(password) < 12:
        logger.error("Grafana password too weak, generating secure password")
        password = generate_secure_password(24)

    return {"username": username, "password": password}


def get_prometheus_credentials() -> Dict[str, Any]:
    """
    Get Prometheus security configuration.

    Returns:
        Dict with Prometheus security settings
    """
    is_production = os.getenv("ENVIRONMENT", "development").lower() == "production"

    config = {
        "basic_auth_enabled": is_production,
        "tls_enabled": is_production,
        "web_external_url": os.getenv("PROMETHEUS_EXTERNAL_URL", "http://localhost:9090"),
    }

    if config["basic_auth_enabled"]:
        config["username"] = os.getenv("PROMETHEUS_USER", f"prom_user_{secrets.token_hex(4)}")
        config["password"] = os.getenv("PROMETHEUS_PASSWORD", generate_secure_password(24))

    return config


def generate_monitoring_env_file(filepath: str = ".env.monitoring") -> None:
    """
    Generate secure monitoring environment file.

    Args:
        filepath: Path to save the environment file
    """
    grafana_creds = get_grafana_credentials()
    prometheus_config = get_prometheus_credentials()

    env_content = f"""# Monitoring Security Configuration
# Generated automatically - DO NOT commit to version control

# Grafana Admin Credentials
GRAFANA_ADMIN_USER={grafana_creds["username"]}
GRAFANA_ADMIN_PASSWORD={grafana_creds["password"]}

# Grafana Security Settings
GF_SECURITY_DISABLE_INITIAL_ADMIN_CREATION=false
GF_SECURITY_DISABLE_GRAVATAR=true
GF_SECURITY_COOKIE_SECURE=true
GF_SECURITY_COOKIE_SAMESITE=strict
GF_SECURITY_STRICT_TRANSPORT_SECURITY=true
GF_SECURITY_X_CONTENT_TYPE_OPTIONS=true
GF_SECURITY_X_XSS_PROTECTION=true
GF_SECURITY_CONTENT_SECURITY_POLICY=true

# Session Security
GF_SESSION_PROVIDER=file
GF_SESSION_COOKIE_SECURE=true
GF_SESSION_SESSION_LIFE_TIME=86400

# Authentication
GF_AUTH_DISABLE_LOGIN_FORM=false
GF_AUTH_DISABLE_SIGNOUT_MENU=false
GF_AUTH_ANONYMOUS_ENABLED=false

# Prometheus Configuration
PROMETHEUS_USER={prometheus_config.get("username", "")}
PROMETHEUS_PASSWORD={prometheus_config.get("password", "")}
PROMETHEUS_EXTERNAL_URL={prometheus_config["web_external_url"]}

# AlertManager Configuration
ALERTMANAGER_USER=alert_admin_{secrets.token_hex(4)}
ALERTMANAGER_PASSWORD={generate_secure_password(24)}

# General Monitoring Settings
MONITORING_RETENTION_DAYS=30
MONITORING_SCRAPE_INTERVAL=15s
MONITORING_EVALUATION_INTERVAL=15s
"""

    # Write to file with restricted permissions
    with open(filepath, "w") as f:
        f.write(env_content)

    # Set restrictive file permissions (Unix-like systems)
    try:
        import stat

        os.chmod(filepath, stat.S_IRUSR | stat.S_IWUSR)  # 600 permissions
    except:
        pass

    logger.info(f"Monitoring environment file generated: {filepath}")
    logger.warning("IMPORTANT: Save the credentials securely and do not commit to version control")


def validate_monitoring_security() -> Dict[str, bool]:
    """
    Validate monitoring security configuration.

    Returns:
        Dict with validation results
    """
    results = {
        "grafana_credentials_secure": True,
        "prometheus_configured": True,
        "tls_enabled": False,
        "authentication_enabled": True,
    }

    # Check Grafana credentials
    grafana_creds = get_grafana_credentials()
    if grafana_creds["username"] == "admin" or grafana_creds["password"] == "admin":
        results["grafana_credentials_secure"] = False
        logger.error("SECURITY RISK: Grafana using default credentials")

    # Check Prometheus configuration
    prometheus_config = get_prometheus_credentials()
    if not prometheus_config.get("basic_auth_enabled"):
        results["authentication_enabled"] = False
        logger.warning("Prometheus basic auth not enabled")

    # Check TLS
    if prometheus_config.get("tls_enabled"):
        results["tls_enabled"] = True

    return results


if __name__ == "__main__":
    # Generate secure monitoring configuration
    print("Generating secure monitoring configuration...")
    generate_monitoring_env_file()

    # Validate security
    print("\nValidating monitoring security...")
    validation = validate_monitoring_security()

    for check, passed in validation.items():
        status = "✓" if passed else "✗"
        print(f"{status} {check}: {passed}")

    if all(validation.values()):
        print("\n✓ All monitoring security checks passed!")
    else:
        print("\n⚠ Some security checks failed. Please review the configuration.")
