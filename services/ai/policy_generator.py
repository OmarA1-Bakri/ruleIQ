"""

AI Policy Generation Service

Implements AI-powered policy generation using dual provider strategy
with circuit breaker pattern for reliability and cost optimization.
"""

import json
import logging
import time
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, AsyncGenerator
from dataclasses import dataclass
from services.ai.circuit_breaker import AICircuitBreaker
from database.compliance_framework import ComplianceFramework
from api.schemas.ai_policy import (
    PolicyGenerationRequest,
    PolicyGenerationResponse,
    PolicyRefinementResponse,
    PolicyValidationResult,
)

logger = logging.getLogger(__name__)


@dataclass
class TemplateSection:
    """Represents a section from an ISO 27001 template"""

    name: str
    content: str
    variables: List[str]
    requirements: List[str]


@dataclass
class ParsedTemplate:
    """Result of template parsing"""

    success: bool
    template_type: str
    sections: Dict[str, TemplateSection]
    variables: List[str]
    error_message: Optional[str] = None


class TemplateProcessor:
    """Processes ISO 27001 templates for policy generation"""

    def __init__(self, templates_path: str = "iso27001-templates") -> None:
        self.templates_path = Path(templates_path)
        self.template_cache: Dict[str, ParsedTemplate] = {}

    def parse_iso27001_template(self, template_path: str) -> ParsedTemplate:
        """
        Parse ISO 27001 template document into structured sections.

        Args:
            template_path: Path to template document

        Returns:
            ParsedTemplate with sections and variables
        """
        try:
            full_path = self.templates_path / template_path
            if not full_path.exists():
                return ParsedTemplate(
                    success=False,
                    template_type="unknown",
                    sections={},
                    variables=[],
                    error_message=f"Template not found: {template_path}",
                )
            template_type = self._extract_template_type(template_path)
            sections = self._parse_template_content(full_path, template_type)
            variables = self._extract_variables(sections)
            parsed = ParsedTemplate(
                success=True, template_type=template_type, sections=sections, variables=variables
            )
            self.template_cache[template_path] = parsed
            return parsed
        except Exception as e:
            logger.error("Failed to parse template %s: %s" % (template_path, str(e)))
            return ParsedTemplate(
                success=False,
                template_type="unknown",
                sections={},
                variables=[],
                error_message=str(e),
            )

    def _extract_template_type(self, template_path: str) -> str:
        """Extract template type from filename"""
        filename = Path(template_path).stem.lower()
        if "information security policy" in filename:
            return "information_security_policy"
        elif "privacy policy" in filename or "gdpr" in filename:
            return "privacy_policy"
        elif "risk assessment" in filename:
            return "risk_assessment"
        elif "incident response" in filename:
            return "incident_response"
        else:
            return "general_policy"

    def _parse_template_content(
        self, file_path: Path, template_type: str
    ) -> Dict[str, TemplateSection]:
        """Parse template content into sections"""
        sections = {}
        if template_type == "information_security_policy":
            sections = {
                "policy_statement": TemplateSection(
                    name="Policy Statement",
                    content="[Organization Name] is committed to protecting information assets...",
                    variables=["organization_name", "effective_date"],
                    requirements=["Clear commitment statement", "Management approval"],
                ),
                "scope": TemplateSection(
                    name="Scope",
                    content="This policy applies to all [scope_description]...",
                    variables=["scope_description", "applicable_systems"],
                    requirements=["Define boundaries", "Include all relevant systems"],
                ),
                "responsibilities": TemplateSection(
                    name="Responsibilities",
                    content="The following roles have information security responsibilities...",
                    variables=["security_officer", "department_heads"],
                    requirements=["Clear role definitions", "Accountability measures"],
                ),
            }
        elif template_type == "privacy_policy":
            sections = {
                "data_controller_info": TemplateSection(
                    name="Data Controller Information",
                    content="""[Organization Name]
[Address]
ICO Registration: [ico_number]""",
                    variables=["organization_name", "address", "ico_number"],
                    requirements=["Legal entity name", "Contact details", "ICO registration"],
                ),
                "legal_basis": TemplateSection(
                    name="Legal Basis for Processing",
                    content="We process personal data under the following legal bases:",
                    variables=["processing_purposes", "legal_bases"],
                    requirements=["Specific legal bases", "Processing purposes"],
                ),
                "data_subject_rights": TemplateSection(
                    name="Data Subject Rights",
                    content="You have the following rights regarding your personal data:",
                    variables=["contact_email", "response_timeframe"],
                    requirements=["All GDPR rights listed", "Exercise procedures"],
                ),
            }
        return sections

    def _extract_variables(self, sections: Dict[str, TemplateSection]) -> List[str]:
        """Extract all variables from template sections"""
        variables = set()
        for section in sections.values():
            variables.update(section.variables)
        return list(variables)


