"""
Agent Manager Service - Factory and state management for agents.

Handles agent creation, configuration, and state persistence.
"""

from typing import Dict, List, Optional, Any, Type
from uuid import UUID, uuid4
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
import logging
import json
from pathlib import Path

from models.agentic_models import Agent, AgentState

logger = logging.getLogger(__name__)


class AgentFactory:
    """Factory for creating different types of agents."""

    # Agent type registry
    _agent_types: Dict[str, Type] = {}

    @classmethod
    def register_agent_type(cls, persona_type: str, agent_class: Type) -> None:
        """Register a new agent type."""
        cls._agent_types[persona_type] = agent_class
        logger.info(f"Registered agent type: {persona_type}")

    @classmethod
    def create_agent(cls, persona_type: str, **kwargs) -> Any:
        """Create an agent of the specified type."""
        if persona_type not in cls._agent_types:
            raise ValueError(f"Unknown agent type: {persona_type}")

        agent_class = cls._agent_types[persona_type]
        return agent_class(**kwargs)


class AgentManager:
    """Manages agent lifecycle and state persistence."""

    def __init__(self, db_session: Session, state_dir: str = ".agent_states") -> None:
        """Initialize agent manager."""
        self.db = db_session
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(exist_ok=True)
        self.loaded_agents: Dict[UUID, Any] = {}

    def create_agent(
        self,
        name: str,
        persona_type: str,
        capabilities: Dict[str, Any],
        config: Optional[Dict[str, Any]] = None,
    ) -> Agent:
        """Create a new agent with factory."""
        try:
            # Create database record
            agent = Agent(
                agent_id=uuid4(),
                name=name,
                persona_type=persona_type,
                capabilities=capabilities,
                config=config or {},
                is_active=True,
            )

            self.db.add(agent)

            # Create agent instance if type is registered
            try:
                agent_instance = AgentFactory.create_agent(
                    persona_type, agent_id=agent.agent_id, name=name, config=config
                )
                self.loaded_agents[agent.agent_id] = agent_instance
            except ValueError:
                logger.warning(f"No implementation for agent type: {persona_type}")

            self.db.commit()
            self.db.refresh(agent)

            logger.info(f"Created agent {agent.agent_id}: {name} ({persona_type})")
            return agent

        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Failed to create agent: {e}")
            raise

    def load_agent_config(self, agent_id: UUID) -> Dict[str, Any]:
        """Load agent configuration from database."""
        try:
            agent = self.db.query(Agent).filter(Agent.agent_id == agent_id).first()

            if not agent:
                raise ValueError(f"Agent {agent_id} not found")

            return {
                "agent_id": str(agent.agent_id),
                "name": agent.name,
                "persona_type": agent.persona_type,
                "capabilities": agent.capabilities,
                "config": agent.config,
                "is_active": agent.is_active,
            }

        except SQLAlchemyError as e:
            logger.error(f"Failed to load agent config: {e}")
            raise

    def save_agent_state(self, agent_id: UUID, state_data: Dict[str, Any]) -> bool:
        """Persist agent state to database and disk."""
        try:
            # Check if state exists
            agent_state = self.db.query(AgentState).filter(AgentState.agent_id == agent_id).first()

            if agent_state:
                # Update existing state
                agent_state.state_data = state_data
                agent_state.updated_at = datetime.utcnow()
                agent_state.version += 1
            else:
                # Create new state
                agent_state = AgentState(
                    state_id=uuid4(), agent_id=agent_id, state_data=state_data, version=1
                )
                self.db.add(agent_state)

            # Also save to disk for backup
            state_file = self.state_dir / f"{agent_id}.json"
            with open(state_file, "w") as f:
                json.dump(state_data, f, default=str)

            self.db.commit()
            logger.info(f"Saved state for agent {agent_id}")
            return True

        except (SQLAlchemyError, IOError) as e:
            self.db.rollback()
            logger.error(f"Failed to save agent state: {e}")
            return False

    def load_agent_state(self, agent_id: UUID) -> Optional[Dict[str, Any]]:
        """Load agent state from database or disk."""
        try:
            # Try database first
            agent_state = (
                self.db.query(AgentState)
                .filter(AgentState.agent_id == agent_id)
                .order_by(AgentState.version.desc())
                .first()
            )

            if agent_state:
                logger.info(f"Loaded state for agent {agent_id} from database")
                return agent_state.state_data

            # Fallback to disk
            state_file = self.state_dir / f"{agent_id}.json"
            if state_file.exists():
                with open(state_file, "r") as f:
                    state_data = json.load(f)
                    logger.info(f"Loaded state for agent {agent_id} from disk")
                    return state_data

            logger.warning(f"No state found for agent {agent_id}")
            return None

        except (SQLAlchemyError, IOError) as e:
            logger.error(f"Failed to load agent state: {e}")
            return None

    def update_agent_config(self, agent_id: UUID, config_updates: Dict[str, Any]) -> bool:
        """Update agent configuration."""
        try:
            agent = self.db.query(Agent).filter(Agent.agent_id == agent_id).first()

            if not agent:
                logger.warning(f"Agent {agent_id} not found")
                return False

            # Merge config updates
            current_config = agent.config or {}
            current_config.update(config_updates)
            agent.config = current_config
            agent.updated_at = datetime.utcnow()

            self.db.commit()
            logger.info(f"Updated config for agent {agent_id}")
            return True

        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Failed to update agent config: {e}")
            return False

    def list_agents(
        self, persona_type: Optional[str] = None, is_active: Optional[bool] = None
    ) -> List[Agent]:
        """List agents with optional filters."""
        try:
            query = self.db.query(Agent)

            if persona_type:
                query = query.filter(Agent.persona_type == persona_type)

            if is_active is not None:
                query = query.filter(Agent.is_active == is_active)

            return query.all()

        except SQLAlchemyError as e:
            logger.error(f"Failed to list agents: {e}")
            return []

    def get_agent_by_id(self, agent_id: UUID) -> Optional[Agent]:
        """Get agent by ID."""
        try:
            return self.db.query(Agent).filter(Agent.agent_id == agent_id).first()

        except SQLAlchemyError as e:
            logger.error(f"Failed to get agent: {e}")
            return None

    def cleanup_old_states(self, days_to_keep: int = 30):
        """Clean up old agent state records."""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)

            old_states = self.db.query(AgentState).filter(AgentState.updated_at < cutoff_date).all()

            for state in old_states:
                self.db.delete(state)

                # Also remove disk backup
                state_file = self.state_dir / f"{state.agent_id}.state"
                if state_file.exists():
                    state_file.unlink()

            self.db.commit()
            logger.info(f"Cleaned up {len(old_states)} old state records")

        except (SQLAlchemyError, IOError) as e:
            self.db.rollback()
            logger.error(f"Failed to cleanup old states: {e}")

    def get_agent_statistics(self) -> Dict[str, Any]:
        """Get overall agent statistics."""
        try:
            total_agents = self.db.query(Agent).count()
            active_agents = self.db.query(Agent).filter(Agent.is_active).count()

            # Count by persona type
            persona_counts = {}
            agents = self.db.query(Agent).all()
            for agent in agents:
                persona_type = agent.persona_type
                persona_counts[persona_type] = persona_counts.get(persona_type, 0) + 1

            return {
                "total_agents": total_agents,
                "active_agents": active_agents,
                "inactive_agents": total_agents - active_agents,
                "agents_by_type": persona_counts,
                "loaded_agents": len(self.loaded_agents),
            }

        except SQLAlchemyError as e:
            logger.error(f"Failed to get agent statistics: {e}")
            return {}
