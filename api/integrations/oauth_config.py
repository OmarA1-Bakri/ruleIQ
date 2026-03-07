"""

OAuth2 configuration for integrations
"""

from pydantic import BaseSettings


class OAuth2Config(BaseSettings):
    """OAuth2 configuration for various providers"""

    # Google OAuth2
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/api/integrations/google/callback"
    GOOGLE_SCOPES: list = [
        "https://www.googleapis.com/auth/admin.reports.audit.readonly",
        "https://www.googleapis.com/auth/admin.directory.user.readonly",
        "https://www.googleapis.com/auth/admin.directory.device.chromeos.readonly",
        "https://www.googleapis.com/auth/admin.directory.domain.readonly",
        "https://www.googleapis.com/auth/admin.security.readonly",
    ]

    # Microsoft OAuth2
    MICROSOFT_CLIENT_ID: str = ""
    MICROSOFT_CLIENT_SECRET: str = ""
    MICROSOFT_TENANT_ID: str = ""
    MICROSOFT_REDIRECT_URI: str = "http://localhost:8000/api/integrations/microsoft/callback"
    MICROSOFT_SCOPES: list = ["https://graph.microsoft.com/.default"]

    # AWS (uses different auth method)
    AWS_ROLE_ARN: str = ""
    AWS_EXTERNAL_ID: str = ""

    class Config:
        env_file = ".env"
        case_sensitive = True

    def get_google_oauth_url(self, state: str) -> str:
        """Generate Google OAuth URL"""
        from urllib.parse import urlencode

        params = {
            "client_id": self.GOOGLE_CLIENT_ID,
            "redirect_uri": self.GOOGLE_REDIRECT_URI,
            "response_type": "code",
            "scope": " ".join(self.GOOGLE_SCOPES),
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
        }

        return f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"

    def get_microsoft_oauth_url(self, state: str) -> str:
        """Generate Microsoft OAuth URL"""
        from urllib.parse import urlencode

        params = {
            "client_id": self.MICROSOFT_CLIENT_ID,
            "response_type": "code",
            "redirect_uri": self.MICROSOFT_REDIRECT_URI,
            "response_mode": "query",
            "scope": " ".join(self.MICROSOFT_SCOPES),
            "state": state,
        }

        if self.MICROSOFT_TENANT_ID:
            base_url = f"https://login.microsoftonline.com/{self.MICROSOFT_TENANT_ID}/oauth2/v2.0/authorize"
        else:
            base_url = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"

        return f"{base_url}?{urlencode(params)}"


oauth2_config = OAuth2Config()
