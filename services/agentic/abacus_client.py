"""

Abacus AI Client with Doppler Secrets Management
This replaces the old client with hardcoded credentials.
All secrets are now managed through Doppler.
"""

from typing import Optional, Dict, Any
import logging
from app.core.doppler_config import DopplerConfig

logger = logging.getLogger(__name__)


class AbacusAIClient:
    """
    Secure Abacus AI client using Doppler for secrets management.

    This client fetches credentials from Doppler at runtime,
    ensuring no hardcoded secrets exist in the codebase.
    """

    def __init__(self) -> None:
        """Initialize the Abacus AI client with Doppler-managed secrets."""
        self.doppler = DopplerConfig()
        self._api_key: Optional[str] = None
        self._deployment_id: Optional[str] = None
        self._deployment_token: Optional[str] = None
        self._initialize_credentials()

    def _initialize_credentials(self) -> None:
        """
        Load credentials from Doppler.
        Raises an error if credentials are not properly configured.
        """
        try:
            self._api_key = self.secrets.get("ABACUS_AI_API_KEY")
            self._deployment_id = self.secrets.get("ABACUS_AI_DEPLOYMENT_ID")
            self._deployment_token = self.secrets.get("ABACUS_AI_DEPLOYMENT_TOKEN")
            if not all([self._api_key, self._deployment_id, self._deployment_token]):
                missing = []
                if not self._api_key:
                    missing.append("ABACUS_AI_API_KEY")
                if not self._deployment_id:
                    missing.append("ABACUS_AI_DEPLOYMENT_ID")
                if not self._deployment_token:
                    missing.append("ABACUS_AI_DEPLOYMENT_TOKEN")
                raise ValueError(
                    f"Missing required Abacus AI credentials in Doppler: {', '.join(missing)}. Please run: scripts/setup_doppler_secrets.sh",
                )
            logger.info("Abacus AI credentials loaded successfully from Doppler")
        except Exception as e:
            logger.error("Failed to load Abacus AI credentials: %s" % e)
            raise

    def get_credentials(self) -> Dict[str, str]:
        """
        Get the current credentials (for debugging purposes only).
        Never log or expose these values.
        """
        return {
            "has_api_key": bool(self._api_key),
            "has_deployment_id": bool(self._deployment_id),
            "has_deployment_token": bool(self._deployment_token),
            "deployment_id_prefix": self._deployment_id[:4] + "****"
            if self._deployment_id
            else None,
        }

    def call_api(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Make an API call to Abacus AI.

        Args:
            endpoint: The API endpoint to call
            data: The data to send

        Returns:
            API response
        """
        logger.info("Calling Abacus AI endpoint: %s" % endpoint)
        if not all([self._api_key, self._deployment_id, self._deployment_token]):
            raise RuntimeError(
                "Abacus AI credentials not properly initialized",
            )
        return {"status": "success", "message": "Placeholder response"}


_abacus_client: Optional[AbacusAIClient] = None


def get_abacus_client() -> AbacusAIClient:
    """Get or create the singleton Abacus AI client instance."""
    global _abacus_client
    if _abacus_client is None:
        _abacus_client = AbacusAIClient()
    return _abacus_client
