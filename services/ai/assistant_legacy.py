"""
LEGACY FILE - DO NOT USE DIRECTLY

This file contains the original 4,032-line ComplianceAssistant implementation.
It has been refactored into a modular architecture:
- services/ai/providers/ - AI provider abstraction
- services/ai/response/ - Response generation and parsing
- services/ai/domains/ - Domain-specific services
- services/ai/assistant_facade.py - Backward-compatible façade

This file is preserved for reference and will be removed after successful
migration and verification.

Date: 2025-09-30
Refactoring: AI Assistant Modular Architecture

ORIGINAL DOCSTRING:
The primary AI service that orchestrates the conversational flow, classifies user intent,
and generates intelligent responses asynchronously.
"""

import requests
import logging


logger = logging.getLogger(__name__)
import asyncio
import json
from datetime import datetime
from datetime import timezone
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple
from uuid import UUID, uuid4
from google.generativeai.types import HarmBlockThreshold, HarmCategory
from sqlalchemy.ext.asyncio import AsyncSession
from config.ai_config import get_ai_model
from config.logging_config import get_logger
from core.exceptions import (
    BusinessLogicException,
    DatabaseException,
    IntegrationException,
    NotFoundException,
)
from database.user import User
from .analytics_monitor import MetricType, get_analytics_monitor
from .cached_content import get_cached_content_manager, CacheContentType
from .circuit_breaker import AICircuitBreaker
from .context_manager import ContextManager
from .exceptions import CircuitBreakerException, ModelUnavailableException
from .safety_manager import SafetyDecision, ContentType
from .instruction_integration import get_instruction_manager
from .performance_optimizer import get_performance_optimizer
from .prompt_templates import PromptTemplates
from .quality_monitor import get_quality_monitor
from .response_cache import get_ai_cache
from .tools import get_tool_schemas, tool_executor
import contextlib

logger = get_logger(__name__)


