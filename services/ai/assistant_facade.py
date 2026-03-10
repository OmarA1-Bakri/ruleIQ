"""
Compliance Assistant Façade

This façade maintains backward compatibility with the original ComplianceAssistant
while delegating to the new modular architecture.

IMPORTANT: This is a transitional façade. New code should use domain services directly.
"""

import json
import re
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple, cast
from uuid import UUID, uuid4

from google.genai import types
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
            "assessment_help": ContentType.ASSESSMENT_GUIDANCE,
            "evidence_recommendations": ContentType.EVIDENCE_CLASSIFICATION,
            "policy_generation": ContentType.POLICY_GENERATION,
            "compliance_analysis": ContentType.COMPLIANCE_ANALYSIS,
            "general": ContentType.GENERAL_QUESTION,
        }

        # Preserve safety settings
        self.safety_settings = {
            types.HarmCategory.HARM_CATEGORY_HARASSMENT: types.HarmBlockThreshold.BLOCK_ONLY_HIGH,
            types.HarmCategory.HARM_CATEGORY_HATE_SPEECH: types.HarmBlockThreshold.BLOCK_ONLY_HIGH,
            types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
            types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: types.HarmBlockThreshold.BLOCK_ONLY_HIGH,
        }

        # Initialize new architecture components
        self.provider_factory = ProviderFactory(self.instruction_manager, self.circuit_breaker)

        self.response_generator = ResponseGenerator(
            self.provider_factory,
            self.safety_manager,
            tool_executor,
            None,  # analytics_monitor initialized lazily
        )

        self.response_parser = ResponseParser()
        self.fallback_generator = FallbackGenerator()

        # Initialize domain services
        self.assessment_service = AssessmentService(
            self.response_generator,
            self.context_manager,
        )

        self.policy_service = PolicyService(
            self.response_generator,
            self.context_manager,
        )

        self.workflow_service = WorkflowService(
            self.response_generator,
            self.response_parser,
            self.fallback_generator,
            self.context_manager,
        )

        self.compliance_service = ComplianceAnalysisService(
            self.response_generator, self.context_manager
        )

        self.evidence_service = EvidenceService(
            self.response_generator,
            self.response_parser,
            self.fallback_generator,
            self.context_manager,
            self.workflow_service,  # For maturity analysis
            self.compliance_service,  # For gap analysis
        )

        logger.info("ComplianceAssistant façade initialized with new architecture")

    def _get_assessment_delegate(
        self, legacy_name: str, current_name: str
    ) -> Callable[..., Any]:
        """Resolve either a monkeypatched legacy assessment method or the current implementation."""
        return getattr(
            self.assessment_service,
            legacy_name,
            getattr(self.assessment_service, current_name),
        )

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
        user_context: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Get contextual help for an assessment question."""
        method = self._get_assessment_delegate("get_help", "get_assessment_help")
        return await method(
            question_id, question_text, framework_id, business_profile_id, section_id, user_context
        )

    async def generate_assessment_followup(
        self,
        current_answers: Dict[str, Any],
        framework_id: str,
        business_profile_id: UUID,
        assessment_context: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Generate follow-up questions based on current answers."""
        method = self._get_assessment_delegate(
            "generate_followup", "generate_assessment_followup"
        )
        return await method(
            current_answers, framework_id, business_profile_id, assessment_context
        )

    async def analyze_assessment_results(
        self, assessment_results: Dict[str, Any], framework_id: str, business_profile_id: UUID
    ) -> Dict[str, Any]:
        """Analyze assessment results."""
        method = self._get_assessment_delegate(
            "analyze_results", "analyze_assessment_results"
        )
        return await method(
            assessment_results, framework_id, business_profile_id
        )

    async def get_assessment_recommendations(
        self,
        assessment_results: Optional[Dict[str, Any]] = None,
        framework_id: str = "",
        business_profile_id: Optional[UUID] = None,
        customization_options: Optional[Dict[str, Any]] = None,
        *,
        gaps: Optional[List[Dict[str, Any]]] = None,
        business_profile: Optional[Dict[str, Any]] = None,
        existing_policies: Optional[List[str]] = None,
        industry_context: Optional[str] = None,
        timeline_preferences: str = "standard",
    ) -> Dict[str, Any]:
        """Get personalized assessment recommendations."""
        assessment_service_any = cast(Any, self.assessment_service)
        legacy_method = getattr(assessment_service_any, "get_recommendations", None)
        if callable(legacy_method):
            if gaps is not None and business_profile is not None:
                return await assessment_service_any.get_recommendations(
                    gaps,
                    business_profile,
                    framework_id,
                    existing_policies,
                    industry_context,
                    timeline_preferences,
                )
            return await assessment_service_any.get_recommendations(
                assessment_results,
                framework_id,
                business_profile_id,
                customization_options,
            )

        if gaps is None:
            gaps = assessment_results.get("gaps", []) if assessment_results else []

        if business_profile is None and business_profile_id is not None:
            context = await self.context_manager.get_conversation_context(
                conversation_id=uuid4(), business_profile_id=business_profile_id
            )
            business_profile = context.get("business_profile", {})

        business_profile = business_profile or {}

        try:
            prompt_data = self.prompt_templates.get_assessment_recommendations_prompt(
                gaps=gaps,
                business_profile=business_profile,
                framework_id=framework_id,
                existing_policies=existing_policies or [],
                industry_context=industry_context,
                timeline_preferences=timeline_preferences,
            )
            response = await self.response_generator.generate_simple(
                system_prompt=prompt_data["system"],
                user_prompt=prompt_data["user"],
                task_type="recommendations",
                context={"framework": framework_id, "business_profile": business_profile},
            )
            structured_response = self._parse_assessment_recommendations_response(response)
            structured_response.update(
                {
                    "request_id": f"recommendations_{framework_id}_{uuid4().hex[:8]}",
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "framework_id": framework_id,
                }
            )
            return structured_response
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Error generating assessment recommendations: %s", e)
            return self._get_fallback_assessment_recommendations(framework_id)

    # ============================================================================
    # Policy Methods (delegate to PolicyService)
    # ============================================================================

    async def generate_customized_policy(
        self,
        user: User,
        business_profile_id: UUID,
        framework: str,
        policy_type: str,
        customization_options: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Generate a customized compliance policy."""
        return await self.policy_service.generate_customized_policy(
            user, business_profile_id, framework, policy_type, customization_options
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
        workflow_type: str = "comprehensive",
    ) -> Dict[str, Any]:
        """Generate an evidence collection workflow."""
        return await self.workflow_service.generate_workflow(
            user, business_profile_id, framework, control_id, workflow_type
        )

    # ============================================================================
    # Evidence Methods (delegate to EvidenceService)
    # ============================================================================

    async def get_evidence_recommendations(
        self,
        user: User,
        business_profile_id: UUID,
        framework: str,
        control_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get evidence collection recommendations."""
        return await self.evidence_service.get_recommendations(
            user, business_profile_id, framework, control_id
        )

    async def get_context_aware_recommendations(
        self,
        user: User,
        business_profile_id: UUID,
        framework: str,
        context_type: str = "comprehensive",
    ) -> Dict[str, Any]:
        """Get enhanced context-aware evidence recommendations."""
        return await self.evidence_service.get_context_aware_recommendations(
            user, business_profile_id, framework, context_type
        )
    # ============================================================================
    # Compliance Analysis Methods (delegate to ComplianceAnalysisService)
    # ============================================================================

    async def analyze_evidence_gap(
        self, business_profile_id: UUID, framework: str
    ) -> Dict[str, Any]:
        """Analyze evidence gaps for a framework."""
        return await self.compliance_service.analyze_evidence_gap(business_profile_id, framework)

    # ============================================================================
    # Legacy Methods (preserved for backward compatibility)
    # ============================================================================

    def _get_task_appropriate_model(
        self,
        task_type: str,
        context: Optional[Dict[str, Any]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        cached_content: Optional[Any] = None,
    ) -> Tuple[Any, str]:
        """
        Get the most appropriate model for the given task type.

        DEPRECATED: Use provider_factory.get_provider_for_task instead.
        Preserved for backward compatibility with tests that may mock this method.
        """
        return self.provider_factory.get_provider_for_task(
            task_type, context, tools, cached_content
        )

    async def _generate_gemini_response(
        self, prompt: str, context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generate a response using Gemini.

        DEPRECATED: Use response_generator.generate_simple instead.
        Preserved for backward compatibility.
        """
        return await self.response_generator.generate_simple(
            system_prompt="You are a compliance expert.",
            user_prompt=prompt,
            task_type="general",
            context=context,
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
        assessment_context: Optional[Dict] = None,
    ):
        """Get or create cached content for assessment."""
        # Placeholder - would delegate to cached content manager
        _ = (framework_id, business_profile, assessment_context)
        return None

    # ============================================================================
    # Streaming Methods (backward compatibility)
    # ============================================================================

    async def _stream_response(
        self,
        system_prompt: str,
        user_prompt: str,
        task_type: str,
        context: Optional[Dict[str, Any]] = None,
    ):
        """
        Stream AI response chunks using the circuit-breaker-aware model.

        DEPRECATED: New code should use domain service streaming methods directly.
        Preserved for backward compatibility with tests.
        """
        from services.ai.exceptions import ModelUnavailableException

        model = None
        model_name = "unknown"
        try:
            model, _instruction_id = self._get_task_appropriate_model(task_type, context)
            model_name = getattr(model, "model_name", "unknown")

            if not self.circuit_breaker.is_model_available(model_name):
                yield "AI service is temporarily unavailable. Please try again shortly."
                return

            full_prompt = f"{system_prompt}\n\n{user_prompt}"
            stream = model.generate_content_stream(full_prompt)

            for chunk in stream:
                text = ""
                if hasattr(chunk, "text") and chunk.text:
                    text = chunk.text
                elif hasattr(chunk, "candidates") and chunk.candidates:
                    candidate = chunk.candidates[0]
                    if hasattr(candidate, "content") and hasattr(candidate.content, "parts"):
                        text = "".join(
                            part.text for part in candidate.content.parts if hasattr(part, "text")
                        )
                if text:
                    self.circuit_breaker.record_success(model_name)
                    yield text

        except ModelUnavailableException as e:
            logger.warning("Model temporarily unavailable: %s", e)
            yield "AI service is temporarily unavailable. Please try again shortly."

        except Exception as e:  # pylint: disable=broad-exception-caught
            if model is not None:
                model_name = getattr(model, "model_name", model_name)
            self.circuit_breaker.record_failure(model_name, e)
            logger.error("Streaming response error: %s", e)
            yield "I'm sorry, I'm unable to provide a response at this time."

    async def analyze_assessment_results_stream(
        self,
        assessment_responses: Any,
        framework_id: str,
        business_profile_id: UUID,
        user_context: Optional[Dict] = None,
    ):
        """Stream assessment analysis."""
        _ = user_context
        try:
            context = await self.context_manager.get_conversation_context(
                conversation_id=uuid4(), business_profile_id=business_profile_id
            )
            business_profile = context.get("business_profile", {})
            prompt_data = self.prompt_templates.get_assessment_analysis_prompt(
                assessment_responses, framework_id, business_profile
            )
            async for chunk in self._stream_response(
                "You are ComplianceGPT, providing comprehensive assessment analysis.",
                prompt_data.get("user", str(assessment_responses)),
                "analysis",
                {"framework": framework_id},
            ):
                yield chunk
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Error streaming assessment analysis: %s", e)
            yield f"Unable to analyze assessment results for {framework_id} at this time."

    async def get_assessment_recommendations_stream(
        self,
        assessment_gaps: Any,
        framework_id: str,
        business_profile_id: UUID,
        user_context: Optional[Dict] = None,
    ):
        """Stream assessment recommendations."""
        _ = user_context
        try:
            context = await self.context_manager.get_conversation_context(
                conversation_id=uuid4(), business_profile_id=business_profile_id
            )
            business_profile = context.get("business_profile", {})
            prompt_data = self.prompt_templates.get_assessment_recommendations_prompt(
                gaps=assessment_gaps,
                business_profile=business_profile,
                framework_id=framework_id,
            )
            async for chunk in self._stream_response(
                "You are ComplianceGPT, providing personalized recommendations.",
                prompt_data.get("user", str(assessment_gaps)),
                "recommendations",
                {"framework": framework_id},
            ):
                yield chunk
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Error streaming recommendations: %s", e)
            yield f"Unable to generate recommendations for {framework_id} at this time."

    async def get_assessment_help_stream(
        self,
        question_id: str,
        question_text: str,
        framework_id: str,
        business_profile_id: UUID,
        section_id: Optional[str] = None,
        user_context: Optional[Dict] = None,
    ):
        """Stream assessment help."""
        _ = (section_id, user_context)
        try:
            context = await self.context_manager.get_conversation_context(
                conversation_id=uuid4(), business_profile_id=business_profile_id
            )
            business_profile = context.get("business_profile", {})
            prompt_data = self.prompt_templates.get_assessment_help_prompt(
                question_text=question_text,
                framework_id=framework_id,
                section_id=section_id,
                business_context=business_profile,
                user_context=user_context,
            )
            async for chunk in self._stream_response(
                "You are ComplianceGPT, providing contextual assessment guidance.",
                prompt_data.get("user", question_text),
                "help",
                {"framework": framework_id},
            ):
                yield chunk
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Error streaming assessment help: %s", e)
            yield f"Unable to provide guidance for question {question_id} at this time."

    def _parse_assessment_recommendations_response(self, response: str) -> Dict[str, Any]:
        """Parse AI response for assessment recommendations into structured format."""
        try:
            if response.strip().startswith("{"):
                return json.loads(response)

            json_match = re.search(r"```json\s*(\{.*?\})\s*```", response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(1))

            json_match = re.search(r"\{.*\}", response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

        recommendations: List[Dict[str, Any]] = []
        current_rec: Optional[Dict[str, Any]] = None
        for raw_line in response.split("\n"):
            line = raw_line.strip()
            if line.startswith(("- ", "* ", "1.", "2.", "3.")):
                if current_rec:
                    recommendations.append(current_rec)
                title = re.sub(r"^[-*\d\.]\s*", "", line)
                current_rec = {
                    "id": f"rec_{len(recommendations) + 1}",
                    "title": title,
                    "description": title,
                    "priority": "medium",
                    "effort_estimate": "2-4 weeks",
                    "impact_score": 0.7,
                    "implementation_steps": [title],
                }
            elif current_rec and line and not line.startswith("#"):
                current_rec = {
                    **cast(Dict[str, Any], current_rec),
                    "description": f"{cast(Dict[str, Any], current_rec).get('description', '')} {line}".strip(),
                }

        if current_rec:
            recommendations.append(current_rec)

        if not recommendations and response.strip():
            recommendations.append(
                {
                    "id": "rec_1",
                    "title": "Review Compliance Requirements",
                    "description": "Please review the compliance requirements for your organization.",
                    "priority": "medium",
                    "effort_estimate": "1-2 weeks",
                    "impact_score": 0.6,
                    "resources": ["Compliance team"],
                    "implementation_steps": ["Review the provided guidance"],
                }
            )

        return {
            "recommendations": recommendations[:5],
            "implementation_plan": {
                "phases": [
                    {
                        "phase_number": 1,
                        "phase_name": "Planning",
                        "duration_weeks": 2,
                        "tasks": ["Review requirements", "Plan implementation"],
                        "dependencies": [],
                    },
                    {
                        "phase_number": 2,
                        "phase_name": "Implementation",
                        "duration_weeks": max(len(recommendations) * 2, 4),
                        "tasks": ["Implement recommendations", "Monitor progress"],
                        "dependencies": ["Planning"],
                    },
                    {
                        "phase_number": 3,
                        "phase_name": "Review",
                        "duration_weeks": 2,
                        "tasks": ["Review implementation", "Document results"],
                        "dependencies": ["Implementation"],
                    },
                ],
                "total_timeline_weeks": max(len(recommendations) * 2 + 4, 8),
                "resource_requirements": ["Compliance team", "Technical team"],
            },
            "success_metrics": ["Compliance score improvement", "Risk reduction"],
        }

    def _get_fallback_assessment_recommendations(self, framework_id: str) -> Dict[str, Any]:
        """Provide fallback response when AI assessment recommendations fail."""
        return {
            "recommendations": [
                {
                    "id": "general_rec_1",
                    "title": "Establish Compliance Program",
                    "description": f"Set up a structured compliance program for {framework_id}",
                    "priority": "high",
                    "effort_estimate": "4-6 weeks",
                    "impact_score": 0.8,
                    "implementation_steps": [
                        "Assign compliance team",
                        "Review framework requirements",
                        "Create implementation plan",
                    ],
                }
            ],
            "implementation_plan": {
                "phases": [
                    {
                        "phase_number": 1,
                        "phase_name": "Planning and Assessment",
                        "duration_weeks": 4,
                        "tasks": ["Identify owners", "Review requirements"],
                        "dependencies": [],
                    }
                ],
                "total_timeline_weeks": 4,
                "resource_requirements": ["Compliance team"],
            },
            "success_metrics": ["Program established", "Roadmap approved"],
            "framework_id": framework_id,
            "is_fallback": True,
        }

    # ============================================================================
    # Backward-Compatibility Delegations
    # ============================================================================
    # These methods delegate to domain services so that existing tests and callers
    # that invoke private helper methods on ComplianceAssistant still work.

    async def _analyze_compliance_maturity(
        self,
        business_context: Dict[str, Any],
        existing_evidence: List[Dict],
        framework: str,
    ) -> Dict[str, Any]:
        """Delegate to workflow_service._analyze_compliance_maturity."""
        # pylint: disable=protected-access
        return await self.workflow_service._analyze_compliance_maturity(
            business_context, existing_evidence, framework
        )

    def _categorize_organization_size(self, employee_count: int) -> str:
        """Delegate to workflow_service._categorize_organization_size."""
        # pylint: disable=protected-access
        return self.workflow_service._categorize_organization_size(employee_count)

    def _prioritize_recommendations(
        self,
        recommendations: List[Dict[str, Any]],
        business_context: Dict[str, Any],
        maturity_analysis: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Delegate to evidence_service._prioritize_recommendations."""
        # pylint: disable=protected-access
        return self.evidence_service._prioritize_recommendations(
            recommendations, business_context, maturity_analysis
        )

    def _add_automation_insights(
        self, recommendations: List[Dict[str, Any]], business_context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Delegate to evidence_service._add_automation_insights."""
        # pylint: disable=protected-access
        return self.evidence_service._add_automation_insights(recommendations, business_context)

    def _calculate_total_effort(self, recommendations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Delegate to evidence_service._calculate_total_effort."""
        # pylint: disable=protected-access
        return self.evidence_service._calculate_total_effort(recommendations)

    def _get_fallback_recommendations(
        self, framework: str, maturity_analysis: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Delegate to fallback_generator.get_recommendations."""
        return self.fallback_generator.get_recommendations(framework, maturity_analysis)

    def _calculate_workflow_effort(self, workflow: Dict[str, Any]) -> Dict[str, Any]:
        """Delegate to workflow_service._calculate_workflow_effort."""
        # pylint: disable=protected-access
        return self.workflow_service._calculate_workflow_effort(workflow)

    def _apply_healthcare_customizations(self, policy: Dict[str, Any]) -> Dict[str, Any]:
        """Delegate to policy_service._apply_healthcare_customizations."""
        # pylint: disable=protected-access
        return self.policy_service._apply_healthcare_customizations(policy)

    def _apply_financial_customizations(self, policy: Dict[str, Any]) -> Dict[str, Any]:
        """Delegate to policy_service._apply_financial_customizations."""
        # pylint: disable=protected-access
        return self.policy_service._apply_financial_customizations(policy)

    def _apply_size_customizations(self, policy: Dict[str, Any], org_size: str) -> Dict[str, Any]:
        """Delegate to policy_service._apply_size_customizations."""
        # pylint: disable=protected-access
        return self.policy_service._apply_size_customizations(policy, org_size)

    def _generate_policy_implementation_guidance(
        self,
        policy: Dict[str, Any],
        business_context: Dict[str, Any],
        maturity_analysis: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Delegate to policy_service._generate_policy_implementation_guidance."""
        # pylint: disable=protected-access
        return self.policy_service._generate_policy_implementation_guidance(
            policy, business_context, maturity_analysis
        )

    def _generate_compliance_mapping(
        self, policy: Dict[str, Any], framework: str, policy_type: str
    ) -> Dict[str, Any]:
        """Delegate to policy_service._generate_compliance_mapping."""
        # pylint: disable=protected-access
        return self.policy_service._generate_compliance_mapping(policy, framework, policy_type)

    def _get_fallback_policy(
        self, framework: str, policy_type: str, business_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Delegate to policy_service._get_fallback_policy."""
        # pylint: disable=protected-access
        return self.policy_service._get_fallback_policy(framework, policy_type, business_context)
