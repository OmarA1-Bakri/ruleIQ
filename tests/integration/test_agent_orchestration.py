"""Integration tests for agent orchestration system."""

import pytest
import asyncio
from datetime import datetime, timedelta
from uuid import uuid4
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from models.agentic_models import Base, Agent, AgentSession, AgentDecision, TrustMetric
from services.agents.orchestrator import OrchestratorService
from services.agents.agent_manager import AgentManager
from services.agents.session_manager import SessionManager
from services.agents.context_manager import ContextManager
from services.agents.decision_tracker import DecisionTracker
from services.agents.trust_manager import TrustManager
from services.agents.communication import CommunicationProtocol
from services.agents.coordinator import AgentCoordinator
from services.agents.monitor import AgentMonitor


@pytest.fixture(scope="function")
def test_db():
    """Create a test database for integration tests."""
    # Use in-memory SQLite for tests
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()

    yield session

    session.close()
    engine.dispose()


@pytest.fixture
def orchestrator(test_db):
    """Create an OrchestratorService with real database."""
    return OrchestratorService(test_db)


@pytest.fixture
def agent_manager(test_db):
    """Create an AgentManager with real database."""
    return AgentManager(test_db)


@pytest.fixture
def session_manager(test_db):
    """Create a SessionManager with real database."""
    return SessionManager(test_db)


@pytest.fixture
def trust_manager(test_db):
    """Create a TrustManager with real database."""
    return TrustManager(test_db)


@pytest.fixture
def decision_tracker(test_db):
    """Create a DecisionTracker with real database."""
    return DecisionTracker(test_db)