class ComplianceAssistant:
    """AI-powered compliance assistant using Google Gemini, with full async support."""

    def __init__(self, db: AsyncSession, user_context: Optional[Dict[str, Any]] = None) -> None:
        self.db = db
        self.user_context = user_context or {}
        self.model = None
        self.context_manager = ContextManager(db)
        self.prompt_templates = PromptTemplates()
        self.instruction_manager = get_instruction_manager()
        self.ai_cache = None
        self.cached_content_manager = None
        self.performance_optimizer = None
        self.analytics_monitor = None
        self.quality_monitor = None
        self.circuit_breaker = AICircuitBreaker()
        from services.ai.safety_manager import get_safety_manager_for_user, ContentType

        self.safety_manager = get_safety_manager_for_user(self.user_context)
        self.content_type_map = {
            "assessment_help": ContentType.ASSESSMENT_GUIDANCE,
            "evidence_recommendations": ContentType.EVIDENCE_CLASSIFICATION,
            "policy_generation": ContentType.POLICY_GENERATION,
            "compliance_analysis": ContentType.COMPLIANCE_ANALYSIS,
            "general": ContentType.GENERAL_QUESTION,
        }
        self.safety_settings = {
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_ONLY_HIGH,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
        }

    def _get_task_appropriate_model(
        self,
        task_type: str,
        context: Optional[Dict[str, Any]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        cached_content=None,
    ) -> Tuple[Any, str]:
        """
        Get the most appropriate model for the given task type with system instructions and circuit breaker protection

        Args:
            task_type: Type of task (help, analysis, recommendations, etc.)
            context: Additional context for model selection
            tools: List of tool schemas for function calling
            cached_content: Optional Google CachedContent for improved performance

        Returns:
            Tuple of (configured AI model instance, instruction_id)

        Raises:
            ModelUnavailableException: If no models are available
        """
        {
            "task_type": task_type,
            "prompt_length": context.get("prompt_length", 0) if context else 0,
            "framework": context.get("framework") if context else None,
            "business_context": context.get("business_context", {}) if context else {},
        }
        if task_type in ["help", "guidance"]:
            complexity = "simple"
            prefer_speed = True
        elif task_type in ["analysis", "assessment", "gap_analysis"]:
            complexity = "complex"
            prefer_speed = False
        elif task_type in ["recommendations", "followup"]:
            complexity = "medium"
            prefer_speed = False
        else:
            complexity = "auto"
            prefer_speed = False
        try:
            model, instruction_id = self.instruction_manager.get_model_with_instruction(
                instruction_type=task_type,
                framework=context.get("framework") if context else None,
                business_profile=context.get("business_context", {}) if context else None,
                task_complexity=complexity,
                tools=tools,
                prefer_speed=prefer_speed,
            )
            if cached_content:
                model._cached_content = cached_content
                logger.debug("Attached cached content to model for %s" % task_type)
            model_name = getattr(model, "model_name", "unknown")
            if not self.circuit_breaker.is_model_available(model_name):
                logger.warning("Model %s unavailable, trying fallback" % model_name)
                fallback_model = get_ai_model()
                fallback_model_name = getattr(fallback_model, "model_name", "unknown")
                if not self.circuit_breaker.is_model_available(fallback_model_name):
                    raise ModelUnavailableException(
                        model_name=fallback_model_name,
                        reason="All models unavailable due to circuit breaker",
                    )
                return fallback_model, "fallback_default"
            return model, instruction_id
        except (OSError, requests.RequestException) as e:
            logger.error("Failed to get model for %s: %s" % (task_type, e))
            raise ModelUnavailableException(
                model_name="unknown", reason=f"Model selection failed: {e!s}"
            )

    async def _get_cached_content_manager(self):
        """Initialize and return the cached content manager."""
        if self.cached_content_manager is None:
            self.cached_content_manager = await get_cached_content_manager()
        return self.cached_content_manager

    async def _get_or_create_assessment_cache(
        self,
        framework_id: str,
        business_profile: Dict[str, Any],
        assessment_context: Optional[Dict[str, Any]] = None,
    ):
        """
        Get or create cached content for assessment context.

        Args:
            framework_id: Compliance framework ID
            business_profile: Business profile data
            assessment_context: Additional assessment context

        Returns:
            CachedContent instance or None if caching fails
        """
        try:
            cached_content_manager = await self._get_cached_content_manager()
            cached_content = await cached_content_manager.create_assessment_cache(
                framework_id=framework_id,
                business_profile=business_profile,
                assessment_context=assessment_context,
            )
            if cached_content:
                logger.info("Using cached content for assessment: %s" % framework_id)
                return cached_content
            else:
                logger.warning("Failed to create cached content for assessment: %s" % framework_id)
                return None
        except OSError as e:
            logger.warning("Error with cached content for assessment: %s" % e)
            return None

    async def _handle_function_calls(
        self, response, context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Handle function calls from AI model responses

        Args:
            response: AI model response that may contain function calls
            context: Additional context for function execution

        Returns:
            Dictionary containing function call results and next steps
        """
        function_results = []
        try:
            if hasattr(response, "candidates") and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate.content, "parts"):
                    for part in candidate.content.parts:
                        if hasattr(part, "function_call"):
                            function_call = part.function_call
                            function_name = function_call.name
                            function_args = dict(function_call.args) if function_call.args else {}
                            logger.info(
                                "Executing function call: %s with args: %s"
                                % (function_name, function_args)
                            )
                            result = await tool_executor.execute_tool(
                                tool_name=function_name, parameters=function_args, context=context
                            )
                            function_results.append(
                                {
                                    "function_name": function_name,
                                    "parameters": function_args,
                                    "result": result.to_dict(),
                                    "execution_time": result.execution_time,
                                }
                            )
                            if result.success:
                                logger.info(
                                    "Function %s executed successfully in %ss"
                                    % (function_name, result.execution_time)
                                )
                            else:
                                logger.error(
                                    "Function %s failed: %s" % (function_name, result.error)
                                )
            return {
                "has_function_calls": len(function_results) > 0,
                "function_results": function_results,
                "execution_count": len(function_results),
            }
        except (Exception, KeyError, IndexError) as e:
            logger.error("Error handling function calls: %s" % e)
            return {
                "has_function_calls": False,
                "function_results": [],
                "execution_count": 0,
                "error": str(e),
            }

    async def _generate_response_with_tools(
        self,
        prompt: str,
        task_type: str = "analysis",
        tool_names: Optional[List[str]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Generate AI response with function calling support

        Args:
            prompt: Input prompt for the AI model
            task_type: Type of task for model selection
            tool_names: Specific tools to include (if None, includes all relevant tools)
            context: Additional context for execution

        Returns:
            Dictionary containing response text, function call results, and metadata
        """
        try:
            if tool_names:
                tools = get_tool_schemas(tool_names)
            else:
                tools = self._get_tools_for_task(task_type)
            model, instruction_id = self._get_task_appropriate_model(task_type, context, tools)
            logger.info("Generating response with %s tools for task: %s" % (len(tools), task_type))
            response = model.generate_content(prompt)
            function_call_results = await self._handle_function_calls(response, context)
            response_text = ""
            if hasattr(response, "text") and response.text:
                response_text = response.text
            elif hasattr(response, "candidates") and response.candidates:
                for part in response.candidates[0].content.parts:
                    if hasattr(part, "text") and part.text:
                        response_text += part.text
            try:
                from .instruction_monitor import InstructionMetricType

                self.instruction_manager.record_instruction_usage(
                    instruction_id,
                    metric_type=InstructionMetricType.RESPONSE_QUALITY,
                    value=0.8,
                    context={
                        "task_type": task_type,
                        "tools_used": len(tools),
                        "function_calls": function_call_results.get("has_function_calls", False),
                    },
                )
            except requests.RequestException as e:
                logger.warning("Failed to record instruction usage: %s" % e)
            return {
                "response_text": response_text,
                "function_calls": function_call_results,
                "tools_used": [tool["name"] for tool in tools],
                "model_used": getattr(model, "model_name", "unknown"),
                "instruction_id": instruction_id,
                "success": True,
            }
        except (requests.RequestException, KeyError, IndexError) as e:
            logger.error("Error generating response with tools: %s" % e)
            return {
                "response_text": f"I apologize, but I encountered an error while processing your request: {e!s}",
                "function_calls": {"has_function_calls": False, "function_results": []},
                "tools_used": [],
                "model_used": "unknown",
                "success": False,
                "error": str(e),
            }

    def _get_tools_for_task(self, task_type: str) -> List[Dict[str, Any]]:
        """
        Get appropriate tools based on task type

        Args:
            task_type: Type of task being performed

        Returns:
            List of tool schemas appropriate for the task
        """
        task_tool_mapping = {
            "gap_analysis": ["extract_compliance_gaps"],
            "recommendations": ["generate_compliance_recommendations"],
            "regulation_lookup": ["lookup_industry_regulations", "check_compliance_requirements"],
            "assessment": ["extract_compliance_gaps", "generate_compliance_recommendations"],
            "analysis": ["extract_compliance_gaps", "lookup_industry_regulations"],
            "help": ["lookup_industry_regulations", "check_compliance_requirements"],
            "guidance": ["check_compliance_requirements"],
        }
        tool_names = task_tool_mapping.get(
            task_type,
            [
                "extract_compliance_gaps",
                "generate_compliance_recommendations",
                "lookup_industry_regulations",
            ],
        )
        return get_tool_schemas(tool_names)

    async def process_message(
        self, conversation_id: UUID, user: User, message: str, business_profile_id: UUID
    ) -> Tuple[str, Dict[str, Any]]:
        """Processes a user's message and generates a contextual response with performance optimizations."""
        try:
            processing_start = datetime.now(timezone.utc)
            adversarial_check = self._handle_adversarial_input(message)
            if adversarial_check["is_adversarial"]:
                return adversarial_check["response"], {
                    "timestamp": processing_start.isoformat(),
                    "context_used": False,
                    "safety_triggered": True,
                    "intent": "adversarial_blocked",
                    "processing_time_ms": 0,
                }
            parallel_tasks = [
                asyncio.create_task(asyncio.to_thread(self._classify_intent, message)),
                asyncio.create_task(asyncio.to_thread(self._extract_entities, message)),
                asyncio.create_task(
                    self.context_manager.get_conversation_context(
                        conversation_id, business_profile_id
                    )
                ),
            ]
            try:
                intent_result, entities, context = await asyncio.wait_for(
                    asyncio.gather(*parallel_tasks), timeout=5.0
                )
            except asyncio.TimeoutError:
                logger.warning(
                    "Parallel processing timed out, using fallbacks",
                )
                intent_result = {"intent": "general", "confidence": 0.5, "framework": None}
                entities = {}
                context = {"company_size": "unknown", "industry": "unknown"}
            optimized_context = {
                **context,
                "timeout": 8.0,
                "priority": "speed",
            }
            try:
                response_text = await asyncio.wait_for(
                    self._generate_response(message, optimized_context, intent_result, entities),
                    timeout=10.0,
                )
            except asyncio.TimeoutError:
                logger.warning("Response generation timed out, using fallback")
                response_text = self._get_fallback_response_text(message, optimized_context)
            try:
                safety_check = await asyncio.wait_for(
                    asyncio.to_thread(self._validate_response_safety, response_text),
                    timeout=1.0,
                )
                if not safety_check["is_safe"]:
                    response_text = safety_check["modified_response"]
            except asyncio.TimeoutError:
                logger.warning("Safety validation timed out, using response as-is")
                safety_check = {"is_safe": True, "safety_score": 0.8}
            follow_up_task = asyncio.create_task(
                asyncio.to_thread(
                    self._generate_follow_ups,
                    {"intent": intent_result, "entities": entities, "context": context},
                )
            )
            processing_end = datetime.now(timezone.utc)
            processing_time = (processing_end - processing_start).total_seconds()
            logger.info("Message processed in %ss (optimized)" % processing_time)
            try:
                follow_ups = await asyncio.wait_for(
                    follow_up_task,
                    timeout=2.0,
                )
            except asyncio.TimeoutError:
                logger.info("Follow-up generation timed out, skipping")
                follow_ups = []
            metadata = {
                "timestamp": processing_end.isoformat(),
                "context_used": True,
                "intent": intent_result.get("intent", "general"),
                "framework": intent_result.get("framework"),
                "confidence": intent_result.get("confidence", 0.5),
                "entities": entities,
                "safety_score": safety_check.get("safety_score", 0.8),
                "follow_up_suggestions": follow_ups,
                "processing_time_ms": int(processing_time * 1000),
                "optimized": True,
                "performance_mode": "fast",
            }
            return response_text, metadata
        except (NotFoundException, DatabaseException, IntegrationException) as e:
            logger.warning(
                "Known exception while processing message for conversation %s: %s"
                % (conversation_id, e)
            )
            raise
        except (requests.RequestException, Exception, ValueError) as e:
            logger.error(
                "Unexpected error processing message for conversation %s: %s"
                % (conversation_id, e),
                exc_info=True,
            )
            return self._get_fallback_response_text(message, {}), {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error": "Processing failed",
                "intent": "fallback",
                "processing_time_ms": 1000,
                "optimized": False,
            }

    async def _generate_gemini_response(
        self, prompt: str, context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Sends a prompt to the Gemini model and returns the text response with optimized caching and performance."""
        try:
            if not self.ai_cache:
                self.ai_cache = await get_ai_cache()
            if not self.performance_optimizer:
                self.performance_optimizer = await get_performance_optimizer()
            if not self.analytics_monitor:
                self.analytics_monitor = await get_analytics_monitor()
            if not self.quality_monitor:
                self.quality_monitor = await get_quality_monitor()
            safe_context = context or {}
            priority = safe_context.get("priority", 1)
            f"fast_{hash(prompt)}_{hash(str(safe_context))}"
            try:
                cached_response = await asyncio.wait_for(
                    self.ai_cache.get_cached_response(prompt, safe_context), timeout=0.5
                )
                if cached_response:
                    logger.debug("Using cached AI response (fast path)")
                    await self.analytics_monitor.record_metric(
                        MetricType.CACHE, "cache_hit", 1, metadata={"fast_path": True}
                    )
                    return cached_response["response"]
            except asyncio.TimeoutError:
                logger.debug("Cache check timed out, proceeding with generation")
            try:
                optimization_task = asyncio.create_task(
                    self.performance_optimizer.optimize_ai_request(prompt, safe_context, priority)
                )
                optimized_prompt, optimization_metadata = await asyncio.wait_for(
                    optimization_task, timeout=2.0
                )
            except asyncio.TimeoutError:
                logger.warning("Prompt optimization timed out, using original")
                optimized_prompt = prompt
                optimization_metadata = {"optimized": False, "timeout": True}
            await self.analytics_monitor.record_metric(
                MetricType.CACHE, "cache_miss", 1, metadata={"fast_path": True}
            )
            try:
                await asyncio.wait_for(
                    self.performance_optimizer.apply_rate_limiting(), timeout=1.0
                )
            except asyncio.TimeoutError:
                logger.warning("Rate limiting check timed out")
            try:
                model, instruction_id = self._get_task_appropriate_model(
                    task_type="general", context=safe_context
                )
                generation_config = {
                    "temperature": 0.3,
                    "max_output_tokens": 800,
                    "top_p": 0.8,
                    "top_k": 20,
                }
                start_time = datetime.now(timezone.utc)
                generation_task = asyncio.create_task(
                    asyncio.to_thread(
                        model.generate_content,
                        optimized_prompt,
                        safety_settings=self.safety_settings,
                        generation_config=generation_config,
                    )
                )
                timeout_seconds = safe_context.get("timeout", 8.0)
                response = await asyncio.wait_for(generation_task, timeout=timeout_seconds)
                end_time = datetime.now(timezone.utc)
                response_time = (end_time - start_time).total_seconds()
                try:
                    response_text = self._extract_response_text(response)
                except Exception as extract_error:
                    logger.error("Response extraction failed: %s" % extract_error)
                    response_text = self._get_fallback_response_text(optimized_prompt, safe_context)
                logger.info("AI response generated in %ss" % response_time)
                estimated_tokens = len(optimized_prompt) // 4 + len(response_text) // 4
                if hasattr(self.performance_optimizer, "update_performance_metrics"):
                    self.performance_optimizer.update_performance_metrics(
                        response_time, estimated_tokens
                    )
                asyncio.create_task(
                    self._record_ai_analytics(
                        response_time, estimated_tokens, safe_context, optimization_metadata
                    )
                )
                cache_metadata = {
                    "response_time_ms": int(response_time * 1000),
                    "prompt_length": len(prompt),
                    "response_length": len(response_text),
                    "model": "gemini",
                    "optimized": True,
                    "generation_config": generation_config,
                }
                asyncio.create_task(
                    self.ai_cache.cache_response(
                        prompt, response_text, safe_context, cache_metadata
                    )
                )
                response_id = (f"resp_{int(datetime.now(timezone.utc).timestamp() * 1000)}",)
                asyncio.create_task(
                    self._assess_response_quality(
                        response_id, response_text, optimized_prompt, safe_context
                    ),
                )
                return response_text
            except asyncio.TimeoutError:
                logger.warning(
                    "AI generation timed out after %ss, using fallback" % timeout_seconds
                )
                return self._get_fallback_response_text(optimized_prompt, safe_context)
            finally:
                if hasattr(self.performance_optimizer, "release_rate_limit"):
                    self.performance_optimizer.release_rate_limit()
        except ValueError as e:
            logger.error("Gemini API call failed: %s" % e, exc_info=True)
            return self._get_fallback_response_text(prompt, context or {})

    def _get_fallback_response_text(self, prompt: str, context: Dict[str, Any]) -> str:
        """Generate a fallback response when AI generation fails"""
        prompt_lower = prompt.lower()
        if "gdpr" in prompt_lower:
            return """Based on GDPR requirements, here are key considerations:

• Lawful basis for processing personal data
• Data subject rights (access, rectification, erasure)
• Privacy by design and by default
• Data Protection Impact Assessments for high-risk processing
• Records of processing activities

I recommend consulting with a data protection specialist for specific guidance."""
        elif "iso" in prompt_lower and "27001" in prompt_lower:
            return """For ISO 27001 implementation:

• Risk assessment and treatment
• Information security policies
• Security awareness and training
• Access control management
• Incident response procedures

Consider engaging an ISO 27001 consultant for detailed implementation."""
        else:
            return """I'm currently experiencing high demand. Here's general compliance guidance:

• Identify applicable regulations for your industry
• Conduct gap analysis against requirements
• Develop policies and procedures
• Implement necessary controls
• Monitor and review regularly

Please try your question again or contact support for immediate assistance."""

    async def _record_ai_analytics(
        self,
        response_time: float,
        token_count: int,
        context: Optional[Dict[str, Any]] = None,
        optimization_metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record comprehensive analytics for AI operations."""
        try:
            if not self.analytics_monitor:
                return
            await self.analytics_monitor.record_metric(
                MetricType.PERFORMANCE,
                "response_time_ms",
                response_time * 1000,
                metadata={
                    "content_type": context.get("content_type") if context else "unknown",
                    "framework": context.get("framework") if context else "unknown",
                    "optimization_applied": bool(optimization_metadata),
                },
            )
            await self.analytics_monitor.record_metric(
                MetricType.USAGE,
                "token_usage",
                token_count,
                metadata={
                    "content_type": context.get("content_type") if context else "unknown",
                    "framework": context.get("framework") if context else "unknown",
                },
            )
            estimated_cost = token_count * 1e-05
            await self.analytics_monitor.record_metric(
                MetricType.COST,
                "cost_estimate",
                estimated_cost,
                metadata={
                    "content_type": context.get("content_type") if context else "unknown",
                    "framework": context.get("framework") if context else "unknown",
                    "token_count": token_count,
                },
            )
            quality_score = 8.5
            await self.analytics_monitor.record_metric(
                MetricType.QUALITY,
                "response_quality",
                quality_score,
                metadata={
                    "content_type": context.get("content_type") if context else "unknown",
                    "framework": context.get("framework") if context else "unknown",
                },
            )
        except requests.RequestException as e:
            logger.warning("Failed to record analytics: %s" % e)

    async def _assess_response_quality(
        self,
        response_id: str,
        response_text: str,
        prompt: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Perform asynchronous quality assessment of AI response."""
        try:
            if not self.quality_monitor:
                return
            assessment = await self.quality_monitor.assess_response_quality(
                response_id=response_id, response_text=response_text, prompt=prompt, context=context
            )
            await self.analytics_monitor.record_metric(
                MetricType.QUALITY,
                "response_quality",
                assessment.overall_score,
                metadata={
                    "quality_level": assessment.quality_level.value,
                    "content_type": context.get("content_type") if context else "unknown",
                    "framework": context.get("framework") if context else "unknown",
                    "response_id": response_id,
                },
            )
        except requests.RequestException as e:
            logger.warning("Failed to assess response quality: %s" % e)

    async def get_evidence_recommendations(
        self, user: User, business_profile_id: UUID, target_framework: str
    ) -> List[Dict[str, Any]]:
        """Generates evidence collection recommendations based on business context."""
        try:
            from uuid import uuid4

            context = await self.context_manager.get_conversation_context(
                uuid4(), business_profile_id
            )
            business_context = context.get("business_profile", {})
            prompt = self.prompt_templates.get_evidence_recommendation_prompt(
                target_framework, business_context
            )
            response = await self._generate_gemini_response(prompt)
            return [
                {
                    "framework": target_framework,
                    "recommendations": response,
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                }
            ]
        except (NotFoundException, DatabaseException, IntegrationException) as e:
            logger.warning(
                "Known exception while generating recommendations for business %s: %s"
                % (business_profile_id, e)
            )
            raise
        except (OSError, requests.RequestException, Exception) as e:
            logger.error(
                "Error generating evidence recommendations for business %s: %s"
                % (business_profile_id, e),
                exc_info=True,
            )
            raise BusinessLogicException(
                "An unexpected error occurred while generating recommendations."
            ) from e

    async def get_context_aware_recommendations(
        self,
        user: User,
        business_profile_id: UUID,
        framework: str,
        context_type: str = "comprehensive",
    ) -> Dict[str, Any]:
        """
        Enhanced context-aware evidence recommendations that consider:
        - Business profile and industry specifics
        - Existing evidence and gaps
        - User behavior patterns
        - Compliance maturity level
        - Risk assessment
        """
        try:
            context = await self.context_manager.get_conversation_context(
                uuid4(), business_profile_id
            )
            business_context = context.get("business_profile", {})
            existing_evidence = context.get("recent_evidence", [])
            maturity_analysis = await self._analyze_compliance_maturity(
                business_context, existing_evidence, framework
            )
            gaps_analysis = await self.analyze_evidence_gap(business_profile_id, framework)
            recommendations = await self._generate_contextual_recommendations(
                business_context, existing_evidence, maturity_analysis, gaps_analysis, framework
            )
            prioritized_recommendations = self._prioritize_recommendations(
                recommendations, business_context, maturity_analysis
            )
            return {
                "framework": framework,
                "business_context": {
                    "company_name": business_context.get("company_name", "Unknown"),
                    "industry": business_context.get("industry", "Unknown"),
                    "employee_count": business_context.get("employee_count", 0),
                    "maturity_level": maturity_analysis.get("maturity_level", "Basic"),
                },
                "current_status": {
                    "completion_percentage": gaps_analysis.get("completion_percentage", 0),
                    "evidence_collected": len(existing_evidence),
                    "critical_gaps_count": len(gaps_analysis.get("critical_gaps", [])),
                },
                "recommendations": prioritized_recommendations,
                "next_steps": self._generate_next_steps(prioritized_recommendations[:3]),
                "estimated_effort": self._calculate_total_effort(prioritized_recommendations),
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }
        except (OSError, requests.RequestException, KeyError) as e:
            logger.error("Error generating context-aware recommendations: %s" % e, exc_info=True)
            raise BusinessLogicException("Unable to generate context-aware recommendations") from e

    async def _analyze_compliance_maturity(
        self, business_context: Dict[str, Any], existing_evidence: List[Dict], framework: str
    ) -> Dict[str, Any]:
        """Analyze the organization's compliance maturity level."""
        try:
            evidence_count = len(existing_evidence)
            evidence_types = len({item.get("evidence_type", "") for item in existing_evidence})
            industry = business_context.get("industry", "").lower()
            employee_count = business_context.get("employee_count", 0)
            if evidence_count >= 50 and evidence_types >= 8:
                maturity_level = "Advanced"
                maturity_score = 85
            elif evidence_count >= 20 and evidence_types >= 5:
                maturity_level = "Intermediate"
                maturity_score = 65
            elif evidence_count >= 5 and evidence_types >= 3:
                maturity_level = "Basic"
                maturity_score = 40
            else:
                maturity_level = "Initial"
                maturity_score = 20
            if industry in ["healthcare", "finance", "government"]:
                maturity_score = min(maturity_score + 10, 100)
            elif industry in ["technology", "consulting"]:
                maturity_score = min(maturity_score + 5, 100)
            return {
                "maturity_level": maturity_level,
                "maturity_score": maturity_score,
                "evidence_diversity": evidence_types,
                "evidence_volume": evidence_count,
                "industry_context": industry,
                "size_category": self._categorize_organization_size(employee_count),
            }
        except (requests.RequestException, KeyError, IndexError) as e:
            logger.error("Error analyzing compliance maturity: %s" % e)
            return {
                "maturity_level": "Basic",
                "maturity_score": 40,
                "evidence_diversity": 0,
                "evidence_volume": 0,
                "industry_context": "unknown",
                "size_category": "small",
            }

    def _categorize_organization_size(self, employee_count: int) -> str:
        """Categorize organization size for compliance recommendations."""
        if employee_count >= 1000:
            return "enterprise"
        elif employee_count >= 100:
            return "medium"
        elif employee_count >= 10:
            return "small"
        else:
            return "micro"

    async def _generate_contextual_recommendations(
        self,
        business_context: Dict[str, Any],
        existing_evidence: List[Dict],
        maturity_analysis: Dict[str, Any],
        gaps_analysis: Dict[str, Any],
        framework: str,
    ) -> List[Dict[str, Any]]:
        """Generate intelligent recommendations based on comprehensive context analysis."""
        try:
            prompt_dict = self._build_contextual_recommendation_prompt(
                business_context, existing_evidence, maturity_analysis, gaps_analysis, framework
            )
            combined_prompt = (f"System: {prompt_dict['system']}\n\nUser: {prompt_dict['user']}",)
            cache_context = {
                "content_type": ContentType.RECOMMENDATION.value,
                "framework": framework,
                "business_context": business_context,
                "enable_similarity_matching": True,
            }
            response = await self._generate_gemini_response(combined_prompt, cache_context)
            recommendations = self._parse_ai_recommendations(response, framework)
            enhanced_recommendations = self._add_automation_insights(
                recommendations, business_context
            )
            return enhanced_recommendations
        except (ValueError, KeyError, IndexError) as e:
            logger.error("Error generating contextual recommendations: %s" % e)
            return self._get_fallback_recommendations(framework, maturity_analysis)

    def _build_contextual_recommendation_prompt(
        self,
        business_context: Dict[str, Any],
        existing_evidence: List[Dict],
        maturity_analysis: Dict[str, Any],
        gaps_analysis: Dict[str, Any],
        framework: str,
    ) -> Dict[str, str]:
        """Build a comprehensive prompt for contextual recommendations."""
        system_prompt = f"""You are an expert compliance consultant specializing in {framework}.
        Generate intelligent, context-aware evidence collection recommendations based on the organization's
        specific situation, maturity level, and existing compliance posture.

        Focus on:
        1. Practical, actionable recommendations
        2. Prioritization based on risk and business impact
        3. Consideration of organizational capacity and maturity
        4. Industry-specific requirements and best practices
        5. Automation opportunities where applicable

        Return recommendations as a JSON array with this structure:
        [{{
            "control_id": "AC-1",
            "title": "Access Control Policy",
            "description": "Specific action to take",
            "priority": "High|Medium|Low",
            "effort_hours": 8,
            "automation_possible": true,
            "business_justification": "Why this is important for this organization",
            "implementation_steps": ["Step 1", "Step 2", "Step 3"]
        }}]"""
        user_prompt = f"""
        Organization Profile:
        - Company: {business_context.get("company_name", "Unknown")}
        - Industry: {business_context.get("industry", "Unknown")}
        - Size: {business_context.get("employee_count", 0)} employees
        - Maturity Level: {maturity_analysis.get("maturity_level", "Basic")}
        - Maturity Score: {maturity_analysis.get("maturity_score", 40)}/100

        Current Compliance Status:
        - Framework: {framework}
        - Completion: {gaps_analysis.get("completion_percentage", 0)}%
        - Evidence Items: {len(existing_evidence)}
        - Critical Gaps: {len(gaps_analysis.get("critical_gaps", []))}

        Existing Evidence Types:
        {self._summarize_evidence_types(existing_evidence)}

        Critical Gaps Identified:
        {gaps_analysis.get("critical_gaps", [])}

        Generate 8-12 prioritized recommendations that address the most critical gaps while
        considering the organization's maturity level and capacity for implementation.
        """
        return {"system": system_prompt, "user": user_prompt}

    def _summarize_evidence_types(self, existing_evidence: List[Dict]) -> str:
        """Summarize existing evidence types for context."""
        if not existing_evidence:
            return "No evidence collected yet"
        type_counts = {}
        for item in existing_evidence:
            evidence_type = item.get("evidence_type", "unknown")
            type_counts[evidence_type] = type_counts.get(evidence_type, 0) + 1
        summary = []
        for evidence_type, count in sorted(type_counts.items()):
            summary.append(f"- {evidence_type}: {count} items")
        return "\n".join(summary)

    def _parse_ai_recommendations(self, response: str, framework: str) -> List[Dict[str, Any]]:
        """Parse AI response into structured recommendations."""
        try:
            import json
            import re

            json_match = re.search("\\[.*\\]", response, re.DOTALL)
            if json_match:
                recommendations = json.loads(json_match.group())
                return recommendations
            return self._parse_text_recommendations(response, framework)
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.warning("Error parsing AI recommendations: %s" % e)
            return self._get_fallback_recommendations(framework, {"maturity_level": "Basic"})

    def _parse_text_recommendations(self, response: str, framework: str) -> List[Dict[str, Any]]:
        """Parse text-based recommendations as fallback."""
        recommendations = []
        lines = response.split("\n")
        current_rec = {}
        for line in lines:
            line = line.strip()
            if line.startswith("- ") or line.startswith("* "):
                if current_rec:
                    recommendations.append(current_rec)
                current_rec = {
                    "control_id": f"{framework}-{len(recommendations) + 1}",
                    "title": line[2:],
                    "description": line[2:],
                    "priority": "Medium",
                    "effort_hours": 4,
                    "automation_possible": False,
                    "business_justification": "Important for compliance",
                    "implementation_steps": [line[2:]],
                }
        if current_rec:
            recommendations.append(current_rec)
        return recommendations[:10]

    def _add_automation_insights(
        self, recommendations: List[Dict[str, Any]], business_context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Add automation insights to recommendations based on business context."""
        automation_map = {
            "policy": True,
            "procedure": True,
            "log_analysis": True,
            "system_configuration": True,
            "access_review": True,
            "vulnerability_scan": True,
            "backup_verification": True,
            "training_record": False,
            "physical_security": False,
            "vendor_assessment": False,
        }
        enhanced_recommendations = []
        for rec in recommendations:
            control_type = rec.get("title", "").lower()
            automation_possible = any(
                auto_type in control_type
                for auto_type in automation_map
                if automation_map[auto_type]
            )
            rec["automation_possible"] = automation_possible
            if automation_possible:
                rec["automation_guidance"] = self._get_automation_guidance(rec, business_context)
            enhanced_recommendations.append(rec)
        return enhanced_recommendations

    def _get_automation_guidance(
        self, recommendation: Dict[str, Any], business_context: Dict[str, Any]
    ) -> str:
        """Provide specific automation guidance for a recommendation."""
        control_type = recommendation.get("title", "").lower()
        org_size = self._categorize_organization_size(business_context.get("employee_count", 0))
        if "policy" in control_type:
            return (
                f"Use policy templates and automated policy management tools. For {org_size} organizations, consider document management systems with version control.",
            )
        elif "log" in control_type:
            return (
                f"Implement SIEM or log management solutions. For {org_size} organizations, consider cloud-based logging services.",
            )
        elif "access" in control_type:
            return (
                f"Use identity management systems with automated access reviews. For {org_size} organizations, consider cloud IAM solutions.",
            )
        elif "vulnerability" in control_type:
            return (
                f"Deploy automated vulnerability scanning tools. For {org_size} organizations, consider managed security services.",
            )
        else:
            return (
                "Consider workflow automation tools and integration platforms to streamline this process.",
            )

    def _prioritize_recommendations(
        self,
        recommendations: List[Dict[str, Any]],
        business_context: Dict[str, Any],
        maturity_analysis: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Prioritize recommendations based on business context and maturity."""

        def calculate_priority_score(rec: Dict[str, Any]) -> float:
            score = 0.0
            priority_scores = {"High": 3.0, "Medium": 2.0, "Low": 1.0}
            score += priority_scores.get(rec.get("priority", "Medium"), 2.0)
            maturity_level = maturity_analysis.get("maturity_level", "Basic")
            if maturity_level == "Initial":
                if any(
                    keyword in rec.get("title", "").lower()
                    for keyword in ["policy", "procedure", "training"]
                ):
                    score += 1.0
            elif maturity_level == "Advanced":
                if any(
                    keyword in rec.get("title", "").lower()
                    for keyword in ["monitoring", "automation", "integration"]
                ):
                    score += 1.0
            industry = business_context.get("industry", "").lower()
            if industry in ["healthcare", "finance"]:
                if any(
                    keyword in rec.get("title", "").lower()
                    for keyword in ["access", "encryption", "audit"]
                ):
                    score += 0.5
            if rec.get("automation_possible", False):
                score += 0.3
            effort_hours = rec.get("effort_hours", 4)
            if effort_hours <= 2:
                score += 0.2
            elif effort_hours >= 16:
                score -= 0.2
            return score

        for rec in recommendations:
            rec["priority_score"] = calculate_priority_score(rec)
        return sorted(recommendations, key=lambda x: x.get("priority_score", 0), reverse=True)

    def _generate_next_steps(self, top_recommendations: List[Dict[str, Any]]) -> List[str]:
        """Generate actionable next steps from top recommendations."""
        next_steps = []
        for i, rec in enumerate(top_recommendations[:3], 1):
            title = rec.get("title", "Unknown")
            effort = rec.get("effort_hours", 4)
            if rec.get("automation_possible", False):
                step = (f"{i}. Start with {title} (Est. {effort}h) - Consider automation tools",)
            else:
                step = (f"{i}. Implement {title} (Est. {effort}h) - Manual process required",)
            next_steps.append(step)
        return next_steps

    def _calculate_total_effort(self, recommendations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate total effort estimates for recommendations."""
        total_hours = sum(rec.get("effort_hours", 4) for rec in recommendations)
        high_priority_hours = sum(
            rec.get("effort_hours", 4) for rec in recommendations if rec.get("priority") == "High"
        )
        return {
            "total_hours": total_hours,
            "high_priority_hours": high_priority_hours,
            "estimated_weeks": round(total_hours / 40, 1),
            "quick_wins": len([r for r in recommendations if r.get("effort_hours", 4) <= 2]),
        }

    def _get_fallback_recommendations(
        self, framework: str, maturity_analysis: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Provide fallback recommendations when AI generation fails."""
        base_recommendations = {
            "GDPR": [
                {
                    "control_id": "GDPR-1",
                    "title": "Data Processing Policy",
                    "description": "Develop comprehensive data processing policies",
                    "priority": "High",
                    "effort_hours": 8,
                    "automation_possible": True,
                    "business_justification": "Required for GDPR compliance",
                    "implementation_steps": ["Draft policy", "Review with legal", "Implement"],
                },
                {
                    "control_id": "GDPR-2",
                    "title": "Data Subject Rights Procedures",
                    "description": "Implement procedures for handling data subject requests",
                    "priority": "High",
                    "effort_hours": 12,
                    "automation_possible": True,
                    "business_justification": "Essential for GDPR compliance",
                    "implementation_steps": ["Design workflow", "Create forms", "Train staff"],
                },
            ],
            "ISO27001": [
                {
                    "control_id": "ISO-A.5.1",
                    "title": "Information Security Policy",
                    "description": "Establish information security management policy",
                    "priority": "High",
                    "effort_hours": 6,
                    "automation_possible": True,
                    "business_justification": "Foundation of ISO 27001 compliance",
                    "implementation_steps": ["Draft policy", "Management approval", "Communicate"],
                },
                {
                    "control_id": "ISO-A.9.1",
                    "title": "Access Control Policy",
                    "description": "Implement access control management",
                    "priority": "High",
                    "effort_hours": 10,
                    "automation_possible": True,
                    "business_justification": "Critical security control",
                    "implementation_steps": [
                        "Define roles",
                        "Implement controls",
                        "Monitor access",
                    ],
                },
            ],
        }
        return base_recommendations.get(framework, base_recommendations["ISO27001"])

    async def generate_evidence_collection_workflow(
        self,
        user: User,
        business_profile_id: UUID,
        framework: str,
        control_id: Optional[str] = None,
        workflow_type: str = "comprehensive",
    ) -> Dict[str, Any]:
        """
        Generate intelligent, step-by-step evidence collection workflows
        tailored to specific frameworks, controls, and business contexts.
        """
        try:
            context = await self.context_manager.get_conversation_context(
                uuid4(), business_profile_id
            )
            business_context = context.get("business_profile", {})
            existing_evidence = context.get("recent_evidence", [])
            maturity_analysis = await self._analyze_compliance_maturity(
                business_context, existing_evidence, framework
            )
            workflow = await self._generate_contextual_workflow(
                framework, control_id, business_context, maturity_analysis, workflow_type
            )
            workflow = self._enhance_workflow_with_automation(workflow, business_context)
            workflow["effort_estimation"] = self._calculate_workflow_effort(workflow)
            return workflow
        except (OSError, requests.RequestException, KeyError) as e:
            logger.error("Error generating evidence collection workflow: %s" % e, exc_info=True)
            raise BusinessLogicException("Unable to generate evidence collection workflow") from e

    async def _generate_contextual_workflow(
        self,
        framework: str,
        control_id: str,
        business_context: Dict[str, Any],
        maturity_analysis: Dict[str, Any],
        workflow_type: str,
    ) -> Dict[str, Any]:
        """Generate a contextual workflow using AI."""
        try:
            prompt = self._build_workflow_generation_prompt(
                framework, control_id, business_context, maturity_analysis, workflow_type
            )
            cache_context = {
                "content_type": ContentType.WORKFLOW.value,
                "framework": framework,
                "control_id": control_id,
                "business_context": business_context,
                "enable_similarity_matching": True,
            }
            response = await self._generate_gemini_response(prompt, cache_context)
            workflow = self._parse_workflow_response(response, framework, control_id)
            return workflow
        except ValueError as e:
            logger.error("Error generating contextual workflow: %s" % e)
            return self._get_fallback_workflow(framework, control_id, maturity_analysis)

    def _build_workflow_generation_prompt(
        self,
        framework: str,
        control_id: str,
        business_context: Dict[str, Any],
        maturity_analysis: Dict[str, Any],
        workflow_type: str,
    ) -> Dict[str, str]:
        """Build prompt for workflow generation."""
        system_prompt = f"""You are an expert compliance consultant specializing in {framework}.
        Generate a detailed, step-by-step evidence collection workflow that is practical and
        tailored to the organization's specific context and maturity level.

        The workflow should include:
        1. Clear, actionable steps in logical sequence
        2. Specific deliverables and artifacts for each step
        3. Role assignments and responsibilities
        4. Time estimates and dependencies
        5. Quality checkpoints and validation criteria
        6. Tools and resources needed
        7. Common pitfalls and how to avoid them

        Return the workflow as JSON with this structure:
        {{
            "workflow_id": "unique_id",
            "title": "Workflow Title",
            "description": "Brief description",
            "framework": "{framework}",
            "control_id": "{control_id or "general"}",
            "phases": [
                {{
                    "phase_id": "phase_1",
                    "title": "Phase Title",
                    "description": "Phase description",
                    "estimated_hours": 4,
                    "steps": [
                        {{
                            "step_id": "step_1",
                            "title": "Step Title",
                            "description": "Detailed step description",
                            "deliverables": ["Deliverable 1", "Deliverable 2"],
                            "responsible_role": "Role",
                            "estimated_hours": 2,
                            "dependencies": [],
                            "tools_needed": ["Tool 1"],
                            "validation_criteria": ["Criteria 1"]
                        }},
                    ]
                }},
            ]
        }}"""
        control_context = f" for control {control_id}" if control_id else ""
        user_prompt = f"""
        Generate a {workflow_type} evidence collection workflow for {framework}{control_context}.

        Organization Context:
        - Company: {business_context.get("company_name", "Unknown")}
        - Industry: {business_context.get("industry", "Unknown")}
        - Size: {business_context.get("employee_count", 0)} employees
        - Maturity Level: {maturity_analysis.get("maturity_level", "Basic")}
        - Organization Category: {maturity_analysis.get("size_category", "small")}

        Requirements:
        - Tailor the workflow to the organization's maturity level
        - Consider industry-specific requirements
        - Include both manual and automated approaches where applicable
        - Provide realistic time estimates
        - Include quality assurance checkpoints
        - Consider resource constraints for {maturity_analysis.get("size_category", "small")} organizations

        Generate a comprehensive workflow with 3-5 phases and 2-4 steps per phase.
        """
        return {"system": system_prompt, "user": user_prompt}

    def _parse_workflow_response(
        self, response: str, framework: str, control_id: str
    ) -> Dict[str, Any]:
        """Parse AI workflow response into structured format."""
        try:
            import json
            import re

            json_match = re.search("\\{.*\\}", response, re.DOTALL)
            if json_match:
                workflow = json.loads(json_match.group())
                workflow = self._validate_workflow_structure(workflow, framework, control_id)
                return workflow
            return self._parse_text_workflow(response, framework, control_id)
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning("Error parsing workflow response: %s" % e)
            return self._get_fallback_workflow(framework, control_id, {"maturity_level": "Basic"})

    def _validate_workflow_structure(
        self, workflow: Dict[str, Any], framework: str, control_id: str
    ) -> Dict[str, Any]:
        """Validate and enhance workflow structure."""
        workflow.setdefault(
            "workflow_id", f"{framework}_{control_id or 'general'}_{uuid4().hex[:8]}"
        )
        workflow.setdefault("framework", framework)
        workflow.setdefault("control_id", control_id or "general")
        workflow.setdefault("created_at", datetime.now(timezone.utc).isoformat())
        workflow.setdefault("phases", [])
        for i, phase in enumerate(workflow["phases"]):
            phase.setdefault("phase_id", f"phase_{i + 1}")
            phase.setdefault("estimated_hours", 4)
            phase.setdefault("steps", [])
            for j, step in enumerate(phase["steps"]):
                step.setdefault("step_id", f"step_{j + 1}")
                step.setdefault("estimated_hours", 2)
                step.setdefault("deliverables", [])
                step.setdefault("dependencies", [])
                step.setdefault("tools_needed", [])
                step.setdefault("validation_criteria", [])
                step.setdefault("responsible_role", "Compliance Team")
        return workflow

    def _parse_text_workflow(
        self, response: str, framework: str, control_id: str
    ) -> Dict[str, Any]:
        """Parse text-based workflow as fallback."""
        workflow = {
            "workflow_id": f"{framework}_{control_id or 'general'}_{uuid4().hex[:8]}",
            "title": f"{framework} Evidence Collection Workflow",
            "description": f"Evidence collection workflow for {framework}",
            "framework": framework,
            "control_id": control_id or "general",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "phases": [],
        }
        lines = response.split("\n")
        current_phase = None
        for line in lines:
            line = line.strip()
            if line.startswith("Phase") or line.startswith("##"):
                if current_phase:
                    workflow["phases"].append(current_phase)
                current_phase = {
                    "phase_id": f"phase_{len(workflow['phases']) + 1}",
                    "title": line,
                    "description": line,
                    "estimated_hours": 8,
                    "steps": [],
                }
            elif line.startswith("Step") or line.startswith("-") or line.startswith("*"):
                if current_phase:
                    step = {
                        "step_id": f"step_{len(current_phase['steps']) + 1}",
                        "title": line,
                        "description": line,
                        "deliverables": [line],
                        "responsible_role": "Compliance Team",
                        "estimated_hours": 2,
                        "dependencies": [],
                        "tools_needed": [],
                        "validation_criteria": ["Complete deliverables"],
                    }
                    current_phase["steps"].append(step)
        if current_phase:
            workflow["phases"].append(current_phase)
        return workflow

    def _enhance_workflow_with_automation(
        self, workflow: Dict[str, Any], business_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Enhance workflow with automation recommendations."""
        org_size = self._categorize_organization_size(business_context.get("employee_count", 0))
        industry = business_context.get("industry", "").lower()
        for phase in workflow.get("phases", []):
            for step in phase.get("steps", []):
                step["automation_opportunities"] = self._identify_step_automation(
                    step,
                    org_size,
                    industry,
                )
                if step["automation_opportunities"].get("high_automation_potential", False):
                    step["estimated_hours_with_automation"] = max(
                        1, step.get("estimated_hours", 2) * 0.3
                    )
                else:
                    step["estimated_hours_with_automation"] = step.get("estimated_hours", 2)
        workflow["automation_summary"] = self._calculate_workflow_automation_potential(workflow)
        return workflow

    def _identify_step_automation(
        self, step: Dict[str, Any], org_size: str, industry: str
    ) -> Dict[str, Any]:
        """Identify automation opportunities for a workflow step."""
        step_title = step.get("title", "").lower()
        step_description = step.get("description", "").lower()
        automation_keywords = {
            "high": ["policy", "template", "scan", "monitor", "log", "report", "backup"],
            "medium": ["review", "assess", "document", "configure", "test"],
            "low": ["interview", "training", "meeting", "approval", "sign-off"],
        }
        automation_level = "low"
        for level, keywords in automation_keywords.items():
            if any(keyword in step_title or keyword in step_description for keyword in keywords):
                automation_level = level
                break
        if org_size in ["enterprise", "medium"] and automation_level == "medium":
            automation_level = "high"
        automation_tools = self._suggest_automation_tools(step_title, org_size, industry)
        return {
            "automation_level": automation_level,
            "high_automation_potential": automation_level == "high",
            "suggested_tools": automation_tools,
            "effort_reduction_percentage": {"high": 70, "medium": 40, "low": 10}[automation_level],
        }

    def _suggest_automation_tools(self, step_title: str, org_size: str, industry: str) -> List[str]:
        """Suggest specific automation tools for a step."""
        tools = []
        step_lower = step_title.lower()
        if "policy" in step_lower:
            tools.extend(["Policy management platforms", "Document automation tools"])
        if "scan" in step_lower or "vulnerability" in step_lower:
            tools.extend(["Vulnerability scanners", "Security assessment tools"])
        if "log" in step_lower or "monitor" in step_lower:
            tools.extend(["SIEM solutions", "Log management platforms"])
        if "backup" in step_lower:
            tools.extend(["Backup automation tools", "Cloud backup services"])
        if "access" in step_lower:
            tools.extend(["Identity management systems", "Access governance tools"])
        if org_size in ["enterprise", "medium"]:
            tools.extend(["Enterprise workflow platforms", "Compliance management suites"])
        else:
            tools.extend(["Cloud-based automation tools", "SaaS compliance platforms"])
        return list(set(tools))

    def _calculate_workflow_automation_potential(self, workflow: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate overall automation potential for the workflow."""
        total_steps = 0
        high_automation_steps = 0
        total_manual_hours = 0
        total_automated_hours = 0
        for phase in workflow.get("phases", []):
            for step in phase.get("steps", []):
                total_steps += 1
                manual_hours = step.get("estimated_hours", 2)
                automated_hours = step.get("estimated_hours_with_automation", manual_hours)
                total_manual_hours += manual_hours
                total_automated_hours += automated_hours
                if step.get("automation_opportunities", {}).get("high_automation_potential", False):
                    high_automation_steps += 1
        automation_percentage = high_automation_steps / total_steps * 100 if total_steps > 0 else 0
        effort_savings = (
            (total_manual_hours - total_automated_hours) / total_manual_hours * 100
            if total_manual_hours > 0
            else 0
        )
        return {
            "automation_percentage": round(automation_percentage, 1),
            "effort_savings_percentage": round(effort_savings, 1),
            "manual_hours": total_manual_hours,
            "automated_hours": total_automated_hours,
            "hours_saved": total_manual_hours - total_automated_hours,
            "high_automation_steps": high_automation_steps,
            "total_steps": total_steps,
        }

    def _calculate_workflow_effort(self, workflow: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate comprehensive effort estimation for workflow."""
        total_manual_hours = 0
        total_automated_hours = 0
        phases_count = len(workflow.get("phases", []))
        steps_count = 0
        phase_efforts = []
        for phase in workflow.get("phases", []):
            phase_manual_hours = 0
            phase_automated_hours = 0
            phase_steps = len(phase.get("steps", []))
            steps_count += phase_steps
            for step in phase.get("steps", []):
                manual_hours = step.get("estimated_hours", 2)
                automated_hours = step.get("estimated_hours_with_automation", manual_hours)
                phase_manual_hours += manual_hours
                phase_automated_hours += automated_hours
            phase_efforts.append(
                {
                    "phase_id": phase.get("phase_id"),
                    "manual_hours": phase_manual_hours,
                    "automated_hours": phase_automated_hours,
                    "steps_count": phase_steps,
                }
            )
            total_manual_hours += phase_manual_hours
            total_automated_hours += phase_automated_hours
        return {
            "total_manual_hours": total_manual_hours,
            "total_automated_hours": total_automated_hours,
            "estimated_weeks_manual": round(total_manual_hours / 40, 1),
            "estimated_weeks_automated": round(total_automated_hours / 40, 1),
            "phases_count": phases_count,
            "steps_count": steps_count,
            "phase_breakdown": phase_efforts,
            "effort_savings": {
                "hours_saved": total_manual_hours - total_automated_hours,
                "percentage_saved": round(
                    (total_manual_hours - total_automated_hours) / total_manual_hours * 100, 1
                )
                if total_manual_hours > 0
                else 0,
            },
        }

    def _get_fallback_workflow(
        self, framework: str, control_id: str, maturity_analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Provide fallback workflow when AI generation fails."""
        return {
            "workflow_id": f"{framework}_{control_id or 'general'}_{uuid4().hex[:8]}",
            "title": f"{framework} Evidence Collection Workflow",
            "description": f"Standard evidence collection workflow for {framework}",
            "framework": framework,
            "control_id": control_id or "general",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "phases": [
                {
                    "phase_id": "phase_1",
                    "title": "Planning and Preparation",
                    "description": "Initial planning and resource allocation",
                    "estimated_hours": 4,
                    "steps": [
                        {
                            "step_id": "step_1",
                            "title": "Define scope and objectives",
                            "description": "Clearly define what evidence needs to be collected",
                            "deliverables": ["Scope document", "Objectives list"],
                            "responsible_role": "Compliance Manager",
                            "estimated_hours": 2,
                            "dependencies": [],
                            "tools_needed": ["Documentation tools"],
                            "validation_criteria": ["Scope approved by stakeholders"],
                        }
                    ],
                },
                {
                    "phase_id": "phase_2",
                    "title": "Evidence Collection",
                    "description": "Systematic collection of required evidence",
                    "estimated_hours": 8,
                    "steps": [
                        {
                            "step_id": "step_1",
                            "title": "Collect documentation",
                            "description": "Gather all relevant policies and procedures",
                            "deliverables": ["Policy documents", "Procedure documents"],
                            "responsible_role": "Compliance Team",
                            "estimated_hours": 4,
                            "dependencies": ["phase_1"],
                            "tools_needed": ["Document management system"],
                            "validation_criteria": ["All documents collected and verified"],
                        }
                    ],
                },
            ],
            "automation_summary": {
                "automation_percentage": 30.0,
                "effort_savings_percentage": 20.0,
                "manual_hours": 12,
                "automated_hours": 10,
                "hours_saved": 2,
            },
            "effort_estimation": {
                "total_manual_hours": 12,
                "total_automated_hours": 10,
                "estimated_weeks_manual": 0.3,
                "estimated_weeks_automated": 0.25,
                "phases_count": 2,
                "steps_count": 2,
            },
        }

    async def generate_customized_policy(
        self,
        user: User,
        business_profile_id: UUID,
        framework: str,
        policy_type: str,
        customization_options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Generate AI-powered, customized compliance policies based on:
        - Business profile and industry specifics
        - Framework requirements
        - Organizational size and maturity
        - Industry best practices
        - Regulatory requirements
        """
        try:
            context = await self.context_manager.get_conversation_context(
                uuid4(), business_profile_id
            )
            business_context = context.get("business_profile", {})
            existing_evidence = context.get("recent_evidence", [])
            maturity_analysis = await self._analyze_compliance_maturity(
                business_context, existing_evidence, framework
            )
            policy = await self._generate_contextual_policy(
                framework,
                policy_type,
                business_context,
                maturity_analysis,
                customization_options or {},
            )
            policy["implementation_guidance"] = self._generate_policy_implementation_guidance(
                policy, business_context, maturity_analysis
            )
            policy["compliance_mapping"] = self._generate_compliance_mapping(
                policy, framework, policy_type
            )
            return policy
        except (OSError, requests.RequestException, KeyError) as e:
            logger.error("Error generating customized policy: %s" % e, exc_info=True)
            raise BusinessLogicException("Unable to generate customized policy") from e

    async def _generate_contextual_policy(
        self,
        framework: str,
        policy_type: str,
        business_context: Dict[str, Any],
        maturity_analysis: Dict[str, Any],
        customization_options: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Generate a contextual policy using AI."""
        try:
            prompt = self._build_policy_generation_prompt(
                framework, policy_type, business_context, maturity_analysis, customization_options
            )
            cache_context = {
                "content_type": ContentType.POLICY.value,
                "framework": framework,
                "policy_type": policy_type,
                "business_context": business_context,
                "enable_similarity_matching": True,
            }
            response = await self._generate_gemini_response(prompt, cache_context)
            policy = self._parse_policy_response(response, framework, policy_type)
            policy = self._apply_business_customizations(
                policy, business_context, customization_options
            )
            return policy
        except ValueError as e:
            logger.error("Error generating contextual policy: %s" % e)
            return self._get_fallback_policy(framework, policy_type, business_context)

    def _build_policy_generation_prompt(
        self,
        framework: str,
        policy_type: str,
        business_context: Dict[str, Any],
        maturity_analysis: Dict[str, Any],
        customization_options: Dict[str, Any],
    ) -> Dict[str, str]:
        """Build comprehensive prompt for policy generation."""
        system_prompt = f"""You are an expert compliance consultant and policy writer specializing in {framework}.
        Generate a comprehensive, business-specific {policy_type} policy that is:

        1. Tailored to the organization's industry, size, and maturity level
        2. Compliant with {framework} requirements
        3. Practical and implementable
        4. Written in clear, professional language
        5. Includes specific procedures and controls
        6. Addresses industry-specific risks and requirements

        Return the policy as JSON with this structure:
        {{
            "policy_id": "unique_id",
            "title": "Policy Title",
            "version": "1.0",
            "effective_date": "YYYY-MM-DD",
            "framework": "{framework}",
            "policy_type": "{policy_type}",
            "sections": [
                {{
                    "section_id": "section_1",
                    "title": "Section Title",
                    "content": "Detailed section content",
                    "subsections": [
                        {{
                            "subsection_id": "subsection_1",
                            "title": "Subsection Title",
                            "content": "Detailed subsection content",
                            "controls": ["Control 1", "Control 2"]
                        }},
                    ]
                }},
            ],
            "roles_responsibilities": [
                {{
                    "role": "Role Name",
                    "responsibilities": ["Responsibility 1", "Responsibility 2"]
                }},
            ],
            "procedures": [
                {{
                    "procedure_id": "proc_1",
                    "title": "Procedure Title",
                    "steps": ["Step 1", "Step 2", "Step 3"]
                }},
            ],
            "compliance_requirements": [
                {{
                    "requirement_id": "req_1",
                    "description": "Requirement description",
                    "control_reference": "Control reference"
                }},
            ]
        }}"""
        industry_context = business_context.get("industry", "Unknown")
        company_size = self._categorize_organization_size(business_context.get("employee_count", 0))
        user_prompt = f"""
        Generate a {policy_type} policy for {framework} compliance.

        Organization Profile:
        - Company: {business_context.get("company_name", "Organization")}
        - Industry: {industry_context}
        - Size: {business_context.get("employee_count", 0)} employees ({company_size} organization)
        - Maturity Level: {maturity_analysis.get("maturity_level", "Basic")}
        - Geographic Scope: {customization_options.get("geographic_scope", "Single location")}

        Customization Requirements:
        - Tone: {customization_options.get("tone", "Professional")}
        - Detail Level: {customization_options.get("detail_level", "Standard")}
        - Include Templates: {customization_options.get("include_templates", True)}
        - Industry Focus: {customization_options.get("industry_focus", industry_context)}

        Special Considerations:
        - Address {industry_context}-specific risks and requirements
        - Consider {company_size} organization constraints and capabilities
        - Align with {maturity_analysis.get("maturity_level", "Basic")} maturity level
        - Include practical implementation guidance
        - Ensure regulatory compliance for {framework}

        Generate a comprehensive policy with 5-8 main sections, detailed procedures,
        and clear roles and responsibilities.
        """
        return {"system": system_prompt, "user": user_prompt}

    def _parse_policy_response(
        self, response: str, framework: str, policy_type: str
    ) -> Dict[str, Any]:
        """Parse AI policy response into structured format."""
        try:
            import json
            import re

            json_match = re.search("\\{.*\\}", response, re.DOTALL)
            if json_match:
                policy = json.loads(json_match.group())
                policy = self._validate_policy_structure(policy, framework, policy_type)
                return policy
            return self._parse_text_policy(response, framework, policy_type)
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning("Error parsing policy response: %s" % e)
            return self._get_fallback_policy(framework, policy_type, {})

    def _validate_policy_structure(
        self, policy: Dict[str, Any], framework: str, policy_type: str
    ) -> Dict[str, Any]:
        """Validate and enhance policy structure."""
        policy.setdefault("policy_id", f"{framework}_{policy_type}_{uuid4().hex[:8]}")
        policy.setdefault("title", f"{policy_type.replace('_', ' ').title()} Policy")
        policy.setdefault("version", "1.0")
        policy.setdefault("effective_date", datetime.now(timezone.utc).strftime("%Y-%m-%d"))
        policy.setdefault("framework", framework)
        policy.setdefault("policy_type", policy_type)
        policy.setdefault("created_at", datetime.now(timezone.utc).isoformat())
        policy.setdefault("sections", [])
        policy.setdefault("roles_responsibilities", [])
        policy.setdefault("procedures", [])
        policy.setdefault("compliance_requirements", [])
        for i, section in enumerate(policy["sections"]):
            section.setdefault("section_id", f"section_{i + 1}")
            section.setdefault("subsections", [])
            for j, subsection in enumerate(section.get("subsections", [])):
                subsection.setdefault("subsection_id", f"subsection_{j + 1}")
                subsection.setdefault("controls", [])
        return policy

    def _parse_text_policy(self, response: str, framework: str, policy_type: str) -> Dict[str, Any]:
        """Parse text-based policy as fallback."""
        policy = {
            "policy_id": f"{framework}_{policy_type}_{uuid4().hex[:8]}",
            "title": f"{policy_type.replace('_', ' ').title()} Policy",
            "version": "1.0",
            "effective_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "framework": framework,
            "policy_type": policy_type,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "sections": [],
            "roles_responsibilities": [],
            "procedures": [],
            "compliance_requirements": [],
        }
        lines = response.split("\n")
        current_section = None
        for line in lines:
            line = line.strip()
            if line.startswith("#") or line.startswith("Section"):
                if current_section:
                    policy["sections"].append(current_section)
                current_section = {
                    "section_id": f"section_{len(policy['sections']) + 1}",
                    "title": line.replace("#", "").strip(),
                    "content": "",
                    "subsections": [],
                }
            elif current_section and line:
                current_section["content"] += line + "\n"
        if current_section:
            policy["sections"].append(current_section)
        return policy

    def _apply_business_customizations(
        self,
        policy: Dict[str, Any],
        business_context: Dict[str, Any],
        customization_options: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Apply business-specific customizations to the policy."""
        policy["business_context"] = {
            "company_name": business_context.get("company_name", "Organization"),
            "industry": business_context.get("industry", "Unknown"),
            "employee_count": business_context.get("employee_count", 0),
            "customization_applied": datetime.now(timezone.utc).isoformat(),
        }
        industry = business_context.get("industry", "").lower()
        if industry in ["healthcare", "medical"]:
            policy = self._apply_healthcare_customizations(policy)
        elif industry in ["finance", "banking", "fintech"]:
            policy = self._apply_financial_customizations(policy)
        elif industry in ["technology", "software", "saas"]:
            policy = self._apply_technology_customizations(policy)
        org_size = self._categorize_organization_size(business_context.get("employee_count", 0))
        policy = self._apply_size_customizations(policy, org_size)
        return policy

    def _apply_healthcare_customizations(self, policy: Dict[str, Any]) -> Dict[str, Any]:
        """Apply healthcare industry-specific customizations."""
        healthcare_section = {
            "section_id": "healthcare_specific",
            "title": "Healthcare Industry Requirements",
            "content": "This section addresses healthcare-specific compliance requirements including HIPAA, patient data protection, and medical device security.",
            "subsections": [
                {
                    "subsection_id": "hipaa_compliance",
                    "title": "HIPAA Compliance",
                    "content": "Procedures for handling protected health information (PHI) in accordance with HIPAA requirements.",
                    "controls": ["PHI access controls", "Audit logging", "Breach notification"],
                }
            ],
        }
        policy["sections"].append(healthcare_section)
        policy["roles_responsibilities"].extend(
            [
                {
                    "role": "HIPAA Security Officer",
                    "responsibilities": [
                        "Oversee PHI security",
                        "Conduct risk assessments",
                        "Manage security incidents",
                    ],
                },
                {
                    "role": "Privacy Officer",
                    "responsibilities": [
                        "Ensure privacy compliance",
                        "Handle patient requests",
                        "Manage consent processes",
                    ],
                },
            ]
        )
        return policy

    def _apply_financial_customizations(self, policy: Dict[str, Any]) -> Dict[str, Any]:
        """Apply financial industry-specific customizations."""
        financial_section = {
            "section_id": "financial_specific",
            "title": "Financial Industry Requirements",
            "content": "This section addresses financial industry compliance requirements including SOX, PCI DSS, and banking regulations.",
            "subsections": [
                {
                    "subsection_id": "sox_compliance",
                    "title": "Sarbanes-Oxley Compliance",
                    "content": "Controls for financial reporting and internal controls over financial reporting.",
                    "controls": ["Financial controls", "Audit trails", "Segregation of duties"],
                }
            ],
        }
        policy["sections"].append(financial_section)
        policy["roles_responsibilities"].extend(
            [
                {
                    "role": "Chief Risk Officer",
                    "responsibilities": [
                        "Oversee risk management",
                        "Ensure regulatory compliance",
                        "Report to board",
                    ],
                },
                {
                    "role": "Compliance Officer",
                    "responsibilities": [
                        "Monitor regulatory changes",
                        "Conduct compliance training",
                        "Manage audits",
                    ],
                },
            ]
        )
        return policy

    def _apply_technology_customizations(self, policy: Dict[str, Any]) -> Dict[str, Any]:
        """Apply technology industry-specific customizations."""
        tech_section = {
            "section_id": "technology_specific",
            "title": "Technology Industry Requirements",
            "content": "This section addresses technology industry requirements including data protection, software security, and cloud compliance.",
            "subsections": [
                {
                    "subsection_id": "software_security",
                    "title": "Software Security",
                    "content": "Security requirements for software development and deployment.",
                    "controls": [
                        "Secure coding practices",
                        "Code reviews",
                        "Vulnerability testing",
                    ],
                }
            ],
        }
        policy["sections"].append(tech_section)
        policy["roles_responsibilities"].extend(
            [
                {
                    "role": "Chief Technology Officer",
                    "responsibilities": [
                        "Oversee technology strategy",
                        "Ensure security architecture",
                        "Manage technical risks",
                    ],
                },
                {
                    "role": "DevSecOps Lead",
                    "responsibilities": [
                        "Integrate security in development",
                        "Automate security testing",
                        "Monitor deployments",
                    ],
                },
            ]
        )
        return policy

    def _apply_size_customizations(self, policy: Dict[str, Any], org_size: str) -> Dict[str, Any]:
        """Apply organization size-specific customizations."""
        if org_size == "micro":
            policy["implementation_notes"] = [
                "Consider outsourcing complex compliance activities",
                "Focus on essential controls first",
                "Use cloud-based solutions to reduce overhead",
            ]
        elif org_size == "small":
            policy["implementation_notes"] = [
                "Implement controls in phases",
                "Consider managed services for specialized areas",
                "Focus on automation to reduce manual effort",
            ]
        elif org_size == "medium":
            policy["implementation_notes"] = [
                "Establish dedicated compliance team",
                "Implement comprehensive monitoring",
                "Consider compliance management platforms",
            ]
        else:
            policy["implementation_notes"] = [
                "Implement enterprise-grade solutions",
                "Establish compliance centers of excellence",
                "Consider advanced automation and AI tools",
            ]
        return policy

    def _generate_policy_implementation_guidance(
        self,
        policy: Dict[str, Any],
        business_context: Dict[str, Any],
        maturity_analysis: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Generate implementation guidance for the policy."""
        org_size = self._categorize_organization_size(business_context.get("employee_count", 0))
        maturity_analysis.get("maturity_level", "Basic")
        return {
            "implementation_phases": [
                {
                    "phase": "Phase 1: Foundation",
                    "duration_weeks": 2 if org_size in ["micro", "small"] else 4,
                    "activities": [
                        "Review and approve policy",
                        "Identify key stakeholders",
                        "Establish governance structure",
                    ],
                },
                {
                    "phase": "Phase 2: Implementation",
                    "duration_weeks": 4 if org_size in ["micro", "small"] else 8,
                    "activities": [
                        "Deploy controls and procedures",
                        "Train staff on new requirements",
                        "Implement monitoring systems",
                    ],
                },
                {
                    "phase": "Phase 3: Validation",
                    "duration_weeks": 2 if org_size in ["micro", "small"] else 4,
                    "activities": [
                        "Test controls effectiveness",
                        "Conduct internal audit",
                        "Address any gaps identified",
                    ],
                },
            ],
            "success_metrics": [
                "Policy approval and communication completion",
                "Staff training completion rate > 95%",
                "Control implementation rate > 90%",
                "Audit findings resolution rate > 95%",
            ],
            "common_challenges": [
                "Resource constraints",
                "Staff resistance to change",
                "Technical implementation complexity",
                "Ongoing maintenance requirements",
            ],
            "mitigation_strategies": [
                "Phased implementation approach",
                "Regular communication and training",
                "Automation where possible",
                "Regular review and updates",
            ],
        }

    def _generate_compliance_mapping(
        self, policy: Dict[str, Any], framework: str, policy_type: str
    ) -> Dict[str, Any]:
        """Generate compliance mapping for the policy."""
        control_mappings = {
            "ISO27001": {
                "information_security": ["A.5.1.1", "A.5.1.2"],
                "access_control": ["A.9.1.1", "A.9.1.2", "A.9.2.1"],
                "incident_management": ["A.16.1.1", "A.16.1.2", "A.16.1.3"],
                "business_continuity": ["A.17.1.1", "A.17.1.2", "A.17.2.1"],
            },
            "GDPR": {
                "data_protection": ["Art. 5", "Art. 6", "Art. 7"],
                "data_subject_rights": ["Art. 12", "Art. 13", "Art. 14", "Art. 15-22"],
                "privacy_by_design": ["Art. 25"],
                "breach_notification": ["Art. 33", "Art. 34"],
            },
            "SOC2": {
                "security": ["CC6.1", "CC6.2", "CC6.3"],
                "availability": ["A1.1", "A1.2", "A1.3"],
                "confidentiality": ["C1.1", "C1.2"],
                "processing_integrity": ["PI1.1", "PI1.2"],
            },
        }
        mapped_controls = control_mappings.get(framework, {}).get(policy_type, [])
        return {
            "framework": framework,
            "policy_type": policy_type,
            "mapped_controls": mapped_controls,
            "compliance_objectives": [
                f"Ensure compliance with {framework} requirements",
                "Establish clear governance and accountability",
                "Implement effective risk management",
                "Enable continuous monitoring and improvement",
            ],
            "audit_considerations": [
                "Document all policy implementations",
                "Maintain evidence of compliance activities",
                "Regular review and update cycles",
                "Staff training and awareness programs",
            ],
        }

    def _get_fallback_policy(
        self, framework: str, policy_type: str, business_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Provide fallback policy when AI generation fails."""
        return {
            "policy_id": f"{framework}_{policy_type}_{uuid4().hex[:8]}",
            "title": f"{policy_type.replace('_', ' ').title()} Policy",
            "version": "1.0",
            "effective_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "framework": framework,
            "policy_type": policy_type,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "sections": [
                {
                    "section_id": "section_1",
                    "title": "Purpose and Scope",
                    "content": f"This policy establishes the framework for {policy_type} in accordance with {framework} requirements.",
                    "subsections": [],
                },
                {
                    "section_id": "section_2",
                    "title": "Roles and Responsibilities",
                    "content": "This section defines the roles and responsibilities for implementing and maintaining this policy.",
                    "subsections": [],
                },
            ],
            "roles_responsibilities": [
                {
                    "role": "Policy Owner",
                    "responsibilities": ["Maintain policy", "Ensure compliance", "Regular reviews"],
                }
            ],
            "procedures": [
                {
                    "procedure_id": "proc_1",
                    "title": "Policy Review Procedure",
                    "steps": ["Annual review", "Update as needed", "Communicate changes"],
                }
            ],
            "compliance_requirements": [
                {
                    "requirement_id": "req_1",
                    "description": f"Comply with {framework} requirements",
                    "control_reference": "General compliance",
                }
            ],
            "business_context": business_context,
        }

    def _classify_intent(
        self, message: str, assessment_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Classifies the user's intent from their message, including assessment-specific intents."""
        import re

        message_lower = message.lower()
        assessment_context = assessment_context or {}
        intent_patterns = {
            "assessment_help": [
                "help.*question",
                "explain.*question",
                "clarify.*question",
                "what.*mean",
                "how.*answer",
                "guidance.*question",
                "assessment.*help",
                "question.*help",
            ],
            "question_clarification": [
                "clarify",
                "explain.*better",
                "don't understand",
                "what.*asking",
                "rephrase",
                "more.*detail",
            ],
            "gap_analysis": [
                "gap.*analysis",
                "what.*missing",
                "identify.*gaps",
                "compliance.*gaps",
                "missing.*requirements",
                "analyze.*gaps",
            ],
            "implementation_guidance": [
                "how.*implement",
                "implementation.*plan",
                "next.*steps",
                "action.*plan",
                "roadmap",
                "timeline.*implementation",
            ],
            "compliance_guidance": [
                "what.*requirements",
                "guide.*compliance",
                "help.*gdpr",
                "help.*iso",
                "help.*soc",
                "help.*hipaa",
            ],
            "evidence_guidance": [
                "what.*evidence",
                "collect.*evidence",
                "audit.*evidence",
                "documentation.*need",
                "records.*required",
            ],
            "policy_generation": [
                "create.*policy",
                "generate.*policy",
                "policy.*template",
                "draft.*policy",
                "write.*policy",
            ],
            "risk_assessment": [
                "risk.*assessment",
                "identify.*risks",
                "security.*risks",
                "vulnerability.*assessment",
            ],
            "out_of_scope": ["weather", "joke", "pasta", "recipe", "sports", "movie"],
        }
        frameworks = {
            "GDPR": "gdpr|general data protection",
            "ISO 27001": "iso.*27001|iso27001",
            "SOC 2": "soc.*2|soc2",
            "HIPAA": "hipaa|health insurance",
            "PCI DSS": "pci.*dss|payment card",
        }
        detected_intent = "general_query"
        confidence = 0.5
        detected_framework = None
        if assessment_context and assessment_context.get("in_assessment"):
            for intent, patterns in intent_patterns.items():
                if intent.startswith("assessment_") or intent in [
                    "question_clarification",
                    "gap_analysis",
                    "implementation_guidance",
                ]:
                    for pattern in patterns:
                        if re.search(pattern, message_lower):
                            detected_intent = intent
                            confidence = 0.9
                            break
                    if detected_intent != "general_query":
                        break
        if detected_intent == "general_query":
            for intent, patterns in intent_patterns.items():
                for pattern in patterns:
                    if re.search(pattern, message_lower):
                        detected_intent = intent
                        confidence = 0.85
                        break
                if detected_intent != "general_query":
                    break
        for framework, pattern in frameworks.items():
            if re.search(pattern, message_lower):
                detected_framework = framework
                confidence = min(confidence + 0.1, 0.95)
                break
        assessment_metadata = {}
        if assessment_context:
            assessment_metadata = {
                "framework_id": assessment_context.get("framework_id"),
                "question_id": assessment_context.get("question_id"),
                "section_id": assessment_context.get("section_id"),
                "assessment_progress": assessment_context.get("progress", 0),
            }
        return {
            "intent": detected_intent,
            "framework": detected_framework,
            "confidence": confidence,
            "message_length": len(message),
            "contains_question": "?" in message,
            "assessment_context": assessment_metadata,
        }

    def _extract_entities(
        self, message: str, assessment_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, List[str]]:
        """Extracts compliance-related entities from the message, including assessment-specific entities."""
        import re

        message_lower = message.lower()
        assessment_context = assessment_context or {}
        frameworks = []
        evidence_types = []
        control_domains = []
        assessment_entities = []
        framework_patterns = {
            "GDPR": "gdpr|general data protection",
            "ISO 27001": "iso.*27001|iso27001",
            "SOC 2": "soc.*2|soc2",
            "HIPAA": "hipaa|health insurance",
            "PCI DSS": "pci.*dss|payment card",
            "Cyber Essentials": "cyber.*essentials",
            "FCA": "fca|financial conduct",
        }
        evidence_patterns = {
            "policies": "polic(y|ies)",
            "procedures": "procedure",
            "logs": "log|audit trail",
            "training_records": "training.*record",
            "risk_assessments": "risk.*assessment",
            "incident_reports": "incident.*report",
        }
        control_patterns = {
            "access_control": "access.*control",
            "data_protection": "data.*protection",
            "network_security": "network.*security",
            "incident_management": "incident.*management",
            "business_continuity": "business.*continuity",
        }
        for framework, pattern in framework_patterns.items():
            if re.search(pattern, message_lower):
                frameworks.append(framework)
        for evidence_type, pattern in evidence_patterns.items():
            if re.search(pattern, message_lower):
                evidence_types.append(evidence_type)
        for control_domain, pattern in control_patterns.items():
            if re.search(pattern, message_lower):
                control_domains.append(control_domain)
        assessment_patterns = {
            "question_types": "multiple.*choice|yes.*no|free.*text|rating|scale",
            "assessment_stages": "stage|phase|section|part",
            "completion_status": "complete|incomplete|in.*progress|pending",
            "difficulty_indicators": "difficult|confusing|unclear|complex|simple|easy",
        }
        if assessment_context and assessment_context.get("in_assessment"):
            for entity_type, pattern in assessment_patterns.items():
                if re.search(pattern, message_lower):
                    assessment_entities.append(entity_type)
        if assessment_context:
            if assessment_context.get("framework_id"):
                frameworks.append(assessment_context["framework_id"])
            if assessment_context.get("section_id"):
                assessment_entities.append(f"section_{assessment_context['section_id']}")
        return {
            "frameworks": frameworks,
            "evidence_types": evidence_types,
            "control_domains": control_domains,
            "assessment_entities": assessment_entities,
            "context_enhanced": bool(assessment_context),
        }

    def _handle_adversarial_input(self, message: str) -> Dict[str, Any]:
        """Detects and handles adversarial input attempts."""
        import re

        message_lower = message.lower()
        adversarial_patterns = [
            "ignore.*previous.*instruction",
            "bypass.*security",
            "override.*system",
            "<script.*>",
            "select.*from.*where",
            "drop.*table",
            "union.*select",
            "exec.*cmd",
            "system\\(",
            "eval\\(",
            "javascript:",
            "data:text/html",
        ]
        is_adversarial = False
        for pattern in adversarial_patterns:
            if re.search(pattern, message_lower):
                is_adversarial = True
                break
        if len(message) > 5000:
            is_adversarial = True
        if len(set(message.split())) < len(message.split()) * 0.3:
            is_adversarial = True
        if is_adversarial:
            return {
                "is_adversarial": True,
                "response": "I'm designed to provide helpful compliance guidance. I can assist you with understanding regulatory requirements and implementation strategies. What specific aspect of compliance would you like to discuss?",
                "safety_triggered": True,
            }
        return {"is_adversarial": False, "response": None, "safety_triggered": False}

    async def _generate_response(
        self,
        message: str,
        context: Dict[str, Any],
        intent_result: Dict[str, Any],
        entities: Dict[str, Any],
    ) -> str:
        """Generates a contextual response based on intent and entities."""
        prompt = self.prompt_templates.get_main_prompt(message, context)
        enhanced_prompt = f"""
        User Intent: {intent_result["intent"]}
        Detected Framework: {intent_result.get("framework", "None")}
        Confidence: {intent_result["confidence"]}
        Entities: {entities}

        {prompt}

        Please provide a comprehensive response that addresses the user's specific intent and includes relevant compliance requirements, implementation guidance, and practical next steps.
        """
        return await self._generate_gemini_response(enhanced_prompt)

    def _validate_response_safety(
        self,
        response: str,
        input_content: str = "",
        content_type: str = "general",
        confidence_score: float = 0.8,
    ) -> Dict[str, Any]:
        """Validates the safety of the generated response using advanced role-based safety manager."""
        try:
            from services.ai.safety_manager import ContentType

            mapped_content_type = self.content_type_map.get(
                content_type, ContentType.GENERAL_QUESTION
            )
            safety_record = self.safety_manager.evaluate_content_safety(
                input_content=input_content,
                response_content=response,
                content_type=mapped_content_type,
                confidence_score=confidence_score,
                user_id=self.user_context.get("user_id"),
                session_id=getattr(self, "current_session_id", None),
            )
            is_safe = safety_record.decision in [SafetyDecision.ALLOW, SafetyDecision.MODIFY]
            safety_score = confidence_score * (1.0 - (safety_record.confidence_score or 0.0))
            modified_response = response
            if safety_record.decision == SafetyDecision.BLOCK:
                modified_response = (
                    "I can only provide guidance on compliance and regulatory matters. How can I help you with your compliance requirements?",
                )
                is_safe = False
                safety_score = 0.0
            elif safety_record.decision == SafetyDecision.MODIFY:
                modified_response = self.safety_manager.modify_response_content(
                    response, safety_record.applied_filters
                )
            return {
                "is_safe": is_safe,
                "safety_score": safety_score,
                "modified_response": modified_response,
                "safety_record": safety_record,
                "decision_reasoning": safety_record.reasoning,
            }
        except (requests.RequestException, KeyError, IndexError) as e:
            logger.warning("Advanced safety validation failed, using fallback: %s" % e)
            return self._basic_safety_validation(response)

    def _basic_safety_validation(self, response: str) -> Dict[str, Any]:
        """Fallback basic safety validation."""
        import re

        unsafe_patterns = [
            "bypass.*security",
            "ignore.*compliance",
            "violate.*regulation",
            "<script.*>",
            "javascript:",
            "data:text/html",
        ]
        is_safe = True
        safety_score = 1.0
        response_lower = response.lower()
        for pattern in unsafe_patterns:
            if re.search(pattern, response_lower):
                is_safe = False
                safety_score = 0.0
                break
        if len(response.strip()) < 10:
            safety_score = 0.5
        compliance_terms = ["compliance", "regulation", "framework", "policy", "audit", "evidence"]
        if not any(term in response_lower for term in compliance_terms):
            safety_score = max(safety_score - 0.2, 0.0)
        modified_response = response
        if not is_safe:
            modified_response = (
                "I can only provide guidance on compliance and regulatory matters. How can I help you with your compliance requirements?",
            )
        return {
            "is_safe": is_safe,
            "safety_score": safety_score,
            "modified_response": modified_response,
        }

    def _generate_follow_ups(self, context: Dict[str, Any]) -> List[str]:
        """Generates follow-up suggestions based on the conversation context."""
        intent = context.get("intent", {}).get("intent", "general_query")
        framework = context.get("intent", {}).get("framework")
        context.get("entities", {})
        follow_ups = []
        if intent == "compliance_guidance":
            if framework:
                follow_ups.extend(
                    [
                        f"Would you like me to explain specific {framework} requirements?",
                        f"Should I help you create an implementation plan for {framework}?",
                        f"Do you need guidance on {framework} evidence collection?",
                    ]
                )
            else:
                follow_ups.extend(
                    [
                        "Which compliance framework are you most interested in?",
                        "Would you like me to recommend frameworks for your industry?",
                        "Should I help you assess your current compliance posture?",
                    ]
                )
        elif intent == "evidence_guidance":
            follow_ups.extend(
                [
                    "Would you like me to create an evidence collection checklist?",
                    "Should I explain how to organize your compliance documentation?",
                    "Do you need help with audit preparation?",
                ]
            )
        elif intent == "policy_generation":
            follow_ups.extend(
                [
                    "Would you like me to help draft a specific policy?",
                    "Should I explain policy review and approval processes?",
                    "Do you need guidance on policy implementation?",
                ]
            )
        else:
            follow_ups.extend(
                [
                    "What specific compliance challenge can I help you with?",
                    "Would you like to learn about compliance frameworks?",
                    "Should I help you assess your compliance needs?",
                ]
            )
        return follow_ups[:3]

    def _handle_rate_limit(self, user_id: UUID) -> Dict[str, Any]:
        """Handles AI service rate limiting."""
        import time

        time.time()
        rate_limited = False
        if rate_limited:
            return {
                "rate_limited": True,
                "retry_after": 60,
                "fallback_response": "I'm currently experiencing high demand. Please try your question again in a moment, or check our knowledge base for immediate answers.",
                "cached_response": None,
            }
        return {
            "rate_limited": False,
            "retry_after": 0,
            "fallback_response": None,
            "cached_response": None,
        }

    def _manage_context(
        self, conversation_id: UUID, conversation_history: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        """Manages conversation context and maintains topic continuity."""
        context_window = (
            conversation_history[-6:] if len(conversation_history) > 6 else conversation_history
        )
        topic_continuity = True
        framework_context = None
        frameworks = ["GDPR", "ISO 27001", "SOC 2", "HIPAA", "PCI DSS"]
        for message in reversed(context_window):
            content = message.get("content", "").upper()
            for framework in frameworks:
                if framework in content:
                    framework_context = framework
                    break
            if framework_context:
                break
        if len(context_window) > 0:
            recent_topics = [msg.get("content", "")[:50] for msg in context_window[-3:]]
            context_summary = f"Recent discussion: {', '.join(recent_topics)}"
        else:
            context_summary = "New conversation"
        return {
            "context_window": context_window,
            "topic_continuity": topic_continuity,
            "framework_context": framework_context,
            "context_summary": context_summary,
        }

    @staticmethod
    def _validate_accuracy(response: str, framework: str) -> Dict[str, Any]:
        """Validates the accuracy of compliance information in the response."""
        import re

        accuracy_patterns = {
            "GDPR": {
                "72 hours": "72.*hour.*notification",
                "supervisory authorities": "supervisory.*authorit",
                "data protection officer": "data.*protection.*officer",
                "lawful basis": "lawful.*basis",
            },
            "ISO 27001": {
                "risk assessment": "risk.*assessment",
                "management system": "management.*system",
                "continuous improvement": "continuous.*improvement",
            },
            "SOC 2": {
                "trust services criteria": "trust.*services.*criteria",
                "type ii": "type.*ii",
                "operational effectiveness": "operational.*effectiveness",
            },
        }
        response_lower = response.lower()
        framework_patterns = accuracy_patterns.get(framework, {})
        fact_checks = []
        verified_count = 0
        for claim, pattern in framework_patterns.items():
            verified = bool(re.search(pattern, response_lower))
            fact_checks.append(
                {"claim": claim, "verified": verified, "source": f"{framework} regulations"}
            )
            if verified:
                verified_count += 1
        accuracy_score = verified_count / len(framework_patterns) if framework_patterns else 0.8
        return {
            "accuracy_score": accuracy_score,
            "fact_checks": fact_checks,
            "confidence": accuracy_score,
            "sources": [f"{framework} regulations"] if framework_patterns else [],
        }

    @staticmethod
    def _detect_hallucination(response: str) -> Dict[str, Any]:
        """Detects potential AI hallucinations in compliance responses."""
        import re

        suspicious_patterns = [
            "€\\d+,\\d+.*registration.*fee",
            "\\$\\d+,\\d+.*annual.*cost",
            "article.*\\d+.*requires.*€",
            "section.*\\d+.*mandates.*\\$",
            "must.*pay.*\\d+.*annually",
        ]
        response_lower = response.lower()
        suspicious_claims = []
        for pattern in suspicious_patterns:
            matches = re.findall(pattern, response_lower)
            suspicious_claims.extend(matches)
        hallucination_detected = len(suspicious_claims) > 0
        confidence = 0.9 if hallucination_detected else 0.1
        return {
            "hallucination_detected": hallucination_detected,
            "confidence": confidence,
            "suspicious_claims": suspicious_claims,
            "verified_claims": [],
            "recommendation": "flag_for_review" if hallucination_detected else "approved",
        }

    async def analyze_evidence_gap(
        self, business_profile_id: UUID, framework: str
    ) -> Dict[str, Any]:
        """
        Analyze compliance evidence gaps for a specific framework.
        Called by chat router for compliance analysis.
        """
        try:
            context = await self.context_manager.get_conversation_context(
                conversation_id=uuid4(), business_profile_id=business_profile_id
            )
            prompt = f"""Analyze compliance evidence gaps for {framework}:

            Business Profile:
            - Company: {context.get("business_profile", {}).get("company_name", "Unknown")}
            - Industry: {context.get("business_profile", {}).get("industry", "Unknown")}
            - Size: {context.get("business_profile", {}).get("employee_count", 0)} employees

            Current Evidence Status:
            - Total Evidence Items: {len(context.get("recent_evidence", []))}
            - Evidence Types: {self._get_evidence_types_summary(context.get("recent_evidence", []))}

            Framework: {framework}

            Provide a structured analysis with:
            1. Current completion percentage (0-100)
            2. Critical missing evidence types
            3. Top 3 priority recommendations with specific actions
            4. Risk assessment of current gaps
            """
            response = await self._generate_ai_response(
                "You are a compliance expert analyzing evidence gaps.", prompt
            )
            try:
                import json

                if isinstance(response, str) and response.strip().startswith("{"):
                    parsed_response = json.loads(response)
                    completion_percentage = parsed_response.get("completion_percentage", 50)
                    recommendations = parsed_response.get(
                        "recommendations",
                        [],
                    )
                    critical_gaps = parsed_response.get("critical_gaps", [])
                    risk_level = parsed_response.get("risk_level", "Medium")
                else:
                    completion_percentage = 30
                    recommendations = [
                        {
                            "type": "documentation",
                            "description": "Review compliance documentation",
                            "priority": "medium",
                        },
                        {
                            "type": "policy",
                            "description": "Update security policies",
                            "priority": "high",
                        },
                        {
                            "type": "training",
                            "description": "Conduct staff training",
                            "priority": "medium",
                        },
                    ]
                    critical_gaps = ["Analysis unavailable", "Manual review needed"]
                    risk_level = "Medium"
            except (json.JSONDecodeError, AttributeError):
                completion_percentage = 30
                recommendations = [
                    {
                        "type": "documentation",
                        "description": "Review compliance documentation",
                        "priority": "medium",
                    },
                    {
                        "type": "policy",
                        "description": "Update security policies",
                        "priority": "high",
                    },
                    {
                        "type": "training",
                        "description": "Conduct staff training",
                        "priority": "medium",
                    },
                ]
                critical_gaps = ["Documentation gaps", "Policy updates needed"]
                risk_level = "Medium"
            evidence_items = context.get("recent_evidence", [])
            evidence_types_dict = self._get_evidence_types_summary(evidence_items)
            evidence_types = list(evidence_types_dict.keys())
            return {
                "framework": framework,
                "completion_percentage": completion_percentage,
                "evidence_collected": len(evidence_items),
                "evidence_types": evidence_types,
                "recent_activity": len([item for item in evidence_items if item.get("updated_at")]),
                "recommendations": recommendations,
                "critical_gaps": critical_gaps,
                "risk_level": risk_level,
            }
        except (json.JSONDecodeError, requests.RequestException, ValueError) as e:
            logger.error("Error analyzing evidence gap: %s" % e)
            return {
                "framework": framework,
                "completion_percentage": 30,
                "evidence_collected": 0,
                "evidence_types": [],
                "recent_activity": 0,
                "recommendations": [
                    {
                        "type": "documentation",
                        "description": "Review compliance documentation",
                        "priority": "medium",
                    },
                    {
                        "type": "policy",
                        "description": "Update security policies",
                        "priority": "high",
                    },
                    {
                        "type": "training",
                        "description": "Conduct staff training",
                        "priority": "medium",
                    },
                ],
                "critical_gaps": ["Analysis unavailable", "Manual review needed"],
                "risk_level": "Medium",
            }

    async def get_assessment_help(
        self,
        question_id: str,
        question_text: str,
        framework_id: str,
        business_profile_id: UUID,
        section_id: Optional[str] = None,
        user_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Provide AI-powered contextual guidance for specific assessment questions.
        Optimized for performance with caching and fast fallbacks.

        Args:
            question_id: Unique identifier for the question
            question_text: The actual question text
            framework_id: The compliance framework (e.g., 'gdpr', 'iso27001')
            business_profile_id: User's business profile for context
            section_id: Optional section identifier within the framework
            user_context: Additional context from the user

        Returns:
            Dict containing guidance, confidence score, related topics, etc.
        """
        try:
            cache_key = f"help_{framework_id}_{question_id}_{hash(question_text)}"
            if hasattr(self, "ai_cache") and self.ai_cache:
                cached_response = await self.ai_cache.get(cache_key)
                if cached_response:
                    logger.debug("Returning cached help response for %s" % question_id)
                    return cached_response
            system_prompt = (
                f"You are a {framework_id} compliance expert. Provide concise, actionable guidance.",
            )
            user_prompt = f"""Question: {question_text}

Provide brief, practical guidance in JSON format with 'guidance' and 'confidence_score' fields."""
            start_time = datetime.now(timezone.utc)
            response = await asyncio.wait_for(
                self._generate_ai_response(system_prompt, user_prompt), timeout=2.5
            )
            response_time = (datetime.now(timezone.utc) - start_time).total_seconds()
            structured_response = self._parse_assessment_help_response(
                response,
            )
            structured_response.update(
                {
                    "request_id": f"help_{framework_id}_{question_id}_{uuid4().hex[:8]}",
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "framework_id": framework_id,
                    "question_id": question_id,
                    "response_time": response_time,
                }
            )
            if hasattr(self, "ai_cache") and self.ai_cache:
                await self.ai_cache.set(
                    cache_key,
                    structured_response,
                    ttl=300,
                )
            return structured_response
        except asyncio.TimeoutError:
            logger.warning("AI help request timed out for %s, using fast fallback" % question_id)
            if self.analytics_monitor:
                with contextlib.suppress(ValueError, TypeError):
                    await self.analytics_monitor.record_metric(
                        MetricType.ERROR,
                        "ai_timeout_error",
                        1,
                        metadata={
                            "error_type": "TimeoutError",
                            "operation": "get_assessment_help",
                            "question_id": question_id,
                            "framework_id": framework_id,
                        },
                    )
            return self._get_fast_fallback_help(question_text, framework_id, question_id)
        except (ValueError, TypeError) as e:
            logger.error("Error generating assessment help: %s" % e)
            if self.analytics_monitor:
                with contextlib.suppress(ValueError, TypeError):
                    await self.analytics_monitor.record_metric(
                        MetricType.ERROR,
                        "ai_service_error",
                        1,
                        metadata={
                            "error_type": type(e).__name__,
                            "operation": "get_assessment_help",
                            "question_id": question_id,
                            "framework_id": framework_id,
                        },
                    )
            return self._get_fallback_assessment_help(question_text, framework_id)

    async def generate_assessment_followup(
        self,
        current_answers: Dict[str, Any],
        framework_id: str,
        business_profile_id: UUID,
        assessment_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Generate intelligent follow-up questions based on current assessment progress.

        Args:
            current_answers: User's current assessment responses
            framework_id: The compliance framework being assessed
            business_profile_id: User's business profile for context
            assessment_context: Additional assessment context

        Returns:
            Dict containing follow-up questions and recommendations
        """
        try:
            context = await self.context_manager.get_conversation_context(
                conversation_id=uuid4(), business_profile_id=business_profile_id
            )
            prompt_data = self.prompt_templates.get_assessment_followup_prompt(
                current_answers=current_answers,
                framework_id=framework_id,
                business_context=context.get("business_profile", {}),
                assessment_context=assessment_context or {},
            )
            response = await self._generate_ai_response(prompt_data["system"], prompt_data["user"])
            structured_response = self._parse_assessment_followup_response(response)
            structured_response.update(
                {
                    "request_id": f"followup_{framework_id}_{uuid4().hex[:8]}",
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "framework_id": framework_id,
                }
            )
            return structured_response
        except (OSError, requests.RequestException, ValueError) as e:
            logger.error("Error generating assessment followup: %s" % e)
            return self._get_fallback_assessment_followup(framework_id)

    async def analyze_assessment_results(
        self, assessment_results: Dict[str, Any], framework_id: str, business_profile_id: UUID
    ) -> Dict[str, Any]:
        """
        Perform comprehensive AI analysis of assessment results.

        Args:
            assessment_results: The completed assessment responses
            framework_id: The compliance framework being assessed
            business_profile_id: User's business profile for context

        Returns:
            Dict containing gaps, recommendations, risk assessment, etc.
        """
        try:
            context = await self.context_manager.get_conversation_context(
                conversation_id=uuid4(), business_profile_id=business_profile_id
            )
            business_profile = context.get("business_profile", {})
            cached_content = await self._get_or_create_assessment_cache(
                framework_id=framework_id,
                business_profile=business_profile,
                assessment_context={
                    "assessment_type": "analysis",
                    "results_summary": assessment_results,
                },
            )
            prompt_data = self.prompt_templates.get_assessment_analysis_prompt(
                assessment_results=assessment_results,
                framework_id=framework_id,
                business_context=business_profile,
            )
            response = await self._generate_ai_response_with_cache(
                prompt_data["system"],
                prompt_data["user"],
                task_type="analysis",
                context=context,
                cached_content=cached_content,
            )
            structured_response = self._parse_assessment_analysis_response(response)
            structured_response.update(
                {
                    "request_id": f"analysis_{framework_id}_{uuid4().hex[:8]}",
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "framework_id": framework_id,
                }
            )
            return structured_response
        except (OSError, requests.RequestException, ValueError) as e:
            logger.error("Error analyzing assessment results: %s" % e)
            return self._get_fallback_assessment_analysis(framework_id)

    async def get_assessment_recommendations(
        self,
        gaps: List[Dict[str, Any]],
        business_profile: Dict[str, Any],
        framework_id: str,
        existing_policies: Optional[List[str]] = None,
        industry_context: Optional[str] = None,
        timeline_preferences: str = "standard",
    ) -> Dict[str, Any]:
        """
        Generate personalized implementation recommendations based on assessment gaps.

        Args:
            gaps: Identified compliance gaps from assessment
            business_profile: Business context and profile information
            framework_id: The compliance framework
            existing_policies: List of existing policies
            industry_context: Industry-specific context
            timeline_preferences: Implementation timeline preference

        Returns:
            Dict containing recommendations and implementation plan
        """
        try:
            prompt_data = self.prompt_templates.get_assessment_recommendations_prompt(
                gaps=gaps,
                business_profile=business_profile,
                framework_id=framework_id,
                existing_policies=existing_policies or [],
                industry_context=industry_context,
                timeline_preferences=timeline_preferences,
            )
            response = await self._generate_ai_response(prompt_data["system"], prompt_data["user"])
            structured_response = self._parse_assessment_recommendations_response(response)
            logger.info("Structured response type: %s" % type(structured_response))
            logger.info(
                "Structured response keys: %s"
                % (
                    structured_response.keys()
                    if isinstance(structured_response, dict)
                    else "Not a dict"
                )
            )
            if isinstance(structured_response, dict) and "recommendations" in structured_response:
                logger.info(
                    "Recommendations count: %s" % len(structured_response["recommendations"])
                )
                if structured_response["recommendations"]:
                    logger.info(
                        "First recommendation type: %s"
                        % type(structured_response["recommendations"][0])
                    )
                    logger.info(
                        "First recommendation: %s" % structured_response["recommendations"][0]
                    )
            structured_response.update(
                {
                    "request_id": f"recommendations_{framework_id}_{uuid4().hex[:8]}",
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "framework_id": framework_id,
                }
            )
            return structured_response
        except (OSError, requests.RequestException, ValueError) as e:
            logger.error("Error generating assessment recommendations: %s" % e)
            return self._get_fallback_assessment_recommendations(framework_id)

    def _get_evidence_types_summary(self, evidence_items: List[Dict[str, Any]]) -> Dict[str, int]:
        """Summarize evidence types from evidence items."""
        type_counts = {}
        for item in evidence_items:
            evidence_type = item.get("evidence_type", "unknown")
            type_counts[evidence_type] = type_counts.get(evidence_type, 0) + 1
        return type_counts

    async def _generate_ai_response_with_cache(
        self,
        system_prompt: str,
        user_prompt: str,
        task_type: str = "general",
        context: Optional[Dict[str, Any]] = None,
        cached_content=None,
    ) -> str:
        """
        Generate AI response using cached content for improved performance.

        Args:
            system_prompt: System prompt
            user_prompt: User prompt
            task_type: Type of task for model selection
            context: Additional context
            cached_content: Google CachedContent for performance optimization

        Returns:
            AI generated response text
        """
        start_time = datetime.now()
        cache_hit = cached_content is not None
        try:
            model, instruction_id = self._get_task_appropriate_model(
                task_type=task_type, context=context, cached_content=cached_content
            )
            conversation_parts = [system_prompt, user_prompt]
            if cached_content:
                logger.debug("Using cached content for %s task" % task_type)
                response = model.generate_content(conversation_parts, cached_content=cached_content)
            else:
                logger.debug("No cached content available for %s task" % task_type)
                logger.info(
                    "Generating response with model: %s"
                    % (model.model_name if hasattr(model, "model_name") else "unknown")
                )
                logger.info("System prompt: %s..." % system_prompt[:100])
                logger.info("User prompt: %s..." % user_prompt[:200])
                response = model.generate_content(conversation_parts)
                logger.info(
                    "Got response object: %s, type: %s" % (response is not None, type(response))
                )
            response_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            if self.cached_content_manager and context:
                cache_key = self._generate_cache_key_for_context(context, task_type)
                self.cached_content_manager.record_cache_performance(
                    cache_key, response_time_ms, cache_hit
                )
                if not cache_hit and response_time_ms < 1000:
                    await self._add_to_cache_warming_queue(context, task_type)
            model_name = getattr(model, "model_name", "unknown")
            self.circuit_breaker.record_success(model_name)
            response_text = self._extract_response_text(response)
            logger.debug(
                "Response text for %s: %s"
                % (task_type, response_text[:200] if response_text else "EMPTY")
            )
            return response_text
        except (ValueError, KeyError, IndexError) as e:
            try:
                model_name = (
                    getattr(model, "model_name", "unknown") if "model" in locals() else "unknown"
                )
                self.circuit_breaker.record_failure(model_name)
            except (ValueError, TypeError):
                pass
            logger.error("Error generating AI response with cache: %s" % e)
            logger.error("Exception type: %s" % type(e).__name__)
            logger.error("Exception details: %s" % str(e))
            import traceback

            logger.error("Traceback: %s" % traceback.format_exc())
            return await self._generate_ai_response(system_prompt, user_prompt)

    async def _generate_ai_response(self, system_prompt: str, user_prompt: str) -> str:
        """Generate AI response using the configured model."""
        try:
            model, instruction_id = self._get_task_appropriate_model(
                task_type="general", context={"priority": 1}
            )
            full_prompt = f"System: {system_prompt}\n\nUser: {user_prompt}"
            response = model.generate_content(full_prompt)
            if hasattr(response, "text") and response.text:
                return response.text
            elif hasattr(response, "candidates") and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, "finish_reason"):
                    if candidate.finish_reason == 2:
                        logger.warning(
                            "AI response blocked by safety filters - providing compliance-focused fallback",
                        )
                        return (
                            "I understand you're asking about compliance matters. For regulatory compliance, it's important to follow established frameworks and maintain proper documentation. Could you please rephrase your question to be more specific about the compliance area you need help with?",
                        )
                    elif candidate.finish_reason == 3:
                        logger.warning("AI response blocked due to recitation concerns")
                        return (
                            "I can help with compliance guidance using my own analysis. Please rephrase your question and I'll provide original insights based on compliance best practices.",
                        )
                    else:
                        logger.warning(
                            "AI response incomplete, finish_reason: %s" % candidate.finish_reason
                        )
                        return (
                            "I'm here to help with compliance and regulatory matters. Please try rephrasing your question to focus on specific compliance requirements.",
                        )
            return (
                "I apologize, but I'm unable to provide a response at this time. Please try again later.",
            )
        except (KeyError, IndexError) as e:
            logger.error("Error generating AI response: %s" % e)
            return (
                "I apologize, but I'm unable to provide a response at this time. Please try again later.",
            )

    def _extract_response_text(self, response) -> str:
        """Safely extract text from Google AI response, handling safety filtering and other issues."""
        logger.info("=== DEBUG: Extracting response text ===")
        logger.info("Raw response type: %s" % type(response))
        logger.info("Response has text attr: %s" % hasattr(response, "text"))
        logger.info("Response object: %s" % response)
        try:
            if hasattr(response, "text"):
                text_value = response.text
                logger.info("Response.text value: %s" % repr(text_value))
                logger.info("Text length: %s" % (len(text_value) if text_value else 0))
                if text_value and text_value.strip():
                    logger.info("SUCCESS: Found valid text content")
                    return text_value.strip()
                else:
                    logger.warning("PROBLEM: response.text is empty or None")
        except (ValueError, TypeError) as e:
            logger.error("Quick accessor failed: %s, type: %s" % (e, type(e).__name__))
        logger.info("=== DEBUG: Detailed response inspection ===")
        try:
            if hasattr(response, "__dict__"):
                logger.info("Response attributes: %s" % list(response.__dict__.keys()))
            if hasattr(response, "candidates"):
                logger.info(
                    "Has candidates: %s" % (len(response.candidates) if response.candidates else 0)
                )
                if response.candidates:
                    candidate = response.candidates[0]
                    logger.info("Candidate type: %s" % type(candidate))
                    logger.info(
                        "Candidate attributes: %s"
                        % (
                            list(candidate.__dict__.keys())
                            if hasattr(candidate, "__dict__")
                            else "No __dict__"
                        )
                    )
                    if hasattr(candidate, "finish_reason"):
                        logger.info("Finish reason: %s" % candidate.finish_reason)
                        logger.info("Finish reason type: %s" % type(candidate.finish_reason))
                        if candidate.finish_reason == 1:
                            logger.info("Finish reason: STOP (normal completion)")
                        elif candidate.finish_reason == 2:
                            logger.warning(
                                "Finish reason: MAX_TOKENS (response truncated)",
                            )
                        elif candidate.finish_reason == 3:
                            logger.warning("Finish reason: SAFETY (content filtered)")
                        elif candidate.finish_reason == 4:
                            logger.warning("Finish reason: RECITATION (content blocked)")
                        elif candidate.finish_reason == 5:
                            logger.warning("Finish reason: OTHER (unknown issue)")
                        else:
                            logger.info(
                                "Finish reason: %s (unknown code)" % candidate.finish_reason
                            )
                    if hasattr(candidate, "content"):
                        logger.info("Has content: %s" % (candidate.content is not None))
                        if candidate.content:
                            logger.info("Content type: %s" % type(candidate.content))
                            if hasattr(candidate.content, "__dict__"):
                                logger.info(
                                    "Content attributes: %s"
                                    % list(candidate.content.__dict__.keys())
                                )
                            if hasattr(candidate.content, "parts"):
                                logger.info(
                                    "Has parts: %s"
                                    % (
                                        len(candidate.content.parts)
                                        if candidate.content.parts
                                        else 0
                                    )
                                )
                                if candidate.content.parts:
                                    for i, part in enumerate(candidate.content.parts):
                                        logger.info("Part %s type: %s" % (i, type(part)))
                                        if hasattr(part, "text"):
                                            logger.info("Part %s text: %s" % (i, repr(part.text)))
                                        if hasattr(part, "__dict__"):
                                            logger.info(
                                                "Part %s attributes: %s"
                                                % (i, list(part.__dict__.keys()))
                                            )
            if hasattr(response, "prompt_feedback"):
                logger.info("Has prompt_feedback: %s" % (response.prompt_feedback is not None))
                if response.prompt_feedback:
                    logger.info("Prompt feedback type: %s" % type(response.prompt_feedback))
                    if hasattr(response.prompt_feedback, "__dict__"):
                        logger.info(
                            "Prompt feedback attributes: %s"
                            % list(response.prompt_feedback.__dict__.keys())
                        )
                    if hasattr(response.prompt_feedback, "block_reason"):
                        logger.info("Block reason: %s" % response.prompt_feedback.block_reason)
                    if hasattr(response.prompt_feedback, "safety_ratings"):
                        logger.info("Safety ratings: %s" % response.prompt_feedback.safety_ratings)
        except Exception as inspect_error:
            logger.error(
                "Error during response inspection: %s" % inspect_error,
            )
        try:
            if hasattr(response, "candidates") and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, "finish_reason"):
                    if candidate.finish_reason in [2, 3, 4, 5]:
                        logger.warning(
                            "Response blocked with finish_reason: %s" % candidate.finish_reason
                        )
                        if hasattr(response, "prompt_feedback") and response.prompt_feedback:
                            if hasattr(response.prompt_feedback, "block_reason"):
                                if response.prompt_feedback.block_reason == "RECITATION":
                                    logger.warning(
                                        "AI response blocked due to Google API recitation bug - providing fallback",
                                    )
                                    return (
                                        "Content temporarily unavailable due to system limitations. Please rephrase your question and I'll provide original compliance insights.",
                                    )
                        if candidate.finish_reason == 2:
                            logger.warning("AI response truncated due to token limit")
                            return (
                                "Response truncated. Please try a more specific question for complete guidance on compliance requirements.",
                            )
                        elif candidate.finish_reason == 3:
                            logger.warning("AI response blocked by safety filters")
                            return (
                                "I understand you're asking about compliance matters. Let me provide general guidance: For regulatory compliance, it's important to follow established frameworks, maintain proper documentation, and ensure regular audits. Could you please rephrase your question to be more specific about the compliance area you need help with?",
                            )
                        elif candidate.finish_reason == 4:
                            logger.warning(
                                "AI response blocked due to recitation concerns",
                            )
                            return (
                                "I can help with compliance guidance using my own analysis. Please rephrase your question and I'll provide original insights based on compliance best practices.",
                            )
                        else:
                            logger.warning("AI response blocked for other reasons")
                            return (
                                "I'm here to help with compliance and regulatory matters. Please try rephrasing your question to focus on specific compliance requirements or frameworks.",
                            )
                if hasattr(candidate, "content") and candidate.content:
                    if hasattr(candidate.content, "parts") and candidate.content.parts:
                        text_parts = []
                        for part in candidate.content.parts:
                            if hasattr(part, "text") and part.text:
                                text_parts.append(part.text.strip())
                        if text_parts:
                            result_text = "\n".join(text_parts).strip()
                            logger.info(
                                "SUCCESS: Extracted text from parts: %s chars" % len(result_text)
                            )
                            return result_text
            logger.error(
                "CRITICAL: No valid response text found after all extraction attempts",
            )
            return (
                "I apologize, but I'm unable to provide a response at this time. Please try rephrasing your question.",
            )
        except (KeyError, IndexError) as e:
            logger.error("Error extracting response text: %s" % e)
            import traceback

            logger.error("Traceback: %s" % traceback.format_exc())
            return (
                "I apologize, but I'm unable to provide a response at this time. Please try again later.",
            )

    async def _stream_response(
        self,
        system_prompt: str,
        user_prompt: str,
        task_type: str = "general",
        context: Optional[Dict[str, Any]] = None,
    ) -> AsyncIterator[str]:
        """Generate streaming AI response using task-appropriate model with circuit breaker protection."""
        model = None
        model_name = "unknown"
        try:
            tools = (
                self._get_tools_for_task(task_type)
                if task_type in ["analysis", "recommendations"]
                else []
            )
            model, instruction_id = self._get_task_appropriate_model(task_type, context, tools)
            model_name = getattr(model, "model_name", "unknown")
            full_prompt = f"System: {system_prompt}\n\nUser: {user_prompt}"
            if not self.circuit_breaker.is_model_available(model_name):
                raise ModelUnavailableException(
                    model_name=model_name, reason="Circuit breaker is open"
                )
            response_stream = model.generate_content_stream(full_prompt)
            for chunk in response_stream:
                if hasattr(chunk, "text") and chunk.text:
                    self.circuit_breaker.record_success(model_name)
                    yield chunk.text
                elif hasattr(chunk, "candidates") and chunk.candidates:
                    for candidate in chunk.candidates:
                        if hasattr(candidate, "content") and candidate.content:
                            for part in candidate.content.parts:
                                if hasattr(part, "text") and part.text:
                                    self.circuit_breaker.record_success(model_name)
                                    yield part.text
        except (ModelUnavailableException, CircuitBreakerException) as e:
            logger.error("Model %s unavailable for streaming: %s" % (model_name, e))
            yield "I apologize, but the AI service is temporarily unavailable. Please try again in a few moments."
        except (KeyError, IndexError) as e:
            logger.error(
                "Error generating streaming AI response with model %s: %s" % (model_name, e)
            )
            if model:
                self.circuit_breaker.record_failure(model_name, e)
            if self.analytics_monitor:
                try:
                    await self.analytics_monitor.record_metric(
                        MetricType.ERROR,
                        "ai_service_error",
                        1,
                        metadata={
                            "error_type": type(e).__name__,
                            "model_name": model_name,
                            "operation": "streaming_response",
                        },
                    )
                except Exception as analytics_error:
                    logger.warning("Failed to record error metric: %s" % analytics_error)
            yield "I apologize, but I'm unable to provide a response at this time. Please try again later."

    async def analyze_assessment_results_stream(
        self,
        assessment_responses: List[Dict[str, Any]],
        framework_id: str,
        business_profile_id: UUID,
        user_context: Optional[Dict[str, Any]] = None,
    ) -> AsyncIterator[str]:
        """
        Stream AI-powered analysis of assessment responses with real-time updates.

        Args:
            assessment_responses: List of question responses
            framework_id: The compliance framework
            business_profile_id: User's business profile for context
            user_context: Additional context from the user

        Yields:
            String chunks of the analysis as they're generated
        """
        try:
            context = await self.context_manager.get_conversation_context(
                conversation_id=uuid4(), business_profile_id=business_profile_id
            )
            prompt_dict = self.prompt_templates.get_assessment_analysis_prompt(
                assessment_results={
                    "responses": assessment_responses,
                    "framework_id": framework_id,
                },
                framework_id=framework_id,
                business_context=context.get("business_profile", {}),
            )
            prompt = prompt_dict.get("user", "")
            stream_context = {
                "framework": framework_id,
                "business_context": context.get("business_profile", {}),
                "prompt_length": len(prompt) if isinstance(prompt, str) else 1000,
            }
            async for chunk in self._stream_response(
                "You are ComplianceGPT, providing comprehensive assessment analysis.",
                prompt,
                task_type="analysis",
                context=stream_context,
            ):
                yield chunk
        except (OSError, requests.RequestException) as e:
            logger.error("Error streaming assessment analysis: %s" % e)
            yield f"Unable to analyze assessment results for {framework_id} at this time."

    async def get_assessment_recommendations_stream(
        self,
        assessment_gaps: List[Dict[str, Any]],
        framework_id: str,
        business_profile_id: UUID,
        priority_level: str = "high",
        user_context: Optional[Dict[str, Any]] = None,
    ) -> AsyncIterator[str]:
        """
        Stream personalized recommendations based on assessment gaps.

        Args:
            assessment_gaps: List of identified compliance gaps
            framework_id: The compliance framework
            business_profile_id: User's business profile for context
            priority_level: Priority filter for recommendations
            user_context: Additional context from the user

        Yields:
            String chunks of recommendations as they're generated
        """
        try:
            context = await self.context_manager.get_conversation_context(
                conversation_id=uuid4(), business_profile_id=business_profile_id
            )
            prompt_dict = self.prompt_templates.get_assessment_recommendations_prompt(
                gaps=assessment_gaps,
                business_profile=context.get("business_profile", {}),
                framework_id=framework_id,
            )
            prompt = prompt_dict.get("user", "")
            stream_context = {
                "framework": framework_id,
                "business_context": context.get("business_profile", {}),
                "prompt_length": len(prompt),
                "priority_level": priority_level,
            }
            async for chunk in self._stream_response(
                "You are ComplianceGPT, providing practical implementation recommendations.",
                prompt,
                task_type="recommendations",
                context=stream_context,
            ):
                yield chunk
        except (OSError, requests.RequestException) as e:
            logger.error("Error streaming assessment recommendations: %s" % e)
            yield f"Unable to generate recommendations for {framework_id} at this time."

    async def get_assessment_help_stream(
        self,
        question_id: str,
        question_text: str,
        framework_id: str,
        business_profile_id: UUID,
        section_id: Optional[str] = None,
        user_context: Optional[Dict[str, Any]] = None,
    ) -> AsyncIterator[str]:
        """
        Stream contextual guidance for specific assessment questions.

        Args:
            question_id: Unique identifier for the question
            question_text: The actual question text
            framework_id: The compliance framework
            business_profile_id: User's business profile for context
            section_id: Optional section identifier
            user_context: Additional context from the user

        Yields:
            String chunks of guidance as they're generated
        """
        try:
            context = await self.context_manager.get_conversation_context(
                conversation_id=uuid4(), business_profile_id=business_profile_id
            )
            prompt_dict = self.prompt_templates.get_assessment_help_prompt(
                question_id=question_id,
                question_text=question_text,
                framework_id=framework_id,
                section_id=section_id,
                business_context=context.get("business_profile", {}),
                user_context=user_context or {},
            )
            prompt = prompt_dict.get("user", "")
            stream_context = {
                "framework": framework_id,
                "business_context": context.get("business_profile", {}),
                "prompt_length": len(prompt),
                "question_type": "help",
            }
            async for chunk in self._stream_response(
                "You are ComplianceGPT, providing contextual assessment guidance.",
                prompt,
                task_type="help",
                context=stream_context,
            ):
                yield chunk
        except (OSError, requests.RequestException) as e:
            logger.error("Error streaming assessment help: %s" % e)
            yield f"Unable to provide guidance for question {question_id} at this time."

    def _parse_assessment_help_response(self, response: str) -> Dict[str, Any]:
        """Parse AI response for assessment help into structured format."""
        try:
            import json

            if response.strip().startswith("{"):
                return json.loads(response)
        except json.JSONDecodeError:
            pass
        return {
            "guidance": response,
            "confidence_score": 0.8,
            "related_topics": [],
            "follow_up_suggestions": [],
            "source_references": [],
        }

    def _parse_assessment_followup_response(self, response: str) -> Dict[str, Any]:
        """Parse AI response for assessment followup into structured format."""
        try:
            import json

            if response.strip().startswith("{"):
                return json.loads(response)
        except json.JSONDecodeError:
            pass
        return {"follow_up_questions": [response], "recommendations": [], "confidence_score": 0.8}

    def _parse_assessment_analysis_response(self, response: str) -> Dict[str, Any]:
        """Parse AI response for assessment analysis into structured format."""
        try:
            import json

            if response.strip().startswith("{"):
                return json.loads(response)
        except json.JSONDecodeError:
            pass
        return {
            "gaps": [],
            "recommendations": [],
            "risk_assessment": {"level": "medium", "description": response},
            "compliance_insights": {"summary": response},
            "evidence_requirements": [],
        }

    def _parse_assessment_recommendations_response(self, response: str) -> Dict[str, Any]:
        """Parse AI response for assessment recommendations into structured format."""
        try:
            import json
            import re

            if response.strip().startswith("{"):
                return json.loads(response)
            json_match = re.search("```json\\s*(\\{.*?\\})\\s*```", response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(1))
            json_match = re.search("\\{.*\\}", response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass
        logger.info("Parsing text response for recommendations: %s..." % response[:200])
        if "```json" in response and '"recommendations"' in response:
            logger.info("Found JSON in response, attempting to extract...")
            try:
                start = response.find("```json") + 7
                end = response.find("```", start)
                if end > start:
                    json_str = response[start:end].strip()
                    parsed = json.loads(json_str)
                    if "recommendations" in parsed:
                        logger.info(
                            "Successfully extracted %s recommendations from JSON"
                            % len(parsed["recommendations"])
                        )
                        return parsed
            except (json.JSONDecodeError, ValueError, KeyError) as e:
                logger.warning("Failed to extract JSON: %s" % e)
        recommendations = []
        lines = response.split("\n")
        current_rec = None
        for line in lines:
            line = line.strip()
            if (
                line.startswith("- ")
                or line.startswith("* ")
                or line.startswith("1.")
                or line.startswith("2.")
                or line.startswith("3.")
            ):
                if current_rec:
                    recommendations.append(current_rec)
                title = re.sub("^[-*\\d\\.]\\s*", "", line)
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
                current_rec["description"] += f" {line}"
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

    def _get_fallback_assessment_help(
        self, question_text: str, framework_id: str
    ) -> Dict[str, Any]:
        """Provide fallback response when AI assessment help fails."""
        return {
            "guidance": f"For questions about {framework_id}, please refer to the official documentation or consult with a compliance expert. The specific question '{question_text}' requires careful consideration of your business context.",
            "confidence_score": 0.5,
            "related_topics": [framework_id, "compliance guidance"],
            "follow_up_suggestions": [
                "Review framework documentation",
                "Consult compliance expert",
            ],
            "source_references": [f"{framework_id} official documentation"],
            "request_id": f"fallback_help_{framework_id}",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def _get_fast_fallback_help(
        self, question_text: str, framework_id: str, question_id: str
    ) -> Dict[str, Any]:
        """Provide fast fallback response when AI times out (optimized for performance)."""
        framework_guidance = {
            "gdpr": "GDPR requires lawful basis for processing personal data. Consider data minimization, consent, and individual rights.",
            "iso27001": "ISO 27001 focuses on information security management. Implement risk assessment and security controls.",
            "sox": "SOX requires internal controls over financial reporting. Ensure accurate financial disclosures.",
            "hipaa": "HIPAA protects health information. Implement safeguards for PHI and ensure business associate agreements.",
        }
        guidance = framework_guidance.get(
            framework_id.lower(),
            f"This {framework_id} question requires careful analysis of your specific business context and compliance requirements.",
        )
        return {
            "guidance": guidance,
            "confidence_score": 0.7,
            "related_topics": [framework_id, "compliance requirements"],
            "follow_up_suggestions": ["Review specific requirements", "Consult documentation"],
            "source_references": [f"{framework_id} standards"],
            "request_id": f"fast_fallback_{framework_id}_{question_id}",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "response_time": 0.1,
        }

    def _get_fallback_assessment_followup(self, framework_id: str) -> Dict[str, Any]:
        """Provide fallback response when AI assessment followup fails."""
        return {
            "follow_up_questions": [
                f"What specific aspects of {framework_id} are you most concerned about?",
                "Do you have existing policies that might be relevant?",
                "What is your target timeline for compliance?",
            ],
            "recommendations": [
                "Review current compliance posture",
                "Identify key stakeholders",
                "Establish implementation timeline",
            ],
            "confidence_score": 0.5,
            "request_id": f"fallback_followup_{framework_id}",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def _get_fallback_assessment_analysis(self, framework_id: str) -> Dict[str, Any]:
        """Provide fallback response when AI assessment analysis fails."""
        return {
            "gaps": [
                {
                    "id": "general_gap",
                    "title": "General Compliance Gap",
                    "description": f"Unable to perform detailed analysis for {framework_id} at this time",
                    "severity": "medium",
                    "category": "general",
                }
            ],
            "recommendations": [
                {
                    "id": "general_rec",
                    "title": "Conduct Manual Review",
                    "description": "Perform manual compliance assessment with expert guidance",
                    "priority": "high",
                    "effort_estimate": "2-4 weeks",
                    "impact_score": 0.7,
                }
            ],
            "risk_assessment": {
                "level": "medium",
                "description": "Unable to assess specific risks at this time",
            },
            "compliance_insights": {
                "summary": f"Manual review recommended for {framework_id} compliance"
            },
            "evidence_requirements": [],
            "request_id": f"fallback_analysis_{framework_id}",
            "generated_at": datetime.now(timezone.utc).isoformat(),
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
                        "tasks": ["Review requirements", "Assess current state"],
                        "dependencies": [],
                    }
                ],
                "total_timeline_weeks": 12,
                "resource_requirements": ["Compliance team", "Documentation tools"],
            },
            "success_metrics": [
                "Compliance program established",
                "Key policies documented",
                "Regular reviews scheduled",
            ],
            "request_id": f"fallback_recommendations_{framework_id}",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def _is_recent_activity(self, evidence_item: Dict) -> bool:
        """Check if evidence item represents recent activity (within last 30 days)."""
        from datetime import datetime, timedelta, timezone

        try:
            created_at = evidence_item.get("created_at")
            if isinstance(created_at, str):
                created_date = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            elif isinstance(created_at, datetime):
                created_date = created_at
            else:
                return False
            thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
            if created_date.tzinfo is None:
                created_date = created_date.replace(tzinfo=timezone.utc)
            return created_date > thirty_days_ago
        except (ValueError, TypeError):
            return False

    def _format_recommendations(self, recommendations: List) -> List[Dict[str, str]]:
        """Format recommendations into structured format."""
        formatted = []
        for i, rec in enumerate(recommendations[:3]):
            if isinstance(rec, str):
                formatted.append(
                    {
                        "priority": ["High", "Medium", "Low"][i],
                        "action": rec,
                        "category": "evidence_collection",
                    }
                )
            elif isinstance(rec, dict):
                formatted.append(rec)
        return formatted

    @staticmethod
    def _validate_tone(response: str) -> Dict[str, Any]:
        """Validates the professional tone of compliance responses."""
        import re

        professional_indicators = [
            "should.*implement",
            "organizations.*must",
            "requirements.*include",
            "compliance.*framework",
            "regulatory.*guidance",
            "best.*practices",
        ]
        casual_patterns = [
            "just.*throw.*together",
            "probably.*fine",
            "don't.*worry.*about",
            "easy.*peasy",
            "no.*big.*deal",
            "whatever.*works",
        ]
        response_lower = response.lower()
        professional_count = sum(
            1 for pattern in professional_indicators if re.search(pattern, response_lower)
        )
        casual_count = sum(1 for pattern in casual_patterns if re.search(pattern, response_lower))
        total_indicators = len(professional_indicators)
        professional_score = professional_count / total_indicators if total_indicators > 0 else 0
        tone_score = max(0, professional_score - casual_count * 0.2)
        tone_appropriate = tone_score >= 0.6 and casual_count == 0
        issues = []
        if casual_count > 0:
            issues.extend(["too_casual", "lacks_precision"])
        if tone_score < 0.4:
            issues.append("unprofessional_language")
        if casual_count > 0 and "bypass" in response_lower:
            issues.append("potentially_misleading")
        return {
            "tone_appropriate": tone_appropriate,
            "tone_score": tone_score,
            "issues": issues,
            "professional_language": casual_count == 0,
        }

    async def _generate_response_legacy(self, *args, **kwargs) -> Dict[str, Any]:
        """
        Internal method for generating AI responses with cancellation support.
        Used for graceful shutdown testing and cancellation handling.
        """
        if "question_text" in kwargs:
            return await self.get_assessment_help(*args, **kwargs)
        else:
            raise ValueError("Invalid arguments for _generate_response_legacy")

    async def get_question_help(
        self,
        question_id: str,
        question_text: str,
        framework_id: str,
        business_profile_id: Optional[UUID] = None,
        section_id: Optional[str] = None,
        user_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Alias for get_assessment_help method.
        Provides backward compatibility for tests expecting this method name.
        """
        if business_profile_id is None:
            business_profile_id = uuid4()
        return await self._generate_response(
            question_id=question_id,
            question_text=question_text,
            framework_id=framework_id,
            business_profile_id=business_profile_id,
            section_id=section_id,
            user_context=user_context,
        )

    async def generate_followup_questions(
        self,
        current_answers: Dict[str, Any],
        framework_id: str,
        business_profile_id: UUID,
        assessment_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Alias for generate_assessment_followup method.
        Provides backward compatibility for tests expecting this method name.
        """
        return await self.generate_assessment_followup(
            current_answers=current_answers,
            framework_id=framework_id,
            business_profile_id=business_profile_id,
            assessment_context=assessment_context,
        )

    async def generate_assessment_questions(
        self,
        business_context: Dict[str, Any],
        max_questions: int = 8,
        difficulty_level: str = "mixed",
    ) -> Dict[str, Any]:
        """
        Generate dynamic assessment questions based on business context.

        Args:
            business_context: Business information including type, size, etc.
            max_questions: Maximum number of questions to generate
            difficulty_level: Question difficulty (easy, medium, hard, mixed)

        Returns:
            Dictionary containing generated questions and metadata
        """
        try:
            business_type = business_context.get("business_type", "general")
            company_size = business_context.get("company_size", "small")
            assessment_type = business_context.get(
                "assessment_type",
                "general",
            )
            system_prompt = (
                "You are a compliance assessment expert. Generate practical, business-relevant compliance questions for organizations. Always use 'question_id' as the field name for question identifiers.",
            )
            user_prompt = f"""
            Generate {max_questions} compliance assessment questions for a {business_type} business with {company_size} employees.
            Assessment type: {assessment_type}
            Difficulty level: {difficulty_level}

            Questions should cover:
            - Data protection and privacy (GDPR compliance)
            - Security practices and policies
            - Employee training and awareness
            - Risk management processes
            - Documentation and record keeping

            IMPORTANT: Use 'question_id' as the field name (not 'id').

            Return the questions in this EXACT JSON format:
            {{
                "questions": [
                    {{
                        "question_id": "q1",
                        "question": "Question text",
                        "type": "multiple_choice",
                        "options": ["Option A", "Option B", "Option C", "Option D"],
                        "category": "data_protection",
                        "difficulty": "medium",
                        "compliance_weight": 1.0
                    }},
                ],
                "total_questions": {max_questions},
                "assessment_context": "{assessment_type}"
            }}

            Ensure questions are:
            1. Relevant to {business_type} businesses
            2. Appropriate for {company_size} organizations
            3. Clear and actionable
            4. Varied in difficulty if mixed level requested
            5. Use 'question_id' field name (critical requirement)
            """
            response = await self._generate_ai_response_with_cache(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                task_type="question_generation",
                context={"business_type": business_type, "company_size": company_size},
            )
            questions_data = self._parse_questions_response(
                response, max_questions, assessment_type
            )
            return questions_data
        except (json.JSONDecodeError, requests.RequestException, ValueError) as e:
            logger.error("Error generating assessment questions: %s" % str(e))
            return self._get_fallback_questions_data(max_questions, assessment_type)

    async def generate_contextual_question(
        self,
        context: Optional[Dict[str, Any]] = None,
        business_context: Optional[Dict[str, Any]] = None,
        previous_messages: Optional[List[Dict[str, Any]]] = None,
        previous_answers: Optional[List[Dict[str, Any]]] = None,
        question_type: str = "multiple_choice",
        difficulty: str = "medium",
    ) -> Dict[str, Any]:
        """
        Generate a single contextual question based on business context and previous answers.

        Args:
            context: Assessment context (for compatibility with assessment_agent)
            business_context: Business information including type, size, etc.
            previous_messages: Previous messages from LangGraph (for compatibility)
            previous_answers: List of previous Q&A pairs for context
            question_type: Type of question (multiple_choice, boolean, text)
            difficulty: Question difficulty level

        Returns:
            Dictionary containing generated question and metadata
        """
        try:
            if business_context is None and context is not None:
                business_context = context
            if previous_answers is None and previous_messages is not None:
                previous_answers = []
                for msg in previous_messages[-6:]:
                    if hasattr(msg, "content") and hasattr(msg, "additional_kwargs"):
                        previous_answers.append(
                            {
                                "question": msg.additional_kwargs.get("question_id", "Question"),
                                "answer": msg.content,
                            }
                        )
            business_context = business_context or {}
            business_type = business_context.get("business_type", "general")
            company_size = business_context.get("company_size", "small")
            assessment_type = business_context.get("assessment_type", "compliance")
            context_info = ""
            if previous_answers:
                context_info = "\nPrevious answers context:\n"
                for _i, answer in enumerate(previous_answers[-3:]):
                    context_info += f"""- {answer.get("question", "Question")}: {answer.get("answer", "No answer")}
"""
            system_prompt = (
                "You are a compliance assessment expert. Generate a single, contextually relevant compliance question that builds upon previous responses. Always use 'question_id' as the field name for question identifiers.",
            )
            user_prompt = f"""
            Generate 1 contextual compliance question for a {business_type} business with {company_size} employees.
            Assessment type: {assessment_type}
            Question type: {question_type}
            Difficulty: {difficulty}
            {context_info}

            The question should:
            1. Be relevant to the business context
            2. Build upon or relate to previous answers if provided
            3. Cover important compliance areas (GDPR, security, training, documentation)
            4. Be clear and actionable
            5. Use 'question_id' as the field name (critical requirement)

            Return the question in this EXACT JSON format:
            {{
                "question_text": "Question text here",
                "question_id": "ctx_q1",
                "question_type": "{question_type}",
                "options": ["Option A", "Option B", "Option C", "Option D"],
                "category": "data_protection",
                "difficulty": "{difficulty}",
                "compliance_weight": 1.0,
                "contextual": true
            }}

            For boolean questions, use ["Yes", "No"] as options.
            For text questions, omit the options field entirely.
            """
            response = await self._generate_ai_response_with_cache(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                task_type="contextual_question_generation",
                context={
                    "business_type": business_type,
                    "company_size": company_size,
                    "previous_count": len(previous_answers or []),
                },
            )
            try:
                import json
                import re

                logger.debug(
                    "Raw response before parsing: %s" % (response[:500] if response else "EMPTY")
                )
                if isinstance(response, str):
                    cleaned_response = response.strip()
                    if cleaned_response.startswith("```"):
                        cleaned_response = re.sub("^```(?:json)?\\s*", "", cleaned_response)
                        cleaned_response = re.sub("\\s*```$", "", cleaned_response)
                    json_match = re.search("\\{[\\s\\S]*\\}", cleaned_response)
                    if json_match:
                        cleaned_response = json_match.group()
                    logger.debug(
                        "Cleaned response for parsing: %s"
                        % (cleaned_response[:200] if cleaned_response else "EMPTY")
                    )
                    parsed_response = json.loads(cleaned_response)
                else:
                    parsed_response = response
                return {
                    "question_text": parsed_response.get(
                        "question_text",
                        "How does your organization ensure data protection compliance?",
                    ),
                    "question_id": parsed_response.get("question_id", "ctx_fallback_1"),
                    "question_type": parsed_response.get("question_type", question_type),
                    "options": parsed_response.get("options"),
                    "category": parsed_response.get("category", "data_protection"),
                    "difficulty": parsed_response.get("difficulty", difficulty),
                    "compliance_weight": parsed_response.get("compliance_weight", 1.0),
                    "contextual": True,
                }
            except (json.JSONDecodeError, KeyError) as parse_error:
                logger.warning("Failed to parse contextual question response: %s" % parse_error)
                return {
                    "question_text": f"What compliance measures are most important for your {business_type} organization?",
                    "question_id": "ctx_fallback_2",
                    "question_type": question_type,
                    "options": ["Documentation", "Training", "Monitoring", "All of the above"]
                    if question_type == "multiple_choice"
                    else None,
                    "category": "general_compliance",
                    "difficulty": difficulty,
                    "compliance_weight": 1.0,
                    "contextual": True,
                }
        except (json.JSONDecodeError, requests.RequestException, ValueError) as e:
            logger.error("Error generating contextual question: %s" % str(e))
            return {
                "question_text": "Does your organization have documented compliance policies?",
                "question_id": "ctx_error_fallback",
                "question_type": "boolean",
                "options": ["Yes", "No"],
                "category": "documentation",
                "difficulty": "easy",
                "compliance_weight": 1.0,
                "contextual": True,
            }

    async def generate_recommendations(
        self,
        business_profile: Dict[str, Any],
        compliance_needs: List[str],
        identified_risks: List[Dict[str, Any]],
        compliance_score: float,
    ) -> List[Dict[str, Any]]:
        """
        Generate compliance recommendations based on assessment results.

        Args:
            business_profile: Business profile information
            compliance_needs: List of identified compliance needs
            identified_risks: List of identified compliance risks
            compliance_score: Overall compliance score (0.0 to 1.0)

        Returns:
            List of recommendation dictionaries with actions and priorities
        """
        try:
            business_type = business_profile.get("business_type", "general")
            company_size = business_profile.get("company_size", "small")
            industry = business_profile.get("industry", "general")
            risk_context = ""
            if identified_risks:
                risk_context = "\nIdentified risks:\n"
                for risk in identified_risks[:5]:
                    severity = risk.get("severity", "medium")
                    description = risk.get("description", "Risk identified")
                    risk_context += f"- {severity.upper()}: {description}\n"
            needs_context = ""
            if compliance_needs:
                needs_context = f"""
Compliance frameworks needed: {", ".join(compliance_needs[:3])}
"""
            if compliance_score < 0.4:
                urgency = "critical"
                action_priority = "immediate action required"
            elif compliance_score < 0.7:
                urgency = "high"
                action_priority = "address within 30 days"
            else:
                urgency = "medium"
                action_priority = "improve over next quarter"
            system_prompt = (
                "You are a compliance expert providing actionable recommendations. Generate practical, specific recommendations that businesses can implement to improve their compliance posture.",
            )
            user_prompt = f"""
            Generate 3-5 specific compliance recommendations for a {business_type} business with {company_size} employees in the {industry} industry.

            Current compliance score: {compliance_score:.1%}
            Urgency level: {urgency} - {action_priority}
            {needs_context}{risk_context}

            For each recommendation, provide:
            1. Clear, actionable title
            2. Specific steps to implement
            3. Priority level (critical, high, medium, low)
            4. Estimated timeline
            5. Expected compliance impact

            Return recommendations in this JSON format:
            {{
                "recommendations": [
                    {{
                        "title": "Recommendation title",
                        "description": "Detailed implementation steps",
                        "priority": "high",
                        "timeline": "30 days",
                        "compliance_impact": "Addresses GDPR Article 32 requirements",
                        "category": "security",
                        "effort_level": "medium"
                    }},
                ]
            }}

            Focus on the most impactful recommendations first.
            """
            model_instance, instruction_id = self._get_task_appropriate_model(
                task_type="recommendations",
                context={
                    "business_profile": business_profile,
                    "compliance_score": compliance_score,
                },
            )
            try:
                response = await model_instance.generate_content_async(
                    [system_prompt, user_prompt],
                    generation_config={
                        "temperature": 0.3,
                        "max_output_tokens": 2000,
                        "top_p": 0.8,
                        "top_k": 40,
                    },
                )
                response_text = response.text.strip()
                import json
                import re

                json_match = re.search("\\{.*\\}", response_text, re.DOTALL)
                if json_match:
                    try:
                        recommendations_data = json.loads(json_match.group())
                        recommendations = recommendations_data.get("recommendations", [])
                        validated_recommendations = []
                        for rec in recommendations[:5]:
                            if isinstance(rec, dict) and rec.get("title"):
                                validated_rec = {
                                    "id": f"rec_{len(validated_recommendations) + 1}",
                                    "title": rec.get("title", "Compliance Recommendation"),
                                    "description": rec.get(
                                        "description", "Implement compliance measures"
                                    ),
                                    "priority": rec.get("priority", "medium"),
                                    "timeline": rec.get("timeline", "60 days"),
                                    "compliance_impact": rec.get(
                                        "compliance_impact", "Improves overall compliance"
                                    ),
                                    "category": rec.get("category", "general"),
                                    "effort_level": rec.get("effort_level", "medium"),
                                    "business_context": {
                                        "business_type": business_type,
                                        "company_size": company_size,
                                        "compliance_score": compliance_score,
                                    },
                                }
                                validated_recommendations.append(validated_rec)
                        if validated_recommendations:
                            logger.info(
                                "Generated %s recommendations for assessment"
                                % len(validated_recommendations)
                            )
                            return validated_recommendations
                    except json.JSONDecodeError as e:
                        logger.warning("Failed to parse recommendations JSON: %s" % e)
            except Exception as model_error:
                logger.warning("AI model failed to generate recommendations: %s" % model_error)
            logger.info("Using fallback recommendations")
            fallback_recommendations = []
            if compliance_score < 0.4:
                fallback_recommendations = [
                    {
                        "id": "rec_critical_1",
                        "title": "Establish Data Protection Policies",
                        "description": "Create and implement comprehensive data protection policies covering data collection, processing, and storage procedures.",
                        "priority": "critical",
                        "timeline": "14 days",
                        "compliance_impact": "Essential for GDPR compliance and data breach prevention",
                        "category": "documentation",
                        "effort_level": "high",
                    },
                    {
                        "id": "rec_critical_2",
                        "title": "Implement Access Controls",
                        "description": "Set up role-based access controls and user authentication systems to protect sensitive data.",
                        "priority": "critical",
                        "timeline": "21 days",
                        "compliance_impact": "Addresses security requirements across multiple frameworks",
                        "category": "security",
                        "effort_level": "high",
                    },
                    {
                        "id": "rec_critical_3",
                        "title": "Conduct Security Training",
                        "description": "Provide mandatory security awareness training for all employees handling personal data.",
                        "priority": "high",
                        "timeline": "30 days",
                        "compliance_impact": "Required for ISO 27001 and reduces human error risks",
                        "category": "training",
                        "effort_level": "medium",
                    },
                ]
            elif compliance_score < 0.7:
                fallback_recommendations = [
                    {
                        "id": "rec_medium_1",
                        "title": "Enhance Incident Response Plan",
                        "description": "Develop and test a comprehensive incident response plan including breach notification procedures.",
                        "priority": "high",
                        "timeline": "45 days",
                        "compliance_impact": "Required for GDPR Article 33 and improves overall security posture",
                        "category": "procedures",
                        "effort_level": "medium",
                    },
                    {
                        "id": "rec_medium_2",
                        "title": "Regular Compliance Audits",
                        "description": "Establish quarterly internal audits to identify and address compliance gaps proactively.",
                        "priority": "medium",
                        "timeline": "60 days",
                        "compliance_impact": "Maintains ongoing compliance and identifies improvement areas",
                        "category": "monitoring",
                        "effort_level": "medium",
                    },
                ]
            else:
                fallback_recommendations = [
                    {
                        "id": "rec_good_1",
                        "title": "Optimize Privacy Controls",
                        "description": "Fine-tune privacy settings and implement privacy-by-design principles in new systems.",
                        "priority": "medium",
                        "timeline": "90 days",
                        "compliance_impact": "Enhances privacy posture and demonstrates best practices",
                        "category": "optimization",
                        "effort_level": "low",
                    }
                ]
            for rec in fallback_recommendations:
                rec["business_context"] = {
                    "business_type": business_type,
                    "company_size": company_size,
                    "compliance_score": compliance_score,
                }
            return fallback_recommendations
        except (json.JSONDecodeError, requests.RequestException, ValueError) as e:
            logger.error("Error generating compliance recommendations: %s" % str(e))
            return [
                {
                    "id": "rec_error_fallback",
                    "title": "Review Compliance Status",
                    "description": "Conduct a comprehensive review of current compliance measures and identify areas for improvement.",
                    "priority": "medium",
                    "timeline": "30 days",
                    "compliance_impact": "Establishes baseline for compliance improvements",
                    "category": "assessment",
                    "effort_level": "low",
                    "business_context": {
                        "business_type": business_profile.get("business_type", "general"),
                        "company_size": business_profile.get("company_size", "small"),
                        "compliance_score": compliance_score,
                    },
                }
            ]

    async def analyze_conversation_context(
        self, messages: List[Dict[str, str]], business_profile: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Analyze conversation context to extract insights and identify compliance needs.

        Args:
            messages: List of conversation messages
            business_profile: Current business profile

        Returns:
            Dictionary containing insights, compliance needs, expertise level, and follow-up needed flag
        """
        try:
            conversation = "\n".join(
                [
                    f"{getattr(msg, 'type', 'user')}: {getattr(msg, 'content', '')}"
                    for msg in messages
                    if hasattr(msg, "content") and msg.content
                ]
            )
            business_type = business_profile.get("business_type", "general")
            company_size = business_profile.get("company_size", "small")
            industry = business_profile.get("industry", "general")
            system_prompt = """You are an AI compliance analyst. Analyze the conversation to extract:
1. Key business insights and characteristics
2. Compliance needs and requirements
3. User's expertise level with compliance
4. Whether follow-up questions are needed

Return a JSON object with these fields:
- insights: object with business characteristics
- compliance_needs: array of identified compliance requirements
- expertise_level: string (beginner/intermediate/expert)
- follow_up_needed: boolean"""
            user_prompt = f"""Business Context:
- Type: {business_type}
- Size: {company_size}
- Industry: {industry}

Conversation:
{conversation[:2000]}  # Limit context to avoid token limits

Analyze this conversation and provide insights in JSON format."""
            if not self.circuit_breaker.is_model_available("gemini-2.5-flash"):
                return {
                    "insights": {
                        "business_type": business_type,
                        "company_size": company_size,
                        "industry": industry,
                    },
                    "compliance_needs": ["GDPR", "data_protection"],
                    "expertise_level": "intermediate",
                    "follow_up_needed": True,
                }
            response = await self._generate_ai_response(system_prompt, user_prompt)
            import json
            import re

            json_match = re.search("\\{[\\s\\S]*\\}", response)
            if json_match:
                try:
                    analysis = json.loads(json_match.group())
                    return {
                        "insights": analysis.get("insights", {}),
                        "compliance_needs": analysis.get(
                            "compliance_needs", ["GDPR", "data_protection"]
                        ),
                        "expertise_level": analysis.get("expertise_level", "intermediate"),
                        "follow_up_needed": analysis.get("follow_up_needed", True),
                    }
                except json.JSONDecodeError:
                    logger.warning("Failed to parse AI analysis response as JSON")
            return {
                "insights": {
                    "business_type": business_type,
                    "company_size": company_size,
                    "industry": industry,
                },
                "compliance_needs": ["GDPR", "data_protection"],
                "expertise_level": "intermediate",
                "follow_up_needed": True,
            }
        except (json.JSONDecodeError, requests.RequestException, ValueError) as e:
            logger.error("Error analyzing conversation context: %s" % str(e))
            return {
                "insights": business_profile,
                "compliance_needs": ["GDPR", "data_protection", "ISO27001"],
                "expertise_level": "intermediate",
                "follow_up_needed": True,
            }

    async def get_personalized_recommendations(
        self,
        assessment_context: Dict[str, Any],
        analysis_results: Dict[str, Any],
        compliance_score: float,
    ) -> Dict[str, Any]:
        """
        Generate personalized recommendations based on assessment results.

        Args:
            assessment_context: Context from the assessment including business profile
            analysis_results: Results from the assessment analysis
            compliance_score: Overall compliance score

        Returns:
            Dictionary containing personalized recommendations
        """
        try:
            business_profile = assessment_context.get("business_profile", {})
            business_type = business_profile.get("business_type", "general")
            company_size = business_profile.get("company_size", "small")
            industry = business_profile.get("industry", "general")
            if compliance_score < 30:
                priority_level = "critical"
                focus_areas = ["immediate_compliance", "risk_mitigation", "basic_policies"]
            elif compliance_score < 60:
                priority_level = "high"
                focus_areas = ["compliance_gaps", "policy_development", "training"]
            elif compliance_score < 80:
                priority_level = "medium"
                focus_areas = ["optimization", "advanced_compliance", "continuous_improvement"]
            else:
                priority_level = "low"
                focus_areas = ["maintenance", "best_practices", "innovation"]
            prompt = f"""
            Generate personalized compliance recommendations for a {company_size} {business_type} business in the {industry} industry.

            Current compliance score: {compliance_score}%
            Priority level: {priority_level}
            Focus areas: {", ".join(focus_areas)}

            Analysis insights:
            {json.dumps(analysis_results.get("insights", {}), indent=2)}

            Compliance needs identified:
            {json.dumps(analysis_results.get("compliance_needs", []), indent=2)}

            Generate 3-5 specific, actionable recommendations that:
            1. Address the most critical compliance gaps
            2. Are appropriate for the business size and type
            3. Include clear next steps
            4. Consider resource constraints
            5. Provide measurable outcomes

            Format as JSON:
            {{
                "recommendations": [
                    {{
                        "title": "Recommendation title",
                        "description": "Detailed description",
                        "priority": "critical/high/medium/low",
                        "timeline": "immediate/30-days/60-days/90-days",
                        "steps": ["step1", "step2"],
                        "expected_outcome": "What will be achieved",
                        "resources_needed": "What resources are required",
                        "compliance_impact": "How this improves compliance"
                    }},
                ]
            }}
            """
            response = await self._get_ai_response_with_fallback(prompt)
            import json
            import re

            json_match = re.search("\\{[\\s\\S]*\\}", response)
            if json_match:
                try:
                    recommendations_data = json.loads(json_match.group())
                    recommendations = recommendations_data.get("recommendations", [])
                    if not recommendations:
                        raise ValueError("No recommendations generated")
                    for i, rec in enumerate(recommendations):
                        rec["id"] = f"rec_{i + 1}"
                        rec["business_context"] = {
                            "business_type": business_type,
                            "company_size": company_size,
                            "industry": industry,
                            "compliance_score": compliance_score,
                        }
                    return {
                        "recommendations": recommendations,
                        "priority_level": priority_level,
                        "focus_areas": focus_areas,
                        "generated_at": datetime.now(timezone.utc).isoformat(),
                    }
                except json.JSONDecodeError:
                    logger.warning("Failed to parse recommendations response as JSON")
            return self._get_fallback_recommendations(
                compliance_score, business_type, company_size, priority_level, focus_areas
            )
        except (json.JSONDecodeError, requests.RequestException, ValueError) as e:
            logger.error("Error generating personalized recommendations: %s" % str(e))
            return {
                "recommendations": [
                    {
                        "id": "rec_1",
                        "title": "Conduct Compliance Assessment",
                        "description": "Perform a comprehensive compliance assessment to identify gaps and priorities.",
                        "priority": "high",
                        "timeline": "30-days",
                        "steps": [
                            "Review current policies and procedures",
                            "Identify applicable regulations",
                            "Document compliance gaps",
                        ],
                        "expected_outcome": "Clear understanding of compliance status",
                        "resources_needed": "Internal team time or external consultant",
                        "compliance_impact": "Establishes baseline for improvements",
                        "business_context": {
                            "business_type": assessment_context.get("business_profile", {}).get(
                                "business_type", "general"
                            ),
                            "company_size": assessment_context.get("business_profile", {}).get(
                                "company_size", "small"
                            ),
                            "compliance_score": compliance_score,
                        },
                    }
                ],
                "priority_level": "medium",
                "focus_areas": ["assessment", "planning"],
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }

    def _get_fallback_recommendations(
        self,
        compliance_score: float,
        business_type: str,
        company_size: str,
        priority_level: str,
        focus_areas: List[str],
    ) -> Dict[str, Any]:
        """Generate fallback recommendations when AI is unavailable."""
        recommendations = []
        if compliance_score < 30:
            recommendations.extend(
                [
                    {
                        "id": "rec_critical_1",
                        "title": "Implement Basic Data Protection Measures",
                        "description": "Establish fundamental data protection policies and procedures to meet minimum legal requirements.",
                        "priority": "critical",
                        "timeline": "immediate",
                        "steps": [
                            "Create data inventory",
                            "Implement access controls",
                            "Document data processing activities",
                        ],
                        "expected_outcome": "Basic GDPR compliance",
                        "resources_needed": "Data protection officer or consultant",
                        "compliance_impact": "Reduces risk of regulatory penalties",
                    },
                    {
                        "id": "rec_critical_2",
                        "title": "Develop Privacy Policy",
                        "description": "Create comprehensive privacy policy covering data collection, use, and user rights.",
                        "priority": "critical",
                        "timeline": "immediate",
                        "steps": [
                            "Review data practices",
                            "Draft privacy policy",
                            "Publish and communicate to users",
                        ],
                        "expected_outcome": "Transparent data practices",
                        "resources_needed": "Legal review",
                        "compliance_impact": "Meets transparency requirements",
                    },
                ]
            )
        elif compliance_score < 70:
            recommendations.extend(
                [
                    {
                        "id": "rec_medium_1",
                        "title": "Enhance Security Controls",
                        "description": "Strengthen security measures to better protect sensitive data.",
                        "priority": "high",
                        "timeline": "30-days",
                        "steps": [
                            "Conduct security assessment",
                            "Implement multi-factor authentication",
                            "Regular security training",
                        ],
                        "expected_outcome": "Improved data security",
                        "resources_needed": "Security tools and training",
                        "compliance_impact": "Reduces breach risk",
                    },
                    {
                        "id": "rec_medium_2",
                        "title": "Establish Compliance Monitoring",
                        "description": "Set up regular compliance reviews and monitoring processes.",
                        "priority": "medium",
                        "timeline": "60-days",
                        "steps": [
                            "Define compliance metrics",
                            "Schedule regular audits",
                            "Create reporting dashboard",
                        ],
                        "expected_outcome": "Ongoing compliance visibility",
                        "resources_needed": "Compliance management tools",
                        "compliance_impact": "Maintains compliance over time",
                    },
                ]
            )
        else:
            recommendations.extend(
                [
                    {
                        "id": "rec_optimize_1",
                        "title": "Pursue Certification",
                        "description": "Consider pursuing ISO 27001 or SOC 2 certification to demonstrate compliance maturity.",
                        "priority": "low",
                        "timeline": "90-days",
                        "steps": [
                            "Gap analysis against standard",
                            "Implement required controls",
                            "Engage certification body",
                        ],
                        "expected_outcome": "Industry-recognized certification",
                        "resources_needed": "Certification consultant and auditor",
                        "compliance_impact": "Demonstrates compliance excellence",
                    }
                ]
            )
        for rec in recommendations:
            rec["business_context"] = {
                "business_type": business_type,
                "company_size": company_size,
                "compliance_score": compliance_score,
            }
        return {
            "recommendations": recommendations,
            "priority_level": priority_level,
            "focus_areas": focus_areas,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def _parse_questions_response(
        self, response: str, max_questions: int, assessment_type: str
    ) -> Dict[str, Any]:
        """Parse AI response to extract questions data."""
        try:
            import json
            import re

            logger.debug("=== DEBUG: Parsing questions response ===")
            logger.debug("Response type: %s" % type(response))
            logger.debug("Response length: %s" % (len(response) if response else 0))
            logger.debug("Response content: %s" % (repr(response[:500]) if response else "EMPTY"))
            if not response or not response.strip():
                logger.warning("Response is empty or None - using fallback questions")
                return self._get_fallback_questions_data(max_questions, assessment_type)
            json_match = re.search("\\{.*\\}", response, re.DOTALL)
            if json_match:
                json_text = json_match.group()
                logger.debug("Found JSON match: %s..." % json_text[:200])
                try:
                    questions_data = json.loads(json_text)
                    logger.debug("Successfully parsed JSON. Keys: %s" % list(questions_data.keys()))
                except json.JSONDecodeError as json_error:
                    logger.error("JSON decode error: %s" % json_error)
                    logger.error("Problematic JSON: %s" % json_text)
                    return self._get_fallback_questions_data(max_questions, assessment_type)
                if "questions" in questions_data and isinstance(questions_data["questions"], list):
                    logger.debug("Found %s questions" % len(questions_data["questions"]))
                    for i, question in enumerate(questions_data["questions"]):
                        logger.debug("Question %s keys: %s" % (i, list(question.keys())))
                        if "id" in question and "question_id" not in question:
                            logger.debug("Converting 'id' to 'question_id' for question %s" % i)
                            question["question_id"] = question["id"]
                        elif "question_id" not in question:
                            logger.warning(
                                "Question %s missing both 'id' and 'question_id', adding fallback ID"
                                % i
                            )
                            question["question_id"] = f"q{i + 1}"
                        if "question" not in question and "question_text" not in question:
                            logger.warning("Question %s missing question text" % i)
                            question["question"] = f"Question {i + 1} content missing"
                        if "question_text" in question and "question" not in question:
                            question["question"] = question["question_text"]
                    logger.debug("Final questions structure validated")
                    return questions_data
                else:
                    logger.warning("Response has no 'questions' array or it's not a list")
            logger.debug("No valid JSON found, falling back to text parsing")
            return self._parse_text_questions(response, max_questions, assessment_type)
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.error("Exception parsing questions response: %s" % str(e))
            logger.error(
                "Response that caused error: %s" % (repr(response) if response else "None")
            )
            import traceback

            logger.error("Traceback: %s" % traceback.format_exc())
            return self._get_fallback_questions_data(max_questions, assessment_type)

    def _parse_text_questions(
        self, response: str, max_questions: int, assessment_type: str
    ) -> Dict[str, Any]:
        """Parse text-format questions from AI response."""
        questions = []
        lines = response.split("\n")
        current_question = {}
        question_count = 0
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if (
                line.startswith(("1.", "2.", "3.", "4.", "5.", "6.", "7.", "8."))
                and question_count < max_questions
            ):
                if current_question:
                    questions.append(current_question)
                question_count += 1
                current_question = {
                    "question_id": f"q{question_count}",
                    "question": line[2:].strip(),
                    "type": "multiple_choice",
                    "options": ["Yes", "No", "Partially", "Not Applicable"],
                    "category": "compliance",
                    "difficulty": "medium",
                    "compliance_weight": 1.0,
                }
        if current_question:
            questions.append(current_question)
        return {
            "questions": questions[:max_questions],
            "total_questions": min(len(questions), max_questions),
            "assessment_context": assessment_type,
        }

    def _get_fallback_questions_data(
        self, max_questions: int, assessment_type: str
    ) -> Dict[str, Any]:
        """Generate fallback questions when AI generation fails."""
        fallback_questions = [
            {
                "question_id": "q1",
                "question": "Does your organization have a documented data protection policy?",
                "type": "multiple_choice",
                "options": ["Yes, comprehensive", "Yes, basic", "In development", "No"],
                "category": "data_protection",
                "difficulty": "easy",
                "compliance_weight": 1.5,
            },
            {
                "question_id": "q2",
                "question": "How often do you conduct security awareness training for employees?",
                "type": "multiple_choice",
                "options": ["Monthly", "Quarterly", "Annually", "Never"],
                "category": "security",
                "difficulty": "medium",
                "compliance_weight": 1.2,
            },
            {
                "question_id": "q3",
                "question": "Do you have processes for handling data subject access requests?",
                "type": "multiple_choice",
                "options": ["Yes, automated", "Yes, manual", "Informal process", "No process"],
                "category": "data_protection",
                "difficulty": "medium",
                "compliance_weight": 1.8,
            },
            {
                "question_id": "q4",
                "question": "How do you monitor and log access to sensitive data?",
                "type": "multiple_choice",
                "options": [
                    "Comprehensive logging",
                    "Basic logging",
                    "Limited logging",
                    "No logging",
                ],
                "category": "security",
                "difficulty": "hard",
                "compliance_weight": 1.4,
            },
            {
                "question_id": "q5",
                "question": "Do you conduct regular risk assessments for data processing activities?",
                "type": "multiple_choice",
                "options": ["Yes, regularly", "Yes, occasionally", "Planning to", "No"],
                "category": "risk_management",
                "difficulty": "medium",
                "compliance_weight": 1.3,
            },
            {
                "question_id": "q6",
                "question": "How do you ensure third-party vendors comply with data protection requirements?",
                "type": "multiple_choice",
                "options": [
                    "Formal agreements",
                    "Basic requirements",
                    "Verbal agreements",
                    "No requirements",
                ],
                "category": "vendor_management",
                "difficulty": "hard",
                "compliance_weight": 1.6,
            },
            {
                "question_id": "q7",
                "question": "Do you have an incident response plan for data breaches?",
                "type": "multiple_choice",
                "options": ["Yes, tested", "Yes, documented", "In development", "No"],
                "category": "incident_response",
                "difficulty": "medium",
                "compliance_weight": 1.7,
            },
            {
                "question_id": "q8",
                "question": "How often do you review and update your compliance policies?",
                "type": "multiple_choice",
                "options": ["Quarterly", "Annually", "As needed", "Never"],
                "category": "governance",
                "difficulty": "easy",
                "compliance_weight": 1.1,
            },
        ]
        selected_questions = fallback_questions[:max_questions]
        return {
            "questions": selected_questions,
            "total_questions": len(selected_questions),
            "assessment_context": assessment_type,
            "fallback_used": True,
        }

    async def select_optimal_model(
        self,
        task_type: str,
        complexity: str = "medium",
        prefer_speed: bool = False,
        context: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """
        Select the optimal AI model based on task requirements.
        Returns a model object with model_name attribute.
        """
        try:
            model, instruction_id = await self._select_model_and_instruction(
                task_type=task_type, context=context or {}
            )
            return model
        except (ValueError, TypeError) as e:
            logger.error("Error selecting optimal model: %s" % e)
            from config.ai_config import get_ai_model

            return get_ai_model()

    async def get_performance_metrics(self) -> Dict[str, Any]:
        """
        Get AI performance metrics.
        Returns performance data including response times, success rates, etc.
        """
        try:
            if hasattr(self, "performance_optimizer") and self.performance_optimizer:
                return await self.performance_optimizer.get_performance_metrics()
            else:
                return {
                    "response_times": {"gemini-2.5-flash": 1.5, "gemini-2.5-pro": 2.8},
                    "success_rates": {"gemini-2.5-flash": 0.95, "gemini-2.5-pro": 0.98},
                    "token_usage": {
                        "total": 10000,
                        "gemini-2.5-flash": 6000,
                        "gemini-2.5-pro": 4000,
                    },
                    "cost_metrics": {"total_cost": 5.0, "optimization_savings": 1.2},
                }
        except (ValueError, TypeError) as e:
            logger.error("Error getting performance metrics: %s" % e)
            return {
                "response_times": {"gemini-2.5-flash": 1.5},
                "success_rates": {"gemini-2.5-flash": 0.95},
                "token_usage": {"total": 5000},
                "cost_metrics": {"total_cost": 2.5},
            }

    def _generate_cache_key_for_context(self, context: Dict[str, Any], task_type: str) -> str:
        """Generate cache key for performance tracking."""
        business_profile_id = context.get("business_profile", {}).get("id", "unknown")
        framework_id = context.get("framework_id", "unknown")
        return f"cache_perf:{task_type}:{framework_id}:{business_profile_id}"

    async def _add_to_cache_warming_queue(self, context: Dict[str, Any], task_type: str) -> None:
        """Add context to cache warming queue for proactive caching."""
        if not self.cached_content_manager:
            return
        if task_type in ["analysis", "assessment"]:
            content_type = CacheContentType.ASSESSMENT_CONTEXT
            priority = 2
        elif "business_profile" in context:
            content_type = CacheContentType.BUSINESS_PROFILE
            priority = 3
        else:
            content_type = CacheContentType.FRAMEWORK_CONTEXT
            priority = 4
        warming_context = {
            "framework_id": context.get("framework_id"),
            "business_profile_id": context.get("business_profile", {}).get("id"),
            "business_profile": context.get("business_profile"),
            "assessment_context": context.get("assessment_context"),
            "industry_context": context.get("business_profile", {}).get("industry", "General"),
        }
        self.cached_content_manager.add_to_warming_queue(content_type, warming_context, priority)
        logger.debug("Added %s context to cache warming queue" % task_type)

    async def trigger_cache_invalidation(self, trigger_type: str, context: Dict[str, Any]) -> None:
        """Trigger intelligent cache invalidation."""
        if not self.cached_content_manager:
            return
        self.cached_content_manager.trigger_intelligent_invalidation(trigger_type, context)

    async def process_cache_warming_queue(self) -> int:
        """Process pending cache warming requests."""
        if not self.cached_content_manager:
            return 0
        return await self.cached_content_manager.process_warming_queue()

    async def get_cache_strategy_metrics(self) -> Dict[str, Any]:
        """Get cache strategy optimization metrics."""
        if not self.cached_content_manager:
            return {"cache_strategy": "not_available"}
        base_metrics = self.cached_content_manager.get_cache_metrics()
        strategy_metrics = self.cached_content_manager.get_cache_strategy_metrics()
        return {**base_metrics, "strategy_optimization": strategy_metrics}
