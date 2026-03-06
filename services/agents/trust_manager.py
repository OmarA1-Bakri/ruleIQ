"""
Trust Manager Service - Manages agent trust levels and progression.

Implements trust level calculations, transitions, and degradation logic.
"""

from typing import Dict, List, Optional, Tuple
from uuid import UUID
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
import logging
from dataclasses import dataclass, asdict

from models.agentic_models import Agent, Decision, TrustLevel, TrustMetric

logger = logging.getLogger(__name__)


@dataclass
class TrustProgressionRules:
    """Rules for trust level progression."""

    min_decisions_for_evaluation: int = 10
    accuracy_threshold_for_upgrade: float = 0.9
    rejection_rate_threshold_for_downgrade: float = 0.2
    critical_error_penalty: int = -3  # Drop levels
    inactivity_days_for_degradation: int = 7
    min_confidence_for_decisions: float = 0.7


class TrustManager:
    """Manages trust levels and progression for agents."""

    def __init__(self, db_session: Session, rules: Optional[TrustProgressionRules] = None) -> None:
        """Initialize trust manager."""
        self.db = db_session
        self.rules = rules or TrustProgressionRules()
        self.trust_levels = [
            TrustLevel.L0_OBSERVED,
            TrustLevel.L1_ASSISTED,
            TrustLevel.L2_SUPERVISED,
            TrustLevel.L3_DELEGATED,
            TrustLevel.L4_AUTONOMOUS,
        ]

    def calculate_trust_metrics(
        self,
        agent_id: UUID,
        session_id: Optional[UUID] = None,
        time_window: timedelta = timedelta(days=7),
    ) -> TrustMetric:
        """Calculate current trust metrics for an agent."""
        try:
            cutoff_time = datetime.utcnow() - time_window

            # Get recent decisions
            query = self.db.query(Decision).filter(
                Decision.agent_id == agent_id, Decision.created_at >= cutoff_time
            )

            if session_id:
                query = query.filter(Decision.session_id == session_id)

            decisions = query.all()

            # Calculate metrics
            total_decisions = len(decisions)
            successful_decisions = 0
            rejected_decisions = 0
            total_confidence = 0
            critical_errors = 0

            for decision in decisions:
                total_confidence += decision.confidence

                if decision.status == "executed":
                    successful_decisions += 1
                elif decision.status == "rejected":
                    rejected_decisions += 1
                elif decision.status == "failed":
                    # Check if it was a critical error
                    if decision.decision_data.get("is_critical", False):
                        critical_errors += 1

            # Calculate rates
            accuracy_rate = 0.0
            rejection_rate = 0.0
            avg_confidence = 0.0

            if total_decisions > 0:
                accuracy_rate = successful_decisions / total_decisions
                rejection_rate = rejected_decisions / total_decisions
                avg_confidence = total_confidence / total_decisions

            # Get current trust level
            agent = self.db.query(Agent).filter(Agent.agent_id == agent_id).first()

            current_trust_level = TrustLevel.L0_OBSERVED
            if agent and agent.config:
                current_trust_level = TrustLevel(
                    agent.config.get("trust_level", TrustLevel.L0_OBSERVED.value)
                )

            # Create trust metric
            trust_metric = TrustMetric(
                metric_id=UUID.uuid4(),
                agent_id=agent_id,
                session_id=session_id,
                trust_level=current_trust_level,
                accuracy_rate=accuracy_rate,
                rejection_rate=rejection_rate,
                total_decisions=total_decisions,
                successful_decisions=successful_decisions,
                confidence_avg=avg_confidence,
                critical_errors=critical_errors,
                calculated_at=datetime.utcnow(),
            )

            # Store metric
            self.db.add(trust_metric)
            self.db.commit()
            self.db.refresh(trust_metric)

            logger.info(f"Calculated trust metrics for agent {agent_id}: {asdict(trust_metric)}")
            return trust_metric

        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Failed to calculate trust metrics: {e}")
            raise

    def evaluate_trust_progression(
        self, agent_id: UUID, trust_metric: Optional[TrustMetric] = None
    ) -> Tuple[TrustLevel, str]:
        """Evaluate if agent should progress to different trust level."""
        try:
            if not trust_metric:
                trust_metric = self.calculate_trust_metrics(agent_id)

            current_level = trust_metric.trust_level
            new_level = current_level
            reason = "No change required"

            # Check for critical errors
            if trust_metric.critical_errors > 0:
                new_level = TrustLevel.L0_OBSERVED
                reason = f"Critical error occurred ({trust_metric.critical_errors} errors)"

            # Check if enough decisions for evaluation
            elif trust_metric.total_decisions < self.rules.min_decisions_for_evaluation:
                reason = f"Insufficient decisions ({trust_metric.total_decisions}/{self.rules.min_decisions_for_evaluation})"

            # Check for downgrade conditions
            elif trust_metric.rejection_rate > self.rules.rejection_rate_threshold_for_downgrade:
                new_level = self._get_lower_trust_level(current_level)
                reason = f"High rejection rate ({trust_metric.rejection_rate:.2%})"

            # Check for upgrade conditions
            elif trust_metric.accuracy_rate > self.rules.accuracy_threshold_for_upgrade:
                if trust_metric.confidence_avg >= self.rules.min_confidence_for_decisions:
                    new_level = self._get_higher_trust_level(current_level)
                    reason = f"High accuracy ({trust_metric.accuracy_rate:.2%}) and confidence ({trust_metric.confidence_avg:.2f})"
                else:
                    reason = f"Accuracy sufficient but confidence too low ({trust_metric.confidence_avg:.2f})"

            # Check for inactivity degradation
            else:
                last_decision = (
                    self.db.query(Decision)
                    .filter(Decision.agent_id == agent_id)
                    .order_by(Decision.created_at.desc())
                    .first()
                )

                if last_decision:
                    days_inactive = (datetime.utcnow() - last_decision.created_at).days
                    if days_inactive > self.rules.inactivity_days_for_degradation:
                        new_level = self._get_lower_trust_level(current_level)
                        reason = f"Inactive for {days_inactive} days"

            logger.info(
                f"Trust evaluation for agent {agent_id}: {current_level} → {new_level} ({reason})"
            )
            return new_level, reason

        except Exception as e:
            logger.error(f"Failed to evaluate trust progression: {e}")
            return current_level, f"Evaluation error: {e}"

    def update_trust_level(self, agent_id: UUID, new_level: TrustLevel, reason: str = "") -> bool:
        """Update agent's trust level."""
        try:
            agent = self.db.query(Agent).filter(Agent.agent_id == agent_id).first()

            if not agent:
                logger.warning(f"Agent {agent_id} not found")
                return False

            old_level = TrustLevel(agent.config.get("trust_level", TrustLevel.L0_OBSERVED.value))

            # Update agent config
            if not agent.config:
                agent.config = {}

            agent.config["trust_level"] = new_level.value
            agent.config["trust_level_updated_at"] = datetime.utcnow().isoformat()
            agent.config["trust_level_change_reason"] = reason
            agent.config["previous_trust_level"] = old_level.value

            agent.updated_at = datetime.utcnow()

            self.db.commit()

            logger.info(
                f"Updated trust level for agent {agent_id}: {old_level} → {new_level} ({reason})"
            )
            return True

        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Failed to update trust level: {e}")
            return False

    def apply_trust_transition(
        self, agent_id: UUID, force_evaluation: bool = False
    ) -> Tuple[bool, str]:
        """Apply trust level transition based on current metrics."""
        try:
            # Calculate current metrics
            trust_metric = self.calculate_trust_metrics(agent_id)

            # Evaluate progression
            new_level, reason = self.evaluate_trust_progression(agent_id, trust_metric)

            # Get current level
            agent = self.db.query(Agent).filter(Agent.agent_id == agent_id).first()

            if not agent:
                return False, "Agent not found"

            current_level = TrustLevel(
                agent.config.get("trust_level", TrustLevel.L0_OBSERVED.value)
            )

            # Apply transition if needed
            if new_level != current_level or force_evaluation:
                success = self.update_trust_level(agent_id, new_level, reason)
                if success:
                    return True, f"Trust level updated: {current_level} → {new_level} ({reason})"
                else:
                    return False, "Failed to update trust level"
            else:
                return True, f"Trust level unchanged: {current_level} ({reason})"

        except Exception as e:
            logger.error(f"Failed to apply trust transition: {e}")
            return False, str(e)

    def apply_degradation(
        self, agent_id: UUID, levels_to_drop: int = 1, reason: str = "Manual degradation"
    ) -> bool:
        """Apply trust level degradation."""
        try:
            agent = self.db.query(Agent).filter(Agent.agent_id == agent_id).first()

            if not agent:
                return False

            current_level = TrustLevel(
                agent.config.get("trust_level", TrustLevel.L0_OBSERVED.value)
            )

            # Calculate new level
            current_index = self.trust_levels.index(current_level)
            new_index = max(0, current_index - levels_to_drop)
            new_level = self.trust_levels[new_index]

            return self.update_trust_level(agent_id, new_level, reason)

        except Exception as e:
            logger.error(f"Failed to apply degradation: {e}")
            return False

    def get_trust_history(self, agent_id: UUID, limit: int = 100) -> List[TrustMetric]:
        """Get trust metric history for an agent."""
        try:
            metrics = (
                self.db.query(TrustMetric)
                .filter(TrustMetric.agent_id == agent_id)
                .order_by(TrustMetric.calculated_at.desc())
                .limit(limit)
                .all()
            )

            return metrics

        except SQLAlchemyError as e:
            logger.error(f"Failed to get trust history: {e}")
            return []

    def get_required_approvals(self, trust_level: TrustLevel, action_type: str) -> Dict[str, Any]:
        """Get required approvals based on trust level."""
        approval_matrix = {
            TrustLevel.L0_OBSERVED: {
                "all_actions": True,
                "requires_human": True,
                "auto_approve": [],
            },
            TrustLevel.L1_ASSISTED: {
                "all_actions": False,
                "requires_human": True,
                "auto_approve": ["read", "suggest"],
            },
            TrustLevel.L2_SUPERVISED: {
                "all_actions": False,
                "requires_human": True,
                "auto_approve": ["read", "suggest", "validate"],
            },
            TrustLevel.L3_DELEGATED: {
                "all_actions": False,
                "requires_human": False,
                "auto_approve": ["read", "suggest", "validate", "execute_non_critical"],
            },
            TrustLevel.L4_AUTONOMOUS: {
                "all_actions": False,
                "requires_human": False,
                "auto_approve": ["all"],
            },
        }

        rules = approval_matrix.get(trust_level, approval_matrix[TrustLevel.L0_OBSERVED])

        return {
            "trust_level": trust_level.value,
            "action_type": action_type,
            "requires_approval": (
                rules["all_actions"]
                or action_type not in rules["auto_approve"]
                and "all" not in rules["auto_approve"]
            ),
            "requires_human": rules["requires_human"],
            "approval_rules": rules,
        }

    def _get_higher_trust_level(self, current: TrustLevel) -> TrustLevel:
        """Get the next higher trust level."""
        current_index = self.trust_levels.index(current)
        if current_index < len(self.trust_levels) - 1:
            return self.trust_levels[current_index + 1]
        return current

    def _get_lower_trust_level(self, current: TrustLevel) -> TrustLevel:
        """Get the next lower trust level."""
        current_index = self.trust_levels.index(current)
        if current_index > 0:
            return self.trust_levels[current_index - 1]
        return current

    def bulk_evaluate_agents(self) -> Dict[UUID, Tuple[bool, str]]:
        """Evaluate and update trust levels for all active agents."""
        results = {}

        try:
            active_agents = self.db.query(Agent).filter(Agent.is_active).all()

            for agent in active_agents:
                success, message = self.apply_trust_transition(agent.agent_id)
                results[agent.agent_id] = (success, message)

            logger.info(f"Bulk evaluated {len(active_agents)} agents")
            return results

        except SQLAlchemyError as e:
            logger.error(f"Failed to bulk evaluate agents: {e}")
            return results
