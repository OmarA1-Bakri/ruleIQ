"""
Comprehensive Integration Tests for Agentic System

Tests complete agent workflows, multi-agent coordination, trust level progression,
session management, error handling, and performance scenarios.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from uuid import uuid4
from unittest.mock import patch, MagicMock, AsyncMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
import json
import tempfile
import shutil
from freezegun import freeze_time
from faker import Faker

from models.agentic_models import (
    Base,
    Agent,
    AgentSession,
    AgentDecision,
    TrustMetric,
    Decision,
    DecisionFeedback,
    SessionContext,
)
from services.agents.orchestrator import OrchestratorService
from services.agents.trust_manager import TrustManager, TrustProgressionRules
from services.agents.session_manager import SessionManager
from services.agents.decision_tracker import DecisionTracker, DecisionType, DecisionStatus
from services.agents.trust_algorithm import TrustLevel, TrustProgressionAlgorithm
from services.agents.trust_algorithm import MetricType, BehaviorMetric


@pytest.fixture(scope="function")
def test_db():
    """Create a test database for integration tests."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()

    yield session

    session.close()
    engine.dispose()


@pytest.fixture
def faker():
    """Provide faker instance for test data generation."""
    return Faker()


@pytest.fixture
def orchestrator(test_db):
    """Create an OrchestratorService with real database."""
    return OrchestratorService(test_db)


@pytest.fixture
def trust_manager(test_db):
    """Create a TrustManager with real database."""
    return TrustManager(test_db)


@pytest.fixture
def session_manager(test_db):
    """Create a SessionManager with real database."""
    return SessionManager(test_db)


@pytest.fixture
def decision_tracker(test_db):
    """Create a DecisionTracker with real database."""
    return DecisionTracker(test_db)


class TestAgentWorkflowIntegration:
    """Test complete agent workflow scenarios."""

    @pytest.mark.asyncio
    async def test_complete_agent_lifecycle(self, orchestrator, test_db, faker):
        """Test complete agent lifecycle from creation to termination."""
        # Create agent
        agent = await orchestrator.create_agent(
            name=faker.name(),
            persona_type="developer",
            capabilities={"code_generation": True, "testing": True, "review": True},
            config={
                "max_tokens": 2000,
                "temperature": 0.7,
                "trust_level": TrustLevel.L0_OBSERVED.value,
            },
        )

        assert agent is not None
        assert agent.agent_id is not None
        assert agent.name is not None

        # Verify agent in database
        db_agent = test_db.query(Agent).filter(Agent.agent_id == agent.agent_id).first()
        assert db_agent is not None
        assert db_agent.name == agent.name
        assert db_agent.persona_type == "developer"

        # Activate agent
        activation_result = await orchestrator.activate_agent(agent.agent_id)
        assert activation_result is True
        assert agent.agent_id in orchestrator.agent_registry

        # Create session
        user_id = str(uuid4())
        session = await orchestrator.create_session(
            agent_id=agent.agent_id,
            user_id=user_id,
            initial_context={
                "task": "Generate unit tests",
                "language": "Python",
                "framework": "pytest",
            },
        )

        assert session is not None
        assert session.session_id is not None
        assert session.trust_level == TrustLevel.L0_OBSERVED

        # Verify session in database
        db_session = (
            test_db.query(AgentSession)
            .filter(AgentSession.session_id == session.session_id)
            .first()
        )
        assert db_session is not None
        assert db_session.context["task"] == "Generate unit tests"

        # End session
        end_result = await orchestrator.end_session(session.session_id)
        assert end_result is True
        assert session.session_id not in orchestrator.active_sessions

        # Terminate agent
        termination_result = await orchestrator.terminate_agent(agent.agent_id)
        assert termination_result is True
        assert agent.agent_id not in orchestrator.agent_registry

    @pytest.mark.asyncio
    async def test_agent_workflow_with_decisions(
        self, orchestrator, decision_tracker, test_db, faker
    ):
        """Test agent workflow including decision tracking."""
        # Create and activate agent
        agent = await orchestrator.create_agent(
            name=f"TestAgent_{faker.name()}",
            persona_type="developer",
            capabilities={"code_generation": True},
        )
        await orchestrator.activate_agent(agent.agent_id)

        # Create session
        session = await orchestrator.create_session(
            agent_id=agent.agent_id,
            user_id=str(uuid4()),
            initial_context={"task": "implement_feature"},
        )

        # Record decision
        decision = decision_tracker.record_decision(
            session_id=session.session_id,
            agent_id=agent.agent_id,
            decision_type=DecisionType.ACTION,
            decision_data={"action": "generate_code", "language": "python", "complexity": 0.7},
            confidence=0.85,
            trust_level=TrustLevel.L0_OBSERVED,
        )

        assert decision is not None
        assert decision.decision_id is not None
        assert decision.status == DecisionStatus.PENDING.value

        # Validate decision
        is_valid, errors = decision_tracker.validate_decision(decision.decision_id)
        assert is_valid is True
        assert len(errors) == 0

        # Execute decision
        execution_result = decision_tracker.execute_decision(
            decision_id=decision.decision_id, execution_result={"code_generated": True, "lines": 25}
        )
        assert execution_result is True

        # Verify decision status updated
        updated_decision = (
            test_db.query(Decision).filter(Decision.decision_id == decision.decision_id).first()
        )
        assert updated_decision.status == DecisionStatus.EXECUTED.value
        assert updated_decision.executed_at is not None

        # Record feedback
        feedback = decision_tracker.record_feedback(
            decision_id=decision.decision_id,
            feedback_type="approval",
            feedback_value=True,
            user_id=str(uuid4()),
        )
        assert feedback is not None

        # Clean up
        await orchestrator.end_session(session.session_id)
        await orchestrator.terminate_agent(agent.agent_id)


