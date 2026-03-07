"""
Unit tests for middleware/security_headers.py — SecurityHeadersMiddleware,
CSPViolationHandler, and factory functions.

No external services required.
"""

import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault("TESTING", "true")
os.environ.setdefault("ENVIRONMENT", "testing")

from middleware.security_headers import (
    SecurityHeadersMiddleware,
    CSPViolationHandler,
    create_security_headers_middleware,
)


# ---------------------------------------------------------------------------
# SecurityHeadersMiddleware — header injection
# ---------------------------------------------------------------------------

class TestBasicSecurityHeaders:
    """Tests for _add_basic_security_headers()."""

    def setup_method(self):
        self.mw = SecurityHeadersMiddleware(
            app=MagicMock(),
            csp_enabled=False,
            cors_enabled=False,
        )

    def test_x_content_type_options(self):
        resp = MagicMock()
        resp.headers = {}
        self.mw._add_basic_security_headers(resp)
        assert resp.headers["X-Content-Type-Options"] == "nosniff"

    def test_x_xss_protection(self):
        resp = MagicMock()
        resp.headers = {}
        self.mw._add_basic_security_headers(resp)
        assert resp.headers["X-XSS-Protection"] == "1; mode=block"

    def test_x_frame_options(self):
        resp = MagicMock()
        resp.headers = {}
        self.mw._add_basic_security_headers(resp)
        assert resp.headers["X-Frame-Options"] == "DENY"

    def test_referrer_policy(self):
        resp = MagicMock()
        resp.headers = {}
        self.mw._add_basic_security_headers(resp)
        assert resp.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"

    def test_hsts(self):
        resp = MagicMock()
        resp.headers = {}
        self.mw._add_basic_security_headers(resp)
        assert "max-age=31536000" in resp.headers["Strict-Transport-Security"]
        assert "includeSubDomains" in resp.headers["Strict-Transport-Security"]

    def test_permissions_policy(self):
        resp = MagicMock()
        resp.headers = {}
        self.mw._add_basic_security_headers(resp)
        pp = resp.headers["Permissions-Policy"]
        assert "camera=()" in pp
        assert "microphone=()" in pp
        assert "geolocation=()" in pp


# ---------------------------------------------------------------------------
# CSP header
# ---------------------------------------------------------------------------

class TestCSPHeader:
    """Tests for _add_csp_header()."""

    def test_default_csp_includes_self(self):
        mw = SecurityHeadersMiddleware(
            app=MagicMock(),
            csp_enabled=True,
            nonce_enabled=False,
        )
        resp = MagicMock()
        resp.headers = {}
        mw._add_csp_header(resp, nonce=None)
        csp = resp.headers["Content-Security-Policy"]
        assert "default-src 'self'" in csp
        assert "object-src 'none'" in csp

    def test_custom_csp(self):
        custom = "default-src 'none'; script-src 'self'"
        mw = SecurityHeadersMiddleware(
            app=MagicMock(),
            csp_enabled=True,
            custom_csp=custom,
        )
        resp = MagicMock()
        resp.headers = {}
        mw._add_csp_header(resp)
        assert resp.headers["Content-Security-Policy"] == custom

    def test_nonce_injected(self):
        mw = SecurityHeadersMiddleware(
            app=MagicMock(),
            csp_enabled=True,
            nonce_enabled=True,
        )
        resp = MagicMock()
        resp.headers = {}
        mw._add_csp_header(resp, nonce="abc123")
        csp = resp.headers["Content-Security-Policy"]
        assert "'nonce-abc123'" in csp

    def test_report_uri_appended(self):
        mw = SecurityHeadersMiddleware(
            app=MagicMock(),
            csp_enabled=True,
            nonce_enabled=False,
            report_uri="https://example.com/csp-report",
        )
        resp = MagicMock()
        resp.headers = {}
        mw._add_csp_header(resp)
        csp = resp.headers["Content-Security-Policy"]
        assert "report-uri https://example.com/csp-report" in csp


# ---------------------------------------------------------------------------
# CORS headers
# ---------------------------------------------------------------------------

