"""
Automatic Rollback System for RuleIQ

Monitors key metrics and triggers automatic rollback when thresholds
are exceeded, ensuring <5 minute recovery time.
"""

import asyncio
import subprocess
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from enum import Enum
from dataclasses import dataclass, field
import os

logger = logging.getLogger(__name__)


class DeploymentState(str, Enum):
    """Deployment state enumeration."""

    STABLE = "stable"
    DEPLOYING = "deploying"
    MONITORING = "monitoring"
    ROLLBACK_TRIGGERED = "rollback_triggered"
    ROLLING_BACK = "rolling_back"
    ROLLED_BACK = "rolled_back"


class RollbackReason(str, Enum):
    """Reasons for triggering rollback."""

    HIGH_ERROR_RATE = "high_error_rate"
    SLOW_RESPONSE = "slow_response"
    DB_CONNECTION_FAILURE = "db_connection_failure"
    REDIS_FAILURE = "redis_failure"
    AUTH_SPIKE = "auth_spike"
    AI_COST_EXCEEDED = "ai_cost_exceeded"
    MANUAL_TRIGGER = "manual_trigger"
    HEALTH_CHECK_FAILED = "health_check_failed"


@dataclass
class MetricThreshold:
    """Threshold configuration for a metric."""

    name: str
    current_value: float = 0.0
    threshold_value: float = 0.0
    duration_seconds: int = 60
    exceeded_at: Optional[datetime] = None

    def check_threshold(self, value: float) -> bool:
        """Check if threshold is exceeded."""
        self.current_value = value

        if value > self.threshold_value:
            if self.exceeded_at is None:
                self.exceeded_at = datetime.now(timezone.utc)

            # Check if duration requirement is met
            duration = (datetime.now(timezone.utc) - self.exceeded_at).total_seconds()
            return duration >= self.duration_seconds
        else:
            self.exceeded_at = None
            return False


@dataclass
class DeploymentVersion:
    """Deployment version information."""

    version: str
    deployed_at: datetime
    commit_hash: str
    docker_image: str
    config_snapshot: Dict[str, Any] = field(default_factory=dict)
    metrics_baseline: Dict[str, float] = field(default_factory=dict)


