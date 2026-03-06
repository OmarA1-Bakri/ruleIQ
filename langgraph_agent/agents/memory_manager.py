"""

Advanced memory management with Graphiti vector database integration.
Handles conversation history, entity extraction, and contextual memory retrieval.
"""

import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4
import json

from graphiti_core import Graphiti
from graphiti_core.nodes import EpisodeType
from graphiti_core.search.search_config_recipes import NODE_HYBRID_SEARCH_RRF


logger = logging.getLogger(__name__)


class MemoryType(str, Enum):
    """Types of memory storage."""

    SHORT_TERM = "short_term"  # Recent conversation context
    LONG_TERM = "long_term"  # Persistent user/company knowledge
    EPISODIC = "episodic"  # Specific events and interactions
    SEMANTIC = "semantic"  # Facts and knowledge entities
    PROCEDURAL = "procedural"  # Process and workflow memories
    CONTEXTUAL = "contextual"  # Situational context and preferences


class MemoryImportance(str, Enum):
    """Memory importance levels for retention."""

    CRITICAL = "critical"  # Never forget
    HIGH = "high"  # Long retention
    MEDIUM = "medium"  # Standard retention
    LOW = "low"  # Short retention
    MINIMAL = "minimal"  # Cache-like, disposable


@dataclass
class MemoryEntry:
    """Individual memory entry with metadata."""

    id: str
    content: str
    memory_type: MemoryType
    importance: MemoryImportance
    company_id: UUID
    user_id: Optional[UUID] = None
    session_id: Optional[str] = None

    # Temporal data
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_accessed: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    access_count: int = 0

    # Contextual data
    entities: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    sentiment: Optional[float] = None
    confidence: float = 1.0

    # Relational data
    related_memories: List[str] = field(default_factory=list)
    source_type: str = "conversation"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def update_access(self) -> None:
        """Update access tracking."""
        self.last_accessed = datetime.now(timezone.utc)
        self.access_count += 1

    def is_expired(self) -> bool:
        """Check if memory has expired."""
        if not self.expires_at:
            return False
        return datetime.now(timezone.utc) > self.expires_at

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "id": self.id,
            "content": self.content,
            "memory_type": self.memory_type.value,
            "importance": self.importance.value,
            "company_id": str(self.company_id),
            "user_id": str(self.user_id) if self.user_id else None,
            "session_id": self.session_id,
            "created_at": self.created_at.isoformat(),
            "last_accessed": self.last_accessed.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "access_count": self.access_count,
            "entities": self.entities,
            "keywords": self.keywords,
            "sentiment": self.sentiment,
            "confidence": self.confidence,
            "related_memories": self.related_memories,
            "source_type": self.source_type,
            "metadata": self.metadata,
        }


@dataclass
class ConversationSummary:
    """Summary of a conversation session."""

    session_id: str
    company_id: UUID
    user_id: Optional[UUID]

    start_time: datetime
    end_time: Optional[datetime] = None

    # Content summary
    key_topics: List[str] = field(default_factory=list)
    main_outcomes: List[str] = field(default_factory=list)
    action_items: List[str] = field(default_factory=list)
    entities_mentioned: List[str] = field(default_factory=list)

    # Metrics
    total_turns: int = 0
    total_tokens: int = 0
    sentiment_trend: Optional[float] = None
    satisfaction_score: Optional[float] = None

    # Context for future sessions
    context_for_next: Optional[str] = None
    unresolved_questions: List[str] = field(default_factory=list)


