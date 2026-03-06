"""Trust Progression Algorithm for agent autonomy management."""

from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any, Tuple
from enum import IntEnum, Enum
import statistics
import logging
from dataclasses import dataclass, field
from collections import deque

from pydantic import BaseModel, Field


logger = logging.getLogger(__name__)


class TrustLevel(IntEnum):
    """Trust levels for agent autonomy."""

    L0_OBSERVED = 0  # All actions require approval
    L1_ASSISTED = 1  # Low-risk actions auto-approved
    L2_SUPERVISED = 2  # Most actions auto-approved
    L3_AUTONOMOUS = 3  # Full autonomy with audit


class MetricType(str, Enum):
    """Types of behavioral metrics tracked."""

    APPROVAL_RATE = "approval_rate"
    ERROR_RATE = "error_rate"
    CONSISTENCY_SCORE = "consistency_score"
    COMPLEXITY_SCORE = "complexity_score"
    RESPONSE_TIME = "response_time"
    SUCCESS_RATE = "success_rate"


@dataclass
class BehaviorMetric:
    """Individual behavior metric."""

    metric_type: MetricType
    value: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    weight: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TrustScore:
    """Calculated trust score with components."""

    overall_score: float
    approval_rate: float
    success_rate: float
    consistency_score: float
    complexity_score: float
    time_decay_factor: float
    calculated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class PromotionThresholds(BaseModel):
    """Thresholds for trust level promotion."""

    min_score: float = Field(ge=0.0, le=100.0)
    min_actions: int = Field(ge=0)
    min_days_active: int = Field(ge=0)
    min_approval_rate: float = Field(ge=0.0, le=1.0)
    cooldown_days: int = Field(default=7)


