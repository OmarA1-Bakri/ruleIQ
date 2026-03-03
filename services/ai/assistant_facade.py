"""
Compliance Assistant Façade

This façade maintains backward compatibility with the original ComplianceAssistant
while delegating to the new modular architecture.

IMPORTANT: This is a transitional façade. New code should use domain services directly.
"""

from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

import warnings
warnings.filterwarnings("ignore", category=FutureWarning, module=r"google\.generativeai")
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from sqlalchemy.ext.asyncio import AsyncSession

from config.logging_config import get_logger
from database.user import User

# Import new architecture components
from .providers.factory import ProviderFactory
from .response.generator import ResponseGenerator
from .response.parser import ResponseParser
from .response.fallback import FallbackGenerator
from .domains.assessment_service import AssessmentService
from .domains.policy_service import PolicyService
from .domains.workflow_service import WorkflowService
from .domains.evidence_service import EvidenceService
from .domains.compliance_service import ComplianceAnalysisService

# Import existing infrastructure
from .circuit_breaker import AICircuitBreaker
from .context_manager import ContextManager
from .instruction_integration import get_instruction_manager
from .prompt_templates import PromptTemplates
from .safety_manager import get_safety_manager_for_user, ContentType
from .tools import tool_executor

logger = get_logger(__name__)


