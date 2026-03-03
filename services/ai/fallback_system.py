"""
Fallback Response System for AI Services

Provides graceful degradation with pre-defined responses when AI services
are unavailable or experiencing issues. Includes static templates and
cached response management.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, Optional

from services.ai.exceptions import AIServiceException


class FallbackLevel(Enum):
    """Levels of fallback degradation"""

#     NONE = "none"  # No fallback, fail immediately  # Unused variable
#     BASIC = "basic"  # Basic static responses  # Unused variable
#     CACHED = "cached"  # Use cached responses  # Unused variable
#     TEMPLATE = "template"  # Use response templates  # Unused variable
#     COMPREHENSIVE = "comprehensive"  # Full fallback system  # Unused variable


@dataclass
class FallbackResponse:
    """Structure for fallback responses"""

    content: str
    confidence: float = 0.5  # Confidence in the fallback response (0-1)
    source: str = "fallback"  # Source of the response
    generated_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses"""
        return {
            "content": self.content,
            "confidence": self.confidence,
            "source": self.source,
            "generated_at": self.generated_at.isoformat(),
            "metadata": self.metadata,
            "fallback": True,
        }


class FallbackTemplateManager:
    """Manages fallback response templates"""

    def __init__(self) -> None:
        self.templates = self._initialize_templates()
        self.logger = logging.getLogger(__name__)

    def _initialize_templates(self) -> Dict[str, Dict[str, Any]]:
        """Initialize static fallback templates"""
        return {
            # Assessment help templates
            "assessment_help": {
                "gdpr": {
                    "content": """**GDPR Assessment Guidance**

Key areas to focus on for GDPR compliance:

1. **Lawful Basis for Processing**
   - Identify your lawful basis for each data processing activity
   - Document and communicate the basis to data subjects

2. **Data Subject Rights**
   - Implement procedures for handling data subject requests
   - Ensure you can respond within 30 days

3. **Data Protection Impact Assessments (DPIA)**
   - Conduct DPIAs for high-risk processing activities
   - Document the assessment process and outcomes

4. **Privacy by Design**
   - Implement privacy considerations from the design stage
   - Use data minimization principles

5. **Data Breach Procedures**
   - Establish incident response procedures
   - Ensure 72-hour notification capability to supervisory authority

*Note: This is a simplified guidance. Please consult with legal experts for comprehensive compliance.*""",
                    "confidence": 0.7,
                    "metadata": {"framework": "GDPR", "type": "assessment_help"},
                },
                "iso27001": {
                    "content": """**ISO 27001 Assessment Guidance**

Key areas for Information Security Management System:

1. **Information Security Policy**
   - Develop comprehensive security policies
   - Ensure management commitment and communication

2. **Risk Assessment and Treatment**
   - Identify and assess information security risks
   - Implement appropriate risk treatment measures

3. **Asset Management**
   - Maintain an inventory of information assets
   - Classify assets based on their importance

4. **Access Control**
   - Implement proper user access management
   - Regular review of access rights

5. **Incident Management**
   - Establish incident response procedures
   - Document and learn from security incidents

*Note: This is basic guidance. Detailed assessment requires expert consultation.*""",
                    "confidence": 0.7,
                    "metadata": {"framework": "ISO27001", "type": "assessment_help"},
                },
                "general": {
                    "content": """**General Compliance Assessment Guidance**

Universal compliance principles to consider:

1. **Documentation**
   - Maintain comprehensive records of all compliance activities
   - Ensure documentation is current and accessible

2. **Risk Assessment**
   - Regularly assess risks in your business operations
   - Implement controls proportionate to identified risks

3. **Training and Awareness**
   - Provide regular compliance training to staff
   - Ensure awareness of relevant regulations

4. **Monitoring and Review**
   - Establish regular compliance monitoring procedures
   - Review and update compliance measures periodically

5. **Incident Response**
   - Develop clear incident response procedures
   - Practice and test response capabilities

*Note: This is general guidance. Specific regulatory requirements may vary.*""",
                    "confidence": 0.6,
                    "metadata": {"framework": "general", "type": "assessment_help"},
                },
            },
            # Assessment recommendations
            "assessment_recommendations": {
                "high_risk": {
                    "content": """**High Priority Compliance Recommendations**

Based on common compliance gaps, prioritize these actions:

**Immediate Actions (1-30 days):**
1. Document current data processing activities
2. Implement basic access controls
3. Establish incident response contact procedures
4. Create employee awareness communications

**Short-term Actions (1-3 months):**
1. Conduct comprehensive risk assessment
2. Develop detailed compliance policies
3. Implement monitoring and logging systems
4. Establish vendor management procedures

**Medium-term Actions (3-6 months):**
1. Complete staff training programs
2. Implement advanced security controls
3. Establish regular compliance auditing
4. Develop business continuity plans

*Note: Specific recommendations depend on your business context and applicable regulations.*""",
                    "confidence": 0.6,
                    "metadata": {"risk_level": "high", "type": "recommendations"},
                },
                "medium_risk": {
                    "content": """**Medium Priority Compliance Recommendations**

Focus on strengthening existing compliance measures:

**Enhancement Actions:**
1. Review and update existing policies
2. Strengthen monitoring and reporting procedures
3. Enhance staff training and awareness
4. Improve documentation and record-keeping

**Optimization Actions:**
1. Automate routine compliance tasks
2. Establish key performance indicators
3. Implement continuous improvement processes
4. Strengthen vendor and third-party management

*Note: Continue regular monitoring and periodic reviews of your compliance program.*""",
                    "confidence": 0.6,
                    "metadata": {"risk_level": "medium", "type": "recommendations"},
                },
            },
            # Service unavailable messages
            "service_unavailable": {
                "content": """**AI Service Temporarily Unavailable**

Our AI analysis service is currently experiencing issues. Please try again later.

**Alternative Actions:**
1. Review our compliance resource library
2. Contact our support team for manual assistance
3. Use the basic assessment templates available in your dashboard
4. Schedule a consultation with our compliance experts

We apologize for the inconvenience and are working to restore full service quickly.""",
                "confidence": 0.9,
                "metadata": {"type": "service_unavailable"},
            },
        }

    def get_template(
        self, template_type: str, subtype: str = "general"
    ) -> Optional[Dict[str, Any]]:
        """Get a fallback template"""
        if template_type in self.templates:
            if subtype in self.templates[template_type]:
                return self.templates[template_type][subtype]
            elif "general" in self.templates[template_type]:
                return self.templates[template_type]["general"]
        return None

    def get_assessment_help_fallback(
        self, framework: str = "general"
    ) -> FallbackResponse:
        """Get fallback response for assessment help"""
        template = self.get_template("assessment_help", framework.lower())

        if template:
            return FallbackResponse(
                content=template["content"],
                confidence=template["confidence"],
                source="static_template",
                metadata=template["metadata"],
            )
        else:
            return FallbackResponse(
                content="Assessment guidance is temporarily unavailable. Please contact support.",
                confidence=0.3,
                source="default_fallback",
            )

    def get_recommendations_fallback(
        self, risk_level: str = "medium"
    ) -> FallbackResponse:
        """Get fallback response for recommendations"""
        template = self.get_template("assessment_recommendations", risk_level.lower())

        if template:
            return FallbackResponse(
                content=template["content"],
                confidence=template["confidence"],
                source="static_template",
                metadata=template["metadata"],
            )
        else:
            return FallbackResponse(
                content=(
                    "Recommendations are temporarily unavailable. Please contact support for personalized "
                    "guidance."
                ),
                confidence=0.3,
                source="default_fallback",
            )

    def get_service_unavailable_fallback(self) -> FallbackResponse:
        """Get service unavailable message"""
        template = self.templates["service_unavailable"]

        return FallbackResponse(
            content=template["content"],
            confidence=template["confidence"],
            source="service_status",
            metadata=template["metadata"],
        )


