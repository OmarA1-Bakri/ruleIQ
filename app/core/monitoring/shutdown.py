"""
import logging


logger = logging.getLogger(__name__)
Graceful shutdown handling for the application.
"""

import asyncio
import signal
import sys
from typing import Optional, Set, Callable, Any
from datetime import datetime, timezone
from .logger import get_logger

logger = get_logger(__name__)


class GracefulShutdown:
    """Manages graceful shutdown of the application."""

    def __init__(self, timeout: float = 30.0) -> None:
        """
        Initialize graceful shutdown handler.

        Args:
            timeout: Maximum time to wait for shutdown (seconds)
        """
        self.timeout = timeout
        self.shutdown_event = asyncio.Event()
        self.tasks: Set[asyncio.Task] = set()
        self.cleanup_callbacks: list[Callable] = []
        self._shutdown_initiated = False
        self._shutdown_start_time: Optional[datetime] = None

    def add_cleanup(self, callback: Callable) -> None:
        """
        Add a cleanup callback to run during shutdown.

        Args:
            callback: Async or sync function to call during shutdown
        """
        self.cleanup_callbacks.append(callback)

    def register_task(self, task: asyncio.Task) -> None:
        """
        Register a task to track during shutdown.

        Args:
            task: Asyncio task to track
        """
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)

    async def shutdown(self) -> None:
        """Perform graceful shutdown."""
        if self._shutdown_initiated:
            logger.warning("Shutdown already initiated, ignoring duplicate request")
            return
        self._shutdown_initiated = True
        self._shutdown_start_time = datetime.now(timezone.utc)
        logger.info(f"Initiating graceful shutdown (timeout: {self.timeout}s)")
        self.shutdown_event.set()
        for callback in self.cleanup_callbacks:
            try:
                logger.debug(f"Running cleanup callback: {callback.__name__}")
                if asyncio.iscoroutinefunction(callback):
                    await asyncio.wait_for(callback(), timeout=5.0)
                else:
                    callback()
            except asyncio.TimeoutError:
                logger.error(f"Cleanup callback {callback.__name__} timed out")
            except Exception as e:
                logger.error(f"Error in cleanup callback {callback.__name__}: {e}")
        if self.tasks:
            logger.info(f"Cancelling {len(self.tasks)} running tasks")
            for task in self.tasks:
                task.cancel()
            try:
                await asyncio.wait_for(
                    asyncio.gather(*self.tasks, return_exceptions=True), timeout=self.timeout / 2
                )
            except asyncio.TimeoutError:
                logger.warning(f"{len(self.tasks)} tasks did not complete in time")
        if self._shutdown_start_time:
            duration = (datetime.now(timezone.utc) - self._shutdown_start_time).total_seconds()
            logger.info(f"Graceful shutdown completed in {duration:.2f}s")

    def install_signal_handlers(self) -> None:
        """Install signal handlers for graceful shutdown."""

        def signal_handler(signum, frame) -> None:
            """Handle shutdown signal."""
            logger.info(f"Received signal {signum}")
            asyncio.create_task(self.shutdown())

        for sig in [signal.SIGTERM, signal.SIGINT]:
            signal.signal(sig, signal_handler)
        if sys.platform == "win32":
            signal.signal(signal.SIGBREAK, signal_handler)
        logger.info("Signal handlers installed for graceful shutdown")

    async def wait_for_shutdown(self) -> None:
        """Wait for shutdown signal."""
        await self.shutdown_event.wait()


class ConnectionDrainer:
    """Manages connection draining during shutdown."""

    def __init__(self, drain_timeout: float = 15.0) -> None:
        """
        Initialize connection drainer.

        Args:
            drain_timeout: Time to wait for connections to drain
        """
        self.drain_timeout = drain_timeout
        self.active_connections = 0
        self._lock = asyncio.Lock()
        self._draining = False

    async def __aenter__(self) -> Any:
        """Track connection entry."""
        async with self._lock:
            if self._draining:
                raise RuntimeError("Server is shutting down")
            self.active_connections += 1
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Track connection exit."""
        async with self._lock:
            self.active_connections -= 1

    async def drain(self) -> None:
        """Drain active connections."""
        async with self._lock:
            self._draining = True
        logger.info(f"Draining {self.active_connections} active connections")
        start_time = datetime.now(timezone.utc)
        while self.active_connections > 0:
            elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
            if elapsed > self.drain_timeout:
                logger.warning(
                    f"Drain timeout reached, {self.active_connections} connections still active"
                )
                break
            await asyncio.sleep(0.1)
        if self.active_connections == 0:
            logger.info("All connections drained successfully")


_shutdown_manager: Optional[GracefulShutdown] = None
_connection_drainer: Optional[ConnectionDrainer] = None


def get_shutdown_manager() -> GracefulShutdown:
    """Get or create the global shutdown manager."""
    global _shutdown_manager
    if _shutdown_manager is None:
        _shutdown_manager = GracefulShutdown()
    return _shutdown_manager


def get_connection_drainer() -> ConnectionDrainer:
    """Get or create the global connection drainer."""
    global _connection_drainer
    if _connection_drainer is None:
        _connection_drainer = ConnectionDrainer()
    return _connection_drainer


async def graceful_shutdown_middleware(request, call_next) -> Any:
    """
    Middleware to handle connection tracking during shutdown.

    Args:
        request: The incoming request
        call_next: Next middleware/handler in chain
    """
    drainer = get_connection_drainer()
    try:
        async with drainer:
            response = await call_next(request)
            return response
    except RuntimeError as e:
        if "shutting down" in str(e):
            from fastapi.responses import JSONResponse

            return JSONResponse(status_code=503, content={"detail": "Service is shutting down"})
        raise