class TestAgentOrchestrationIntegration:
    """Integration tests for the complete agent orchestration system."""

    @pytest.mark.asyncio
    async def test_complete_agent_workflow(self, orchestrator, test_db):
        """Test a complete agent workflow from creation to decision making."""
        # Step 1: Create an agent
        agent = await orchestrator.create_agent(
            name="IntegrationTestAgent",
            persona_type="developer",
            capabilities={"code_generation": True, "testing": True, "review": True},
            config={"max_tokens": 2000, "temperature": 0.7},
        )

        assert agent is not None
        assert agent.agent_id is not None

        # Verify agent is in database
        db_agent = test_db.query(Agent).filter(Agent.agent_id == agent.agent_id).first()
        assert db_agent is not None
        assert db_agent.name == "IntegrationTestAgent"

        # Step 2: Activate the agent
        activation_result = await orchestrator.activate_agent(agent.agent_id)
        assert activation_result is True
        assert agent.agent_id in orchestrator.agent_registry

        # Step 3: Create a session
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
        assert session.trust_level == 0  # L0_OBSERVED by default

        # Verify session is in database
        db_session = (
            test_db.query(AgentSession)
            .filter(AgentSession.session_id == session.session_id)
            .first()
        )
        assert db_session is not None
        assert db_session.context["task"] == "Generate unit tests"

        # Step 4: Simulate decision making
        decision = AgentDecision(
            decision_id=uuid4(),
            session_id=session.session_id,
            decision_type="code_generation",
            input_context={
                "request": "Generate test for add function",
                "function_signature": "def add(a, b): return a + b",
            },
            decision_rationale="Simple unit test for basic arithmetic function",
            action_taken={"generated_code": "def test_add():\n    assert add(2, 3) == 5"},
            confidence_score=0.95,
            execution_time_ms=150,
        )

        test_db.add(decision)
        test_db.commit()

        # Step 5: Record trust metrics
        trust_metric = TrustMetric(
            metric_id=uuid4(),
            session_id=session.session_id,
            metric_type="accuracy",
            metric_value=95.0,
            measurement_context={"decision_id": str(decision.decision_id), "test_passed": True},
        )

        test_db.add(trust_metric)
        test_db.commit()

        # Step 6: End the session
        end_result = await orchestrator.end_session(session.session_id)
        assert end_result is True
        assert session.session_id not in orchestrator.active_sessions

        # Step 7: Terminate the agent
        termination_result = await orchestrator.terminate_agent(agent.agent_id)
        assert termination_result is True
        assert agent.agent_id not in orchestrator.agent_registry

    @pytest.mark.asyncio
    async def test_multi_agent_coordination(self, orchestrator, test_db):
        """Test coordination between multiple agents."""
        # Create multiple agents with different personas
        developer_agent = await orchestrator.create_agent(
            name="DevAgent", persona_type="developer", capabilities={"code_generation": True}
        )

        qa_agent = await orchestrator.create_agent(
            name="QAAgent", persona_type="qa", capabilities={"testing": True, "review": True}
        )

        architect_agent = await orchestrator.create_agent(
            name="ArchitectAgent",
            persona_type="architect",
            capabilities={"design": True, "review": True},
        )

        # Activate all agents
        await orchestrator.activate_agent(developer_agent.agent_id)
        await orchestrator.activate_agent(qa_agent.agent_id)
        await orchestrator.activate_agent(architect_agent.agent_id)

        # Create sessions for each agent
        user_id = str(uuid4())

        dev_session = await orchestrator.create_session(
            developer_agent.agent_id, user_id=user_id, initial_context={"task": "implement_feature"}
        )

        qa_session = await orchestrator.create_session(
            qa_agent.agent_id, user_id=user_id, initial_context={"task": "test_feature"}
        )

        arch_session = await orchestrator.create_session(
            architect_agent.agent_id, user_id=user_id, initial_context={"task": "review_design"}
        )

        # Verify all sessions are active
        active_sessions = await orchestrator.get_active_sessions()
        assert len(active_sessions) == 3

        # Clean up all sessions
        await orchestrator.end_session(dev_session.session_id)
        await orchestrator.end_session(qa_session.session_id)
        await orchestrator.end_session(arch_session.session_id)

        # Verify all sessions are ended
        active_sessions = await orchestrator.get_active_sessions()
        assert len(active_sessions) == 0

    @pytest.mark.asyncio
    async def test_trust_level_progression(self, trust_manager, test_db):
        """Test trust level progression based on metrics."""
        agent_id = uuid4()
        user_id = str(uuid4())
        session_id = uuid4()

        # Create agent and session records
        agent = Agent(
            agent_id=agent_id,
            name="TrustTestAgent",
            persona_type="developer",
            capabilities={},
            is_active=True,
        )
        test_db.add(agent)

        session = AgentSession(
            session_id=session_id,
            agent_id=agent_id,
            user_id=user_id,
            trust_level=0,  # Start at L0
            context={},
            started_at=datetime.utcnow(),
        )
        test_db.add(session)
        test_db.commit()

        # Add positive trust metrics
        for i in range(10):
            metric = TrustMetric(
                metric_id=uuid4(),
                session_id=session_id,
                metric_type="accuracy",
                metric_value=95.0 + i,  # High accuracy
                measurement_context={"iteration": i},
            )
            test_db.add(metric)

        test_db.commit()

        # Calculate new trust level
        new_trust_level = await trust_manager.calculate_trust_level(
            agent_id=agent_id, user_id=user_id, session_id=session_id
        )

        # Should progress from L0 due to high accuracy
        assert new_trust_level > 0

    @pytest.mark.asyncio
    async def test_session_expiration_cleanup(self, orchestrator, test_db):
        """Test automatic cleanup of expired sessions."""
        # Create an agent
        agent = await orchestrator.create_agent(
            name="ExpirationTestAgent", persona_type="developer", capabilities={}
        )

        await orchestrator.activate_agent(agent.agent_id)

        # Create multiple sessions with different ages
        sessions = []

        # Create an old session (should be cleaned up)
        old_session = await orchestrator.create_session(
            agent_id=agent.agent_id, user_id=str(uuid4())
        )
        # Manually set the started_at to make it old
        old_session.started_at = datetime.utcnow() - timedelta(hours=2)
        test_db.commit()
        sessions.append(old_session)

        # Create a recent session (should not be cleaned up)
        recent_session = await orchestrator.create_session(
            agent_id=agent.agent_id, user_id=str(uuid4())
        )
        sessions.append(recent_session)

        # Run cleanup
        await orchestrator.cleanup_expired_sessions()

        # Verify old session is cleaned up
        assert old_session.session_id not in orchestrator.active_sessions
        assert recent_session.session_id in orchestrator.active_sessions

    @pytest.mark.asyncio
    async def test_agent_state_persistence(self, agent_manager, test_db):
        """Test agent state saving and loading."""
        # Create an agent
        agent = agent_manager.create_agent(
            name="StatePersistenceAgent",
            persona_type="developer",
            capabilities={"persistent": True},
            config={"version": "1.0"},
        )

        # Save agent state
        state_data = {
            "memory": {"last_task": "test_implementation"},
            "preferences": {"language": "Python"},
            "statistics": {"tasks_completed": 5},
        }

        save_result = agent_manager.save_agent_state(agent_id=agent.agent_id, state_data=state_data)
        assert save_result is True

        # Load agent state
        loaded_state = agent_manager.load_agent_state(agent.agent_id)
        assert loaded_state is not None
        assert loaded_state["memory"]["last_task"] == "test_implementation"
        assert loaded_state["preferences"]["language"] == "Python"
        assert loaded_state["statistics"]["tasks_completed"] == 5

    @pytest.mark.asyncio
    async def test_concurrent_session_creation(self, orchestrator, test_db):
        """Test creating multiple sessions concurrently."""
        # Create and activate an agent
        agent = await orchestrator.create_agent(
            name="ConcurrentTestAgent", persona_type="developer", capabilities={}
        )
        await orchestrator.activate_agent(agent.agent_id)

        # Create multiple sessions concurrently
        async def create_session(index):
            return await orchestrator.create_session(
                agent_id=agent.agent_id,
                user_id=str(uuid4()),
                initial_context={"session_index": index},
            )

        # Create 10 sessions concurrently
        tasks = [create_session(i) for i in range(10)]
        sessions = await asyncio.gather(*tasks)

        # Verify all sessions were created
        assert len(sessions) == 10
        assert len(orchestrator.active_sessions) == 10

        # Verify each session has unique ID
        session_ids = [s.session_id for s in sessions]
        assert len(set(session_ids)) == 10

    @pytest.mark.asyncio
    async def test_error_recovery(self, orchestrator, test_db):
        """Test error handling and recovery mechanisms."""
        # Create an agent
        agent = await orchestrator.create_agent(
            name="ErrorTestAgent", persona_type="developer", capabilities={}
        )

        # Simulate database error during activation
        with patch.object(test_db, "commit", side_effect=Exception("DB Error")):
            result = await orchestrator.activate_agent(agent.agent_id)
            assert result is False

        # Verify agent is not in registry due to error
        assert agent.agent_id not in orchestrator.agent_registry

        # Try activation again (recovery)
        result = await orchestrator.activate_agent(agent.agent_id)
        assert result is True
        assert agent.agent_id in orchestrator.agent_registry

    @pytest.mark.asyncio
    async def test_agent_metrics_calculation(self, orchestrator, test_db):
        """Test calculation of agent performance metrics."""
        # Create and activate an agent
        agent = await orchestrator.create_agent(
            name="MetricsTestAgent", persona_type="developer", capabilities={}
        )
        await orchestrator.activate_agent(agent.agent_id)

        # Create multiple sessions
        sessions = []
        for i in range(5):
            session = await orchestrator.create_session(
                agent_id=agent.agent_id, user_id=str(uuid4())
            )
            sessions.append(session)

            # End some sessions
            if i < 3:
                await orchestrator.end_session(session.session_id)

        # Get agent metrics
        metrics = await orchestrator.get_agent_metrics(agent.agent_id)

        # Verify metrics
        assert metrics["agent_id"] == str(agent.agent_id)
        assert metrics["total_sessions"] == 5
        assert metrics["active_sessions"] == 2
        assert metrics["is_active"] is True
