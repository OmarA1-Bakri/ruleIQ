"""Unit tests for the OrchestratorService."""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timedelta
from uuid import uuid4
import asyncio

from services.agents.orchestrator import OrchestratorService, AgentStatus
from models.agentic_models import Agent, AgentSession, TrustLevel


@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    session = MagicMock()
    session.add = MagicMock()
    session.commit = MagicMock()
    session.rollback = MagicMock()
    session.refresh = MagicMock()
    session.query = MagicMock()
    return session


@pytest.fixture
def orchestrator(mock_db_session):
    """Create an OrchestratorService instance with mocked dependencies."""
    return OrchestratorService(mock_db_session)


@pytest.fixture
def sample_agent():
    """Create a sample agent for testing."""
    return Agent(
        agent_id=uuid4(),
        name="TestAgent",
        persona_type="developer",
        capabilities={"code_generation": True, "testing": True},
        config={"max_tokens": 1000},
        is_active=True,
    )


@pytest.fixture
def sample_session(sample_agent):
    """Create a sample session for testing."""
    return AgentSession(
        session_id=uuid4(),
        agent_id=sample_agent.agent_id,
        user_id=str(uuid4()),
        trust_level=TrustLevel.L0_OBSERVED,
        context={"test": "context"},
        started_at=datetime.utcnow(),
    )