class TrustProgressionAlgorithm:
    """
    Algorithm for tracking and progressing user trust levels.

    Monitors user behavior, calculates trust scores, and manages
    trust level transitions with comprehensive safety checks.
    """

    # Promotion thresholds for each level
    PROMOTION_THRESHOLDS = {
        TrustLevel.L1_ASSISTED: PromotionThresholds(
            min_score=70.0, min_actions=100, min_days_active=30, min_approval_rate=0.90
        ),
        TrustLevel.L2_SUPERVISED: PromotionThresholds(
            min_score=85.0, min_actions=500, min_days_active=60, min_approval_rate=0.95
        ),
        TrustLevel.L3_AUTONOMOUS: PromotionThresholds(
            min_score=95.0, min_actions=1000, min_days_active=90, min_approval_rate=0.98
        ),
    }

    # Scoring weights
    SCORE_WEIGHTS = {
        "approval_rate": 0.40,
        "success_rate": 0.30,
        "consistency": 0.20,
        "complexity": 0.10,
    }

    # Time decay parameters
    TIME_DECAY_WINDOW_DAYS = 90
    TIME_DECAY_FACTOR = 0.95  # Applied monthly

    def __init__(
        self, user_id: str, initial_trust_level: TrustLevel = TrustLevel.L0_OBSERVED
    ) -> None:
        """Initialize trust progression algorithm for a user."""
        self.user_id = user_id
        self.current_trust_level = initial_trust_level
        self.metrics_history: deque = deque(maxlen=10000)  # Last 10k metrics
        self.action_history: List[Dict[str, Any]] = []
        self.promotion_history: List[Dict[str, Any]] = []
        self.violation_history: List[Dict[str, Any]] = []
        self.last_promotion_date: Optional[datetime] = None
        self.account_created_date = datetime.now(timezone.utc)
        self.total_actions = 0
        self.anomaly_detector = AnomalyDetector(user_id)

    async def track_action(
        self,
        action_type: str,
        was_approved: bool,
        was_successful: Optional[bool] = None,
        complexity: float = 0.5,
        execution_time_ms: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Track a user action for trust scoring.

        Args:
            action_type: Type of action performed
            was_approved: Whether action was approved
            was_successful: Whether action succeeded (if executed)
            complexity: Complexity score of action (0-1)
            execution_time_ms: Time taken to decide/execute
            metadata: Additional action metadata
        """
        self.total_actions += 1

        # Record action
        action_record = {
            "timestamp": datetime.now(timezone.utc),
            "action_type": action_type,
            "approved": was_approved,
            "successful": was_successful,
            "complexity": complexity,
            "execution_time_ms": execution_time_ms,
            "trust_level": self.current_trust_level,
            "metadata": metadata or {},
        }
        self.action_history.append(action_record)

        # Update metrics
        if was_approved:
            self.metrics_history.append(BehaviorMetric(MetricType.APPROVAL_RATE, 1.0))
        else:
            self.metrics_history.append(BehaviorMetric(MetricType.APPROVAL_RATE, 0.0))

        if was_successful is not None:
            success_value = 1.0 if was_successful else 0.0
            self.metrics_history.append(BehaviorMetric(MetricType.SUCCESS_RATE, success_value))

            # Track error rate
            if not was_successful:
                self.metrics_history.append(BehaviorMetric(MetricType.ERROR_RATE, 1.0))

        # Track complexity handling
        self.metrics_history.append(BehaviorMetric(MetricType.COMPLEXITY_SCORE, complexity))

        # Check for anomalies
        if await self.anomaly_detector.check_anomaly(action_record):
            await self._handle_anomaly(action_record)

    def calculate_trust_score(self) -> TrustScore:
        """
        Calculate current trust score based on behavioral metrics.

        Returns:
            TrustScore with detailed component scores
        """
        if not self.metrics_history:
            return TrustScore(
                overall_score=0.0,
                approval_rate=0.0,
                success_rate=0.0,
                consistency_score=0.0,
                complexity_score=0.0,
                time_decay_factor=1.0,
            )

        # Calculate component scores
        approval_rate = self._calculate_approval_rate()
        success_rate = self._calculate_success_rate()
        consistency_score = self._calculate_consistency_score()
        complexity_score = self._calculate_complexity_score()
        time_decay_factor = self._calculate_time_decay()

        # Calculate weighted overall score
        overall_score = (
            (
                approval_rate * self.SCORE_WEIGHTS["approval_rate"]
                + success_rate * self.SCORE_WEIGHTS["success_rate"]
                + consistency_score * self.SCORE_WEIGHTS["consistency"]
                + complexity_score * self.SCORE_WEIGHTS["complexity"]
            )
            * time_decay_factor
            * 100
        )

        return TrustScore(
            overall_score=min(100.0, max(0.0, overall_score)),
            approval_rate=approval_rate,
            success_rate=success_rate,
            consistency_score=consistency_score,
            complexity_score=complexity_score,
            time_decay_factor=time_decay_factor,
        )

    def _calculate_approval_rate(self) -> float:
        """Calculate approval rate from recent actions."""
        recent_approvals = [
            m.value for m in self.metrics_history if m.metric_type == MetricType.APPROVAL_RATE
        ][-100:]  # Last 100 actions

        if not recent_approvals:
            return 0.0

        return sum(recent_approvals) / len(recent_approvals)

    def _calculate_success_rate(self) -> float:
        """Calculate success rate from recent actions."""
        recent_successes = [
            m.value for m in self.metrics_history if m.metric_type == MetricType.SUCCESS_RATE
        ][-100:]

        if not recent_successes:
            return 1.0  # Assume success if no data

        return sum(recent_successes) / len(recent_successes)

    def _calculate_consistency_score(self) -> float:
        """Calculate consistency of decisions over time."""
        if len(self.action_history) < 10:
            return 0.5  # Not enough data

        # Group actions by type and calculate variance in decisions
        action_groups = {}
        for action in self.action_history[-50:]:
            action_type = action["action_type"]
            if action_type not in action_groups:
                action_groups[action_type] = []
            action_groups[action_type].append(1 if action["approved"] else 0)

        # Calculate consistency for each action type
        consistencies = []
        for actions in action_groups.values():
            if len(actions) > 1:
                # Low variance = high consistency
                variance = statistics.variance(actions)
                consistency = 1.0 - min(variance * 2, 1.0)
                consistencies.append(consistency)

        if not consistencies:
            return 0.5

        return statistics.mean(consistencies)

    def _calculate_complexity_score(self) -> float:
        """Calculate ability to handle complex tasks."""
        complexity_metrics = [
            m.value for m in self.metrics_history if m.metric_type == MetricType.COMPLEXITY_SCORE
        ][-50:]

        if not complexity_metrics:
            return 0.0

        # Higher average complexity with success = better score
        avg_complexity = statistics.mean(complexity_metrics)

        # Get success rate for complex tasks
        complex_actions = [a for a in self.action_history[-50:] if a.get("complexity", 0) > 0.7]

        if complex_actions:
            complex_success_rate = sum(
                1 for a in complex_actions if a.get("successful", False)
            ) / len(complex_actions)
        else:
            complex_success_rate = 0.5

        return avg_complexity * complex_success_rate

    def _calculate_time_decay(self) -> float:
        """Calculate time decay factor for old behaviors."""
        if not self.action_history:
            return 1.0

        # Find oldest relevant action
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=self.TIME_DECAY_WINDOW_DAYS)
        recent_actions = [a for a in self.action_history if a["timestamp"] > cutoff_date]

        if not recent_actions:
            return 0.5  # Heavy decay if no recent activity

        # Calculate activity ratio
        days_since_first_action = (datetime.now(timezone.utc) - self.account_created_date).days

        if days_since_first_action > self.TIME_DECAY_WINDOW_DAYS:
            # Apply monthly decay
            months_inactive = (days_since_first_action - self.TIME_DECAY_WINDOW_DAYS) / 30
            return self.TIME_DECAY_FACTOR**months_inactive

        return 1.0

    async def check_promotion_eligibility(self) -> Tuple[bool, Optional[TrustLevel], List[str]]:
        """
        Check if user is eligible for trust level promotion.

        Returns:
            Tuple of (eligible, next_level, reasons)
        """
        # Can't promote from highest level
        if self.current_trust_level == TrustLevel.L3_AUTONOMOUS:
            return False, None, ["Already at maximum trust level"]

        next_level = TrustLevel(self.current_trust_level + 1)
        thresholds = self.PROMOTION_THRESHOLDS[next_level]
        reasons = []

        # Check cooldown period
        if self.last_promotion_date:
            days_since_promotion = (datetime.now(timezone.utc) - self.last_promotion_date).days
            if days_since_promotion < thresholds.cooldown_days:
                reasons.append(
                    f"Cooldown period: {thresholds.cooldown_days - days_since_promotion} days remaining"
                )

        # Check trust score
        current_score = self.calculate_trust_score()
        if current_score.overall_score < thresholds.min_score:
            reasons.append(
                f"Trust score too low: {current_score.overall_score:.1f} < {thresholds.min_score}"
            )

        # Check total actions
        if self.total_actions < thresholds.min_actions:
            reasons.append(f"Insufficient actions: {self.total_actions} < {thresholds.min_actions}")

        # Check days active
        days_active = (datetime.now(timezone.utc) - self.account_created_date).days
        if days_active < thresholds.min_days_active:
            reasons.append(f"Account too new: {days_active} < {thresholds.min_days_active} days")

        # Check approval rate
        if current_score.approval_rate < thresholds.min_approval_rate:
            reasons.append(
                f"Approval rate too low: {current_score.approval_rate:.2%} < {thresholds.min_approval_rate:.2%}"
            )

        # Check for recent violations
        recent_violations = [
            v
            for v in self.violation_history
            if (datetime.now(timezone.utc) - v["timestamp"]).days < 30
        ]
        if recent_violations:
            reasons.append(f"Recent violations: {len(recent_violations)} in last 30 days")

        eligible = len(reasons) == 0
        return eligible, next_level if eligible else None, reasons

    async def promote_trust_level(
        self, authorized_by: str, reason: str, is_override: bool = False
    ) -> Dict[str, Any]:
        """
        Promote user to next trust level.

        Args:
            authorized_by: ID of authorizing user/system
            reason: Reason for promotion
            is_override: Whether this is a manual override

        Returns:
            Promotion result details
        """
        # Check eligibility unless override
        if not is_override:
            eligible, next_level, reasons = await self.check_promotion_eligibility()
            if not eligible:
                return {
                    "success": False,
                    "current_level": self.current_trust_level.name,
                    "reasons": reasons,
                }
        else:
            next_level = TrustLevel(min(self.current_trust_level + 1, TrustLevel.L3_AUTONOMOUS))

        # Record promotion
        promotion_record = {
            "timestamp": datetime.now(timezone.utc),
            "from_level": self.current_trust_level.name,
            "to_level": next_level.name,
            "authorized_by": authorized_by,
            "reason": reason,
            "is_override": is_override,
            "trust_score": self.calculate_trust_score().overall_score,
            "total_actions": self.total_actions,
        }
        self.promotion_history.append(promotion_record)

        # Update trust level
        old_level = self.current_trust_level
        self.current_trust_level = next_level
        self.last_promotion_date = datetime.now(timezone.utc)

        logger.info(f"User {self.user_id} promoted from {old_level.name} to {next_level.name}")

        return {
            "success": True,
            "previous_level": old_level.name,
            "new_level": next_level.name,
            "promotion_record": promotion_record,
        }

    async def demote_trust_level(
        self, reason: str, severity: str = "medium", authorized_by: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Demote user trust level due to violations.

        Args:
            reason: Reason for demotion
            severity: Violation severity (low, medium, high, critical)
            authorized_by: ID of authorizing user/system

        Returns:
            Demotion result details
        """
        # Determine demotion amount based on severity
        demotion_levels = {
            "low": 0,  # Warning only
            "medium": 1,
            "high": 2,
            "critical": 3,  # Back to L0
        }

        levels_to_demote = demotion_levels.get(severity, 1)

        if levels_to_demote == 0:
            # Just record violation
            self.violation_history.append(
                {
                    "timestamp": datetime.now(timezone.utc),
                    "reason": reason,
                    "severity": severity,
                    "trust_level": self.current_trust_level.name,
                }
            )
            return {
                "success": True,
                "action": "warning",
                "current_level": self.current_trust_level.name,
            }

        # Calculate new level
        new_level_value = max(0, self.current_trust_level - levels_to_demote)
        new_level = TrustLevel(new_level_value)

        # Record violation and demotion
        violation_record = {
            "timestamp": datetime.now(timezone.utc),
            "from_level": self.current_trust_level.name,
            "to_level": new_level.name,
            "reason": reason,
            "severity": severity,
            "authorized_by": authorized_by or "system",
        }
        self.violation_history.append(violation_record)

        # Update trust level
        old_level = self.current_trust_level
        self.current_trust_level = new_level

        logger.warning(
            f"User {self.user_id} demoted from {old_level.name} to {new_level.name} - {reason}"
        )

        return {
            "success": True,
            "action": "demotion",
            "previous_level": old_level.name,
            "new_level": new_level.name,
            "violation_record": violation_record,
        }

    async def _handle_anomaly(self, action_record: Dict[str, Any]) -> None:
        """Handle detected anomaly in user behavior."""
        logger.warning(f"Anomaly detected for user {self.user_id}: {action_record}")

        # Add to violation history as potential issue
        self.violation_history.append(
            {
                "timestamp": datetime.now(timezone.utc),
                "type": "anomaly",
                "action": action_record,
                "trust_level": self.current_trust_level.name,
            }
        )

        # Consider auto-demotion for repeated anomalies
        recent_anomalies = [
            v
            for v in self.violation_history
            if v.get("type") == "anomaly" and (datetime.now(timezone.utc) - v["timestamp"]).days < 7
        ]

        if len(recent_anomalies) >= 3:
            await self.demote_trust_level(
                reason="Multiple anomalies detected in behavior", severity="medium"
            )

    def get_audit_trail(self) -> Dict[str, Any]:
        """Get complete audit trail for user trust progression."""
        return {
            "user_id": self.user_id,
            "current_trust_level": self.current_trust_level.name,
            "trust_score": self.calculate_trust_score().overall_score,
            "total_actions": self.total_actions,
            "account_age_days": (datetime.now(timezone.utc) - self.account_created_date).days,
            "promotion_history": self.promotion_history,
            "violation_history": self.violation_history[-10:],  # Last 10 violations
            "recent_actions": len(
                [
                    a
                    for a in self.action_history
                    if (datetime.now(timezone.utc) - a["timestamp"]).days < 7
                ]
            ),
        }


class AnomalyDetector:
    """Detect anomalies in user behavior patterns."""

    def __init__(self, user_id: str) -> None:
        """Initialize anomaly detector."""
        self.user_id = user_id
        self.baseline_patterns: Dict[str, Any] = {}
        self.anomaly_threshold = 2.5  # Standard deviations

    async def check_anomaly(self, action: Dict[str, Any]) -> bool:
        """
        Check if action represents anomalous behavior.

        Returns:
            True if anomaly detected
        """
        # Check for rapid-fire actions
        if action.get("execution_time_ms", 1000) < 50:
            return True  # Too fast to be human

        # Check for unusual patterns
        # In production, this would use ML models

        # Simple heuristics for PoC
        if action.get("complexity", 0) > 0.9 and not action.get("approved"):
            return False  # Complex actions often rejected is normal

        # Check for automation patterns
        # (Would implement more sophisticated checks in production)

        return False
