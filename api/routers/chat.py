"""
Chat Router Façade - Backward Compatibility Layer

This file is a façade that re-exports the modular chat router implementation.
The actual implementation has been refactored into focused domain modules under
api/routers/chat/ directory.

Legacy imports like:
    from api.routers.chat import router

Will continue to work and now resolve to the modular implementation.

For new code, you can import directly from the package:
    from api.routers.chat import router

Migration Status: FAÇADE ACTIVE (Jan 2025)
Original monolith: 1,606 lines → Refactored into 6 focused modules
"""

# Re-export the unified router from the modular implementation
from api.routers.chat import router

# Re-export any commonly used symbols for full backward compatibility
__all__ = ["router"]
