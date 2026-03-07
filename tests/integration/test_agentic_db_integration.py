"""Integration tests for Agentic AI database schema."""

import pytest
from datetime import datetime
from decimal import Decimal
from uuid import uuid4
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Import models after database setup
from models.agentic_models import (
    Agent,
    AgentSession,
    AgentDecision,
    TrustMetric,
    AgentKnowledge,
    ConversationHistory,
    AgentAuditLog,
    Base,
)


@pytest.fixture(scope="function")
def test_session():
    """Create a test database session."""
    # Use test database from environment
    DATABASE_URL = os.getenv(
        "DATABASE_URL", "postgresql://test_user:test_password@localhost:5433/ruleiq_test"
    )

    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    yield session

    # Cleanup
    session.rollback()
    session.close()


def test_create_agent(test_session):
    """Test creating an agent."""
    agent = Agent(
        name="TestAgent",
        persona_type="developer",
        capabilities={"languages": ["python"], "skills": ["testing"]},
        config={"max_tokens": 1000},
    )

    test_session.add(agent)
    test_session.commit()

    # Verify
    assert agent.agent_id is not None
    assert agent.name == "TestAgent"
    assert agent.persona_type == "developer"
    assert agent.is_active is True
    assert agent.version == 1


def test_create_agent_session(test_session):
    """Test creating an agent session."""
    # Create agent first
    agent = Agent(name="SessionAgent", persona_type="qa", capabilities={})
    test_session.add(agent)
    test_session.commit()

    # Create session
    session = AgentSession(
        agent_id=agent.agent_id,
        user_id=uuid4(),
        trust_level=2,
        context={"task": "testing"},
        session_state="active",
    )

    test_session.add(session)
    test_session.commit()

    # Verify
    assert session.session_id is not None
    assert session.trust_level == 2
    assert session.session_state == "active"
    assert session.version == 1


def test_create_decision_with_feedback(test_session):
    """Test creating a decision and updating feedback."""
    # Setup
    agent = Agent(name="DecisionAgent", persona_type="architect", capabilities={})
    test_session.add(agent)
    test_session.commit()

    agent_session = AgentSession(agent_id=agent.agent_id, user_id=uuid4())
    test_session.add(agent_session)
    test_session.commit()

    # Create decision
    decision = AgentDecision(
        session_id=agent_session.session_id,
        decision_type="code_generation",
        input_context={"prompt": "Create test"},
        action_taken={"code": "def test(): pass"},
        confidence_score=Decimal("0.85"),
        user_feedback="pending",
    )

    test_session.add(decision)
    test_session.commit()

    # Verify
    assert decision.decision_id is not None
    assert float(decision.confidence_score) == 0.85
    assert decision.user_feedback == "pending"

    # Update feedback
    decision.user_feedback = "approved"
    test_session.commit()

    assert decision.user_feedback == "approved"


def test_trust_metrics_validation(test_session):
    """Test trust metrics with validation."""
    # Setup
    agent = Agent(name="MetricsAgent", persona_type="security", capabilities={})
    test_session.add(agent)
    test_session.commit()

    agent_session = AgentSession(agent_id=agent.agent_id)
    test_session.add(agent_session)
    test_session.commit()

    # Create valid metrics
    metrics = [
        TrustMetric(
            session_id=agent_session.session_id,
            metric_type="accuracy",
            metric_value=Decimal("85.5"),
        ),
        TrustMetric(
            session_id=agent_session.session_id,
            metric_type="complexity",
            metric_value=Decimal("7.5"),
        ),
        TrustMetric(
            session_id=agent_session.session_id,
            metric_type="efficiency",
            metric_value=Decimal("92.0"),
        ),
    ]

    for metric in metrics:
        test_session.add(metric)

    test_session.commit()

    # Verify
    stored_metrics = (
        test_session.query(TrustMetric).filter_by(session_id=agent_session.session_id).all()
    )

    assert len(stored_metrics) == 3
    assert all(m.metric_id is not None for m in stored_metrics)


def test_conversation_history_thread(test_session):
    """Test conversation history with threading."""
    # Setup
    agent = Agent(name="ChatAgent", persona_type="documentation", capabilities={})
    test_session.add(agent)
    test_session.commit()

    agent_session = AgentSession(agent_id=agent.agent_id)
    test_session.add(agent_session)
    test_session.commit()

    # Create conversation thread
    msg1 = ConversationHistory(
        session_id=agent_session.session_id,
        role="user",
        content="How do I implement this?",
        message_type="text",
        tokens_used=10,
    )
    test_session.add(msg1)
    test_session.commit()

    msg2 = ConversationHistory(
        session_id=agent_session.session_id,
        role="agent",
        content="Here's how you can implement it...",
        message_type="text",
        parent_message_id=msg1.message_id,
        tokens_used=25,
        model_used="gpt-4",
    )
    test_session.add(msg2)
    test_session.commit()

    msg3 = ConversationHistory(
        session_id=agent_session.session_id,
        role="user",
        content="Can you show me an example?",
        message_type="text",
        parent_message_id=msg2.message_id,
        tokens_used=8,
    )
    test_session.add(msg3)
    test_session.commit()

    # Verify thread
    messages = (
        test_session.query(ConversationHistory)
        .filter_by(session_id=agent_session.session_id)
        .order_by(ConversationHistory.created_at)
        .all()
    )

    assert len(messages) == 3
    assert messages[0].content == "How do I implement this?"
    assert messages[1].parent_message_id == msg1.message_id
    assert messages[2].parent_message_id == msg2.message_id


