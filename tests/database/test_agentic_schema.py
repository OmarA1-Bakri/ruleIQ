"""Comprehensive tests for Agentic AI database schema and migrations."""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from alembic import command
from alembic.config import Config

from models.agentic_models import (
    Agent,
    AgentSession,
    AgentDecision,
    TrustMetric,
    AgentKnowledge,
    ConversationHistory,
    AgentAuditLog,
    SchemaVersion,
    Base,
)
from database.repositories.agentic_repository import (
    AgentRepository,
    AgentSessionRepository,
    AgentDecisionRepository,
    TrustMetricRepository,
    AgentKnowledgeRepository,
    ConversationHistoryRepository,
    AgentAuditLogRepository,
)


@pytest.fixture(scope="function")
def test_db():
    """Create a test database with schema."""
    engine = create_engine("postgresql://postgres:postgres@localhost:5432/test_agentic_db")

    # Drop all tables and recreate
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    yield session

    session.close()
    Base.metadata.drop_all(engine)


@pytest.fixture
def sample_agent(test_db):
    """Create a sample agent."""
    agent = Agent(
        name="TestAgent",
        persona_type="developer",
        capabilities={"languages": ["python", "javascript"], "skills": ["testing", "debugging"]},
        config={"max_tokens": 1000, "temperature": 0.7},
    )
    test_db.add(agent)
    test_db.commit()
    return agent


@pytest.fixture
def sample_user_id():
    """Generate a sample user ID."""
    return uuid4()


@pytest.fixture
def sample_session(test_db, sample_agent, sample_user_id):
    """Create a sample agent session."""
    session = AgentSession(
        agent_id=sample_agent.agent_id,
        user_id=sample_user_id,
        trust_level=2,
        context={"current_task": "testing"},
    )
    test_db.add(session)
    test_db.commit()
    return session


class TestSchemaConstraints:
    """Test database schema constraints and relationships."""

    def test_agent_persona_type_constraint(self, test_db):
        """Test that invalid persona types are rejected."""
        with pytest.raises(IntegrityError):
            agent = Agent(
                name="InvalidAgent",
                persona_type="invalid_type",  # Invalid type
                capabilities={},
            )
            test_db.add(agent)
            test_db.commit()

    def test_trust_level_range_constraint(self, test_db, sample_agent):
        """Test trust level must be between 0 and 4."""
        with pytest.raises(IntegrityError):
            session = AgentSession(
                agent_id=sample_agent.agent_id,
                trust_level=5,  # Invalid trust level
            )
            test_db.add(session)
            test_db.commit()

    def test_confidence_score_range_constraint(self, test_db, sample_session):
        """Test confidence score must be between 0 and 1."""
        with pytest.raises(IntegrityError):
            decision = AgentDecision(
                session_id=sample_session.session_id,
                decision_type="code_generation",
                input_context={},
                action_taken={},
                confidence_score=Decimal("1.5"),  # Invalid score
            )
            test_db.add(decision)
            test_db.commit()

    def test_metric_value_ranges(self, test_db, sample_session):
        """Test metric value ranges based on metric type."""
        # Valid accuracy metric (0-100)
        metric1 = TrustMetric(
            session_id=sample_session.session_id,
            metric_type="accuracy",
            metric_value=Decimal("85.5"),
        )
        test_db.add(metric1)
        test_db.commit()

        # Invalid accuracy metric (>100)
        with pytest.raises(IntegrityError):
            metric2 = TrustMetric(
                session_id=sample_session.session_id,
                metric_type="accuracy",
                metric_value=Decimal("150.0"),
            )
            test_db.add(metric2)
            test_db.commit()

    def test_cascade_delete_agent(self, test_db, sample_agent, sample_session):
        """Test CASCADE delete for agent relationships."""
        # Create related data
        decision = AgentDecision(
            session_id=sample_session.session_id,
            decision_type="code_generation",
            input_context={},
            action_taken={},
        )
        knowledge = AgentKnowledge(
            agent_id=sample_agent.agent_id, knowledge_type="pattern", domain="backend", content={}
        )
        test_db.add_all([decision, knowledge])
        test_db.commit()

        # Delete agent should cascade
        test_db.delete(sample_agent)
        test_db.commit()

        # Verify cascaded deletes
        assert (
            test_db.query(AgentSession).filter_by(session_id=sample_session.session_id).first()
            is None
        )
        assert (
            test_db.query(AgentDecision).filter_by(decision_id=decision.decision_id).first() is None
        )
        assert (
            test_db.query(AgentKnowledge).filter_by(knowledge_id=knowledge.knowledge_id).first()
            is None
        )

    def test_restrict_delete_agent_with_audit_logs(self, test_db, sample_agent):
        """Test RESTRICT delete for agent with audit logs."""
        audit_log = AgentAuditLog(
            agent_id=sample_agent.agent_id,
            action_type="code_generation",
            action_details={"files_created": 3},
        )
        test_db.add(audit_log)
        test_db.commit()

        # Should not be able to delete agent with audit logs
        with pytest.raises(IntegrityError):
            test_db.delete(sample_agent)
            test_db.commit()


