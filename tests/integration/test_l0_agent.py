"""Integration tests for L0 Agent implementation."""

import pytest
import asyncio
from datetime import datetime, timezone
from unittest.mock import Mock, AsyncMock, patch

from services.agents.personas.l0_agent import BaseL0Agent, ActionType, RiskLevel, ActionSuggestion


@pytest.fixture
def l0_agent():
    """Create L0 agent instance for testing."""
    return BaseL0Agent(
        agent_id="test_agent_001", session_id="test_session_001", user_id="test_user_001"
    )


@pytest.mark.asyncio
async def test_l0_agent_initialization(l0_agent):
    """Test L0 agent initializes with correct defaults."""
    assert l0_agent.trust_level == 0
    assert l0_agent.CAPABILITIES.execute is False
    assert l0_agent.CAPABILITIES.suggest is True
    assert l0_agent.CAPABILITIES.observe is True
    assert l0_agent.CAPABILITIES.learn is True
    assert len(l0_agent.pending_suggestions) == 0


@pytest.mark.asyncio
async def test_l0_agent_cannot_execute_without_approval(l0_agent):
    """Test that L0 agent cannot execute actions without approval."""
    for action_type in ActionType:
        can_execute = l0_agent.validate_capabilities(action_type)
        assert can_execute is False, f"L0 agent should not execute {action_type}"


@pytest.mark.asyncio
async def test_risk_score_calculation(l0_agent):
    """Test risk score calculation for different action types."""
    # Test low risk action
    score, level = l0_agent.calculate_risk_score(
        ActionType.CODE_GENERATION, {"is_reversible": True, "has_validation": True}
    )
    assert score < 0.3
    assert level == RiskLevel.LOW

    # Test high risk action
    score, level = l0_agent.calculate_risk_score(
        ActionType.SYSTEM_COMMANDS, {"is_critical_path": True}
    )
    assert score > 0.8
    assert level in (RiskLevel.HIGH, RiskLevel.CRITICAL)

    # Test with production flag
    score, level = l0_agent.calculate_risk_score(
        ActionType.DATABASE_QUERIES, {"affects_production": True}
    )
    assert score > 0.6


@pytest.mark.asyncio
async def test_action_suggestion_creation(l0_agent):
    """Test creating action suggestions."""
    suggestion = await l0_agent.suggest_action(
        action_type=ActionType.CODE_GENERATION,
        description="Generate unit test for user service",
        rationale="User requested test coverage improvement",
        code="def test_user_creation():\n    pass",
        context={"has_tests": True},
    )

    assert suggestion.id is not None
    assert suggestion.action_type == ActionType.CODE_GENERATION
    assert suggestion.description == "Generate unit test for user service"
    assert suggestion.rationale == "User requested test coverage improvement"
    assert suggestion.code is not None
    assert suggestion.risk_level in [RiskLevel.LOW, RiskLevel.MEDIUM]
    assert 0 <= suggestion.confidence <= 1.0
    assert len(suggestion.impact) > 0

    # Check suggestion is stored
    assert suggestion.id in l0_agent.pending_suggestions


@pytest.mark.asyncio
async def test_impact_analysis(l0_agent):
    """Test impact analysis for different action types."""
    # Test file deletion impact
    impact = l0_agent._analyze_impact(
        ActionType.FILE_OPERATIONS, "Delete temporary cache files", {}
    )
    assert any("data loss" in i.lower() for i in impact)

    # Test code modification impact
    impact = l0_agent._analyze_impact(
        ActionType.CODE_MODIFICATION, "Update authentication logic", {"affects_tests": True}
    )
    assert any("test" in i.lower() for i in impact)

    # Test API call impact
    impact = l0_agent._analyze_impact(
        ActionType.API_CALLS, "Call payment processing API", {"has_cost": True}
    )
    assert any("cost" in i.lower() for i in impact)


@pytest.mark.asyncio
async def test_confidence_calculation(l0_agent):
    """Test confidence score calculation."""
    # High confidence scenario
    confidence = l0_agent._calculate_confidence(
        {"has_tests": True, "has_validation": True, "well_documented": True}
    )
    assert confidence > 0.7

    # Low confidence scenario
    confidence = l0_agent._calculate_confidence(
        {"experimental": True, "complex_logic": True, "external_dependency": True}
    )
    assert confidence < 0.3

    # Default confidence
    confidence = l0_agent._calculate_confidence({})
    assert confidence == 0.5