class CacheManager:
    """Manages cached AI responses for fallback use"""

    def __init__(self, cache_ttl_hours: int = 24) -> None:
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.cache_ttl = timedelta(hours=cache_ttl_hours)
        self.logger = logging.getLogger(__name__)

    def _generate_cache_key(self, operation: str, context: Dict[str, Any]) -> str:
        """Generate cache key from operation and context"""
        # Create a simple hash of the operation and key context elements
        key_elements = [operation]

        # Add framework if present
        if "framework" in context:
            key_elements.append(f"fw:{context['framework']}")

        # Add business type if present
        if "business_type" in context:
            key_elements.append(f"bt:{context['business_type']}")

        return "|".join(key_elements)

    def store_response(
        self, operation: str, context: Dict[str, Any], response: str
    ) -> None:
        """Store a successful AI response in cache"""
        cache_key = self._generate_cache_key(operation, context)

        self.cache[cache_key] = {
            "response": response,
            "stored_at": datetime.now(),
            "context": context,
            "operation": operation,
        }

        self.logger.debug(f"Cached response for key: {cache_key}")

    def get_cached_response(
        self, operation: str, context: Dict[str, Any]
    ) -> Optional[FallbackResponse]:
        """Get cached response if available and not expired"""
        cache_key = self._generate_cache_key(operation, context)

        if cache_key in self.cache:
            cached_item = self.cache[cache_key]

            # Check if cache is still valid
            if datetime.now() - cached_item["stored_at"] < self.cache_ttl:
                self.logger.info(f"Using cached response for: {cache_key}")

                return FallbackResponse(
                    content=cached_item["response"],
                    confidence=0.8,  # High confidence in recent cache
                    source="cached_response",
                    metadata={
                        "cached_at": cached_item["stored_at"].isoformat(),
                        "cache_key": cache_key,
                    },
                )
            else:
                # Remove expired cache
                del self.cache[cache_key]
                self.logger.debug(f"Removed expired cache for: {cache_key}")

        return None

    def clear_expired_cache(self) -> None:
        """Remove all expired cache entries"""
        current_time = datetime.now()
        expired_keys = []

        for key, item in self.cache.items():
            if current_time - item["stored_at"] >= self.cache_ttl:
                expired_keys.append(key)

        for key in expired_keys:
            del self.cache[key]

        if expired_keys:
            self.logger.info(f"Cleared {len(expired_keys)} expired cache entries")