class TestCORSHeaders:
    """Tests for _add_cors_headers()."""

    def setup_method(self):
        self.mw = SecurityHeadersMiddleware(
            app=MagicMock(),
            cors_enabled=True,
            csp_enabled=False,
        )

    def test_allowed_origin_echoed(self):
        request = MagicMock()
        request.headers = {"Origin": "https://app.ruleiq.com"}
        request.method = "GET"
        resp = MagicMock()
        resp.headers = {}

        self.mw._add_cors_headers(request, resp)
        assert resp.headers["Access-Control-Allow-Origin"] == "https://app.ruleiq.com"

    def test_disallowed_origin_not_echoed(self):
        request = MagicMock()
        request.headers = {"Origin": "https://evil.com"}
        request.method = "GET"
        resp = MagicMock()
        resp.headers = {}

        self.mw._add_cors_headers(request, resp)
        # Should NOT set ACAO for disallowed origin
        assert "Access-Control-Allow-Origin" not in resp.headers

    def test_allow_methods(self):
        request = MagicMock()
        request.headers = {"Origin": "https://app.ruleiq.com"}
        request.method = "GET"
        resp = MagicMock()
        resp.headers = {}

        self.mw._add_cors_headers(request, resp)
        methods = resp.headers["Access-Control-Allow-Methods"]
        assert "GET" in methods
        assert "POST" in methods

    def test_allow_credentials(self):
        request = MagicMock()
        request.headers = {"Origin": "https://app.ruleiq.com"}
        request.method = "GET"
        resp = MagicMock()
        resp.headers = {}

        self.mw._add_cors_headers(request, resp)
        assert resp.headers["Access-Control-Allow-Credentials"] == "true"


# ---------------------------------------------------------------------------
# Advanced security headers
# ---------------------------------------------------------------------------

class TestAdvancedSecurityHeaders:
    """Tests for _add_advanced_security_headers()."""

    def setup_method(self):
        self.mw = SecurityHeadersMiddleware(app=MagicMock())

    def test_expect_ct(self):
        resp = MagicMock()
        resp.headers = {}
        resp.status_code = 200
        self.mw._add_advanced_security_headers(resp)
        assert "enforce" in resp.headers["Expect-CT"]

    def test_cross_origin_policies(self):
        resp = MagicMock()
        resp.headers = {}
        resp.status_code = 200
        self.mw._add_advanced_security_headers(resp)
        assert resp.headers["Cross-Origin-Embedder-Policy"] == "require-corp"
        assert resp.headers["Cross-Origin-Opener-Policy"] == "same-origin"
        assert resp.headers["Cross-Origin-Resource-Policy"] == "same-origin"

    def test_cache_control_for_200(self):
        resp = MagicMock()
        resp.headers = {}
        resp.status_code = 200
        self.mw._add_advanced_security_headers(resp)
        assert "no-store" in resp.headers["Cache-Control"]
        assert resp.headers["Pragma"] == "no-cache"
        assert resp.headers["Expires"] == "0"

    def test_no_cache_control_for_non_200(self):
        resp = MagicMock()
        resp.headers = {}
        resp.status_code = 404
        self.mw._add_advanced_security_headers(resp)
        # Cache-Control should NOT be set for non-200
        assert "Cache-Control" not in resp.headers


# ---------------------------------------------------------------------------
# Nonce generation
# ---------------------------------------------------------------------------

class TestNonceGeneration:
    """Tests for _generate_nonce()."""

    def test_nonce_is_string(self):
        mw = SecurityHeadersMiddleware(app=MagicMock())
        nonce = mw._generate_nonce()
        assert isinstance(nonce, str)
        assert len(nonce) > 10  # URL-safe base64 of 16 bytes

    def test_nonces_are_unique(self):
        mw = SecurityHeadersMiddleware(app=MagicMock())
        nonces = {mw._generate_nonce() for _ in range(100)}
        assert len(nonces) == 100  # All should be unique


# ---------------------------------------------------------------------------
# Configuration mutation methods
# ---------------------------------------------------------------------------