class TestOrchestratorService:
    """Test suite for OrchestratorService."""

    @pytest.mark.asyncio
    async def test_create_agent_success(self, orchestrator, mock_db_session):
        """Test successful agent creation."""
        # Setup
        name = "TestAgent"
        persona_type = "developer"
        capabilities = {"code_generation": True}
        config = {"max_tokens": 1000}

        # Execute
        agent = await orchestrator.create_agent(
            name=name, persona_type=persona_type, capabilities=capabilities, config=config
        )

        # Verify
        assert agent is not None
        assert agent.name == name
        assert agent.persona_type == persona_type
        assert agent.capabilities == capabilities
        assert agent.config == config
        assert agent.is_active is True
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_agent_max_concurrent_limit(self, orchestrator):
        """Test agent creation fails when max concurrent limit reached."""
        # Setup - fill up to max concurrent agents
        orchestrator.max_concurrent_agents = 2

        # Create two agents
        await orchestrator.create_agent("Agent1", "developer", {})
        await orchestrator.create_agent("Agent2", "qa", {})

        # Try to create third agent - should fail
        with pytest.raises(ValueError, match="Max concurrent agents reached"):
            await orchestrator.create_agent("Agent3", "architect", {})

    @pytest.mark.asyncio
    async def test_activate_agent_success(self, orchestrator, sample_agent, mock_db_session):
        """Test successful agent activation."""
        # Setup
        mock_db_session.query().filter().first.return_value = sample_agent

        # Execute
        result = await orchestrator.activate_agent(sample_agent.agent_id)

        # Verify
        assert result is True
        assert sample_agent.agent_id in orchestrator.agent_registry
        mock_db_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_activate_agent_not_found(self, orchestrator, mock_db_session):
        """Test agent activation fails when agent not found."""
        # Setup
        mock_db_session.query().filter().first.return_value = None
        agent_id = uuid4()

        # Execute
        result = await orchestrator.activate_agent(agent_id)

        # Verify
        assert result is False
        assert agent_id not in orchestrator.agent_registry

    @pytest.mark.asyncio
    async def test_suspend_agent_success(self, orchestrator, sample_agent):
        """Test successful agent suspension."""
        # Setup
        orchestrator.agent_registry[sample_agent.agent_id] = sample_agent

        # Execute
        result = await orchestrator.suspend_agent(sample_agent.agent_id, reason="Test suspension")

        # Verify
        assert result is True
        assert sample_agent.agent_id not in orchestrator.agent_registry
        assert sample_agent.is_active is False

    @pytest.mark.asyncio
    async def test_suspend_agent_with_active_sessions(
        self, orchestrator, sample_agent, sample_session
    ):
        """Test agent suspension ends active sessions."""
        # Setup
        orchestrator.agent_registry[sample_agent.agent_id] = sample_agent
        orchestrator.active_sessions[sample_session.session_id] = sample_session

        # Execute
        result = await orchestrator.suspend_agent(sample_agent.agent_id, reason="Test suspension")

        # Verify
        assert result is True
        assert sample_session.session_id not in orchestrator.active_sessions

    @pytest.mark.asyncio
    async def test_terminate_agent_success(self, orchestrator, sample_agent, mock_db_session):
        """Test successful agent termination."""
        # Setup
        orchestrator.agent_registry[sample_agent.agent_id] = sample_agent
        mock_db_session.query().filter().first.return_value = sample_agent

        # Execute
        result = await orchestrator.terminate_agent(sample_agent.agent_id)

        # Verify
        assert result is True
        assert sample_agent.agent_id not in orchestrator.agent_registry
        assert sample_agent.is_active is False
        mock_db_session.commit.assert_called()

    @pytest.mark.asyncio
    async def test_create_session_success(self, orchestrator, sample_agent):
        """Test successful session creation."""
        # Setup
        orchestrator.agent_registry[sample_agent.agent_id] = sample_agent
        user_id = str(uuid4())
        initial_context = {"test": "context"}

        # Execute
        session = await orchestrator.create_session(
            agent_id=sample_agent.agent_id, user_id=user_id, initial_context=initial_context
        )

        # Verify
        assert session is not None
        assert session.agent_id == sample_agent.agent_id
        assert session.user_id == user_id
        assert session.context == initial_context
        assert session.session_id in orchestrator.active_sessions

    @pytest.mark.asyncio
    async def test_create_session_agent_not_active(self, orchestrator):
        """Test session creation fails when agent not active."""
        # Setup
        agent_id = uuid4()

        # Execute & Verify
        with pytest.raises(ValueError, match=f"Agent {agent_id} not active"):
            await orchestrator.create_session(agent_id)

    @pytest.mark.asyncio
    async def test_end_session_success(self, orchestrator, sample_session):
        """Test successful session ending."""
        # Setup
        orchestrator.active_sessions[sample_session.session_id] = sample_session

        # Execute
        result = await orchestrator.end_session(sample_session.session_id)

        # Verify
        assert result is True
        assert sample_session.session_id not in orchestrator.active_sessions
        assert sample_session.ended_at is not None

    @pytest.mark.asyncio
    async def test_end_session_not_found(self, orchestrator):
        """Test ending non-existent session."""
        # Setup
        session_id = uuid4()

        # Execute
        result = await orchestrator.end_session(session_id)

        # Verify
        assert result is False

    @pytest.mark.asyncio
    async def test_cleanup_expired_sessions(self, orchestrator):
        """Test cleanup of expired sessions."""
        # Setup
        # Create an expired session
        expired_session = AgentSession(
            session_id=uuid4(), agent_id=uuid4(), started_at=datetime.utcnow() - timedelta(hours=2)
        )

        # Create an active session
        active_session = AgentSession(
            session_id=uuid4(), agent_id=uuid4(), started_at=datetime.utcnow()
        )

        orchestrator.active_sessions[expired_session.session_id] = expired_session
        orchestrator.active_sessions[active_session.session_id] = active_session

        # Execute
        await orchestrator.cleanup_expired_sessions()

        # Verify
        assert expired_session.session_id not in orchestrator.active_sessions
        assert active_session.session_id in orchestrator.active_sessions

    @pytest.mark.asyncio
    async def test_get_active_agents(self, orchestrator, sample_agent):
        """Test getting list of active agents."""
        # Setup
        orchestrator.agent_registry[sample_agent.agent_id] = sample_agent

        # Execute
        agents = await orchestrator.get_active_agents()

        # Verify
        assert len(agents) == 1
        assert agents[0] == sample_agent

    @pytest.mark.asyncio
    async def test_get_active_sessions(self, orchestrator, sample_session):
        """Test getting list of active sessions."""
        # Setup
        orchestrator.active_sessions[sample_session.session_id] = sample_session

        # Execute
        sessions = await orchestrator.get_active_sessions()

        # Verify
        assert len(sessions) == 1
        assert sessions[0] == sample_session

    @pytest.mark.asyncio
    async def test_get_agent_metrics(self, orchestrator, sample_agent, mock_db_session):
        """Test getting agent metrics."""
        # Setup
        sessions = [
            MagicMock(
                ended_at=datetime.utcnow(), started_at=datetime.utcnow() - timedelta(minutes=30)
            ),
            MagicMock(ended_at=None, started_at=datetime.utcnow()),
        ]
        mock_db_session.query().filter().all.return_value = sessions
        orchestrator.agent_registry[sample_agent.agent_id] = sample_agent

        # Execute
        metrics = await orchestrator.get_agent_metrics(sample_agent.agent_id)

        # Verify
        assert metrics["agent_id"] == str(sample_agent.agent_id)
        assert metrics["total_sessions"] == 2
        assert metrics["active_sessions"] == 1
        assert metrics["avg_session_duration_seconds"] == 1800  # 30 minutes
        assert metrics["is_active"] is True

    @pytest.mark.asyncio
    async def test_concurrent_agent_operations(self, orchestrator):
        """Test concurrent agent operations don't cause race conditions."""
        # Setup
        agent_ids = []

        async def create_and_activate_agent(index):
            agent = await orchestrator.create_agent(f"Agent{index}", "developer", {"test": True})
            agent_ids.append(agent.agent_id)
            await orchestrator.activate_agent(agent.agent_id)
            return agent

        # Execute - create 5 agents concurrently
        orchestrator.max_concurrent_agents = 10
        tasks = [create_and_activate_agent(i) for i in range(5)]
        agents = await asyncio.gather(*tasks)

        # Verify
        assert len(agents) == 5
        assert len(orchestrator.agent_registry) == 5
        assert all(aid in orchestrator.agent_registry for aid in agent_ids)

    @pytest.mark.asyncio
    async def test_error_handling_database_failure(self, orchestrator, mock_db_session):
        """Test error handling when database operations fail."""
        # Setup
        mock_db_session.commit.side_effect = Exception("Database error")

        # Execute & Verify
        with pytest.raises(Exception, match="Database error"):
            await orchestrator.create_agent("TestAgent", "developer", {})

        # Verify rollback was called
        mock_db_session.rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_session_timeout_enforcement(self, orchestrator):
        """Test that session timeout is properly enforced."""
        # Setup
        orchestrator.session_timeout = timedelta(seconds=1)

        session = AgentSession(
            session_id=uuid4(),
            agent_id=uuid4(),
            started_at=datetime.utcnow() - timedelta(seconds=2),
        )

        orchestrator.active_sessions[session.session_id] = session

        # Execute
        await orchestrator.cleanup_expired_sessions()

        # Verify
        assert session.session_id not in orchestrator.active_sessions


@pytest.mark.integration
class TestOrchestratorIntegration:
    """Integration tests for OrchestratorService."""

    @pytest.mark.asyncio
    async def test_full_agent_lifecycle(self, orchestrator):
        """Test complete agent lifecycle from creation to termination."""
        # Create agent
        agent = await orchestrator.create_agent(
            "LifecycleAgent", "developer", {"full_lifecycle": True}
        )
        assert agent is not None

        # Activate agent
        result = await orchestrator.activate_agent(agent.agent_id)
        assert result is True

        # Create session
        session = await orchestrator.create_session(agent.agent_id, user_id=str(uuid4()))
        assert session is not None

        # Suspend agent
        result = await orchestrator.suspend_agent(agent.agent_id, "Testing suspension")
        assert result is True

        # Verify session was ended
        assert session.session_id not in orchestrator.active_sessions

        # Terminate agent
        result = await orchestrator.terminate_agent(agent.agent_id)
        assert result is True

        # Verify agent is gone
        assert agent.agent_id not in orchestrator.agent_registry
