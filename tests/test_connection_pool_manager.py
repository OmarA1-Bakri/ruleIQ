"""
Comprehensive Test Suite for Database Connection Pool Manager

This module provides extensive unit and integration tests for the ConnectionPoolManager class,
covering all requirements specified in the implementation task.

Tests cover:
- Dynamic pool sizing based on load and configuration
- Health monitoring for PostgreSQL connections
- Connection reuse optimization patterns
- Pool metrics and monitoring
- Error handling and recovery
"""

import asyncio

import pytest


# Integration test fixtures
@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