class TestMultiAgentCoordination:
    """Test multi-agent coordination and communication."""

    @pytest.mark.asyncio
    async def test_multi_agent_workflow(self, orchestrator, test_db, faker):
        """Test coordination between multiple agents."""
        # Create multiple agents with different personas
        agents = []
        personas = ["developer", "qa", "architect", "security"]

        for persona in personas:
            agent = await orchestrator.create_agent(
                name=f"{persona.title()}Agent_{faker.name()}",
                persona_type=persona,
                capabilities={
                    "code_generation": persona == "developer",
                    "testing": persona == "qa",
                    "design": persona == "architect",
                    "security_check": persona == "security",
                },
            )
            agents.append(agent)

        # Activate all agents
        for agent in agents:
            activation_result = await orchestrator.activate_agent(agent.agent_id)
            assert activation_result is True

        # Create sessions for each agent
        user_id = str(uuid4())
        sessions = []

        for agent in agents:
            session = await orchestrator.create_session(
                agent_id=agent.agent_id,
                user_id=user_id,
                initial_context={
                    "task": f"perform_{agent.persona_type}_task",
                    "coordination_required": True,
                },
            )
            sessions.append(session)

        # Verify all sessions are active
        active_sessions = await orchestrator.get_active_sessions()
        assert len(active_sessions) == len(agents)

        # Verify agent registry
        active_agents = await orchestrator.get_active_agents()
        assert len(active_agents) == len(agents)

        # Clean up all sessions and agents
        for session in sessions:
            await orchestrator.end_session(session.session_id)

        for agent in agents:
            await orchestrator.terminate_agent(agent.agent_id)

        # Verify cleanup
        active_sessions = await orchestrator.get_active_sessions()
        assert len(active_sessions) == 0

        active_agents = await orchestrator.get_active_agents()
        assert len(active_agents) == 0

    @pytest.mark.asyncio
    async def test_agent_resource_limits(self, orchestrator, test_db, faker):
        """Test agent resource limits and concurrent operation handling."""
        # Create agents up to the limit
        max_agents = orchestrator.max_concurrent_agents
        agents = []

        for i in range(max_agents):
            agent = await orchestrator.create_agent(
                name=f"Agent{i}_{faker.name()}",
                persona_type="developer",
                capabilities={"code_generation": True},
            )
            agents.append(agent)

        # Activate agents up to the limit
        for i, agent in enumerate(agents):
            if i < max_agents:
                activation_result = await orchestrator.activate_agent(agent.agent_id)
                assert activation_result is True
            else:
                # Should fail when limit reached
                activation_result = await orchestrator.activate_agent(agent.agent_id)
                assert activation_result is False

        # Verify active agent count
        active_agents = await orchestrator.get_active_agents()
        assert len(active_agents) == max_agents

        # Clean up
        for agent in agents:
            await orchestrator.terminate_agent(agent.agent_id)


