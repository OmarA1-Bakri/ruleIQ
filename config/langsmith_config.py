"""

LangSmith Configuration for ruleIQ Assessment Agent

This module provides configuration and utilities for LangSmith tracing
to enable observability of the LangGraph assessment agent.

Usage:
1. Set environment variables:
   - LANGCHAIN_TRACING_V2=true
   - LANGCHAIN_API_KEY=your_langsmith_api_key
   - LANGCHAIN_PROJECT=ruleiq-assessment (optional, defaults to this)

2. View traces at: https://smith.langchain.com

3. The assessment agent will automatically enable tracing when these
   environment variables are detected.

Example .env configuration:
```
# LangSmith Tracing (optional but recommended for debugging)
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=ls__your_api_key_here
LANGCHAIN_PROJECT=ruleiq-assessment
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
```
"""

import logging

import os
import time
from typing import Optional, Dict, Any, List, Generator
from functools import wraps
from config.logging_config import get_logger

try:
    from langchain_core.tracers.context import tracing_v2_enabled
except ImportError:
    from contextlib import contextmanager

    @contextmanager
    def tracing_v2_enabled(**kwargs) -> Generator[Any, None, None]:
        yield


logger = get_logger(__name__)


class LangSmithConfig:
    """Configuration manager for LangSmith tracing."""

    @staticmethod
    def is_tracing_enabled() -> bool:
        """Check if LangSmith tracing is enabled."""
        return os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true"

    @staticmethod
    def get_api_key() -> Optional[str]:
        """Get LangSmith API key from environment."""
        return os.getenv("LANGCHAIN_API_KEY")

    @staticmethod
    def get_project_name() -> str:
        """Get LangSmith project name."""
        return os.getenv("LANGCHAIN_PROJECT", "ruleiq-assessment")

    @staticmethod
    def get_endpoint() -> str:
        """Get LangSmith API endpoint."""
        return os.getenv("LANGCHAIN_ENDPOINT", "https://api.smith.langchain.com")

    @staticmethod
    def validate_configuration() -> bool:
        """
        Validate LangSmith configuration.

        Returns:
            True if configuration is valid, False otherwise
        """
        if not LangSmithConfig.is_tracing_enabled():
            logger.debug("LangSmith tracing is disabled")
            return False
        api_key = LangSmithConfig.get_api_key()
        if not api_key:
            logger.warning(
                "LANGCHAIN_TRACING_V2 is enabled but LANGCHAIN_API_KEY is not set. Please set LANGCHAIN_API_KEY to enable tracing.",
            )
            return False
        if not api_key.startswith("ls__"):
            logger.warning(
                "LANGCHAIN_API_KEY should start with 'ls__'. Please check your API key format.",
            )
            return False
        project = LangSmithConfig.get_project_name()
        endpoint = LangSmithConfig.get_endpoint()
        logger.info("LangSmith tracing configured:")
        logger.info("  Project: %s" % project)
        logger.info("  Endpoint: %s" % endpoint)
        logger.info("  View traces at: https://smith.langchain.com")
        return True

    @staticmethod
    def get_trace_metadata(
        session_id: Optional[str] = None, lead_id: Optional[str] = None, **kwargs
    ) -> Dict[str, Any]:
        """
        Generate metadata for tracing.

        Args:
            session_id: Assessment session ID
            lead_id: Lead ID
            **kwargs: Additional metadata

        Returns:
            Metadata dictionary for tracing
        """
        metadata = {
            "application": "ruleiq",
            "component": "assessment_agent",
            "environment": os.getenv("ENVIRONMENT", "development"),
        }
        if session_id:
            metadata["session_id"] = session_id
        if lead_id:
            metadata["lead_id"] = lead_id
        metadata.update(kwargs)
        return metadata

    @staticmethod
    def get_trace_tags(operation: str, phase: Optional[str] = None, **kwargs) -> list:
        """
        Generate tags for tracing.

        Args:
            operation: The operation being traced
            phase: Assessment phase
            **kwargs: Additional tags

        Returns:
            List of tags for tracing
        """
        tags = ["ruleiq", "assessment", "langgraph", operation]
        if phase:
            tags.append(f"phase:{phase}")
        for key, value in kwargs.items():
            tags.append(f"{key}:{value}")
        return tags

    @staticmethod
    def add_custom_tags(tags: List[str], **custom_tags) -> List[str]:
        """
        Add custom tags for enhanced filtering in LangSmith UI.

        Args:
            tags: Existing tags list
            **custom_tags: Custom tag key-value pairs

        Returns:
            Enhanced tags list

        Usage:
            tags = LangSmithConfig.add_custom_tags(
                tags,
                environment="production",
                version="1.2.0",
                customer="enterprise",
                priority="high",
            )
        """
        enhanced_tags = tags.copy()
        for key, value in custom_tags.items():
            if value is not None:
                enhanced_tags.append(f"{key}:{value}")
        import os

        env = os.getenv("ENVIRONMENT", "development")
        enhanced_tags.append(f"env:{env}")
        version = os.getenv("APP_VERSION")
        if version:
            enhanced_tags.append(f"version:{version}")
        if env == "production":
            enhanced_tags.append("tier:critical")
        elif env == "staging":
            enhanced_tags.append("tier:important")
        else:
            enhanced_tags.append("tier:standard")
        return enhanced_tags

    @staticmethod
    def create_filter_query(
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        phase: Optional[str] = None,
        status: Optional[str] = None,
        date_range: Optional[tuple] = None,
    ) -> Dict[str, Any]:
        """
        Create a filter query for LangSmith traces.

        Args:
            session_id: Filter by session
            user_id: Filter by user
            phase: Filter by workflow phase
            status: Filter by status (success/error)
            date_range: Tuple of (start_date, end_date)

        Returns:
            Filter query dictionary for LangSmith API
        """
        query = {}
        if session_id:
            query["tags"] = query.get("tags", [])
            query["tags"].append(f"session:{session_id}")
        if user_id:
            query["tags"] = query.get("tags", [])
            query["tags"].append(f"user:{user_id}")
        if phase:
            query["tags"] = query.get("tags", [])
            query["tags"].append(f"phase:{phase}")
        if status:
            query["metadata.status"] = status
        if date_range:
            start_date, end_date = date_range
            query["date_range"] = {
                "start": start_date.isoformat() if hasattr(start_date, "isoformat") else start_date,
                "end": end_date.isoformat() if hasattr(end_date, "isoformat") else end_date,
            }
        return query

    @staticmethod
    def _extract_metadata(args: tuple, kwargs: dict) -> Dict[str, Any]:
        """
        Extract metadata from function arguments.

        Args:
            args: Function positional arguments
            kwargs: Function keyword arguments

        Returns:
            Dictionary of extracted metadata
        """
        metadata = {}
        if "state" in kwargs and isinstance(kwargs["state"], dict):
            state = kwargs["state"]
            if "session_id" in state:
                metadata["session_id"] = state["session_id"]
            if "current_phase" in state:
                metadata["current_phase"] = state["current_phase"]
            if "user_id" in state:
                metadata["user_id"] = state["user_id"]
        if args and isinstance(args[0], dict):
            state = args[0]
            if "session_id" in state and "session_id" not in metadata:
                metadata["session_id"] = state["session_id"]
            if "current_phase" in state and "current_phase" not in metadata:
                metadata["current_phase"] = state["current_phase"]
            if "user_id" in state and "user_id" not in metadata:
                metadata["user_id"] = state["user_id"]
        return metadata

    @staticmethod
    def _generate_tags(operation: str, metadata: Dict[str, Any]) -> List[str]:
        """
        Generate tags from operation and metadata.

        Args:
            operation: Operation name
            metadata: Metadata dictionary

        Returns:
            List of tags for tracing
        """
        tags = [operation]
        if "session_id" in metadata:
            tags.append(f"session:{metadata['session_id']}")
        if "current_phase" in metadata:
            tags.append(f"phase:{metadata['current_phase']}")
        if "user_id" in metadata:
            tags.append(f"user:{metadata['user_id']}")
        if "." in operation:
            parts = operation.split(".")
            tags.append(f"{parts[0]}.{parts[1]}")
        return tags