class ComplianceAssistant:
    """
    AI-powered compliance assistant using Google Gemini, with full async support.

    This is a façade that maintains backward compatibility while delegating to
    the new modular architecture.
    """

    def __init__(self, db: AsyncSession, user_context: Optional[Dict[str, Any]] = None) -> None:
        """
        Initialize the compliance assistant.

        Args:
            db: Database session
            user_context: Optional user context
        """
        # Preserve original attributes for backward compatibility
        self.db = db
        self.user_context = user_context or {}
        self.model = None

        # Initialize existing infrastructure (preserve original behavior)
        self.context_manager = ContextManager(db)
        self.prompt_templates = PromptTemplates()
        self.instruction_manager = get_instruction_manager()
        self.circuit_breaker = AICircuitBreaker()
        self.safety_manager = get_safety_manager_for_user(self.user_context)

        # Preserve legacy attributes
        self.ai_cache = None
        self.cached_content_manager = None
        self.performance_optimizer = None
        self.analytics_monitor = None
        self.quality_monitor = None

        # Preserve content type map
        self.content_type_map = {
            'assessment_help': ContentType.ASSESSMENT_GUIDANCE,
            'evidence_recommendations': ContentType.EVIDENCE_CLASSIFICATION,
            'policy_generation': ContentType.POLICY_GENERATION,
            'compliance_analysis': ContentType.COMPLIANCE_ANALYSIS,
            'general': ContentType.GENERAL_QUESTION
        }

        # Preserve safety settings
        self.safety_settings = {
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_ONLY_HIGH,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
        }

        # Initialize new architecture components
        self.provider_factory = ProviderFactory(
            self.instruction_manager,
            self.circuit_breaker
        )

        self.response_generator = ResponseGenerator(
            self.provider_factory,
            self.safety_manager,
            tool_executor,
            None  # analytics_monitor initialized lazily
        )

        self.response_parser = ResponseParser()
        self.fallback_generator = FallbackGenerator()

        # Initialize domain services
        self.assessment_service = AssessmentService(
            self.response_generator,
            self.response_parser,
            self.fallback_generator,
            self.context_manager,
            self.prompt_templates,
            None,  # ai_cache initialized lazily
            None   # analytics_monitor initialized lazily
        )

        self.policy_service = PolicyService(
            self.response_generator,
            self.response_parser,
            self.fallback_generator,
            self.context_manager
        )

        self.workflow_service = WorkflowService(
            self.response_generator,
            self.response_parser,
            self.fallback_generator,
            self.context_manager
        )

        self.compliance_service = ComplianceAnalysisService(
            self.response_generator,
            self.context_manager
        )

        self.evidence_service = EvidenceService(
            self.response_generator,
            self.response_parser,
            self.fallback_generator,
            self.context_manager,
            self.workflow_service,  # For maturity analysis
            self.compliance_service  # For gap analysis
        )

        logger.info("ComplianceAssistant façade initialized with new architecture")

    # ============================================================================
    # Assessment Methods (delegate to AssessmentService)
    # ============================================================================

    async def get_assessment_help(
        self,
        question_id: str,
        question_text: str,
        framework_id: str,
        business_profile_id: UUID,
        section_id: Optional[str] = None,
        user_context: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Get contextual help for an assessment question."""
        return await self.assessment_service.get_help(
            question_id,
            question_text,
            framework_id,
            business_profile_id,
            section_id,
            user_context
        )

    async def generate_assessment_followup(
        self,
        current_answers: Dict[str, Any],
        framework_id: str,
        business_profile_id: UUID,
        assessment_context: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Generate follow-up questions based on current answers."""
        return await self.assessment_service.generate_followup(
            current_answers,
            framework_id,
            business_profile_id,
            assessment_context
        )

    async def analyze_assessment_results(
        self,
        assessment_results: Dict[str, Any],
        framework_id: str,
        business_profile_id: UUID
    ) -> Dict[str, Any]:
        """Analyze assessment results."""
        return await self.assessment_service.analyze_results(
            assessment_results,
            framework_id,
            business_profile_id
        )

    async def get_assessment_recommendations(
        self,
        assessment_results: Dict[str, Any],
        framework_id: str,
        business_profile_id: UUID,
        customization_options: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Get personalized assessment recommendations."""
        return await self.assessment_service.get_recommendations(
            assessment_results,
            framework_id,
            business_profile_id,
            customization_options
        )

    # ============================================================================
    # Policy Methods (delegate to PolicyService)
    # ============================================================================

    async def generate_customized_policy(
        self,
        user: User,
        business_profile_id: UUID,
        framework: str,
        policy_type: str,
        customization_options: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Generate a customized compliance policy."""
        return await self.policy_service.generate_policy(
            user,
            business_profile_id,
            framework,
            policy_type,
            customization_options
        )

    # ============================================================================
    # Workflow Methods (delegate to WorkflowService)
    # ============================================================================

    async def generate_evidence_collection_workflow(
        self,
        user: User,
        business_profile_id: UUID,
        framework: str,
        control_id: Optional[str] = None,
        workflow_type: str = 'comprehensive'
    ) -> Dict[str, Any]:
        """Generate an evidence collection workflow."""
        return await self.workflow_service.generate_workflow(
            user,
            business_profile_id,
            framework,
            control_id,
            workflow_type
        )

    # ============================================================================
    # Evidence Methods (delegate to EvidenceService)
    # ============================================================================

    async def get_evidence_recommendations(
        self,
        user: User,
        business_profile_id: UUID,
        framework: str,
        control_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get evidence collection recommendations."""
        return await self.evidence_service.get_recommendations(
            user,
            business_profile_id,
            framework,
            control_id
        )

    async def get_context_aware_recommendations(
        self,
        user: User,
        business_profile_id: UUID,
        framework: str,
        context_type: str = 'comprehensive'
    ) -> Dict[str, Any]:
        """Get enhanced context-aware evidence recommendations."""
        return await self.evidence_service.get_context_aware_recommendations(
            user,
            business_profile_id,
            framework,
            context_type
        )

    # ============================================================================
    # Compliance Analysis Methods (delegate to ComplianceAnalysisService)
    # ============================================================================

    async def analyze_evidence_gap(
        self,
        business_profile_id: UUID,
        framework: str
    ) -> Dict[str, Any]:
        """Analyze evidence gaps for a framework."""
        return await self.compliance_service.analyze_evidence_gap(
            business_profile_id,
            framework
        )

    # ============================================================================
    # Legacy Methods (preserved for backward compatibility)
    # ============================================================================

    def _get_task_appropriate_model(
        self,
        task_type: str,
        context: Optional[Dict[str, Any]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        cached_content: Optional[Any] = None
    ) -> Tuple[Any, str]:
        """
        Get the most appropriate model for the given task type.

        DEPRECATED: Use provider_factory.get_provider_for_task instead.
        Preserved for backward compatibility with tests that may mock this method.
        """
        return self.provider_factory.get_provider_for_task(
            task_type,
            context,
            tools,
            cached_content
        )

    async def _generate_gemini_response(
        self,
        prompt: str,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generate a response using Gemini.

        DEPRECATED: Use response_generator.generate_simple instead.
        Preserved for backward compatibility.
        """
        return await self.response_generator.generate_simple(
            system_prompt="You are a compliance expert.",
            user_prompt=prompt,
            task_type='general',
            context=context
        )

    def _validate_accuracy(self, response: str, framework: str) -> Dict[str, Any]:
        """
        Validate accuracy of response.

        DEPRECATED: Use compliance_service.validate_accuracy instead.
        """
        return self.compliance_service.validate_accuracy(response, framework)

    def _detect_hallucination(self, response: str) -> Dict[str, Any]:
        """
        Detect potential hallucinations.

        DEPRECATED: Use compliance_service.detect_hallucination instead.
        """
        return self.compliance_service.detect_hallucination(response)

    async def _get_cached_content_manager(self):
        """Initialize and return the cached content manager."""
        if self.cached_content_manager is None:
            from .cached_content import get_cached_content_manager
            self.cached_content_manager = await get_cached_content_manager()
        return self.cached_content_manager

    async def _get_or_create_assessment_cache(
        self,
        framework_id: str,
        business_profile: Dict[str, Any],
        assessment_context: Optional[Dict] = None
    ):
        """Get or create cached content for assessment."""
        # Placeholder - would delegate to cached content manager
        pass