class TestTrustLevelProgression:
    """Test trust level progression and algorithm."""

    @pytest.mark.asyncio
    async def test_trust_level_calculation(self, trust_manager, test_db, faker):
        """Test trust level calculation with metrics."""
        agent_id = uuid4()
        session_id = uuid4()

        # Create agent and session records
        agent = Agent(
            agent_id=agent_id,
            name=f"TrustTestAgent_{faker.name()}",
            persona_type="developer",
            capabilities={"code_generation": True},
            is_active=True,
            config={"trust_level": TrustLevel.L0_OBSERVED.value},
        )
        test_db.add(agent)

        session = AgentSession(
            session_id=session_id,
            agent_id=agent_id,
            user_id=str(uuid4()),
            trust_level=TrustLevel.L0_OBSERVED.value,
            context={},
            started_at=datetime.utcnow(),
        )
        test_db.add(session)
        test_db.commit()

        # Add trust metrics
        for i in range(15):  # More than minimum for evaluation
            metric = TrustMetric(
                metric_id=uuid4(),
                session_id=session_id,
                metric_type="accuracy",
                metric_value=95.0 + i,  # High accuracy
                measurement_context={"iteration": i},
            )
            test_db.add(metric)

        test_db.commit()

        # Calculate trust metrics
        trust_metric = trust_manager.calculate_trust_metrics(agent_id)

        assert trust_metric is not None
        assert trust_metric.agent_id == agent_id
        assert trust_metric.total_decisions == 15
        assert trust_metric.accuracy_rate > 0.9  # High accuracy

        # Evaluate trust progression
        new_level, reason = trust_manager.evaluate_trust_progression(agent_id, trust_metric)

        # Should progress from L0 due to high accuracy
        assert new_level.value > TrustLevel.L0_OBSERVED.value
        assert "High accuracy" in reason

    @pytest.mark.asyncio
    async def test_trust_level_demotion(self, trust_manager, test_db, faker):
        """Test trust level demotion on poor performance."""
        agent_id = uuid4()
        session_id = uuid4()

        # Create agent at higher trust level
        agent = Agent(
            agent_id=agent_id,
            name=f"DemotionTestAgent_{faker.name()}",
            persona_type="developer",
            capabilities={"code_generation": True},
            is_active=True,
            config={"trust_level": TrustLevel.L2_SUPERVISED.value},
        )
        test_db.add(agent)

        session = AgentSession(
            session_id=session_id,
            agent_id=agent_id,
            user_id=str(uuid4()),
            trust_level=TrustLevel.L2_SUPERVISED.value,
            context={},
            started_at=datetime.utcnow(),
        )
        test_db.add(session)
        test_db.commit()

        # Add poor performance metrics
        for i in range(20):
            metric = TrustMetric(
                metric_id=uuid4(),
                session_id=session_id,
                metric_type="accuracy",
                metric_value=20.0,  # Very low accuracy
                measurement_context={"iteration": i},
            )
            test_db.add(metric)

        test_db.commit()

        # Calculate metrics and evaluate
        trust_metric = trust_manager.calculate_trust_metrics(agent_id)
        new_level, reason = trust_manager.evaluate_trust_progression(agent_id, trust_metric)

        # Should demote due to low accuracy
        assert new_level.value < TrustLevel.L2_SUPERVISED.value
        assert "rejection rate" in reason.lower() or "accuracy" in reason.lower()

    @pytest.mark.asyncio
    async def test_trust_algorithm_integration(self, faker):
        """Test trust progression algorithm integration."""
        user_id = str(uuid4())
        algorithm = TrustProgressionAlgorithm(user_id)

        # Track successful actions
        for _i in range(150):  # More than minimum threshold
            await algorithm.track_action(
                action_type="code_generation",
                was_approved=True,
                was_successful=True,
                complexity=0.8,
                execution_time_ms=500,
            )

        # Check promotion eligibility
        eligible, next_level, reasons = await algorithm.check_promotion_eligibility()

        assert eligible is True
        assert next_level == TrustLevel.L1_ASSISTED
        assert len(reasons) == 0

        # Promote trust level
        promotion_result = await algorithm.promote_trust_level(
            authorized_by="system", reason="High performance in testing"
        )

        assert promotion_result["success"] is True
        assert promotion_result["new_level"] == TrustLevel.L1_ASSISTED.name