class FallbackSystem:
    """
    Comprehensive fallback system for AI services
    """

    def __init__(
        self, fallback_level: FallbackLevel = FallbackLevel.COMPREHENSIVE
    ) -> None:
        self.fallback_level = fallback_level
        self.template_manager = FallbackTemplateManager()
        self.cache_manager = CacheManager()
        self.logger = logging.getLogger(__name__)

        # Track fallback usage
        self.fallback_stats = {
            "total_fallbacks": 0,
            "fallback_by_type": {},
            "fallback_by_source": {},
        }

    def should_use_fallback(self, exception: Exception) -> bool:
        """Determine if fallback should be used for the given exception"""
        if self.fallback_level == FallbackLevel.NONE:
            return False

        # Always use fallback for service unavailability
        if isinstance(exception, (AIServiceException,)):
            return True

        # Use fallback for timeout and overload exceptions
        from services.ai.exceptions import (
            ModelOverloadedException,
            ModelTimeoutException,
        )

        return bool(
            isinstance(exception, (ModelTimeoutException, ModelOverloadedException)),
        )

    def get_fallback_response(
        self,
        operation: str,
        context: Dict[str, Any],
        exception: Optional[Exception] = None,
    ) -> FallbackResponse:
        """
        Get appropriate fallback response for the given operation and context

        Args:
            operation: Type of operation (e.g., "assessment_help", "recommendations")
            context: Operation context (framework, business_type, etc.)
            exception: The exception that triggered the fallback

        Returns:
            FallbackResponse with appropriate content
        """
        self._update_fallback_stats(operation, "attempt")

        # Try cached response first (if enabled)
        if self.fallback_level in [FallbackLevel.CACHED, FallbackLevel.COMPREHENSIVE]:
            cached_response = self.cache_manager.get_cached_response(operation, context)
            if cached_response:
                self._update_fallback_stats(operation, "cached")
                return cached_response

        # Use templates (if enabled)
        if self.fallback_level in [FallbackLevel.TEMPLATE, FallbackLevel.COMPREHENSIVE]:
            template_response = self._get_template_response(operation, context)
            if template_response:
                self._update_fallback_stats(operation, "template")
                return template_response

        # Basic fallback (if enabled)
        if self.fallback_level in [FallbackLevel.BASIC, FallbackLevel.COMPREHENSIVE]:
            basic_response = self._get_basic_response(operation, exception)
            self._update_fallback_stats(operation, "basic")
            return basic_response

        # This should not happen if levels are configured correctly
        raise AIServiceException(
            message="Fallback system disabled and no alternative available",
            service_name="Fallback System",
            error_code="FALLBACK_DISABLED",
        )

    def _get_template_response(
        self, operation: str, context: Dict[str, Any]
    ) -> Optional[FallbackResponse]:
        """Get response from templates"""
        if operation == "assessment_help":
            framework = context.get("framework", "general")
            return self.template_manager.get_assessment_help_fallback(framework)

        elif operation == "assessment_recommendations":
            # Determine risk level from context
            risk_level = context.get("risk_level", "medium")
            return self.template_manager.get_recommendations_fallback(risk_level)

        return None

    def _get_basic_response(
        self, operation: str, exception: Optional[Exception]
    ) -> FallbackResponse:
        """Get basic fallback response"""
        if exception:
            content = (
                f"The {operation} service is temporarily unavailable due to: {exception!s}. "
                f"Please try again later or contact support."
            )
        else:
            content = f"The {operation} service is temporarily unavailable. Please try again later."

        return FallbackResponse(
            content=content,
            confidence=0.4,
            source="basic_fallback",
            metadata={
                "operation": operation,
                "exception": str(exception) if exception else None,
            },
        )

    def _update_fallback_stats(self, operation: str, source: str) -> None:
        """Update fallback usage statistics"""
        self.fallback_stats["total_fallbacks"] += 1

        if operation not in self.fallback_stats["fallback_by_type"]:
            self.fallback_stats["fallback_by_type"][operation] = 0
        self.fallback_stats["fallback_by_type"][operation] += 1

        if source not in self.fallback_stats["fallback_by_source"]:
            self.fallback_stats["fallback_by_source"][source] = 0
        self.fallback_stats["fallback_by_source"][source] += 1

    def cache_successful_response(
        self, operation: str, context: Dict[str, Any], response: str
    ) -> None:
        """Cache a successful AI response for future fallback use"""
        if self.fallback_level in [FallbackLevel.CACHED, FallbackLevel.COMPREHENSIVE]:
            self.cache_manager.store_response(operation, context, response)

    def get_fallback_statistics(self) -> Dict[str, Any]:
        """Get fallback usage statistics"""
        return {
            "fallback_level": self.fallback_level.value,
            "statistics": self.fallback_stats.copy(),
            "cache_entries": len(self.cache_manager.cache),
            "template_types": list(self.template_manager.templates.keys()),
        }

    def perform_maintenance(self) -> None:
        """Perform routine maintenance (clear expired cache, etc.)"""
        self.cache_manager.clear_expired_cache()
        self.logger.info("Fallback system maintenance completed")


# Global fallback system instance
_fallback_system: Optional[FallbackSystem] = None


def get_fallback_system(
    fallback_level: FallbackLevel = FallbackLevel.COMPREHENSIVE,
) -> FallbackSystem:
    """Get global fallback system instance"""
    global _fallback_system
    if _fallback_system is None:
        _fallback_system = FallbackSystem(fallback_level)
    return _fallback_system


def reset_fallback_system() -> None:
    """Reset global fallback system (for testing)"""
    global _fallback_system
    _fallback_system = None