class TestConfigMutation:
    """Tests for update_csp_directive, add/remove_allowed_origin."""

    def test_update_csp_directive(self):
        mw = SecurityHeadersMiddleware(app=MagicMock())
        mw.update_csp_directive("img-src", ["'self'", "https://cdn.example.com"])
        assert "https://cdn.example.com" in mw.default_csp["img-src"]

    def test_add_allowed_origin(self):
        mw = SecurityHeadersMiddleware(app=MagicMock())
        mw.add_allowed_origin("https://partner.com")
        assert "https://partner.com" in mw.cors_config["allowed_origins"]

    def test_add_duplicate_origin_no_change(self):
        mw = SecurityHeadersMiddleware(app=MagicMock())
        mw.add_allowed_origin("https://app.ruleiq.com")
        count = mw.cors_config["allowed_origins"].count("https://app.ruleiq.com")
        assert count == 1

    def test_remove_allowed_origin(self):
        mw = SecurityHeadersMiddleware(app=MagicMock())
        mw.add_allowed_origin("https://temp.com")
        mw.remove_allowed_origin("https://temp.com")
        assert "https://temp.com" not in mw.cors_config["allowed_origins"]

    def test_remove_nonexistent_origin_no_error(self):
        mw = SecurityHeadersMiddleware(app=MagicMock())
        mw.remove_allowed_origin("https://nonexistent.com")  # No error


# ---------------------------------------------------------------------------
# Security report
# ---------------------------------------------------------------------------

class TestSecurityReport:
    """Tests for get_security_report()."""

    def test_report_structure(self):
        mw = SecurityHeadersMiddleware(app=MagicMock())
        report = mw.get_security_report()
        assert "csp_enabled" in report
        assert "cors_enabled" in report
        assert "nonce_enabled" in report
        assert "csp_directives" in report
        assert "cors_config" in report


# ---------------------------------------------------------------------------
# CSPViolationHandler
# ---------------------------------------------------------------------------

class TestCSPViolationHandler:
    """Tests for CSPViolationHandler."""

    def test_empty_summary(self):
        handler = CSPViolationHandler()
        summary = handler.get_violations_summary()
        assert summary["total"] == 0

    @pytest.mark.asyncio
    async def test_handle_violation(self):
        handler = CSPViolationHandler()
        request = AsyncMock()
        request.json.return_value = {
            "csp-report": {
                "document-uri": "https://example.com/page",
                "blocked-uri": "https://evil.com/script.js",
                "violated-directive": "script-src",
            }
        }

        response = await handler.handle_violation(request)
        assert response.status_code == 204
        assert handler.violations[0]["violated_directive"] == "script-src"
        assert handler.violations[0]["blocked_uri"] == "https://evil.com/script.js"

    @pytest.mark.asyncio
    async def test_handle_invalid_json(self):
        handler = CSPViolationHandler()
        request = AsyncMock()
        request.json.side_effect = Exception("Bad JSON")

        response = await handler.handle_violation(request)
        assert response.status_code == 400

    def test_summary_groups_by_directive(self):
        handler = CSPViolationHandler()
        handler.violations = [
            {"violated_directive": "script-src", "blocked_uri": "a.js"},
            {"violated_directive": "script-src", "blocked_uri": "b.js"},
            {"violated_directive": "style-src", "blocked_uri": "c.css"},
        ]
        summary = handler.get_violations_summary()
        assert summary["total"] == 3
        assert summary["by_directive"]["script-src"] == 2
        assert summary["by_directive"]["style-src"] == 1

    def test_summary_recent_limited_to_10(self):
        handler = CSPViolationHandler()
        handler.violations = [
            {"violated_directive": f"dir-{i}", "blocked_uri": f"uri-{i}"}
            for i in range(20)
        ]
        summary = handler.get_violations_summary()
        assert len(summary["recent"]) == 10


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

class TestFactory:
    """Tests for create_security_headers_middleware factory."""

    def test_default_config(self):
        app = MagicMock()
        mw = create_security_headers_middleware(app)
        assert isinstance(mw, SecurityHeadersMiddleware)
        assert mw.csp_enabled is True
        assert mw.cors_enabled is True

    def test_custom_config(self):
        app = MagicMock()
        mw = create_security_headers_middleware(app, config={
            "csp_enabled": False,
            "nonce_enabled": False,
        })
        assert mw.csp_enabled is False
        assert mw.nonce_enabled is False