class TestSessionManagement:
    """Test session management and context persistence."""

    @pytest.mark.asyncio
    async def test_session_context_persistence(self, session_manager, test_db, faker):
        """Test session context saving and loading."""
        agent_id = uuid4()
        user_id = str(uuid4())

        # Create agent session
        session = await session_manager.create_session(
            agent_id=agent_id,
            user_id=user_id,
            initial_context={
                "task": "implement_feature",
                "language": "python",
                "framework": "fastapi",
            },
        )

        assert session is not None

        # Update context
        context_updates = {
            "current_step": "design_api",
            "completed_steps": ["analyze_requirements"],
            "next_steps": ["implement_endpoints", "add_validation"],
        }

        update_result = await session_manager.update_context(
            session_id=session.session_id, context_updates=context_updates, merge=True
        )

        assert update_result is True

        # Retrieve context
        retrieved_context = await session_manager.get_context(session.session_id)

        assert retrieved_context is not None
        assert retrieved_context["task"] == "implement_feature"
        assert retrieved_context["current_step"] == "design_api"
        assert "analyze_requirements" in retrieved_context["completed_steps"]

        # Test context serialization
        serialized = await session_manager.serialize_context(session.session_id)
        assert serialized is not None

        # Test context deserialization
        new_context = {"restored": True, "timestamp": datetime.utcnow().isoformat()}
        deserialize_result = await session_manager.deserialize_context(
            session_id=session.session_id, context_str=json.dumps(new_context)
        )
        assert deserialize_result is True

        # Verify deserialized context
        final_context = await session_manager.get_context(session.session_id)
        assert final_context["restored"] is True

    @pytest.mark.asyncio
    async def test_session_timeout_handling(self, session_manager, test_db, faker):
        """Test session timeout and cleanup."""
        agent_id = uuid4()

        # Create session
        session = await session_manager.create_session(
            agent_id=agent_id, user_id=str(uuid4()), initial_context={"task": "test_timeout"}
        )

        # Manually set old start time to simulate timeout
        session.started_at = datetime.utcnow() - timedelta(hours=2)
        test_db.commit()

        # Check timeout
        is_timed_out = await session_manager.check_session_timeout(session.session_id)
        assert is_timed_out is True

        # End session (cleanup)
        end_result = await session_manager.end_session(session.session_id, "timeout")
        assert end_result is True

    @pytest.mark.asyncio
    async def test_session_extension(self, session_manager, test_db, faker):
        """Test session extension functionality."""
        agent_id = uuid4()

        # Create session
        session = await session_manager.create_session(
            agent_id=agent_id, user_id=str(uuid4()), initial_context={"task": "test_extension"}
        )

        # Extend session
        extension_result = await session_manager.extend_session(
            session_id=session.session_id, extension_minutes=30
        )

        assert extension_result is True

        # Verify extension metadata
        db_session = (
            test_db.query(AgentSession)
            .filter(AgentSession.session_id == session.session_id)
            .first()
        )

        assert db_session.session_metadata["extension_minutes"] == 30
        assert "extended_at" in db_session.session_metadata

    @pytest.mark.asyncio
    async def test_session_context_history(self, session_manager, test_db, faker):
        """Test session context history tracking."""
        agent_id = uuid4()

        # Create session
        session = await session_manager.create_session(
            agent_id=agent_id, user_id=str(uuid4()), initial_context={"version": 1}
        )

        # Update context multiple times
        for i in range(5):
            await session_manager.update_context(
                session_id=session.session_id,
                context_updates={"version": i + 2, "step": f"step_{i}"},
                merge=True,
            )

        # Get context history
        history = await session_manager.get_session_history(session.session_id)

        assert len(history) == 6  # Initial + 5 updates
        assert history[0].sequence_number == 0  # Initial context
        assert history[-1].sequence_number == 5  # Last update

        # Test context recovery
        recovery_result = await session_manager.recover_context(
            session_id=session.session_id, sequence_number=2
        )

        assert recovery_result is True

        # Verify recovered context
        current_context = await session_manager.get_context(session.session_id)
        assert current_context["version"] == 3  # Sequence 2 has version 3