def with_langsmith_tracing(
    operation: str,
    include_input: bool = True,
    include_output: bool = True,
    custom_name: Optional[str] = None,
) -> Any:
    """
    Enhanced decorator for adding LangSmith tracing to async functions.

    Args:
        operation: Name of the operation being traced
        include_input: Whether to include function inputs in metadata
        include_output: Whether to include function outputs in metadata
        custom_name: Optional custom name for the run (overrides operation)

    Returns:
        Decorated function with LangSmith tracing
    """

    def decorator(func) -> Any:

        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            if not LangSmithConfig.is_tracing_enabled():
                return await func(*args, **kwargs)
            metadata = LangSmithConfig._extract_metadata(args, kwargs)
            metadata["operation"] = operation
            metadata["function"] = func.__name__
            metadata["module"] = func.__module__
            if include_input:
                metadata["inputs"] = {"args": str(args)[:500], "kwargs": str(kwargs)[:500]}
            tags = LangSmithConfig._generate_tags(operation, metadata)
            run_name = custom_name if custom_name else operation
            start_time = time.perf_counter()
            final_metadata = metadata.copy()
            try:
                with tracing_v2_enabled(
                    project_name=LangSmithConfig.get_project_name(),
                    tags=tags,
                    metadata=final_metadata,
                    run_name=run_name,
                ):
                    result = await func(*args, **kwargs)
                    execution_time = time.perf_counter() - start_time
                    final_metadata["execution_time_seconds"] = execution_time
                    final_metadata["status"] = "success"
                    if include_output:
                        final_metadata["output"] = str(result)[:500] if result else None
                    logger.debug(
                        "Traced %s - %s (execution_time: %ss)"
                        % (operation, func.__name__, execution_time)
                    )
                    return result
            except Exception as e:
                execution_time = time.perf_counter() - start_time
                final_metadata["execution_time_seconds"] = execution_time
                final_metadata["status"] = "error"
                final_metadata["error"] = str(e)
                final_metadata["error_type"] = type(e).__name__
                logger.error("Error in traced function %s: %s" % (func.__name__, str(e)))
                raise

        return wrapper

    return decorator


