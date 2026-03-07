"""
Response Formatter

Formats AI responses for display.
"""

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


class ResponseFormatter:
    """Formats responses for different output contexts."""

    @staticmethod
    def format_for_api(response: Dict[str, Any]) -> Dict[str, Any]:
        """Format response for API output."""
        return response

    @staticmethod
    def format_for_display(response: Dict[str, Any]) -> str:
        """Format response as human-readable text."""
        if isinstance(response, dict):
            if "text" in response:
                return response["text"]
            elif "guidance" in response:
                return response["guidance"]
        return str(response)
