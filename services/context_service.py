"""
Context Memory Service for Agentic Behavior

This service implements the foundational context memory layer that enables
ruleIQ to build ongoing relationships with users rather than stateless interactions.

Core Features:
- User interaction pattern learning
- Context continuity across sessions
- Trust relationship tracking
- Personalized experience adaptation
- Predictive need identification

Part of the ruleIQ Agentic Transformation Vision 2025
"""

import json
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from enum import Enum
import redis.asyncio as redis

from services.cache_service import CacheService

logger = logging.getLogger(__name__)


class InteractionType(str, Enum):
#     ASSESSMENT_START = "assessment_start"  # Unused variable
#     ASSESSMENT_CONTINUE = "assessment_continue"  # Unused variable
#     ASSESSMENT_COMPLETE = "assessment_complete"  # Unused variable
#     POLICY_GENERATION = "policy_generation"  # Unused variable
#     POLICY_APPROVAL = "policy_approval"  # Unused variable
#     BUSINESS_PROFILE_UPDATE = "business_profile_update"  # Unused variable
#     QUESTION_ASKED = "question_asked"  # Unused variable
#     RECOMMENDATION_ACCEPTED = "recommendation_accepted"  # Unused variable
#     RECOMMENDATION_REJECTED = "recommendation_rejected"  # Unused variable
#     AUTOMATION_DELEGATED = "automation_delegated"  # Unused variable
#     ERROR_ENCOUNTERED = "error_encountered"  # Unused variable


    """Trust levels for user interactions"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERIFIED = "verified"


class TrustLevel(str, Enum):
    UNKNOWN = "unknown"
    SKEPTICAL = "skeptical"
    CAUTIOUS = "cautious"
    TRUSTING = "trusting"
    DELEGATING = "delegating"


class CommunicationStyle(str, Enum):
    FORMAL = "formal"
    CASUAL = "casual"
    TECHNICAL = "technical"
    CONCISE = "concise"


@dataclass
class UserInteraction:
    """Individual user interaction record"""

    user_id: str
    interaction_type: InteractionType
    timestamp: datetime
    context: Dict[str, Any]
    outcome: Optional[str] = None
    success: bool = True
    session_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class UserPattern:
    """Learned patterns about user behavior"""

    user_id: str
    trust_level: TrustLevel
    communication_style: CommunicationStyle
    preferred_automation_level: int  # 0-100 scale
    common_tasks: List[str]
    error_patterns: List[str]
    success_patterns: List[str]
    session_duration_avg: float  # minutes
    questions_per_session_avg: float
    last_updated: datetime
    confidence_score: float  # 0-1, how confident we are in the patterns


@dataclass
class SessionContext:
    """Current session context and state"""

    session_id: str
    user_id: str
    start_time: datetime
    current_task: Optional[str] = None
    completed_steps: List[str] = None
    pending_actions: List[str] = None
    context_stack: List[Dict[str, Any]] = None
    conversation_state: Dict[str, Any] = None
    trust_signals: List[str] = None

    def __post_init__(self):
        if self.completed_steps is None:
            self.completed_steps = []
        if self.pending_actions is None:
            self.pending_actions = []
        if self.context_stack is None:
            self.context_stack = []
        if self.conversation_state is None:
            self.conversation_state = {}
        if self.trust_signals is None:
            self.trust_signals = []


@dataclass
class PredictedNeed:
    """Predicted user need based on patterns"""

    need_type: str
    confidence: float
    reasoning: str
    suggested_action: str
    estimated_value: Optional[str] = None
    urgency: int = 1  # 1-10 scale


class UserContextService:
    """
    Service for managing user context, patterns, and agentic behavior

    This service enables ruleIQ to:
    1. Remember user interactions across sessions
    2. Learn from user behavior patterns
    3. Build trust relationships over time
    4. Provide personalized experiences
    5. Predict user needs proactively
    """

    def __init__(self) -> None:
        self.cache_service = CacheService()
        self.redis_client = None
        self._session_contexts: Dict[str, SessionContext] = {}

    async def initialize(self) -> None:
        """Initialize the context service"""
        try:
            # Initialize Redis connection for session state
            self.redis_client = redis.Redis(
                host="localhost", port=6379, decode_responses=True,
            )
            await self.redis_client.ping()
            logger.info("Context service initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize context service: {e}")
            raise

    async def store_interaction_context(
        self,
        user_id: str,
        interaction_type: InteractionType,
        context: Dict[str, Any],
        session_id: Optional[str] = None,
        outcome: Optional[str] = None,
        success: bool = True,
    ) -> bool:
        """
        Store a user interaction for pattern learning

        Args:
            user_id: User identifier
            interaction_type: Type of interaction
            context: Interaction context data
            session_id: Optional session identifier
            outcome: Optional outcome description
            success: Whether interaction was successful

        Returns:
            bool: Success status
        """
        try:
            interaction = UserInteraction(
                user_id=user_id,
                interaction_type=interaction_type,
                timestamp=datetime.now(timezone.utc),
                context=context,
                session_id=session_id,
                outcome=outcome,
                success=success,
            )

            # Store in Redis for fast access (TTL: 30 days)
            redis_key = (
                f"user_interaction:{user_id}:{interaction.timestamp.timestamp()}",
            )
            interaction_data = asdict(interaction)
            # Convert datetime to ISO string for JSON serialization
            interaction_data["timestamp"] = interaction.timestamp.isoformat()

            await self.redis_client.setex(
                redis_key,
                timedelta(days=30).total_seconds(),
                json.dumps(interaction_data),
            )

            # Also cache recent interactions list
            recent_key = f"user_recent_interactions:{user_id}"
            await self.redis_client.lpush(recent_key, redis_key)
            await self.redis_client.ltrim(recent_key, 0, 99)  # Keep last 100
            await self.redis_client.expire(
                recent_key, int(timedelta(days=30).total_seconds()),
            )

            # Update user patterns asynchronously
            asyncio.create_task(self._update_user_patterns(user_id))

            logger.debug(f"Stored interaction for user {user_id}: {interaction_type}")
            return True

        except Exception as e:
            logger.error(f"Failed to store interaction context: {e}")
            return False

    async def retrieve_user_patterns(self, user_id: str) -> Optional[UserPattern]:
        """
        Retrieve learned patterns for a user

        Args:
            user_id: User identifier

        Returns:
            UserPattern or None if no patterns found
        """
        try:
            # Check cache first
            cache_key = f"user_patterns:{user_id}"
            cached_data = await self.cache_service.get(cache_key)

            if cached_data:
                pattern_data = json.loads(cached_data)
                # Convert ISO strings back to datetime
                pattern_data["last_updated"] = datetime.fromisoformat(
                    pattern_data["last_updated"],
                )
                return UserPattern(**pattern_data)

            # Generate patterns if not cached
            patterns = await self._analyze_user_patterns(user_id)
            if patterns:
                # Cache for 1 hour
                pattern_data = asdict(patterns)
                pattern_data["last_updated"] = patterns.last_updated.isoformat()
                await self.cache_service.set(
                    cache_key, json.dumps(pattern_data), ttl=3600,
                )

            return patterns

        except Exception as e:
            logger.error(f"Failed to retrieve user patterns: {e}")
            return None

    async def update_trust_score(
        self, user_id: str, success_metrics: Dict[str, Any]
    ) -> bool:
        """
        Update user trust score based on interaction success

        Args:
            user_id: User identifier
            success_metrics: Metrics about interaction success

        Returns:
            bool: Success status
        """
        try:
            current_patterns = await self.retrieve_user_patterns(user_id)
            if not current_patterns:
                return False

            # Calculate trust adjustment based on success metrics
            trust_adjustment = 0.0

            if success_metrics.get("recommendation_accepted", False):
                trust_adjustment += 0.1
            if success_metrics.get("automation_delegated", False):
                trust_adjustment += 0.2
            if success_metrics.get("error_resolved_quickly", False):
                trust_adjustment += 0.05
            if success_metrics.get("task_completed_successfully", False):
                trust_adjustment += 0.1

            # Negative adjustments
            if success_metrics.get("recommendation_rejected", False):
                trust_adjustment -= 0.05
            if success_metrics.get("error_caused_frustration", False):
                trust_adjustment -= 0.1

            # Update trust level based on score
            current_score = current_patterns.confidence_score
            new_score = max(0.0, min(1.0, current_score + trust_adjustment))

            # Map score to trust level
            if new_score < 0.2:
                trust_level = TrustLevel.SKEPTICAL
            elif new_score < 0.4:
                trust_level = TrustLevel.CAUTIOUS
            elif new_score < 0.7:
                trust_level = TrustLevel.TRUSTING
            else:
                trust_level = TrustLevel.DELEGATING

            # Store updated patterns
            current_patterns.trust_level = trust_level
            current_patterns.confidence_score = new_score
            current_patterns.last_updated = datetime.now(timezone.utc)

            # Clear cache to force regeneration
            cache_key = f"user_patterns:{user_id}"
            await self.cache_service.delete(cache_key)

            logger.info(
                f"Updated trust score for user {user_id}: {trust_level} ({new_score:.2f})",
            )
            return True

        except Exception as e:
            logger.error(f"Failed to update trust score: {e}")
            return False

    async def predict_user_needs(self, user_id: str) -> List[PredictedNeed]:
        """
        Predict user needs based on patterns and context

        Args:
            user_id: User identifier

        Returns:
            List of predicted needs
        """
        try:
            patterns = await self.retrieve_user_patterns(user_id)
            if not patterns:
                return []

            predictions = []

            # Get recent interactions
            await self._get_recent_interactions(user_id, limit=20)

            # Predict based on common patterns
            if "assessment" in patterns.common_tasks:
                last_assessment = await self._get_last_interaction_of_type(
                    user_id, InteractionType.ASSESSMENT_COMPLETE,
                )
                if (
                    last_assessment
                    and (datetime.now(timezone.utc) - last_assessment.timestamp).days > 90
                ):
                    predictions.append(
                        PredictedNeed(
                            need_type="compliance_review",
                            confidence=0.8,
                            reasoning="User typically conducts assessments every 3 months",
                            suggested_action="Offer to start quarterly compliance review",
                            urgency=7,
                        ),
                    )

            # Predict policy updates based on business profile changes
            if "policy_generation" in patterns.common_tasks:
                predictions.append(
                    PredictedNeed(
                        need_type="policy_update",
                        confidence=0.6,
                        reasoning="User frequently generates policies and may need updates",
                        suggested_action="Check for regulatory changes affecting user's industry",
                        urgency=5,
                    ),
                )

            # Predict automation opportunities for high-trust users
            if patterns.trust_level in [TrustLevel.TRUSTING, TrustLevel.DELEGATING]:
                if patterns.preferred_automation_level > 70:
                    predictions.append(
                        PredictedNeed(
                            need_type="automation_opportunity",
                            confidence=0.7,
                            reasoning="User has high trust level and prefers automation",
                            suggested_action="Suggest automating recurring compliance tasks",
                            urgency=4,
                        ),
                    )

            return sorted(
                predictions, key=lambda x: x.confidence * x.urgency, reverse=True,
            )

        except Exception as e:
            logger.error(f"Failed to predict user needs: {e}")
            return []

    async def start_session(self, user_id: str, session_id: str) -> SessionContext:
        """
        Start a new session and initialize context

        Args:
            user_id: User identifier
            session_id: Session identifier

        Returns:
            SessionContext: Initialized session context
        """
        try:
            session_context = SessionContext(
                session_id=session_id, user_id=user_id, start_time=datetime.now(timezone.utc),
            )

            # Store in memory for fast access
            self._session_contexts[session_id] = session_context

            # Store in Redis for persistence
            redis_key = f"session_context:{session_id}"
            context_data = asdict(session_context)
            context_data["start_time"] = session_context.start_time.isoformat()

            await self.redis_client.setex(
                redis_key,
                int(timedelta(hours=24).total_seconds()),  # 24 hour session TTL
                json.dumps(context_data),
            )

            logger.info(f"Started session {session_id} for user {user_id}")
            return session_context

        except Exception as e:
            logger.error(f"Failed to start session: {e}")
            raise

    async def get_session_context(self, session_id: str) -> Optional[SessionContext]:
        """
        Get current session context

        Args:
            session_id: Session identifier

        Returns:
            SessionContext or None if not found
        """
        try:
            # Check memory first
            if session_id in self._session_contexts:
                return self._session_contexts[session_id]

            # Check Redis
            redis_key = f"session_context:{session_id}"
            context_data = await self.redis_client.get(redis_key)

            if context_data:
                parsed_data = json.loads(context_data)
                parsed_data["start_time"] = datetime.fromisoformat(
                    parsed_data["start_time"],
                )
                session_context = SessionContext(**parsed_data)

                # Cache in memory
                self._session_contexts[session_id] = session_context
                return session_context

            return None

        except Exception as e:
            logger.error(f"Failed to get session context: {e}")
            return None

    async def update_session_context(
        self, session_id: str, updates: Dict[str, Any]
    ) -> bool:
        """
        Update session context with new information

        Args:
            session_id: Session identifier
            updates: Updates to apply to context

        Returns:
            bool: Success status
        """
        try:
            session_context = await self.get_session_context(session_id)
            if not session_context:
                return False

            # Apply updates
            for key, value in updates.items():
                if hasattr(session_context, key):
                    setattr(session_context, key, value)
                else:
                    # Store in conversation_state for custom fields
                    session_context.conversation_state[key] = value

            # Update in memory
            self._session_contexts[session_id] = session_context

            # Update in Redis
            redis_key = f"session_context:{session_id}"
            context_data = asdict(session_context)
            context_data["start_time"] = session_context.start_time.isoformat()

            await self.redis_client.setex(
                redis_key,
                int(timedelta(hours=24).total_seconds()),
                json.dumps(context_data),
            )

            return True

        except Exception as e:
            logger.error(f"Failed to update session context: {e}")
            return False

    async def _analyze_user_patterns(self, user_id: str) -> Optional[UserPattern]:
        """Analyze user interactions to extract patterns"""
        try:
            # Get recent interactions (last 30 days)
            interactions = await self._get_recent_interactions(user_id, days=30)

            if len(interactions) < 3:  # Need minimum interactions for pattern analysis
                return UserPattern(
                    user_id=user_id,
                    trust_level=TrustLevel.UNKNOWN,
                    communication_style=CommunicationStyle.FORMAL,
                    preferred_automation_level=30,
                    common_tasks=[],
                    error_patterns=[],
                    success_patterns=[],
                    session_duration_avg=15.0,
                    questions_per_session_avg=5.0,
                    last_updated=datetime.now(timezone.utc),
                    confidence_score=0.1,
                )

            # Analyze patterns
            task_counts = {}
            error_patterns = []
            success_patterns = []

            for interaction in interactions:
                # Count task types
                task_type = interaction.interaction_type.value
                task_counts[task_type] = task_counts.get(task_type, 0) + 1

                # Collect error/success patterns
                if not interaction.success:
                    error_patterns.append(
                        interaction.context.get("error_type", "unknown"),
                    )
                else:
                    success_patterns.append(task_type)

            # Determine common tasks
            common_tasks = [task for task, count in task_counts.items() if count >= 2]

            # Estimate trust level based on interaction success rate
            success_rate = len([i for i in interactions if i.success]) / len(
                interactions,
            )
            if success_rate > 0.9:
                trust_level = TrustLevel.TRUSTING
                confidence = 0.8
            elif success_rate > 0.7:
                trust_level = TrustLevel.CAUTIOUS
                confidence = 0.6
            else:
                trust_level = TrustLevel.SKEPTICAL
                confidence = 0.4

            # Estimate communication style (placeholder - would need more sophisticated analysis)
            communication_style = CommunicationStyle.FORMAL

            # Estimate automation preference (placeholder)
            automation_level = min(80, max(20, int(success_rate * 100)))

            return UserPattern(
                user_id=user_id,
                trust_level=trust_level,
                communication_style=communication_style,
                preferred_automation_level=automation_level,
                common_tasks=common_tasks,
                error_patterns=list(set(error_patterns)),
                success_patterns=list(set(success_patterns)),
                session_duration_avg=20.0,  # Placeholder
                questions_per_session_avg=6.0,  # Placeholder
                last_updated=datetime.now(timezone.utc),
                confidence_score=confidence,
            )

        except Exception as e:
            logger.error(f"Failed to analyze user patterns: {e}")
            return None

    async def _get_recent_interactions(
        self, user_id: str, limit: int = 50, days: int = 30
    ) -> List[UserInteraction]:
        """Get recent interactions for a user"""
        try:
            recent_key = f"user_recent_interactions:{user_id}"
            interaction_keys = await self.redis_client.lrange(recent_key, 0, limit - 1)

            interactions = []
            for key in interaction_keys:
                interaction_data = await self.redis_client.get(key)
                if interaction_data:
                    parsed_data = json.loads(interaction_data)
                    parsed_data["timestamp"] = datetime.fromisoformat(
                        parsed_data["timestamp"],
                    )

                    # Filter by date
                    if (datetime.now(timezone.utc) - parsed_data["timestamp"]).days <= days:
                        interactions.append(UserInteraction(**parsed_data))

            return sorted(interactions, key=lambda x: x.timestamp, reverse=True)

        except Exception as e:
            logger.error(f"Failed to get recent interactions: {e}")
            return []

    async def _get_last_interaction_of_type(
        self, user_id: str, interaction_type: InteractionType
    ) -> Optional[UserInteraction]:
        """Get the most recent interaction of a specific type"""
        try:
            interactions = await self._get_recent_interactions(user_id)
            for interaction in interactions:
                if interaction.interaction_type == interaction_type:
                    return interaction
            return None

        except Exception as e:
            logger.error(f"Failed to get last interaction of type: {e}")
            return None

    async def _update_user_patterns(self, user_id: str) -> None:
        """Background task to update user patterns"""
        try:
            # Clear cache to force regeneration on next access
            cache_key = f"user_patterns:{user_id}"
            await self.cache_service.delete(cache_key)

            # Pre-generate patterns for faster access
            await self.retrieve_user_patterns(user_id)

        except Exception as e:
            logger.error(f"Failed to update user patterns: {e}")


# Global service instance
_context_service = None


async def get_context_service() -> UserContextService:
    """Get or create the context service instance"""
    global _context_service
    if _context_service is None:
        _context_service = UserContextService()
        await _context_service.initialize()
    return _context_service
