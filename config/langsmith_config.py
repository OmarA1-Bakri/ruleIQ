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

import os
from typing import Optional, Dict, Any
from functools import wraps
from config.logging_config import get_logger

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
                "LANGCHAIN_TRACING_V2 is enabled but LANGCHAIN_API_KEY is not set. "
                "Please set LANGCHAIN_API_KEY to enable tracing."
            )
            return False
        
        if not api_key.startswith("ls__"):
            logger.warning(
                "LANGCHAIN_API_KEY should start with 'ls__'. "
                "Please check your API key format."
            )
            return False
        
        project = LangSmithConfig.get_project_name()
        endpoint = LangSmithConfig.get_endpoint()
        
        logger.info(f"LangSmith tracing configured:")
        logger.info(f"  Project: {project}")
        logger.info(f"  Endpoint: {endpoint}")
        logger.info(f"  View traces at: https://smith.langchain.com")
        
        return True
    
    @staticmethod
    def get_trace_metadata(
        session_id: Optional[str] = None,
        lead_id: Optional[str] = None,
        **kwargs
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
    def get_trace_tags(
        operation: str,
        phase: Optional[str] = None,
        **kwargs
    ) -> list:
        """
        Generate tags for tracing.
        
        Args:
            operation: The operation being traced
            phase: Assessment phase
            **kwargs: Additional tags
            
        Returns:
            List of tags for tracing
        """
        tags = [
            "ruleiq",
            "assessment",
            "langgraph",
            operation,
        ]
        
        if phase:
            tags.append(f"phase:{phase}")
        
        # Add any additional tags from kwargs
        for key, value in kwargs.items():
            tags.append(f"{key}:{value}")
        
        return tags


def with_langsmith_tracing(
    operation: str,
    include_input: bool = True,
    include_output: bool = True
):
    """
    Decorator to add LangSmith tracing to async functions.
    
    Args:
        operation: Name of the operation being traced
        include_input: Whether to include function inputs in trace
        include_output: Whether to include function output in trace
    
    Usage:
        @with_langsmith_tracing("generate_question")
        async def my_function(self, arg1, arg2):
            ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            if not LangSmithConfig.is_tracing_enabled():
                # Tracing disabled, just run the function
                return await func(*args, **kwargs)
            
            from langchain_core.tracers.context import tracing_v2_enabled
            
            # Extract useful context if available
            metadata = {}
            tags = [operation]
            
            # Try to extract session_id from kwargs or args
            if "session_id" in kwargs:
                metadata["session_id"] = kwargs["session_id"]
                tags.append(f"session:{kwargs['session_id']}")
            
            if "state" in kwargs and isinstance(kwargs["state"], dict):
                if "session_id" in kwargs["state"]:
                    metadata["session_id"] = kwargs["state"]["session_id"]
                    tags.append(f"session:{kwargs['state']['session_id']}")
                if "current_phase" in kwargs["state"]:
                    tags.append(f"phase:{kwargs['state']['current_phase']}")
            
            # Add function inputs to metadata if requested
            if include_input:
                metadata["inputs"] = {
                    "args": str(args)[:500],  # Truncate for brevity
                    "kwargs": str(kwargs)[:500]
                }
            
            # Run function with tracing
            with tracing_v2_enabled(
                project_name=LangSmithConfig.get_project_name(),
                tags=tags,
                metadata=metadata
            ):
                result = await func(*args, **kwargs)
                
                # Add output to metadata if requested
                if include_output and result:
                    metadata["output_type"] = type(result).__name__
                    if isinstance(result, dict):
                        metadata["output_keys"] = list(result.keys())
                
                return result
        
        return wrapper
    return decorator


# Example usage instructions
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
    # Validate configuration when module is run directly
    print(LANGSMITH_SETUP_INSTRUCTIONS)
    print("\nChecking current configuration...")
    
    if LangSmithConfig.validate_configuration():
        print("✅ LangSmith tracing is properly configured!")
    else:
        print("❌ LangSmith tracing is not configured or has issues.")
        print("   Please follow the setup instructions above.")