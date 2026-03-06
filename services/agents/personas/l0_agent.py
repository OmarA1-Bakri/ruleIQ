"""
Trust Level 0 (Observed) Agent Implementation

This agent operates in full observation mode where:
- All actions require explicit user approval
- Complete audit trail of all decisions
- Risk assessment for each action
- Rollback capability for any approved action
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from uuid import uuid4
from enum import Enum
from dataclasses import dataclass, field

from services.agents.base import BaseAgent
from services.agents.trust import TrustLevel
from services.agents.approval.workflow import ApprovalWorkflow, ApprovalState
from services.agents.risk.assessor import RiskAssessor, RiskLevel
from services.agents.audit.l0_auditor import L0Auditor
from services.agents.rollback.manager import RollbackManager


class L0Capability(Enum):
    """Capabilities specific to L0 agents"""

    OBSERVE = "observe"
    SUGGEST = "suggest"
    LEARN = "learn"
    ANALYZE = "analyze"


@dataclass
class L0Suggestion:
    """Represents a suggestion from the L0 agent"""

    id: str = field(default_factory=lambda: str(uuid4()))
    action_type: str = ""
    description: str = ""
    rationale: str = ""
    code: Optional[str] = None
    impact: List[str] = field(default_factory=list)
    risk_level: RiskLevel = RiskLevel.LOW
    risk_score: float = 0.0
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseL0Agent(BaseAgent):
    """
    Base Trust Level 0 Agent

    Operates in full observation mode with all actions requiring
    explicit user approval. Provides detailed rationale for suggestions
    and maintains complete audit trail.
    """

    # L0 Agent behavior configuration
    CAPABILITIES = {
        "execute": False,  # Cannot execute without approval
        "suggest": True,  # Can make suggestions
        "observe": True,  # Can observe system state
        "learn": True,  # Can learn from interactions
    }

    # Actions that always require approval
    APPROVAL_REQUIRED = [
        "code_generation",
        "code_modification",
        "file_operations",
        "system_commands",
        "api_calls",
        "database_queries",
    ]

    # Risk thresholds for L0
    RISK_THRESHOLDS = {"low": 0.3, "medium": 0.6, "high": 0.8, "critical": 0.95}

    # Default timeout for approvals (5 minutes)
    DEFAULT_APPROVAL_TIMEOUT = timedelta(minutes=5)

    def __init__(
        self, agent_id: str, name: str, persona_type: str, config: Optional[Dict[str, Any]] = None
    ) -> None:
        """Initialize L0 Agent with approval and audit systems"""
        super().__init__(
            agent_id=agent_id,
            name=name,
            persona_type=persona_type,
            trust_level=TrustLevel.L0_OBSERVED,
            config=config or {},
        )

        # Initialize subsystems
        self.approval_workflow = ApprovalWorkflow()
        self.risk_assessor = RiskAssessor()
        self.auditor = L0Auditor(agent_id=agent_id)
        self.rollback_manager = RollbackManager()

        # Suggestion tracking
        self.pending_suggestions: Dict[str, L0Suggestion] = {}
        self.suggestion_history: List[L0Suggestion] = []

        # Learning metrics
        self.approval_rate = 0.0
        self.rejection_reasons: List[str] = []
        self.successful_patterns: List[Dict[str, Any]] = []

    async def suggest_action(
        self,
        action_type: str,
        description: str,
        context: Dict[str, Any],
        code: Optional[str] = None,
    ) -> L0Suggestion:
        """
        Generate a suggestion for user approval

        Args:
            action_type: Type of action being suggested
            description: Human-readable description
            context: Current context for the action
            code: Optional code to be executed if approved

        Returns:
            L0Suggestion object with risk assessment
        """
        # Generate rationale
        rationale = await self._generate_rationale(action_type, context)

        # Assess risk
        risk_assessment = await self.risk_assessor.assess_action(
            action_type=action_type, context=context, code=code
        )

        # Analyze impact
        impact = await self._analyze_impact(action_type, context, code)

        # Create suggestion
        suggestion = L0Suggestion(
            action_type=action_type,
            description=description,
            rationale=rationale,
            code=code,
            impact=impact,
            risk_level=risk_assessment.level,
            risk_score=risk_assessment.score,
            expires_at=datetime.utcnow() + self.DEFAULT_APPROVAL_TIMEOUT,
            metadata={
                "context": context,
                "agent_id": self.agent_id,
                "session_id": context.get("session_id"),
                "risk_details": risk_assessment.details,
            },
        )

        # Store pending suggestion
        self.pending_suggestions[suggestion.id] = suggestion

        # Log suggestion creation
        await self.auditor.log_suggestion(suggestion)

        return suggestion

    async def request_approval(
        self, suggestion: L0Suggestion, user_id: str, timeout: Optional[timedelta] = None
    ) -> ApprovalState:
        """
        Request user approval for a suggestion

        Args:
            suggestion: The suggestion to approve
            user_id: ID of the user to request approval from
            timeout: Optional custom timeout

        Returns:
            ApprovalState indicating the result
        """
        timeout = timeout or self.DEFAULT_APPROVAL_TIMEOUT

        # Create approval request
        approval_request = await self.approval_workflow.create_request(
            suggestion_id=suggestion.id,
            user_id=user_id,
            action=suggestion.action_type,
            description=suggestion.description,
            rationale=suggestion.rationale,
            risk_level=suggestion.risk_level,
            timeout=timeout,
        )

        # Wait for approval
        state = await self.approval_workflow.wait_for_approval(
            request_id=approval_request.id, timeout=timeout
        )

        # Log approval decision
        await self.auditor.log_approval_decision(
            suggestion=suggestion, state=state, user_id=user_id
        )

        # Update learning metrics
        if state == ApprovalState.APPROVED:
            self.approval_rate = (self.approval_rate * len(self.suggestion_history) + 1) / (
                len(self.suggestion_history) + 1
            )
            self.successful_patterns.append(
                {
                    "action_type": suggestion.action_type,
                    "risk_level": suggestion.risk_level,
                    "context_keys": list(suggestion.metadata.get("context", {}).keys()),
                }
            )
        elif state == ApprovalState.REJECTED:
            self.approval_rate = (self.approval_rate * len(self.suggestion_history)) / (
                len(self.suggestion_history) + 1
            )

        # Move to history
        self.suggestion_history.append(suggestion)
        del self.pending_suggestions[suggestion.id]

        return state

    async def execute_with_rollback(
        self, suggestion: L0Suggestion, dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Execute an approved suggestion with rollback capability

        Args:
            suggestion: The approved suggestion to execute
            dry_run: If True, simulate execution without side effects

        Returns:
            Execution result with rollback information
        """
        # Create rollback point
        rollback_id = await self.rollback_manager.create_checkpoint(
            action_type=suggestion.action_type, context=suggestion.metadata.get("context", {})
        )

        try:
            # Execute in dry-run mode if requested
            if dry_run:
                result = await self._simulate_execution(suggestion)
            else:
                result = await self._execute_suggestion(suggestion)

            # Log successful execution
            await self.auditor.log_execution(
                suggestion=suggestion, result=result, rollback_id=rollback_id
            )

            return {
                "status": "success",
                "result": result,
                "rollback_id": rollback_id,
                "can_rollback": True,
            }

        except Exception as e:
            # Auto-rollback on failure
            await self.rollback_manager.rollback(rollback_id)

            # Log failure
            await self.auditor.log_execution_failure(
                suggestion=suggestion, error=str(e), rollback_id=rollback_id
            )

            return {
                "status": "failed",
                "error": str(e),
                "rollback_id": rollback_id,
                "rolled_back": True,
            }

    async def _generate_rationale(self, action_type: str, context: Dict[str, Any]) -> str:
        """Generate detailed rationale for the suggestion"""
        rationale_parts = []

        # Explain the action
        rationale_parts.append(f"Action: {action_type}")

        # Explain why this action is suggested
        if action_type in ["code_generation", "code_modification"]:
            rationale_parts.append(
                "This action will modify code to address the current requirement."
            )
        elif action_type in ["file_operations"]:
            rationale_parts.append("File operations are needed to manage project resources.")

        # Include context reasoning
        if "error" in context:
            rationale_parts.append(f"This addresses the error: {context['error']}")
        if "user_request" in context:
            rationale_parts.append(f"This fulfills the request: {context['user_request']}")

        # Add safety notes
        rationale_parts.append(
            "This action requires approval for safety and can be rolled back if needed."
        )

        return " ".join(rationale_parts)

    async def _analyze_impact(
        self, action_type: str, context: Dict[str, Any], code: Optional[str] = None
    ) -> List[str]:
        """Analyze the potential impact of an action"""
        impacts = []

        if action_type == "code_generation":
            impacts.append("New code will be added to the project")
            if code and "class" in code:
                impacts.append("New classes will be defined")
            if code and "def " in code:
                impacts.append("New functions will be created")

        elif action_type == "code_modification":
            impacts.append("Existing code will be modified")
            impacts.append("May affect dependent code")

        elif action_type == "file_operations":
            if "create" in context.get("operation", ""):
                impacts.append("New files will be created")
            elif "delete" in context.get("operation", ""):
                impacts.append("Files will be deleted (recoverable via rollback)")
            elif "modify" in context.get("operation", ""):
                impacts.append("File contents will be changed")

        elif action_type == "database_queries":
            if "SELECT" in str(code).upper():
                impacts.append("Database will be queried (read-only)")
            elif "INSERT" in str(code).upper():
                impacts.append("New data will be added to database")
            elif "UPDATE" in str(code).upper():
                impacts.append("Existing data will be modified")
            elif "DELETE" in str(code).upper():
                impacts.append("Data will be removed from database")

        return impacts

    async def _simulate_execution(self, suggestion: L0Suggestion) -> Dict[str, Any]:
        """Simulate execution for dry-run mode"""
        return {
            "simulated": True,
            "action_type": suggestion.action_type,
            "would_execute": suggestion.code or suggestion.description,
            "expected_impact": suggestion.impact,
            "risk_level": suggestion.risk_level.value,
        }

    async def _execute_suggestion(self, suggestion: L0Suggestion) -> Dict[str, Any]:
        """Execute the actual suggestion"""
        # This would integrate with the actual execution engine
        # For now, return a mock result
        return {
            "executed": True,
            "action_type": suggestion.action_type,
            "result": "Action executed successfully",
            "timestamp": datetime.utcnow().isoformat(),
        }

    async def get_audit_trail(
        self, session_id: Optional[str] = None, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get audit trail for this agent"""
        return await self.auditor.get_audit_trail(session_id=session_id, limit=limit)

    async def rollback_action(self, rollback_id: str) -> bool:
        """Rollback a previously executed action"""
        success = await self.rollback_manager.rollback(rollback_id)

        # Log rollback
        await self.auditor.log_rollback(rollback_id=rollback_id, success=success)

        return success

    async def get_metrics(self) -> Dict[str, Any]:
        """Get performance and learning metrics"""
        return {
            "trust_level": self.trust_level.value,
            "total_suggestions": len(self.suggestion_history),
            "pending_suggestions": len(self.pending_suggestions),
            "approval_rate": self.approval_rate,
            "successful_patterns": self.successful_patterns[:10],  # Top 10
            "rejection_reasons": self.rejection_reasons[:5],  # Top 5
            "capabilities": list(self.CAPABILITIES.keys()),
            "risk_thresholds": self.RISK_THRESHOLDS,
        }
