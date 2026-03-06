"""
Decision Tracker Service - Records and validates agent decisions.

Tracks decision history, feedback, and validation logic.
"""

from typing import Dict, List, Optional, Any, Tuple
from uuid import UUID, uuid4
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from enum import Enum
import logging
from dataclasses import dataclass, asdict

from models.agentic_models import Decision, DecisionFeedback, TrustLevel

logger = logging.getLogger(__name__)


class DecisionType(Enum):
    """Types of decisions agents can make."""

    ACTION = "action"
    SUGGESTION = "suggestion"
    APPROVAL = "approval"
    REJECTION = "rejection"
    DELEGATION = "delegation"
    ESCALATION = "escalation"


class DecisionStatus(Enum):
    """Status of a decision."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTED = "executed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class DecisionMetrics:
    """Metrics for decision quality."""

    total_decisions: int = 0
    successful_decisions: int = 0
    failed_decisions: int = 0
    rejected_decisions: int = 0
    accuracy_rate: float = 0.0
    avg_confidence: float = 0.0
    avg_execution_time: float = 0.0


class DecisionTracker:
    """Tracks and validates agent decisions."""

    def __init__(self, db_session: Session, validation_threshold: float = 0.7) -> None:
        """Initialize decision tracker."""
        self.db = db_session
        self.validation_threshold = validation_threshold
        self.decision_cache: Dict[UUID, Decision] = {}

    def record_decision(
        self,
        session_id: UUID,
        agent_id: UUID,
        decision_type: DecisionType,
        decision_data: Dict[str, Any],
        confidence: float = 0.5,
        trust_level: TrustLevel = TrustLevel.L0_OBSERVED,
    ) -> Decision:
        """Record a new agent decision."""
        try:
            decision = Decision(
                decision_id=uuid4(),
                session_id=session_id,
                agent_id=agent_id,
                decision_type=decision_type.value,
                decision_data=decision_data,
                confidence=confidence,
                trust_level_required=trust_level,
                status=DecisionStatus.PENDING.value,
                created_at=datetime.utcnow(),
            )

            self.db.add(decision)
            self.db.commit()
            self.db.refresh(decision)

            self.decision_cache[decision.decision_id] = decision
            logger.info(f"Recorded decision {decision.decision_id} for agent {agent_id}")

            return decision

        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Failed to record decision: {e}")
            raise

    def validate_decision(
        self, decision_id: UUID, validation_rules: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, List[str]]:
        """Validate a decision against rules."""
        errors = []

        try:
            decision = self.db.query(Decision).filter(Decision.decision_id == decision_id).first()

            if not decision:
                errors.append(f"Decision {decision_id} not found")
                return False, errors

            # Check confidence threshold
            if decision.confidence < self.validation_threshold:
                errors.append(
                    f"Confidence {decision.confidence} below threshold {self.validation_threshold}"
                )

            # Apply custom validation rules
            if validation_rules:
                for rule_name, rule_func in validation_rules.items():
                    if callable(rule_func):
                        try:
                            if not rule_func(decision):
                                errors.append(f"Failed validation rule: {rule_name}")
                        except Exception as e:
                            errors.append(f"Validation rule error: {rule_name} - {e}")

            # Check decision data completeness
            if not decision.decision_data:
                errors.append("Decision data is empty")
            elif "action" not in decision.decision_data:
                errors.append("Decision missing action field")

            # Update decision status based on validation
            if not errors:
                decision.status = DecisionStatus.APPROVED.value
            else:
                decision.status = DecisionStatus.REJECTED.value

            self.db.commit()

            return len(errors) == 0, errors

        except SQLAlchemyError as e:
            logger.error(f"Failed to validate decision: {e}")
            errors.append(f"Database error: {e}")
            return False, errors

    def execute_decision(
        self, decision_id: UUID, execution_result: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Mark a decision as executed."""
        try:
            decision = self.db.query(Decision).filter(Decision.decision_id == decision_id).first()

            if not decision:
                logger.warning(f"Decision {decision_id} not found")
                return False

            if decision.status != DecisionStatus.APPROVED.value:
                logger.warning(f"Decision {decision_id} not approved for execution")
                return False

            decision.status = DecisionStatus.EXECUTED.value
            decision.executed_at = datetime.utcnow()

            if execution_result:
                decision.decision_data["execution_result"] = execution_result

            self.db.commit()
            logger.info(f"Executed decision {decision_id}")
            return True

        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Failed to execute decision: {e}")
            return False

    def record_feedback(
        self,
        decision_id: UUID,
        feedback_type: str,
        feedback_value: Any,
        user_id: Optional[str] = None,
    ) -> DecisionFeedback:
        """Record feedback for a decision."""
        try:
            feedback = DecisionFeedback(
                feedback_id=uuid4(),
                decision_id=decision_id,
                feedback_type=feedback_type,
                feedback_value=feedback_value,
                user_id=user_id,
                created_at=datetime.utcnow(),
            )

            self.db.add(feedback)

            # Update decision based on feedback
            decision = self.db.query(Decision).filter(Decision.decision_id == decision_id).first()

            if decision:
                if feedback_type == "rejection":
                    decision.status = DecisionStatus.REJECTED.value
                elif feedback_type == "approval":
                    decision.status = DecisionStatus.APPROVED.value

            self.db.commit()
            self.db.refresh(feedback)

            logger.info(f"Recorded feedback for decision {decision_id}")
            return feedback

        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Failed to record feedback: {e}")
            raise

    def process_feedback(
        self, agent_id: UUID, time_window: timedelta = timedelta(days=7)
    ) -> DecisionMetrics:
        """Process feedback to calculate decision metrics."""
        try:
            cutoff_time = datetime.utcnow() - time_window

            # Get recent decisions for agent
            decisions = (
                self.db.query(Decision)
                .filter(Decision.agent_id == agent_id, Decision.created_at >= cutoff_time)
                .all()
            )

            metrics = DecisionMetrics()
            metrics.total_decisions = len(decisions)

            if not decisions:
                return metrics

            total_confidence = 0
            total_execution_time = 0
            executed_count = 0

            for decision in decisions:
                total_confidence += decision.confidence

                if decision.status == DecisionStatus.EXECUTED.value:
                    metrics.successful_decisions += 1
                    if decision.executed_at:
                        exec_time = (decision.executed_at - decision.created_at).total_seconds()
                        total_execution_time += exec_time
                        executed_count += 1

                elif decision.status == DecisionStatus.FAILED.value:
                    metrics.failed_decisions += 1

                elif decision.status == DecisionStatus.REJECTED.value:
                    metrics.rejected_decisions += 1

            # Calculate averages
            metrics.avg_confidence = total_confidence / metrics.total_decisions

            if executed_count > 0:
                metrics.avg_execution_time = total_execution_time / executed_count

            # Calculate accuracy rate
            if metrics.total_decisions > 0:
                metrics.accuracy_rate = metrics.successful_decisions / metrics.total_decisions

            logger.info(f"Processed feedback for agent {agent_id}: {asdict(metrics)}")
            return metrics

        except SQLAlchemyError as e:
            logger.error(f"Failed to process feedback: {e}")
            return DecisionMetrics()

    def get_decision_history(
        self, agent_id: Optional[UUID] = None, session_id: Optional[UUID] = None, limit: int = 100
    ) -> List[Decision]:
        """Get decision history with filters."""
        try:
            query = self.db.query(Decision)

            if agent_id:
                query = query.filter(Decision.agent_id == agent_id)

            if session_id:
                query = query.filter(Decision.session_id == session_id)

            decisions = query.order_by(Decision.created_at.desc()).limit(limit).all()

            return decisions

        except SQLAlchemyError as e:
            logger.error(f"Failed to get decision history: {e}")
            return []

    def get_pending_decisions(self, trust_level: Optional[TrustLevel] = None) -> List[Decision]:
        """Get decisions pending approval."""
        try:
            query = self.db.query(Decision).filter(Decision.status == DecisionStatus.PENDING.value)

            if trust_level:
                query = query.filter(Decision.trust_level_required == trust_level)

            return query.all()

        except SQLAlchemyError as e:
            logger.error(f"Failed to get pending decisions: {e}")
            return []

    def cancel_decision(self, decision_id: UUID, reason: str = "") -> bool:
        """Cancel a pending decision."""
        try:
            decision = self.db.query(Decision).filter(Decision.decision_id == decision_id).first()

            if not decision:
                return False

            if decision.status in [DecisionStatus.EXECUTED.value, DecisionStatus.CANCELLED.value]:
                logger.warning(f"Cannot cancel decision {decision_id} in status {decision.status}")
                return False

            decision.status = DecisionStatus.CANCELLED.value
            decision.decision_data["cancellation_reason"] = reason

            self.db.commit()
            logger.info(f"Cancelled decision {decision_id}: {reason}")
            return True

        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Failed to cancel decision: {e}")
            return False

    def get_decision_patterns(
        self, agent_id: UUID, pattern_window: timedelta = timedelta(days=30)
    ) -> Dict[str, Any]:
        """Analyze decision patterns for an agent."""
        try:
            cutoff_time = datetime.utcnow() - pattern_window

            decisions = (
                self.db.query(Decision)
                .filter(Decision.agent_id == agent_id, Decision.created_at >= cutoff_time)
                .all()
            )

            patterns = {
                "total_decisions": len(decisions),
                "decision_types": {},
                "confidence_distribution": {
                    "high": 0,  # > 0.8
                    "medium": 0,  # 0.5 - 0.8
                    "low": 0,  # < 0.5
                },
                "status_distribution": {},
                "hourly_distribution": [0] * 24,
                "trust_level_distribution": {},
            }

            for decision in decisions:
                # Count by type
                dtype = decision.decision_type
                patterns["decision_types"][dtype] = patterns["decision_types"].get(dtype, 0) + 1

                # Confidence distribution
                if decision.confidence > 0.8:
                    patterns["confidence_distribution"]["high"] += 1
                elif decision.confidence >= 0.5:
                    patterns["confidence_distribution"]["medium"] += 1
                else:
                    patterns["confidence_distribution"]["low"] += 1

                # Status distribution
                status = decision.status
                patterns["status_distribution"][status] = (
                    patterns["status_distribution"].get(status, 0) + 1
                )

                # Hourly distribution
                hour = decision.created_at.hour
                patterns["hourly_distribution"][hour] += 1

                # Trust level distribution
                trust = str(decision.trust_level_required)
                patterns["trust_level_distribution"][trust] = (
                    patterns["trust_level_distribution"].get(trust, 0) + 1
                )

            logger.info(f"Analyzed patterns for agent {agent_id}")
            return patterns

        except SQLAlchemyError as e:
            logger.error(f"Failed to analyze decision patterns: {e}")
            return {}
