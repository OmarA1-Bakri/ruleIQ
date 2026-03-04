"""

Context variables for sharing request-scoped data.
"""

from contextvars import ContextVar
from typing import Optional
from uuid import UUID

# Context variable to hold the request ID
request_id_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)

# Context variable to hold the user ID
user_id_var: ContextVar[Optional[UUID]] = ContextVar("user_id", default=None)