def test_agent_knowledge_usage(test_session):
    """Test agent knowledge storage and usage tracking."""
    # Setup
    agent = Agent(name="KnowledgeAgent", persona_type="developer", capabilities={})
    test_session.add(agent)
    test_session.commit()

    # Create knowledge item
    knowledge = AgentKnowledge(
        agent_id=agent.agent_id,
        knowledge_type="pattern",
        domain="backend",
        content={
            "pattern": "repository_pattern",
            "description": "Use repository pattern for data access",
        },
        usage_count=5,
        success_rate=Decimal("0.8"),
    )
    test_session.add(knowledge)
    test_session.commit()

    # Verify
    assert knowledge.knowledge_id is not None
    assert knowledge.usage_count == 5
    assert float(knowledge.success_rate) == 0.8

    # Update usage
    knowledge.usage_count += 1
    knowledge.last_used_at = datetime.utcnow()
    test_session.commit()

    assert knowledge.usage_count == 6


def test_audit_log_creation(test_session):
    """Test audit log creation with risk levels."""
    # Setup
    agent = Agent(name="AuditAgent", persona_type="security", capabilities={})
    test_session.add(agent)
    test_session.commit()

    agent_session = AgentSession(agent_id=agent.agent_id)
    test_session.add(agent_session)
    test_session.commit()

    # Create audit logs
    audit_logs = [
        AgentAuditLog(
            agent_id=agent.agent_id,
            session_id=agent_session.session_id,
            action_type="file_read",
            action_details={"file": "config.py"},
            risk_level="low",
        ),
        AgentAuditLog(
            agent_id=agent.agent_id,
            session_id=agent_session.session_id,
            action_type="database_write",
            action_details={"table": "users", "operation": "update"},
            risk_level="medium",
        ),
        AgentAuditLog(
            agent_id=agent.agent_id,
            action_type="admin_action",
            action_details={"action": "delete_all_data"},
            risk_level="critical",
        ),
    ]

    for log in audit_logs:
        test_session.add(log)

    test_session.commit()

    # Verify
    stored_logs = test_session.query(AgentAuditLog).filter_by(agent_id=agent.agent_id).all()

    assert len(stored_logs) == 3
    assert any(log.risk_level == "critical" for log in stored_logs)
    assert all(log.audit_id is not None for log in stored_logs)


def test_cascade_relationships(test_session):
    """Test CASCADE delete relationships."""
    # Create agent with related data
    agent = Agent(name="CascadeAgent", persona_type="developer", capabilities={})
    test_session.add(agent)
    test_session.commit()

    agent_session = AgentSession(agent_id=agent.agent_id)
    test_session.add(agent_session)
    test_session.commit()

    decision = AgentDecision(
        session_id=agent_session.session_id,
        decision_type="review",
        input_context={},
        action_taken={},
    )
    test_session.add(decision)

    knowledge = AgentKnowledge(
        agent_id=agent.agent_id, knowledge_type="solution", domain="frontend", content={}
    )
    test_session.add(knowledge)
    test_session.commit()

    # Store IDs for verification
    session_id = agent_session.session_id
    decision_id = decision.decision_id
    knowledge_id = knowledge.knowledge_id

    # Delete agent (should cascade)
    test_session.delete(agent)
    test_session.commit()

    # Verify cascaded deletes
    assert test_session.query(AgentSession).filter_by(session_id=session_id).first() is None
    assert test_session.query(AgentDecision).filter_by(decision_id=decision_id).first() is None
    assert test_session.query(AgentKnowledge).filter_by(knowledge_id=knowledge_id).first() is None


def test_version_tracking(test_session):
    """Test optimistic locking with version field."""
    # Create agent
    agent = Agent(name="VersionAgent", persona_type="qa", capabilities={})
    test_session.add(agent)
    test_session.commit()

    initial_version = agent.version
    assert initial_version == 1

    # Update agent
    agent.capabilities = {"updated": True}
    agent.version += 1
    test_session.commit()

    assert agent.version == 2

    # Create session
    agent_session = AgentSession(agent_id=agent.agent_id)
    test_session.add(agent_session)
    test_session.commit()

    assert agent_session.version == 1

    # Update session
    agent_session.trust_level = 3
    agent_session.version += 1
    test_session.commit()

    assert agent_session.version == 2
