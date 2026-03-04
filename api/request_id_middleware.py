"""

Custom middleware for the FastAPI application.
"""

import time
import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from api.context import request_id_var


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add a unique request ID to each incoming request and log the response time.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Generate a unique request ID
        request_id = str(uuid.uuid4())

        # Set the request ID in the context variable
        request_id_var.set(request_id)

        start_time = time.time()

        # Proceed with the request
        response = await call_next(request)

        # Add the request ID to the response headers
        response.headers["X-Request-ID"] = request_id

        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)

        return response