class TestErrorHandling:
    """Test error handling and recovery mechanisms."""

    @pytest.mark.asyncio
    async def test_agent_creation_failure_recovery(self, orchestrator, test_db):
        """Test recovery from agent creation failures."""
        # Mock database error during creation
        with patch.object(test_db, "commit", side_effect=Exception("DB Error")):
            with pytest.raises(Exception):
                await orchestrator.create_agent(
                    name="FailingAgent",
                    persona_type="developer",
                    capabilities={"code_generation": True},
                )

        # Verify no agent was created
        agent_count = test_db.query(Agent).count()
        assert agent_count == 0

        # Try creation again (recovery)
        agent = await orchestrator.create_agent(
            name="RecoveredAgent", persona_type="developer", capabilities={"code_generation": True}
        )

        assert agent is not None
        assert agent.name == "RecoveredAgent"

    @pytest.mark.asyncio
    async def test_session_error_recovery(self, session_manager, test_db):
        """Test session error handling and recovery."""
        agent_id = uuid4()

        # Create session
        session = await session_manager.create_session(
            agent_id=agent_id, user_id=str(uuid4()), initial_context={"task": "test_recovery"}
        )

        # Mock database error during context update
        with patch.object(test_db, "commit", side_effect=Exception("DB Error")):
            update_result = await session_manager.update_context(
                session_id=session.session_id, context_updates={"error_test": True}
            )
            assert update_result is False

        # Verify context wasn't updated
        context = await session_manager.get_context(session.session_id)
        assert "error_test" not in context

        # Try update again (recovery)
        update_result = await session_manager.update_context(
            session_id=session.session_id, context_updates={"recovery_test": True}
        )
        assert update_result is True

        # Verify context was updated
        context = await session_manager.get_context(session.session_id)
        assert context["recovery_test"] is True

    @pytest.mark.asyncio
    async def test_decision_validation_error_handling(self, decision_tracker, test_db):
        """Test decision validation error handling."""
        # Create decision with invalid data
        decision = decision_tracker.record_decision(
            session_id=uuid4(),
            agent_id=uuid4(),
            decision_type=DecisionType.ACTION,
            decision_data={},  # Empty data should fail validation
            confidence=0.3,  # Low confidence should fail
            trust_level=TrustLevel.L0_OBSERVED,
        )

        # Validate decision
        is_valid, errors = decision_tracker.validate_decision(decision.decision_id)

        assert is_valid is False
        assert len(errors) > 0
        assert any("confidence" in error.lower() for error in errors)
        assert any("data" in error.lower() for error in errors)

    @pytest.mark.asyncio
    async def test_trust_calculation_error_recovery(self, trust_manager, test_db):
        """Test trust calculation error handling."""
        agent_id = uuid4()

        # Mock database error during trust calculation
        with patch.object(test_db, "query", side_effect=Exception("DB Error")):
            trust_metric = trust_manager.calculate_trust_metrics(agent_id)

            # Should return empty metric on error
            assert trust_metric.total_decisions == 0
            assert trust_metric.accuracy_rate == 0.0