class MemoryManager:
    """
    Advanced memory management with Graphiti vector database.

    Features:
    - Multi-layered memory architecture
    - Entity-based knowledge graphs
    - Contextual retrieval with embeddings
    - Automated memory pruning and summarization
    - Cross-session continuity
    """

    def __init__(
        self,
        neo4j_uri: str,
        neo4j_user: str,
        neo4j_password: str,
        max_memory_entries: int = 10000,
        cleanup_interval_hours: int = 24,
        store_raw_content: bool = True,
    ) -> None:
        self.neo4j_uri = neo4j_uri
        self.neo4j_user = neo4j_user
        self.neo4j_password = neo4j_password
        self.max_memory_entries = max_memory_entries
        self.cleanup_interval_hours = cleanup_interval_hours
        self.store_raw_content = store_raw_content

        # Initialize components
        self.graphiti: Optional[Graphiti] = None

        # Memory caches
        self.short_term_cache: Dict[str, List[MemoryEntry]] = {}
        self.entity_cache: Dict[str, Any] = {}
        self.last_cleanup = datetime.now(timezone.utc)

        # Initialize async components in setup
        self._initialized = False

        logger.info("MemoryManager initialized with Graphiti integration")

    async def setup(self) -> None:
        """Initialize async components."""
        if self._initialized:
            return

        try:
            # Initialize Graphiti with Neo4j connection
            self.graphiti = Graphiti(
                uri=self.neo4j_uri,
                user=self.neo4j_user,
                password=self.neo4j_password,
                store_raw_episode_content=self.store_raw_content,
            )

            # Build indices and constraints
            await self.graphiti.build_indices_and_constraints()

            self._initialized = True
            logger.info("Graphiti vector database initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize Graphiti: {e}")
            raise

    async def store_conversation(
        self,
        company_id: UUID,
        session_id: str,
        user_message: str,
        agent_response: str,
        user_id: Optional[UUID] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> List[MemoryEntry]:
        """
        Store conversation turn with entity extraction and embedding.

        Args:
            company_id: Company identifier
            session_id: Session identifier
            user_message: User's message
            agent_response: Agent's response
            user_id: Optional user identifier
            context: Optional additional context

        Returns:
            List of created memory entries
        """
        if not self._initialized:
            await self.setup()

        memories = []

        try:
            # Create episode content with structured format
            episode_content = {
                "conversation_turn": {
                    "user_message": user_message,
                    "agent_response": agent_response,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "session_id": session_id,
                    "company_id": str(company_id),
                    "user_id": str(user_id) if user_id else None,
                }
            }

            # Create episode metadata
            episode_metadata = {
                "memory_type": MemoryType.EPISODIC.value,
                "importance": MemoryImportance.MEDIUM.value,
                "company_id": str(company_id),
                "user_id": str(user_id) if user_id else None,
                "session_id": session_id,
                "source_type": "conversation_turn",
            }

            if context:
                episode_metadata.update(context)

            # Add episode to Graphiti
            episode_id = f"conv_{session_id}_{uuid4()}"
            await self.graphiti.add_episode(
                name=episode_id,
                episode_body=episode_content,
                episode_type=EpisodeType.json,
                group_id=str(company_id),  # Use company_id for grouping
                source_description=f"Conversation turn for company {company_id}",
                reference_time=datetime.now(timezone.utc),
                metadata=episode_metadata,
            )

            # Create memory entry for tracking
            memory_entry = MemoryEntry(
                id=episode_id,
                content=f"User: {user_message}\nAssistant: {agent_response}",
                memory_type=MemoryType.EPISODIC,
                importance=MemoryImportance.MEDIUM,
                company_id=company_id,
                user_id=user_id,
                session_id=session_id,
                source_type="conversation_turn",
                metadata=episode_metadata,
            )

            memories.append(memory_entry)

            # Update short-term cache
            session_key = f"{company_id}_{session_id}"
            if session_key not in self.short_term_cache:
                self.short_term_cache[session_key] = []
            self.short_term_cache[session_key].append(memory_entry)

            # Maintain cache size
            if len(self.short_term_cache[session_key]) > 20:
                self.short_term_cache[session_key] = self.short_term_cache[session_key][-20:]

            logger.info(f"Stored conversation turn: {len(memories)} memories created")
            return memories

        except Exception as e:
            logger.error(f"Failed to store conversation: {e}")
            return []

    async def get_relevant_memories(
        self,
        company_id: UUID,
        query: str,
        memory_types: Optional[List[MemoryType]] = None,
        max_results: int = 10,
        similarity_threshold: float = 0.7,
        user_id: Optional[UUID] = None,
        session_id: Optional[str] = None,
    ) -> List[MemoryEntry]:
        """
        Retrieve relevant memories based on semantic similarity.

        Args:
            company_id: Company identifier
            query: Query text for similarity search
            memory_types: Optional filter by memory types
            max_results: Maximum number of results
            similarity_threshold: Minimum similarity score
            user_id: Optional user filter
            session_id: Optional session filter

        Returns:
            List of relevant memory entries
        """
        if not self._initialized:
            await self.setup()

        try:
            # Search using Graphiti's hybrid search
            search_results = await self.graphiti.search(
                query=query,
                group_ids=[str(company_id)],  # Filter by company
                limit=max_results,
                search_config=NODE_HYBRID_SEARCH_RRF,
            )

            relevant_memories = []

            for result in search_results:
                try:
                    # Extract metadata from search result
                    metadata = getattr(result, "metadata", {})

                    # Filter by company access
                    if metadata.get("company_id") != str(company_id):
                        continue

                    # Filter by memory types if specified
                    if memory_types:
                        result_memory_type = metadata.get("memory_type")
                        if result_memory_type not in [mt.value for mt in memory_types]:
                            continue

                    # Filter by user if specified
                    if user_id and metadata.get("user_id") != str(user_id):
                        continue

                    # Create memory entry from search result
                    memory = self._create_memory_from_search_result(result, company_id)
                    if memory:
                        # Add similarity score
                        memory.metadata["similarity_score"] = getattr(result, "score", 0.0)
                        memory.update_access()
                        relevant_memories.append(memory)

                except Exception as e:
                    logger.warning(f"Failed to process search result: {e}")
                    continue

            # Include recent short-term memories from current session
            if session_id:
                session_key = f"{company_id}_{session_id}"
                if session_key in self.short_term_cache:
                    recent_memories = self.short_term_cache[session_key][-5:]
                    for memory in recent_memories:
                        if memory not in relevant_memories:
                            relevant_memories.insert(0, memory)

            # Sort by relevance and limit results
            relevant_memories.sort(key=lambda m: self._calculate_relevance_score(m), reverse=True)
            result = relevant_memories[:max_results]

            logger.info(f"Retrieved {len(result)} relevant memories for query")
            return result

        except Exception as e:
            logger.error(f"Failed to retrieve memories: {e}")
            return []

    async def store_session_summary(
        self,
        session_id: str,
        company_id: UUID,
        summary: ConversationSummary,
        user_id: Optional[UUID] = None,
    ) -> Optional[MemoryEntry]:
        """Store conversation summary as long-term memory."""
        if not self._initialized:
            await self.setup()

        try:
            # Create summary content
            summary_content = {
                "session_summary": {
                    "session_id": session_id,
                    "company_id": str(company_id),
                    "user_id": str(user_id) if user_id else None,
                    "start_time": summary.start_time.isoformat(),
                    "end_time": (summary.end_time.isoformat() if summary.end_time else None),
                    "key_topics": summary.key_topics,
                    "main_outcomes": summary.main_outcomes,
                    "action_items": summary.action_items,
                    "entities_mentioned": summary.entities_mentioned,
                    "total_turns": summary.total_turns,
                    "sentiment_trend": summary.sentiment_trend,
                    "context_for_next": summary.context_for_next,
                    "unresolved_questions": summary.unresolved_questions,
                }
            }

            # Episode metadata
            episode_metadata = {
                "memory_type": MemoryType.LONG_TERM.value,
                "importance": MemoryImportance.HIGH.value,
                "company_id": str(company_id),
                "user_id": str(user_id) if user_id else None,
                "session_id": session_id,
                "source_type": "session_summary",
            }

            # Add summary episode to Graphiti
            episode_id = f"summary_{session_id}"
            await self.graphiti.add_episode(
                name=episode_id,
                episode_body=summary_content,
                episode_type=EpisodeType.json,
                group_id=str(company_id),
                source_description=f"Session summary for {session_id}",
                reference_time=summary.end_time or datetime.now(timezone.utc),
                metadata=episode_metadata,
            )

            # Create memory entry
            summary_text = self._format_session_summary(summary)
            summary_memory = MemoryEntry(
                id=episode_id,
                content=summary_text,
                memory_type=MemoryType.LONG_TERM,
                importance=MemoryImportance.HIGH,
                company_id=company_id,
                user_id=user_id,
                session_id=session_id,
                entities=summary.entities_mentioned,
                keywords=summary.key_topics,
                source_type="session_summary",
                metadata=episode_metadata,
            )

            # Clean up short-term cache for this session
            session_key = f"{company_id}_{session_id}"
            if session_key in self.short_term_cache:
                del self.short_term_cache[session_key]

            logger.info(f"Stored session summary for {session_id}")
            return summary_memory

        except Exception as e:
            logger.error(f"Failed to store session summary: {e}")
            return None

    async def load_user_context(
        self,
        company_id: UUID,
        user_id: Optional[UUID] = None,
        context_window_days: int = 30,
    ) -> Dict[str, Any]:
        """Load user context and preferences from memory."""
        if not self._initialized:
            await self.setup()

        try:
            # Search for user-specific memories
            context_query = "user preferences context history"
            if user_id:
                context_query += f" user:{user_id}"

            search_results = await self.graphiti.search(
                query=context_query,
                group_ids=[str(company_id)],
                limit=50,
                search_config=NODE_HYBRID_SEARCH_RRF,
            )

            # Extract user context
            context = {
                "user_preferences": {},
                "recent_topics": [],
                "past_interactions": [],
                "entities_of_interest": [],
                "communication_style": "professional",
                "expertise_level": "intermediate",
            }

            for result in search_results:
                try:
                    metadata = getattr(result, "metadata", {})

                    # Filter by user if specified
                    if user_id and metadata.get("user_id") != str(user_id):
                        continue

                    # Extract content and analyze
                    content = getattr(result, "content", "")
                    if isinstance(content, dict):
                        content = json.dumps(content)

                    # Extract preferences and topics
                    if "preference" in content.lower():
                        prefs = self._extract_preferences(content)
                        context["user_preferences"].update(prefs)

                    # Track topics and entities
                    if hasattr(result, "keywords"):
                        context["recent_topics"].extend(getattr(result, "keywords", []))

                    if hasattr(result, "entities"):
                        context["entities_of_interest"].extend(getattr(result, "entities", []))

                except Exception as e:
                    logger.warning(f"Failed to process context result: {e}")
                    continue

            # Deduplicate and limit
            context["recent_topics"] = list(set(context["recent_topics"]))[:10]
            context["entities_of_interest"] = list(set(context["entities_of_interest"]))[:15]

            logger.info(f"Loaded user context: {len(search_results)} memories processed")
            return context

        except Exception as e:
            logger.error(f"Failed to load user context: {e}")
            return {}

    async def cleanup_expired_memories(self) -> Dict[str, int]:
        """Clean up expired and low-importance memories."""
        if not self._initialized:
            await self.setup()

        cleanup_stats = {
            "expired_removed": 0,
            "low_importance_removed": 0,
            "duplicates_removed": 0,
            "total_remaining": 0,
        }

        try:
            # Note: Graphiti handles most cleanup automatically
            # This method can be used for additional business logic cleanup

            # Clean up short-term cache
            current_time = datetime.now(timezone.utc)
            sessions_to_remove = []

            for session_key, memories in self.short_term_cache.items():
                # Remove sessions older than 24 hours
                if memories and (current_time - memories[-1].created_at).total_seconds() > 86400:
                    sessions_to_remove.append(session_key)

            for session_key in sessions_to_remove:
                del self.short_term_cache[session_key]

            cleanup_stats["expired_removed"] = len(sessions_to_remove)

            # Update cleanup timestamp
            self.last_cleanup = current_time

            logger.info(f"Memory cleanup completed: {cleanup_stats}")
            return cleanup_stats

        except Exception as e:
            logger.error(f"Memory cleanup failed: {e}")
            return cleanup_stats

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on memory systems."""
        health = {
            "status": "healthy",
            "graphiti_connected": False,
            "cache_size": len(self.short_term_cache),
            "last_cleanup": self.last_cleanup.isoformat(),
            "total_sessions": len(self.short_term_cache),
        }

        try:
            if self.graphiti and self._initialized:
                # Test Graphiti connection by performing a simple search
                test_results = await self.graphiti.search(query="test connection", limit=1)
                health["graphiti_connected"] = True
                health["test_search_results"] = len(test_results)

        except Exception as e:
            health["status"] = "degraded"
            health["error"] = str(e)

        return health

    async def close(self) -> None:
        """Close connections and cleanup resources."""
        try:
            if self.graphiti:
                await self.graphiti.close()
            self.short_term_cache.clear()
            self.entity_cache.clear()
            self._initialized = False
            logger.info("MemoryManager closed successfully")
        except Exception as e:
            logger.error(f"Error closing MemoryManager: {e}")

    # Private helper methods

    def _create_memory_from_search_result(
        self, result: Any, company_id: UUID
    ) -> Optional[MemoryEntry]:
        """Create MemoryEntry from Graphiti search result."""
        try:
            metadata = getattr(result, "metadata", {})
            content = getattr(result, "content", "")

            if isinstance(content, dict):
                content = json.dumps(content)

            return MemoryEntry(
                id=metadata.get("id", str(uuid4())),
                content=str(content),
                memory_type=MemoryType(metadata.get("memory_type", MemoryType.EPISODIC.value)),
                importance=MemoryImportance(
                    metadata.get("importance", MemoryImportance.MEDIUM.value)
                ),
                company_id=company_id,
                user_id=UUID(metadata["user_id"]) if metadata.get("user_id") else None,
                session_id=metadata.get("session_id"),
                created_at=(
                    datetime.fromisoformat(metadata["created_at"])
                    if metadata.get("created_at")
                    else datetime.now(timezone.utc)
                ),
                source_type=metadata.get("source_type", "unknown"),
                metadata=metadata,
            )
        except Exception as e:
            logger.error(f"Failed to create memory from search result: {e}")
            return None

    def _calculate_relevance_score(self, memory: MemoryEntry) -> float:
        """Calculate relevance score combining similarity, recency, and importance."""
        base_score = memory.metadata.get("similarity_score", 0.0)

        # Recency boost (newer memories get higher scores)
        hours_since_creation = (
            datetime.now(timezone.utc) - memory.created_at
        ).total_seconds() / 3600
        recency_score = max(0, 1 - (hours_since_creation / (24 * 7)))  # Week decay

        # Importance boost
        importance_weights = {
            MemoryImportance.CRITICAL: 1.0,
            MemoryImportance.HIGH: 0.8,
            MemoryImportance.MEDIUM: 0.6,
            MemoryImportance.LOW: 0.4,
            MemoryImportance.MINIMAL: 0.2,
        }
        importance_score = importance_weights.get(memory.importance, 0.5)

        # Access frequency boost
        access_score = min(0.2, memory.access_count * 0.01)

        return (
            base_score * 0.6 + recency_score * 0.2 + importance_score * 0.15 + access_score * 0.05
        )

    def _format_session_summary(self, summary: ConversationSummary) -> str:
        """Format conversation summary into readable text."""
        parts = [
            f"Session Summary for {summary.session_id}",
            f"Duration: {summary.start_time} to {summary.end_time or 'ongoing'}",
            f"Total turns: {summary.total_turns}",
            "",
            "Key Topics:",
            *[f"- {topic}" for topic in summary.key_topics],
            "",
            "Main Outcomes:",
            *[f"- {outcome}" for outcome in summary.main_outcomes],
            "",
            "Action Items:",
            *[f"- {item}" for item in summary.action_items],
            "",
            "Entities Mentioned:",
            *[f"- {entity}" for entity in summary.entities_mentioned],
        ]

        if summary.context_for_next:
            parts.extend(["", f"Context for next session: {summary.context_for_next}"])

        return "\n".join(parts)

    def _extract_preferences(self, content: str) -> Dict[str, Any]:
        """Extract user preferences from memory content."""
        preferences = {}

        # Simple preference extraction - could be enhanced with NLP
        content_lower = content.lower()

        if "prefer" in content_lower:
            # Basic pattern matching for preferences
            if "email" in content_lower:
                preferences["communication_method"] = "email"
            if "formal" in content_lower:
                preferences["communication_style"] = "formal"
            if "informal" in content_lower or "casual" in content_lower:
                preferences["communication_style"] = "informal"

        return preferences