LANGSMITH_SETUP_INSTRUCTIONS = """
To enable LangSmith tracing for the ruleIQ assessment agent:

1. Sign up for LangSmith at https://smith.langchain.com

2. Get your API key from the LangSmith dashboard

3. Add these environment variables to your .env file:
   ```
   LANGCHAIN_TRACING_V2=true
   LANGCHAIN_API_KEY=ls__your_api_key_here
   LANGCHAIN_PROJECT=ruleiq-assessment
   ```

4. Restart your application

5. View traces at https://smith.langchain.com

The assessment agent will automatically detect these settings and enable tracing.

What you'll see in LangSmith:
- Complete conversation flow through the state graph
- Each node execution with inputs and outputs
- AI model calls with prompts and responses
- Error traces and fallback behavior
- Performance metrics for each step
- Complete assessment session timelines

This is invaluable for:
- Debugging conversation flows
- Understanding AI decision making
- Optimizing performance
- Monitoring production behavior
"""
if __name__ == "__main__":
    logging.info(LANGSMITH_SETUP_INSTRUCTIONS)
    logging.info("\nChecking current configuration...")
    if LangSmithConfig.validate_configuration():
        logging.info("✅ LangSmith tracing is properly configured!")
    else:
        logging.info("❌ LangSmith tracing is not configured or has issues.")
        logging.info("   Please follow the setup instructions above.")