@pytest.mark.slow
class TestPerformance:
    """Test performance with concurrent operations."""

    @pytest.mark.asyncio
    async def test_concurrent_agent_operations(self, orchestrator, test_db, faker):
        """Test concurrent agent creation and operations."""

        async def create_and_operate_agent(index):
            # Create agent
            agent = await orchestrator.create_agent(
                name=f"ConcurrentAgent{index}_{faker.name()}",
                persona_type="developer",
                capabilities={"code_generation": True},
            )

            # Activate agent
            await orchestrator.activate_agent(agent.agent_id)

            # Create session
            session = await orchestrator.create_session(
                agent_id=agent.agent_id,
                user_id=str(uuid4()),
                initial_context={"concurrent_test": True, "index": index},
            )

            # Simulate some operations
            await asyncio.sleep(0.01)  # Small delay to simulate work

            # End session and terminate
            await orchestrator.end_session(session.session_id)
            await orchestrator.terminate_agent(agent.agent_id)

            return agent.agent_id

        # Run 10 concurrent agent operations
        tasks = [create_and_operate_agent(i) for i in range(10)]
        results = await asyncio.gather(*tasks)

        # Verify all operations completed
        assert len(results) == 10
        assert len(set(results)) == 10  # All unique IDs

        # Verify cleanup
        active_agents = await orchestrator.get_active_agents()
        assert len(active_agents) == 0

        active_sessions = await orchestrator.get_active_sessions()
        assert len(active_sessions) == 0

    @pytest.mark.asyncio
    async def test_high_frequency_decision_tracking(self, decision_tracker, test_db):
        """Test decision tracking under high frequency."""
        session_id = uuid4()
        agent_id = uuid4()

        # Record many decisions quickly
        decisions = []
        for i in range(100):
            decision = decision_tracker.record_decision(
                session_id=session_id,
                agent_id=agent_id,
                decision_type=DecisionType.ACTION,
                decision_data={"action": f"action_{i}", "index": i},
                confidence=0.8,
                trust_level=TrustLevel.L1_ASSISTED,
            )
            decisions.append(decision)

        # Verify all decisions recorded
        assert len(decisions) == 100

        # Verify database state
        db_decisions = test_db.query(Decision).filter(Decision.session_id == session_id).all()

        assert len(db_decisions) == 100

        # Test bulk validation
        for decision in decisions[:10]:  # Test first 10
            is_valid, errors = decision_tracker.validate_decision(decision.decision_id)
            assert is_valid is True

    @pytest.mark.asyncio
    async def test_session_cleanup_performance(self, session_manager, test_db):
        """Test session cleanup performance with many sessions."""
        agent_id = uuid4()

        # Create many sessions
        sessions = []
        for i in range(50):
            session = await session_manager.create_session(
                agent_id=agent_id,
                user_id=str(uuid4()),
                initial_context={"bulk_test": True, "index": i},
            )
            sessions.append(session)

        # Manually expire sessions
        for session in sessions:
            session.started_at = datetime.utcnow() - timedelta(hours=2)
        test_db.commit()

        # Run cleanup (this should be fast)
        cleanup_start = datetime.utcnow()

        # End all sessions
        for session in sessions:
            await session_manager.end_session(session.session_id, "bulk_cleanup")

        cleanup_end = datetime.utcnow()
        cleanup_duration = (cleanup_end - cleanup_start).total_seconds()

        # Cleanup should be reasonably fast (< 1 second for 50 sessions)
        assert cleanup_duration < 1.0

        # Verify all sessions ended
        active_sessions = await session_manager.get_active_sessions(agent_id=agent_id)
        assert len(active_sessions) == 0