class TestRepositoryOperations:
    """Test repository pattern operations."""

    def test_agent_repository_get_by_persona(self, test_db):
        """Test getting agents by persona type."""
        repo = AgentRepository(test_db)

        # Create agents with different personas
        dev_agent = Agent(name="DevAgent", persona_type="developer", capabilities={})
        qa_agent = Agent(name="QAAgent", persona_type="qa", capabilities={})

        test_db.add_all([dev_agent, qa_agent])
        test_db.commit()

        # Test retrieval
        dev_agents = repo.get_by_persona_type("developer")
        assert len(dev_agents) == 1
        assert dev_agents[0].name == "DevAgent"

    def test_session_repository_trust_level_update(self, test_db, sample_session):
        """Test updating session trust level."""
        repo = AgentSessionRepository(test_db)

        # Update trust level
        updated_session = repo.update_trust_level(sample_session.session_id, 3)
        assert updated_session.trust_level == 3
        assert updated_session.version == 2

        # Invalid trust level should not update
        invalid_update = repo.update_trust_level(sample_session.session_id, 5)
        assert invalid_update is None

    def test_decision_repository_feedback(self, test_db, sample_session):
        """Test updating decision feedback."""
        repo = AgentDecisionRepository(test_db)

        # Create decision
        decision = AgentDecision(
            session_id=sample_session.session_id,
            decision_type="code_generation",
            input_context={"prompt": "Create a test"},
            action_taken={"code": "def test(): pass"},
            confidence_score=Decimal("0.85"),
        )
        test_db.add(decision)
        test_db.commit()

        # Update feedback
        updated = repo.update_user_feedback(decision.decision_id, "approved")
        assert updated.user_feedback == "approved"

    def test_trust_metrics_aggregation(self, test_db, sample_session):
        """Test trust metrics aggregation."""
        repo = TrustMetricRepository(test_db)

        # Add multiple metrics
        metrics = [
            TrustMetric(
                session_id=sample_session.session_id,
                metric_type="accuracy",
                metric_value=Decimal("80"),
            ),
            TrustMetric(
                session_id=sample_session.session_id,
                metric_type="accuracy",
                metric_value=Decimal("90"),
            ),
            TrustMetric(
                session_id=sample_session.session_id,
                metric_type="accuracy",
                metric_value=Decimal("85"),
            ),
        ]
        test_db.add_all(metrics)
        test_db.commit()

        # Test average calculation
        avg = repo.get_average_metric(sample_session.session_id, "accuracy")
        assert avg == 85.0

    def test_knowledge_usage_tracking(self, test_db, sample_agent):
        """Test knowledge usage and success rate tracking."""
        repo = AgentKnowledgeRepository(test_db)

        # Create knowledge item
        knowledge = AgentKnowledge(
            agent_id=sample_agent.agent_id,
            knowledge_type="pattern",
            domain="backend",
            content={"pattern": "repository_pattern"},
            usage_count=0,
        )
        test_db.add(knowledge)
        test_db.commit()

        # Track successful usage
        updated = repo.increment_usage(knowledge.knowledge_id, was_successful=True)
        assert updated.usage_count == 1
        assert float(updated.success_rate) == 1.0

        # Track failed usage
        updated = repo.increment_usage(knowledge.knowledge_id, was_successful=False)
        assert updated.usage_count == 2
        assert float(updated.success_rate) == 0.5

    def test_conversation_thread_retrieval(self, test_db, sample_session):
        """Test conversation thread retrieval."""
        repo = ConversationHistoryRepository(test_db)

        # Create conversation thread
        msg1 = ConversationHistory(
            session_id=sample_session.session_id, role="user", content="Hello", message_type="text"
        )
        test_db.add(msg1)
        test_db.commit()

        msg2 = ConversationHistory(
            session_id=sample_session.session_id,
            role="agent",
            content="Hi there!",
            message_type="text",
            parent_message_id=msg1.message_id,
        )
        test_db.add(msg2)
        test_db.commit()

        # Test thread retrieval
        thread = repo.get_conversation_thread(msg1.message_id)
        assert len(thread) == 2
        assert thread[0].content == "Hello"
        assert thread[1].content == "Hi there!"

    def test_audit_log_risk_filtering(self, test_db, sample_agent):
        """Test audit log filtering by risk level."""
        repo = AgentAuditLogRepository(test_db)

        # Create audit logs with different risk levels
        logs = [
            AgentAuditLog(
                agent_id=sample_agent.agent_id,
                action_type="read",
                action_details={},
                risk_level="low",
            ),
            AgentAuditLog(
                agent_id=sample_agent.agent_id,
                action_type="write",
                action_details={},
                risk_level="medium",
            ),
            AgentAuditLog(
                agent_id=sample_agent.agent_id,
                action_type="delete",
                action_details={},
                risk_level="high",
            ),
            AgentAuditLog(
                agent_id=sample_agent.agent_id,
                action_type="admin",
                action_details={},
                risk_level="critical",
            ),
        ]
        test_db.add_all(logs)
        test_db.commit()

        # Test high risk filtering
        high_risk = repo.get_high_risk_actions()
        assert len(high_risk) == 2
        assert all(log.risk_level in ["high", "critical"] for log in high_risk)