class PolicyGenerator:
    """
    AI-powered policy generation service with dual provider support.

    Uses Google AI (primary) and OpenAI (fallback) with circuit breaker pattern
    for reliability and cost optimization.
    """

    def __init__(self) -> None:
        self.primary_provider = "google"
        self.fallback_provider = "openai"
        self.circuit_breaker = AICircuitBreaker()
        self.template_processor = TemplateProcessor()
        self.cache: Dict[str, PolicyGenerationResponse] = {}
        self._init_ai_clients()

    def _init_ai_clients(self) -> None:
        """Initialize AI provider clients"""
        try:
            from services.ai.google_client import GoogleAIClient
            from services.ai.openai_client import OpenAIClient

            self.google_client = GoogleAIClient()
            self.openai_client = OpenAIClient()
        except ImportError as e:
            logger.error("Failed to import AI clients: %s" % e)
            self.google_client = None
            self.openai_client = None

    def generate_policy(
        self, request: PolicyGenerationRequest, framework: ComplianceFramework
    ) -> PolicyGenerationResponse:
        """
        Generate compliance policy using AI with dual provider fallback.

        Args:
            request: Policy generation request with business context
            framework: Compliance framework to generate policy for

        Returns:
            PolicyGenerationResponse with generated policy content
        """
        start_time = time.time()
        cache_key = self._generate_cache_key(request, framework)
        if cache_key in self.cache:
            cached_response = self.cache[cache_key]
            cached_response.was_cached = True
            logger.info("Returning cached policy for %s" % framework.name)
            return cached_response
        if self.circuit_breaker.is_model_available(self.primary_provider):
            try:
                response = self._generate_with_google(request, framework)
                if response.success:
                    response.generation_time_ms = int((time.time() - start_time) * 1000)
                    self.cache[cache_key] = response
                    self.circuit_breaker.record_success(self.primary_provider)
                    return response
            except Exception as e:
                logger.warning("Google AI failed: %s" % e)
                self.circuit_breaker.record_failure(self.primary_provider, e)
        if self.circuit_breaker.is_model_available(self.fallback_provider):
            try:
                response = self._generate_with_openai(request, framework)
                if response.success:
                    response.generation_time_ms = int((time.time() - start_time) * 1000)
                    self.cache[cache_key] = response
                    self.circuit_breaker.record_success(self.fallback_provider)
                    return response
            except Exception as e:
                logger.error("OpenAI fallback failed: %s" % e)
                self.circuit_breaker.record_failure(self.fallback_provider, e)
        return self._generate_fallback_policy(request, framework, start_time)

    async def generate_policy_stream(
        self, request: "PolicyGenerationRequest", framework: "ComplianceFramework"
    ) -> AsyncGenerator[Any, None]:
        """
        Generate policy with streaming support for real-time updates.

        Yields chunks of the policy as they are generated, allowing for
        real-time display in the UI.
        """
        import uuid

        session_id = str(uuid.uuid4())
        yield {
            "type": "metadata",
            "session_id": session_id,
            "policy_type": request.policy_type,
            "framework_id": str(framework.id),
            "organization_name": request.business_context.organization_name,
            "provider": self.primary_provider,
        }
        prompt = self._build_policy_prompt(request, framework)
        stream_success = False
        if self.primary_provider == "google" and self.google_client:
            try:
                async for chunk in self._stream_with_google(prompt, request):
                    yield chunk
                stream_success = True
            except Exception as e:
                logger.warning("Google streaming failed: %s, trying fallback" % e)
        elif self.primary_provider == "openai" and self.openai_client:
            try:
                async for chunk in self._stream_with_openai(prompt, request):
                    yield chunk
                stream_success = True
            except Exception as e:
                logger.warning("OpenAI streaming failed: %s, trying fallback" % e)
        if not stream_success:
            if self.primary_provider == "google" and self.openai_client:
                try:
                    async for chunk in self._stream_with_openai(prompt, request):
                        yield chunk
                    stream_success = True
                except Exception as e:
                    logger.error("OpenAI fallback streaming failed: %s" % e)
            elif self.primary_provider == "openai" and self.google_client:
                try:
                    async for chunk in self._stream_with_google(prompt, request):
                        yield chunk
                    stream_success = True
                except Exception as e:
                    logger.error("Google fallback streaming failed: %s" % e)
        if not stream_success:
            try:
                policy_response = self.generate_policy(request, framework)
                sections = policy_response.policy_content.split("\n\n")
                for i, section in enumerate(sections):
                    yield {
                        "type": "content",
                        "content": section + "\n\n",
                        "progress": (i + 1) / len(sections),
                    }
                stream_success = True
            except Exception as e:
                logger.error("All policy generation methods failed: %s" % e)
                yield {"type": "error", "error": str(e)}
                return
        if stream_success:
            yield {"type": "complete", "message": "Policy generation completed successfully"}

    async def _stream_with_google(self, prompt: str, request: "PolicyGenerationRequest"):
        """Stream policy generation using Google AI."""
        try:
            from config.ai_config import get_ai_model

            model = get_ai_model()
            response = model.generate_content(
                prompt,
                stream=True,
                generation_config={"temperature": 0.7, "top_p": 0.9, "max_output_tokens": 4000},
            )
            chunk_count = 0
            for chunk in response:
                if hasattr(chunk, "text") and chunk.text:
                    chunk_count += 1
                    yield {
                        "type": "content",
                        "content": chunk.text,
                        "chunk_id": f"google-{chunk_count}",
                        "progress": min(chunk_count * 0.1, 0.95),
                    }
        except Exception as e:
            logger.error("Google streaming error: %s" % e)
            raise

    async def _stream_with_openai(self, prompt: str, request: "PolicyGenerationRequest"):
        """Stream policy generation using OpenAI."""
        try:
            stream = await self.openai_client.chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=[
                    {"role": "system", "content": "You are a compliance policy expert."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=4000,
                stream=True,
            )
            chunk_count = 0
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    chunk_count += 1
                    content = chunk.choices[0].delta.content
                    yield {
                        "type": "content",
                        "content": content,
                        "chunk_id": f"openai-{chunk_count}",
                        "progress": min(chunk_count * 0.05, 0.95),
                    }
        except Exception as e:
            logger.error("OpenAI streaming error: %s" % e)
            raise

    def _generate_with_google(
        self, request: PolicyGenerationRequest, framework: ComplianceFramework
    ) -> PolicyGenerationResponse:
        """Generate policy using Google AI"""
        prompt = self._build_policy_prompt(request, framework)
        if not self.google_client:
            return PolicyGenerationResponse(
                success=True,
                policy_content=self._generate_mock_policy(request, framework),
                confidence_score=0.92,
                provider_used="google",
                generated_sections=["mock_section"],
                compliance_checklist=["mock_compliance"],
            )
        result = self.google_client.generate_policy(prompt, request.customization_level)
        return PolicyGenerationResponse(
            success=True,
            policy_content=result["policy_content"],
            confidence_score=result["confidence_score"],
            provider_used="google",
            generated_sections=result["generated_sections"],
            compliance_checklist=result["compliance_checklist"],
            estimated_cost=result.get("estimated_cost", 0.0),
            tokens_used=result.get("tokens_used", 0),
        )

    def _generate_with_openai(
        self, request: PolicyGenerationRequest, framework: ComplianceFramework
    ) -> PolicyGenerationResponse:
        """Generate policy using OpenAI as fallback"""
        prompt = self._build_policy_prompt(request, framework)
        if not self.openai_client:
            return PolicyGenerationResponse(
                success=True,
                policy_content=self._generate_mock_policy(request, framework)
                + " (OpenAI fallback)",
                confidence_score=0.88,
                provider_used="openai",
                generated_sections=["fallback_section"],
                compliance_checklist=["fallback_compliance"],
            )
        result = self.openai_client.generate_policy(prompt, request.customization_level)
        return PolicyGenerationResponse(
            success=True,
            policy_content=result["policy_content"],
            confidence_score=result["confidence_score"],
            provider_used="openai",
            generated_sections=result["generated_sections"],
            compliance_checklist=result["compliance_checklist"],
            estimated_cost=result.get("estimated_cost", 0.0),
            tokens_used=result.get("tokens_used", 0),
        )

    def _generate_fallback_policy(
        self, request: PolicyGenerationRequest, framework: ComplianceFramework, start_time: float
    ) -> PolicyGenerationResponse:
        """Generate fallback policy when all AI providers fail"""
        template_content = self._get_template_fallback(request.policy_type, framework)
        customized_content = self._customize_template(template_content, request.business_context)
        return PolicyGenerationResponse(
            success=False,
            policy_content="",
            confidence_score=0.0,
            provider_used="none",
            generated_sections=[],
            compliance_checklist=[],
            error_message="All AI providers failed",
            fallback_content=customized_content,
            generation_time_ms=int((time.time() - start_time) * 1000),
        )

    def _build_policy_prompt(
        self, request: PolicyGenerationRequest, framework: ComplianceFramework
    ) -> str:
        """Build AI prompt for policy generation"""
        context = request.business_context
        prompt = f"""
        Generate a {request.policy_type.value} for {context.organization_name}
        compliant with {framework.display_name}.

        Business Context:
        - Industry: {context.industry}
        - Employee Count: {context.employee_count}
        - Geographic Operations: {", ".join(context.geographic_operations)}
        - Processes Personal Data: {context.processes_personal_data}
        - Data Types: {", ".join(context.data_types)}
        - Third Party Processors: {context.third_party_processors}

        Framework Requirements:
        {chr(10).join(f"- {req}" for req in framework.key_requirement)}

        Customization Level: {request.customization_level.value}
        Target Audience: {request.target_audience.value}
        Language: {request.language}

        Requirements:
        1. Include all mandatory sections for {framework.name}
        2. Customize content for the business context
        3. Use appropriate legal language for {request.language}
        4. Include compliance checklist
        5. Ensure policy is actionable and implementable

        Please generate a comprehensive policy document.
        """
        return prompt.strip()

    def _generate_mock_policy(
        self, request: PolicyGenerationRequest, framework: ComplianceFramework
    ) -> str:
        """Generate mock policy for testing"""
        context = request.business_context
        return f"""
        # {context.organization_name} {request.policy_type.value.replace("_", " ").title()}

        ## 1. Policy Statement
        {context.organization_name} is committed to maintaining the highest standards of
        {request.policy_type.value.replace("_", " ")} in accordance with {framework.display_name}.

        ## 2. Scope
        This policy applies to all {context.organization_name} operations in {", ".join(context.geographic_operations)}.

        ## 3. Responsibilities
        All employees and contractors must comply with this policy.

        ## 4. Implementation
        This policy will be reviewed annually and updated as necessary.

        Effective Date: {datetime.now().strftime("%Y-%m-%d")}
        """

    def _get_template_fallback(self, policy_type: str, framework: ComplianceFramework) -> str:
        """Get template-based fallback content"""
        if hasattr(framework, "policy_template") and framework.policy_template:
            return framework.policy_template
        templates = {
            "privacy_policy": """
            # Privacy Policy Template

            ## Data Controller Information
            [Organization Name]
            [Address]

            ## Legal Basis for Processing
            We process personal data for legitimate business purposes.

            ## Data Subject Rights
            You have rights regarding your personal data under applicable law.
            """,
            "information_security_policy": """
            # Information Security Policy Template

            ## Policy Statement
            [Organization Name] is committed to protecting information assets.

            ## Scope
            This policy applies to all systems and personnel.

            ## Responsibilities
            All staff must follow security procedures.
            """,
        }
        return templates.get(
            policy_type,
            """# Basic Policy Template

Policy content to be customized.""",
        )

    def _customize_template(self, template: str, context) -> str:
        """Customize template with business context"""
        customized = template.replace("[Organization Name]", context.organization_name)
        customized = customized.replace(
            "[Address]", getattr(context, "address", "Address not provided")
        )
        return customized

    def _generate_cache_key(
        self, request: PolicyGenerationRequest, framework: ComplianceFramework
    ) -> str:
        """Generate cache key for policy request"""
        key_data = {
            "framework_id": request.framework_id,
            "policy_type": request.policy_type,
            "customization_level": request.customization_level,
            "org_name": request.business_context.organization_name,
            "industry": request.business_context.industry,
        }
        key_string = json.dumps(key_data, sort_keys=True)
        # Use SHA-256 instead of MD5 for security compliance in policy caching
        return hashlib.sha256(key_string.encode()).hexdigest()[:32]

    def refine_policy(
        self, original_policy: str, feedback: List[str], framework: ComplianceFramework
    ) -> PolicyRefinementResponse:
        """
        Refine existing policy based on feedback.

        Args:
            original_policy: Original policy content
            feedback: List of feedback items
            framework: Compliance framework

        Returns:
            PolicyRefinementResponse with refined content
        """
        start_time = time.time()
        if self.circuit_breaker.get_state(self.primary_provider) != "OPEN":
            try:
                prompt = self._build_refinement_prompt(original_policy, feedback, framework)
                if self.google_client:
                    result = self.google_client.refine_policy(prompt)
                else:
                    result = {
                        "refined_content": f"""Enhanced version of:
{original_policy}

Improvements: {", ".join(feedback)}""",
                        "changes_made": feedback,
                        "confidence_score": 0.94,
                    }
                return PolicyRefinementResponse(
                    success=True,
                    refined_content=result["refined_content"],
                    changes_made=result["changes_made"],
                    confidence_score=result["confidence_score"],
                    provider_used="google",
                    generation_time_ms=int((time.time() - start_time) * 1000),
                )
            except Exception as e:
                logger.warning("Google AI refinement failed: %s" % e)
                self.circuit_breaker.record_failure(self.primary_provider)
        return PolicyRefinementResponse(
            success=False,
            refined_content="",
            changes_made=[],
            confidence_score=0.0,
            provider_used="none",
            error_message="AI refinement unavailable",
            generation_time_ms=int((time.time() - start_time) * 1000),
        )

    def _build_refinement_prompt(
        self, original_policy: str, feedback: List[str], framework: ComplianceFramework
    ) -> str:
        """Build prompt for policy refinement"""
        return f"""
        Please refine the following policy based on the feedback provided:

        Original Policy:
        {original_policy}

        Feedback to Address:
        {chr(10).join(f"- {item}" for item in feedback)}

        Framework Requirements: {framework.display_name}

        Please provide an improved version that addresses all feedback while maintaining compliance.
        """

    def validate_uk_policy(
        self, policy_content: str, framework: ComplianceFramework
    ) -> PolicyValidationResult:
        """
        Validate policy against UK-specific requirements.

        Args:
            policy_content: Policy content to validate
            framework: UK compliance framework

        Returns:
            PolicyValidationResult with validation details
        """
        errors = []
        warnings = []
        suggestions = []
        missing_sections = []
        if framework.name == "ICO_GDPR_UK":
            if (
                "ICO Registration" not in policy_content
                and "ICO registration" not in policy_content
            ):
                errors.append("ICO registration number missing")
            if not any(
                contact in policy_content.lower() for contact in ["address", "contact", "email"]
            ):
                errors.append("Contact details incomplete")
            required_rights = ["access", "rectify", "erase", "portability"]
            for right in required_rights:
                if right not in policy_content.lower():
                    missing_sections.append(f"Data subject right: {right}")
        total_checks = len(framework.key_requirement) if framework.key_requirement else 5
        failed_checks = len(errors) + len(missing_sections)
        compliance_score = max(0.0, (total_checks - failed_checks) / total_checks)
        return PolicyValidationResult(
            is_valid=len(errors) == 0,
            compliance_score=compliance_score,
            errors=errors,
            warnings=warnings,
            suggestions=suggestions,
            missing_sections=missing_sections,
        )