class TestIntegrationScenarios:
    """Test complete integration scenarios."""

    @pytest.mark.asyncio
    async def test_end_to_end_agent_workflow(
        self, orchestrator, trust_manager, session_manager, decision_tracker, test_db, faker
    ):
        """Test complete end-to-end agent workflow."""
        # 1. Create and setup agent
        agent = await orchestrator.create_agent(
            name=f"E2E_Agent_{faker.name()}",
            persona_type="developer",
            capabilities={"code_generation": True, "testing": True},
        )

        await orchestrator.activate_agent(agent.agent_id)

        # 2. Create session with context
        session = await orchestrator.create_session(
            agent_id=agent.agent_id,
            user_id=str(uuid4()),
            initial_context={
                "project": "e2e_test",
                "task": "implement_user_authentication",
                "requirements": ["secure", "scalable", "testable"],
            },
        )

        # 3. Update session context as work progresses
        await session_manager.update_context(
            session_id=session.session_id,
            context_updates={
                "current_phase": "analysis",
                "completed": [],
                "in_progress": ["analyze_requirements"],
            },
        )

        # 4. Record decisions and actions
        decisions = []
        for i in range(3):
            decision = decision_tracker.record_decision(
                session_id=session.session_id,
                agent_id=agent.agent_id,
                decision_type=DecisionType.ACTION,
                decision_data={
                    "action": f"implement_feature_{i}",
                    "complexity": 0.7,
                    "estimated_time": "2 hours",
                },
                confidence=0.85,
                trust_level=TrustLevel.L0_OBSERVED,
            )
            decisions.append(decision)

        # 5. Validate and execute decisions
        for decision in decisions:
            is_valid, errors = decision_tracker.validate_decision(decision.decision_id)
            assert is_valid is True

            decision_tracker.execute_decision(
                decision_id=decision.decision_id,
                execution_result={"success": True, "lines_of_code": 50},
            )

        # 6. Record feedback
        for decision in decisions:
            decision_tracker.record_feedback(
                decision_id=decision.decision_id, feedback_type="approval", feedback_value=True
            )

        # 7. Calculate trust metrics
        trust_metric = trust_manager.calculate_trust_metrics(agent.agent_id)

        # 8. Update context with completion
        await session_manager.update_context(
            session_id=session.session_id,
            context_updates={
                "current_phase": "completed",
                "completed": ["analyze_requirements", "implement_auth", "add_tests"],
                "in_progress": [],
            },
        )

        # 9. End session
        await orchestrator.end_session(session.session_id)

        # 10. Get final metrics
        final_metrics = await orchestrator.get_agent_metrics(agent.agent_id)

        # Verify final state
        assert final_metrics["total_sessions"] == 1
        assert final_metrics["is_active"] is True
        assert trust_metric.total_decisions == 3

        # 11. Cleanup
        await orchestrator.terminate_agent(agent.agent_id)

    @pytest.mark.asyncio
    async def test_multi_agent_collaboration_scenario(
        self, orchestrator, decision_tracker, test_db, faker
    ):
        """Test multi-agent collaboration on a complex task."""
        # Create specialized agents
        agents_data = [
            ("ArchitectAgent", "architect", {"design": True, "planning": True}),
            ("DeveloperAgent", "developer", {"code_generation": True, "implementation": True}),
            ("QAAgent", "qa", {"testing": True, "validation": True}),
            ("SecurityAgent", "security", {"security_check": True, "audit": True}),
        ]

        agents = []
        for name, persona, capabilities in agents_data:
            agent = await orchestrator.create_agent(
                name=f"{name}_{faker.name()}", persona_type=persona, capabilities=capabilities
            )
            await orchestrator.activate_agent(agent.agent_id)
            agents.append(agent)

        user_id = str(uuid4())

        # Create collaborative sessions
        sessions = []
        for agent in agents:
            session = await orchestrator.create_session(
                agent_id=agent.agent_id,
                user_id=user_id,
                initial_context={
                    "collaboration_task": "build_secure_web_app",
                    "agent_role": agent.persona_type,
                    "team_size": len(agents),
                },
            )
            sessions.append(session)

        # Simulate collaborative workflow
        # Architect designs
        design_decision = decision_tracker.record_decision(
            session_id=sessions[0].session_id,
            agent_id=agents[0].agent_id,
            decision_type=DecisionType.ACTION,
            decision_data={
                "action": "design_system_architecture",
                "deliverable": "system_design_document",
            },
            confidence=0.9,
            trust_level=TrustLevel.L1_ASSISTED,
        )

        # Developer implements
        impl_decision = decision_tracker.record_decision(
            session_id=sessions[1].session_id,
            agent_id=agents[1].agent_id,
            decision_type=DecisionType.ACTION,
            decision_data={
                "action": "implement_user_auth",
                "based_on": str(design_decision.decision_id),
            },
            confidence=0.85,
            trust_level=TrustLevel.L1_ASSISTED,
        )

        # QA tests
        test_decision = decision_tracker.record_decision(
            session_id=sessions[2].session_id,
            agent_id=agents[2].agent_id,
            decision_type=DecisionType.ACTION,
            decision_data={"action": "create_test_suite", "target": str(impl_decision.decision_id)},
            confidence=0.8,
            trust_level=TrustLevel.L1_ASSISTED,
        )

        # Security audits
        security_decision = decision_tracker.record_decision(
            session_id=sessions[3].session_id,
            agent_id=agents[3].agent_id,
            decision_type=DecisionType.ACTION,
            decision_data={"action": "security_audit", "target": str(impl_decision.decision_id)},
            confidence=0.95,
            trust_level=TrustLevel.L1_ASSISTED,
        )

        # Execute all decisions
        for decision in [design_decision, impl_decision, test_decision, security_decision]:
            decision_tracker.validate_decision(decision.decision_id)
            decision_tracker.execute_decision(decision.decision_id)

        # Verify collaboration metrics
        for agent in agents:
            metrics = await orchestrator.get_agent_metrics(agent.agent_id)
            assert metrics["total_sessions"] == 1

        # Cleanup
        for session in sessions:
            await orchestrator.end_session(session.session_id)

        for agent in agents:
            await orchestrator.terminate_agent(agent.agent_id)