class TestPerformance:
    """Test performance requirements."""

    def test_query_performance_session_decisions(self, test_db, sample_session):
        """Test query performance for session decisions."""
        # Create 1000 decisions
        decisions = []
        for i in range(1000):
            decision = AgentDecision(
                session_id=sample_session.session_id,
                decision_type="code_generation",
                input_context={"index": i},
                action_taken={"result": f"action_{i}"},
                confidence_score=Decimal("0.85"),
            )
            decisions.append(decision)

        test_db.add_all(decisions)
        test_db.commit()

        # Test query performance
        import time

        start = time.time()

        repo = AgentDecisionRepository(test_db)
        results = repo.get_session_decisions(sample_session.session_id)

        elapsed = (time.time() - start) * 1000  # Convert to milliseconds

        assert len(results) == 1000
        assert elapsed < 100  # Should be under 100ms

    def test_index_usage(self, test_db):
        """Test that indexes are being used for queries."""
        # Check index existence
        result = test_db.execute(
            text("""
            SELECT indexname FROM pg_indexes 
            WHERE tablename = 'agent_sessions' 
            AND indexname = 'idx_agent_sessions_agent_id'
        """)
        )

        indexes = result.fetchall()
        assert len(indexes) > 0  # Index should exist


class TestMigration:
    """Test migration up and down."""

    def test_migration_up(self):
        """Test migration upgrade."""
        config = Config("alembic.ini")

        # Run migration
        command.upgrade(config, "head")

        # Verify tables exist
        engine = create_engine(config.get_main_option("sqlalchemy.url"))
        with engine.connect() as conn:
            result = conn.execute(
                text("""
                SELECT table_name FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name IN ('agents', 'agent_sessions', 'agent_decisions')
            """)
            )
            tables = [row[0] for row in result]

            assert "agents" in tables
            assert "agent_sessions" in tables
            assert "agent_decisions" in tables

    def test_migration_rollback(self):
        """Test migration downgrade."""
        config = Config("alembic.ini")

        # Upgrade then downgrade
        command.upgrade(config, "head")
        command.downgrade(config, "-1")

        # Verify tables are removed
        engine = create_engine(config.get_main_option("sqlalchemy.url"))
        with engine.connect() as conn:
            result = conn.execute(
                text("""
                SELECT table_name FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'agents'
            """)
            )
            tables = result.fetchall()

            assert len(tables) == 0  # Table should not exist


class TestDataRetention:
    """Test data retention policies."""

    def test_conversation_history_partitioning_ready(self, test_db):
        """Test that conversation history is ready for partitioning."""
        # This is a placeholder for partition testing
        # In production, we would test actual PostgreSQL partitioning

        # Verify the table has the necessary columns for partitioning
        result = test_db.execute(
            text("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'conversation_history' 
            AND column_name = 'created_at'
        """)
        )

        columns = result.fetchall()
        assert len(columns) > 0  # created_at column exists for partitioning


class TestConcurrency:
    """Test concurrent access patterns."""

    def test_optimistic_locking(self, test_db, sample_agent):
        """Test optimistic locking with version column."""
        repo = AgentRepository(test_db)

        # Get initial version
        agent = repo.get(sample_agent.agent_id)
        initial_version = agent.version

        # Update capabilities
        updated = repo.update_capabilities(sample_agent.agent_id, {"languages": ["python", "rust"]})

        # Version should increment
        assert updated.version == initial_version + 1

    def test_concurrent_session_creation(self, test_db, sample_agent):
        """Test concurrent session creation."""
        from concurrent.futures import ThreadPoolExecutor

        def create_session(agent_id, user_id):
            session = AgentSession(agent_id=agent_id, user_id=user_id, trust_level=0)
            test_db.add(session)
            test_db.commit()
            return session.session_id

        # Create multiple sessions concurrently
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = []
            for _i in range(10):
                future = executor.submit(create_session, sample_agent.agent_id, uuid4())
                futures.append(future)

            # All should succeed
            session_ids = [f.result() for f in futures]
            assert len(set(session_ids)) == 10  # All unique