@pytest.mark.asyncio
async def test_approval_workflow(l0_agent):
    """Test approval and rejection workflow."""
    # Create suggestion
    suggestion = await l0_agent.suggest_action(
        action_type=ActionType.CODE_GENERATION, description="Test action", rationale="Testing"
    )

    suggestion_id = suggestion.id

    # Test approval
    assert l0_agent.mark_approved(suggestion_id) is True
    assert suggestion_id in l0_agent.approved_actions
    assert suggestion_id not in l0_agent.pending_suggestions

    # Create another suggestion
    suggestion2 = await l0_agent.suggest_action(
        action_type=ActionType.FILE_OPERATIONS, description="Test action 2", rationale="Testing 2"
    )

    # Test rejection
    assert l0_agent.mark_rejected(suggestion2.id, "Too risky") is True
    assert suggestion2.id in l0_agent.rejected_actions
    assert suggestion2.id not in l0_agent.pending_suggestions


@pytest.mark.asyncio
async def test_multiple_pending_suggestions(l0_agent):
    """Test handling multiple pending suggestions."""
    # Create multiple suggestions
    suggestions = []
    for i in range(5):
        suggestion = await l0_agent.suggest_action(
            action_type=ActionType.CODE_GENERATION,
            description=f"Action {i}",
            rationale=f"Reason {i}",
        )
        suggestions.append(suggestion)

    # Check all are pending
    pending = l0_agent.get_pending_suggestions()
    assert len(pending) == 5

    # Approve some, reject others
    l0_agent.mark_approved(suggestions[0].id)
    l0_agent.mark_approved(suggestions[1].id)
    l0_agent.mark_rejected(suggestions[2].id)

    # Check remaining pending
    pending = l0_agent.get_pending_suggestions()
    assert len(pending) == 2


@pytest.mark.asyncio
async def test_observe_and_learn(l0_agent):
    """Test observation and learning from action results."""
    suggestion = await l0_agent.suggest_action(
        action_type=ActionType.CODE_GENERATION,
        description="Generate code",
        rationale="User request",
    )

    # Simulate successful execution
    action_result = {"status": "success", "execution_time_ms": 150, "errors": []}

    # Test learning (should not raise)
    await l0_agent.observe_and_learn(action_result, suggestion.id)

    # Test learning from failure
    failure_result = {
        "status": "failed",
        "execution_time_ms": 50,
        "errors": ["Syntax error on line 10"],
    }

    await l0_agent.observe_and_learn(failure_result, suggestion.id)


@pytest.mark.asyncio
async def test_timeout_handling():
    """Test that suggestions can handle timeout scenarios."""
    agent = BaseL0Agent("agent_001", "session_001", "user_001")

    # Create suggestion with long processing simulation
    async def slow_suggestion():
        await asyncio.sleep(0.1)  # Simulate processing
        return await agent.suggest_action(
            ActionType.SYSTEM_COMMANDS, "Slow command", "Testing timeout"
        )

    # Should complete normally
    suggestion = await slow_suggestion()
    assert suggestion is not None


@pytest.mark.asyncio
async def test_risk_escalation_based_on_context(l0_agent):
    """Test that risk levels escalate properly based on context."""
    base_action = ActionType.CODE_MODIFICATION

    # Normal risk
    score1, level1 = l0_agent.calculate_risk_score(base_action, {})

    # Elevated risk with critical path
    score2, level2 = l0_agent.calculate_risk_score(base_action, {"is_critical_path": True})

    # Maximum risk with production impact
    score3, level3 = l0_agent.calculate_risk_score(
        base_action, {"is_critical_path": True, "affects_production": True}
    )

    assert score1 < score2 < score3
    assert level1.value <= level2.value <= level3.value


@pytest.mark.asyncio
async def test_audit_logging_mock(l0_agent):
    """Test that audit logging is called (mocked)."""
    with patch("builtins.print") as mock_print:
        suggestion = await l0_agent.suggest_action(
            action_type=ActionType.API_CALLS,
            description="Call external API",
            rationale="Data sync required",
        )

        # Check audit log was "written" (printed in PoC)
        assert mock_print.called
        call_args = str(mock_print.call_args_list)
        assert "AUDIT LOG" in call_args
        assert suggestion.id in call_args