class AutomaticRollbackSystem:
    """
    Monitors deployments and triggers automatic rollback when issues are detected.
    Ensures <5 minute recovery time with blue-green deployment switching.
    """

    def __init__(self) -> None:
        self.state = DeploymentState.STABLE
        self.current_version: Optional[DeploymentVersion] = None
        self.previous_version: Optional[DeploymentVersion] = None
        self.rollback_history: List[Dict[str, Any]] = []

        # Metric thresholds
        self.thresholds = {
            "error_rate": MetricThreshold(
                name="error_rate",
                threshold_value=0.05,  # 5%
                duration_seconds=60,
            ),
            "response_time": MetricThreshold(
                name="response_time",
                threshold_value=2.0,  # 2x baseline
                duration_seconds=120,
            ),
            "db_connections": MetricThreshold(
                name="db_connections",
                threshold_value=0.8,  # 80% utilization
                duration_seconds=60,
            ),
            "auth_failures": MetricThreshold(
                name="auth_failures",
                threshold_value=100,  # 100 failures per minute
                duration_seconds=60,
            ),
            "ai_cost_rate": MetricThreshold(
                name="ai_cost_rate",
                threshold_value=10.0,  # $10 per minute
                duration_seconds=60,
            ),
        }

        self.monitoring_interval = 10  # seconds
        self.monitoring_task: Optional[asyncio.Task] = None
        self.rollback_in_progress = False

    async def deploy_new_version(self, version: str, commit_hash: str, docker_image: str) -> bool:
        """Deploy a new version with monitoring."""
        if self.state == DeploymentState.ROLLING_BACK:
            logger.error("Cannot deploy during rollback")
            return False

        logger.info(f"Starting deployment of version {version}")
        self.state = DeploymentState.DEPLOYING

        try:
            # Save current version as previous
            if self.current_version:
                self.previous_version = self.current_version

            # Capture baseline metrics
            baseline = await self._capture_baseline_metrics()

            # Create new version
            self.current_version = DeploymentVersion(
                version=version,
                deployed_at=datetime.now(timezone.utc),
                commit_hash=commit_hash,
                docker_image=docker_image,
                config_snapshot=await self._capture_config(),
                metrics_baseline=baseline,
            )

            # Backup sessions before deployment
            from services.session_manager import get_session_manager

            session_manager = await get_session_manager()
            await session_manager.backup_all_sessions()

            # Perform blue-green switch
            success = await self._blue_green_deploy(docker_image)

            if success:
                self.state = DeploymentState.MONITORING
                # Start monitoring
                if self.monitoring_task:
                    self.monitoring_task.cancel()
                self.monitoring_task = asyncio.create_task(self._monitor_deployment())

                logger.info(f"Deployment of version {version} successful, monitoring started")
                return True
            else:
                logger.error(f"Deployment of version {version} failed")
                self.state = DeploymentState.STABLE
                return False

        except Exception as e:
            logger.error(f"Deployment failed: {e}")
            self.state = DeploymentState.STABLE
            return False

    async def _blue_green_deploy(self, docker_image: str) -> bool:
        """Perform blue-green deployment switch."""
        try:
            # Update docker-compose with new image
            compose_file = "docker-compose.yml"
            backup_file = "docker-compose.backup.yml"

            # Backup current compose file
            subprocess.run(["cp", compose_file, backup_file], check=True)

            # Update image in compose file
            # In production, you'd use a proper YAML parser
            subprocess.run(
                ["sed", "-i", f"s|image:.*ruleiq.*|image: {docker_image}|g", compose_file],
                check=True,
            )

            # Deploy new version to green environment
            subprocess.run(
                ["docker-compose", "-f", "docker-compose.green.yml", "up", "-d"], check=True
            )

            # Wait for health check
            await asyncio.sleep(10)

            # Check if green is healthy
            if await self._check_green_health():
                # Switch traffic to green
                subprocess.run(
                    [
                        "docker-compose",
                        "-f",
                        "docker-compose.nginx.yml",
                        "exec",
                        "nginx",
                        "nginx",
                        "-s",
                        "reload",
                    ],
                    check=True,
                )

                # Stop blue after successful switch
                await asyncio.sleep(5)
                subprocess.run(
                    ["docker-compose", "-f", "docker-compose.blue.yml", "down"], check=True
                )

                return True
            else:
                # Green unhealthy, keep blue running
                subprocess.run(
                    ["docker-compose", "-f", "docker-compose.green.yml", "down"], check=True
                )
                return False

        except subprocess.CalledProcessError as e:
            logger.error(f"Blue-green deployment failed: {e}")
            return False

    async def _check_green_health(self) -> bool:
        """Check health of green deployment."""
        import aiohttp

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("http://localhost:8001/health") as response:
                    return response.status == 200
        except:
            return False

    async def trigger_rollback(self, reason: RollbackReason) -> bool:
        """Trigger automatic rollback to previous version."""
        if self.rollback_in_progress:
            logger.warning("Rollback already in progress")
            return False

        if not self.previous_version:
            logger.error("No previous version available for rollback")
            return False

        logger.critical(f"TRIGGERING ROLLBACK: {reason.value}")
        self.rollback_in_progress = True
        self.state = DeploymentState.ROLLBACK_TRIGGERED

        rollback_start = datetime.now(timezone.utc)

        try:
            # Record rollback event
            self.rollback_history.append(
                {
                    "triggered_at": rollback_start,
                    "reason": reason.value,
                    "from_version": self.current_version.version,
                    "to_version": self.previous_version.version,
                }
            )

            # Stop monitoring
            if self.monitoring_task:
                self.monitoring_task.cancel()

            self.state = DeploymentState.ROLLING_BACK

            # Perform rollback
            success = await self._perform_rollback()

            rollback_duration = (datetime.now(timezone.utc) - rollback_start).total_seconds()

            if success:
                self.state = DeploymentState.ROLLED_BACK
                logger.info(f"Rollback completed in {rollback_duration:.2f} seconds")

                # Restore sessions
                from services.session_manager import get_session_manager

                session_manager = await get_session_manager()
                await session_manager.restore_all_sessions()

                # Swap versions
                self.current_version = self.previous_version
                self.previous_version = None

                # Alert team
                await self._send_rollback_alert(reason, rollback_duration)

                return True
            else:
                logger.error(f"Rollback failed after {rollback_duration:.2f} seconds")
                return False

        finally:
            self.rollback_in_progress = False

    async def _perform_rollback(self) -> bool:
        """Perform the actual rollback."""
        try:
            # Quick switch using blue-green
            subprocess.run(
                [
                    "docker-compose",
                    "-f",
                    "docker-compose.backup.yml",
                    "up",
                    "-d",
                    "--force-recreate",
                ],
                check=True,
                timeout=60,
            )

            # Restore database if needed
            if await self._needs_db_rollback():
                await self._rollback_database()

            # Clear caches
            await self._clear_caches()

            # Verify rollback
            await asyncio.sleep(5)
            return await self._verify_rollback()

        except Exception as e:
            logger.error(f"Rollback failed: {e}")
            return False

    async def _needs_db_rollback(self) -> bool:
        """Check if database rollback is needed."""
        # Check for migration markers
        try:
            from database.db_setup import get_async_db

            async for db in get_async_db():
                result = await db.execute(
                    "SELECT version FROM migrations ORDER BY applied_at DESC LIMIT 1"
                )
                latest = result.scalar()
                return latest != self.previous_version.config_snapshot.get("db_version")
        except:
            return False

    async def _rollback_database(self):
        """Rollback database migrations."""
        try:
            target_version = self.previous_version.config_snapshot.get("db_version")
            subprocess.run(["alembic", "downgrade", target_version], check=True, timeout=30)
            logger.info(f"Database rolled back to version {target_version}")
        except Exception as e:
            logger.error(f"Database rollback failed: {e}")

    async def _clear_caches(self):
        """Clear all caches after rollback."""
        try:
            from config.cache import get_redis_client

            redis_client = await get_redis_client()
            await redis_client.flushdb()
            logger.info("Caches cleared")
        except Exception as e:
            logger.error(f"Cache clear failed: {e}")

    async def _verify_rollback(self) -> bool:
        """Verify rollback was successful."""
        try:
            # Check health endpoint
            import aiohttp

            async with aiohttp.ClientSession() as session:
                async with session.get("http://localhost:8000/health") as response:
                    if response.status != 200:
                        return False

            # Check key metrics are back to normal
            metrics = await self._get_current_metrics()
            error_rate = metrics.get("error_rate", 1.0)

            return error_rate < 0.05  # Below 5% error rate

        except:
            return False

    async def _monitor_deployment(self):
        """Monitor deployment and trigger rollback if needed."""
        monitoring_start = datetime.now(timezone.utc)
        monitoring_duration = 300  # 5 minutes of monitoring

        while self.state == DeploymentState.MONITORING:
            try:
                # Get current metrics
                metrics = await self._get_current_metrics()

                # Check thresholds
                for name, threshold in self.thresholds.items():
                    value = metrics.get(name, 0)

                    # Adjust for baseline (2x check for response time)
                    if name == "response_time" and self.current_version:
                        baseline = self.current_version.metrics_baseline.get(name, value / 2)
                        value = value / baseline if baseline > 0 else 1.0

                    if threshold.check_threshold(value):
                        # Threshold exceeded, trigger rollback
                        reason_map = {
                            "error_rate": RollbackReason.HIGH_ERROR_RATE,
                            "response_time": RollbackReason.SLOW_RESPONSE,
                            "db_connections": RollbackReason.DB_CONNECTION_FAILURE,
                            "auth_failures": RollbackReason.AUTH_SPIKE,
                            "ai_cost_rate": RollbackReason.AI_COST_EXCEEDED,
                        }

                        await self.trigger_rollback(
                            reason_map.get(name, RollbackReason.HEALTH_CHECK_FAILED)
                        )
                        return

                # Check if monitoring period is over
                elapsed = (datetime.now(timezone.utc) - monitoring_start).total_seconds()
                if elapsed > monitoring_duration:
                    self.state = DeploymentState.STABLE
                    logger.info("Deployment monitoring completed successfully")
                    return

                await asyncio.sleep(self.monitoring_interval)

            except Exception as e:
                logger.error(f"Monitoring error: {e}")
                await asyncio.sleep(self.monitoring_interval)

    async def _get_current_metrics(self) -> Dict[str, float]:
        """Get current system metrics."""
        from monitoring.metrics import get_metrics_collector

        get_metrics_collector()

        # In production, you'd parse Prometheus metrics
        # For now, return mock metrics
        return {
            "error_rate": 0.02,  # 2% error rate
            "response_time": 0.5,  # 500ms
            "db_connections": 0.6,  # 60% utilization
            "auth_failures": 10,  # 10 failures per minute
            "ai_cost_rate": 1.5,  # $1.50 per minute
        }

    async def _capture_baseline_metrics(self) -> Dict[str, float]:
        """Capture baseline metrics before deployment."""
        return await self._get_current_metrics()

    async def _capture_config(self) -> Dict[str, Any]:
        """Capture current configuration."""
        return {
            "db_version": await self._get_db_version(),
            "feature_flags": await self._get_feature_flags(),
            "env_vars": self._get_safe_env_vars(),
        }

    async def _get_db_version(self) -> str:
        """Get current database version."""
        try:
            from database.db_setup import get_async_db

            async for db in get_async_db():
                result = await db.execute(
                    "SELECT version FROM migrations ORDER BY applied_at DESC LIMIT 1"
                )
                return result.scalar() or "unknown"
        except:
            return "unknown"

    async def _get_feature_flags(self) -> Dict[str, bool]:
        """Get current feature flag states."""
        from config.feature_flags import feature_flags

        return feature_flags.get_all_flags()

    def _get_safe_env_vars(self) -> Dict[str, str]:
        """Get safe environment variables (no secrets)."""
        safe_vars = [
            "ENVIRONMENT",
            "APP_VERSION",
            "LOG_LEVEL",
            "DATABASE_POOL_SIZE",
            "REDIS_MAX_CONNECTIONS",
        ]
        return {k: os.environ.get(k, "") for k in safe_vars}

    async def _send_rollback_alert(self, reason: RollbackReason, duration: float):
        """Send alert about rollback."""
        alert = {
            "type": "ROLLBACK_COMPLETED",
            "reason": reason.value,
            "duration_seconds": duration,
            "from_version": self.rollback_history[-1]["from_version"],
            "to_version": self.rollback_history[-1]["to_version"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # In production, send to PagerDuty, Slack, etc.
        logger.critical(f"ROLLBACK ALERT: {json.dumps(alert, indent=2)}")

    def get_status(self) -> Dict[str, Any]:
        """Get current rollback system status."""
        return {
            "state": self.state.value,
            "current_version": self.current_version.version if self.current_version else None,
            "previous_version": self.previous_version.version if self.previous_version else None,
            "rollback_in_progress": self.rollback_in_progress,
            "rollback_history": self.rollback_history[-5:],  # Last 5 rollbacks
            "thresholds": {
                name: {
                    "current": t.current_value,
                    "threshold": t.threshold_value,
                    "exceeded": t.exceeded_at is not None,
                }
                for name, t in self.thresholds.items()
            },
        }


# Global rollback system instance
_rollback_system: Optional[AutomaticRollbackSystem] = None


def get_rollback_system() -> AutomaticRollbackSystem:
    """Get or create the global rollback system."""
    global _rollback_system
    if _rollback_system is None:
        _rollback_system = AutomaticRollbackSystem()
    return _rollback_system
