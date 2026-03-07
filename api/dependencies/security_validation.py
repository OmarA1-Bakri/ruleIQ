"""
FastAPI security validation dependencies.

This module provides ready-to-use dependency functions that can be easily
added to router endpoints for automatic security validation.
"""

from typing import Any, Dict, Optional
from fastapi import Depends, HTTPException, Request, UploadFile
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from api.utils.security_validation import (
    SecurityValidator,
    validate_evidence_data as _validate_evidence_data,
    validate_business_profile_data as _validate_business_profile_data,
    validate_integration_data as _validate_integration_data,
)
from middleware.audit_logging import log_security_event


class SecurityDependencies:
    """Collection of security validation dependencies."""

    @staticmethod
    async def validate_request(request: Request) -> Request:
        """
        Validate entire request for security threats.

        Usage:
        ```python
        @router.post("/endpoint", dependencies=[Depends(SecurityDependencies.validate_request)])
        async def endpoint():
            pass
        ```
        """
        try:
            # Validate headers
            SecurityValidator.validate_headers(dict(request.headers))

            # Validate query parameters
            if request.query_params:
                SecurityValidator.validate_query_params(dict(request.query_params))

            # Validate path parameters
            if request.path_params:
                SecurityValidator.validate_query_params(request.path_params)

            return request
        except HTTPException as e:
            # Log security validation failure
            await log_security_event(
                request=request, event_type="validation_failure", details={"error": str(e.detail)}
            )
            raise

    @staticmethod
    async def validate_json_body(request: Request) -> Dict[str, Any]:
        """
        Validate and return JSON request body.

        Usage:
        ```python
        @router.post("/endpoint")
        async def endpoint(data: Dict = Depends(SecurityDependencies.validate_json_body)):
            # Use validated data
            pass
        ```
        """
        try:
            body = await request.json()
            validated = SecurityValidator.validate_json_payload(body)

            # Log successful validation
            await log_security_event(
                request=request, event_type="validation_success", details={"data_type": "json_body"}
            )

            return validated
        except Exception as e:
            # Log validation failure
            await log_security_event(
                request=request,
                event_type="validation_failure",
                details={"error": str(e), "data_type": "json_body"},
            )
            if isinstance(e, HTTPException):
                raise
            raise HTTPException(status_code=400, detail=f"Invalid JSON body: {str(e)}")

    @staticmethod
    async def validate_file_upload(file: UploadFile, request: Request = None) -> UploadFile:
        """
        Validate uploaded file.

        Usage:
        ```python
        @router.post("/upload")
        async def upload(file: UploadFile = Depends(SecurityDependencies.validate_file_upload)):
            # Use validated file
            pass
        ```
        """
        try:
            validated_file, computed_size = await SecurityValidator.validate_file_upload(file)

            # Log file upload validation with computed size
            if request:
                await log_security_event(
                    request=request,
                    event_type="file_upload_validated",
                    details={
                        "filename": file.filename,
                        "content_type": file.content_type,
                        "size": computed_size,
                    },
                )

            return validated_file
        except HTTPException as e:
            # Log validation failure
            if request:
                await log_security_event(
                    request=request,
                    event_type="file_upload_rejected",
                    details={"filename": file.filename, "error": str(e.detail)},
                )
            raise

    @staticmethod
    async def validate_auth_token(
        credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer()), request: Request = None
    ) -> str:
        """
        Validate authentication token.

        Usage:
        ```python
        @router.get("/secure")
        async def secure(token: str = Depends(SecurityDependencies.validate_auth_token)):
            # Use validated token
            pass
        ```
        """
        if not credentials:
            if request:
                await log_security_event(
                    request=request,
                    event_type="auth_failure",
                    details={"reason": "missing_credentials"},
                )
            raise HTTPException(status_code=401, detail="Missing authentication credentials")

        try:
            token = credentials.credentials
            SecurityValidator.validate_no_dangerous_content(token, "authentication token")

            # Log successful auth validation
            if request:
                await log_security_event(
                    request=request,
                    event_type="auth_validated",
                    details={"token_prefix": token[:10] + "..."},
                )

            return token
        except HTTPException as e:
            if request:
                await log_security_event(
                    request=request,
                    event_type="auth_failure",
                    details={"reason": "invalid_token", "error": str(e.detail)},
                )
            raise

    @staticmethod
    async def validate_evidence_request(request: Request) -> Dict[str, Any]:
        """
        Validate evidence-specific request data.

        Usage:
        ```python
        @router.post("/evidence")
        async def create_evidence(data: Dict = Depends(SecurityDependencies.validate_evidence_request)):
            # Use validated evidence data
            pass
        ```
        """
        try:
            body = await request.json()
            validated = await _validate_evidence_data(body)

            await log_security_event(
                request=request,
                event_type="evidence_validation_success",
                details={"data_keys": list(validated.keys())},
            )

            return validated
        except Exception as e:
            await log_security_event(
                request=request, event_type="evidence_validation_failure", details={"error": str(e)}
            )
            if isinstance(e, HTTPException):
                raise
            raise HTTPException(status_code=400, detail=f"Invalid evidence data: {str(e)}")

    @staticmethod
    async def validate_business_profile_request(request: Request) -> Dict[str, Any]:
        """
        Validate business profile request data.

        Usage:
        ```python
        @router.post("/business-profile")
        async def update_profile(data: Dict = Depends(SecurityDependencies.validate_business_profile_request)):
            # Use validated profile data
            pass
        ```
        """
        try:
            body = await request.json()
            validated = await _validate_business_profile_data(body)

            await log_security_event(
                request=request,
                event_type="profile_validation_success",
                details={"data_keys": list(validated.keys())},
            )

            return validated
        except Exception as e:
            await log_security_event(
                request=request, event_type="profile_validation_failure", details={"error": str(e)}
            )
            if isinstance(e, HTTPException):
                raise
            raise HTTPException(status_code=400, detail=f"Invalid business profile data: {str(e)}")

    @staticmethod
    async def validate_integration_request(request: Request) -> Dict[str, Any]:
        """
        Validate integration configuration request.

        Usage:
        ```python
        @router.post("/integration")
        async def configure_integration(data: Dict = Depends(SecurityDependencies.validate_integration_request)):
            # Use validated integration data
            pass
        ```
        """
        try:
            body = await request.json()
            validated = await _validate_integration_data(body)

            # Don't log sensitive credential data
            log_data = {k: v for k, v in validated.items() if k != "credentials"}
            await log_security_event(
                request=request,
                event_type="integration_validation_success",
                details={"data_keys": list(log_data.keys())},
            )

            return validated
        except Exception as e:
            await log_security_event(
                request=request,
                event_type="integration_validation_failure",
                details={"error": str(e)},
            )
            if isinstance(e, HTTPException):
                raise
            raise HTTPException(status_code=400, detail=f"Invalid integration data: {str(e)}")

    @staticmethod
    async def validate_query_params(
        request: Request, allowed_params: Optional[list] = None
    ) -> Dict[str, Any]:
        """
        Validate query parameters against whitelist.

        Usage:
        ```python
        @router.get("/search")
        async def search(params: Dict = Depends(lambda r: SecurityDependencies.validate_query_params(r, ["q", "page", "limit"]))):
            # Use validated query params
            pass
        ```
        """
        query_params = dict(request.query_params)

        # Check against whitelist if provided
        if allowed_params:
            invalid_params = set(query_params.keys()) - set(allowed_params)
            if invalid_params:
                await log_security_event(
                    request=request,
                    event_type="invalid_query_params",
                    details={"invalid_params": list(invalid_params)},
                )
                raise HTTPException(
                    status_code=400, detail=f"Invalid query parameters: {', '.join(invalid_params)}"
                )

        try:
            validated = SecurityValidator.validate_query_params(query_params)
            return validated
        except HTTPException as e:
            await log_security_event(
                request=request,
                event_type="query_param_validation_failure",
                details={"error": str(e.detail)},
            )
            raise

    @staticmethod
    async def validate_form_data(request: Request, **form_fields) -> Dict[str, Any]:
        """
        Validate form data fields.

        Usage:
        ```python
        @router.post("/form")
        async def submit_form(
            username: str = Form(...),
            email: str = Form(...),
            validated: Dict = Depends(SecurityDependencies.validate_form_data)
        ):
            # Form fields are automatically validated
            pass
        ```
        """
        validated = {}
        for field_name, field_value in form_fields.items():
            if isinstance(field_value, str):
                validated[field_name] = SecurityValidator.validate_no_dangerous_content(
                    field_value, field_name
                )
            else:
                validated[field_name] = field_value

        await log_security_event(
            request=request,
            event_type="form_validation_success",
            details={"fields": list(validated.keys())},
        )

        return validated


# Convenience imports for direct use
validate_request = SecurityDependencies.validate_request
validate_json_body = SecurityDependencies.validate_json_body
validate_file_upload = SecurityDependencies.validate_file_upload
validate_auth_token = SecurityDependencies.validate_auth_token
validate_evidence_request = SecurityDependencies.validate_evidence_request
validate_business_profile_request = SecurityDependencies.validate_business_profile_request
validate_integration_request = SecurityDependencies.validate_integration_request
validate_query_params = SecurityDependencies.validate_query_params
validate_form_data = SecurityDependencies.validate_form_data


# Export all dependencies
__all__ = [
    "SecurityDependencies",
    "validate_request",
    "validate_json_body",
    "validate_file_upload",
    "validate_auth_token",
    "validate_evidence_request",
    "validate_business_profile_request",
    "validate_integration_request",
    "validate_query_params",
    "validate_form_data",
]
