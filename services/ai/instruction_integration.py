"""
import logging


logger = logging.getLogger(__name__)
# Constants
CONFIDENCE_THRESHOLD = 0.8
DEFAULT_RETRIES = 5


Integration utilities for system instructions with performance monitoring

This module provides integration between the instruction template system,
performance monitoring, and the ComplianceAssistant.
"""

from typing import Any, Dict, List, Optional, Tuple
from config.ai_config import get_ai_model
from config.logging_config import get_logger
from .instruction_monitor import InstructionMetricType, get_instruction_monitor
from .instruction_templates import SystemInstructionTemplates, get_system_instruction

logger = get_logger(__name__)


class InstructionManager:
    """
    Manages system instructions with integrated performance monitoring
    """

    def __init__(self) -> None:
        self.templates = SystemInstructionTemplates()
        self.monitor = get_instruction_monitor()
        self._instruction_cache = {}

    def get_instruction_with_monitoring(
        self,
        instruction_type: str,
        framework: Optional[str] = None,
        business_profile: Optional[Dict[str, Any]] = None,
        user_persona: Optional[str] = None,
        task_complexity: str = "medium",
        session_id: Optional[str] = None,
        **kwargs,
    ) -> Tuple[str, str]:
        """
        Get system instruction with automatic registration for monitoring

        Args:
            instruction_type: Type of instruction needed
            framework: Framework context
            business_profile: Business profile data
            user_persona: User persona (alex, ben, catherine)
            task_complexity: Task complexity level
            session_id: Session identifier for tracking
            **kwargs: Additional context

        Returns:
            Tuple of (instruction_id, instruction_content)
        """
        instruction_content = get_system_instruction(
            instruction_type=instruction_type,
            framework=framework,
            business_profile=business_profile,
            user_persona=user_persona,
            task_complexity=task_complexity,
            **kwargs,
        )
        instruction_id = self._create_instruction_id(
            instruction_type, framework, user_persona, task_complexity
        )
        if instruction_id not in self.monitor.instruction_registry:
            self.monitor.register_instruction(
                instruction_id=instruction_id,
                instruction_content=instruction_content,
                instruction_type=instruction_type,
                framework=framework,
                metadata={
                    "user_persona": user_persona,
                    "task_complexity": task_complexity,
                    "business_context": business_profile.get("industry")
                    if business_profile
                    else None,
                    "additional_context": kwargs,
                },
            )
        return instruction_id, instruction_content

    def get_model_with_instruction(
        self,
        instruction_type: str,
        framework: Optional[str] = None,
        business_profile: Optional[Dict[str, Any]] = None,
        user_persona: Optional[str] = None,
        task_complexity: str = "medium",
        session_id: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs,
    ) -> Tuple[Any, str]:
        """
        Get AI model with system instruction and register for monitoring

        Args:
            instruction_type: Type of instruction needed
            framework: Framework context
            business_profile: Business profile data
            user_persona: User persona
            task_complexity: Task complexity level
            session_id: Session identifier
            tools: Function calling tools
            **kwargs: Additional context

        Returns:
            Tuple of (model_instance, instruction_id)
        """
        instruction_id, instruction_content = self.get_instruction_with_monitoring(
            instruction_type=instruction_type,
            framework=framework,
            business_profile=business_profile,
            user_persona=user_persona,
            task_complexity=task_complexity,
            session_id=session_id,
            **kwargs,
        )
        model = get_ai_model(
            task_complexity=task_complexity,
            prefer_speed=kwargs.get("prefer_speed", False),
            task_context={
                "framework": framework,
                "task_type": instruction_type,
                "business_context": business_profile,
            },
            system_instruction=instruction_content,
            tools=tools,
        )
        return model, instruction_id

    def record_instruction_usage(
        self,
        instruction_id: str,
        response_quality: Optional[float] = None,
        user_satisfaction: Optional[float] = None,
        response_time: Optional[float] = None,
        token_count: Optional[int] = None,
        had_error: bool = False,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        additional_context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Record usage metrics for an instruction

        Args:
            instruction_id: ID of the instruction used
            response_quality: Quality score (0.0-1.0)
            user_satisfaction: Satisfaction score (0.0-1.0)
            response_time: Response time in seconds
            token_count: Number of tokens used
            had_error: Whether an error occurred
            session_id: Session identifier
            user_id: User identifier
            additional_context: Additional context data
        """
        context = additional_context or {}
        if response_quality is not None:
            self.monitor.record_metric(
                instruction_id=instruction_id,
                metric_type=InstructionMetricType.RESPONSE_QUALITY,
                value=response_quality,
                context=context,
                session_id=session_id,
                user_id=user_id,
            )
        if user_satisfaction is not None:
            self.monitor.record_metric(
                instruction_id=instruction_id,
                metric_type=InstructionMetricType.USER_SATISFACTION,
                value=user_satisfaction,
                context=context,
                session_id=session_id,
                user_id=user_id,
            )
        if response_time is not None:
            self.monitor.record_metric(
                instruction_id=instruction_id,
                metric_type=InstructionMetricType.RESPONSE_TIME,
                value=response_time,
                context=context,
                session_id=session_id,
                user_id=user_id,
            )
        if token_count is not None and response_time is not None:
            efficiency = token_count / response_time if response_time > 0 else 0
            self.monitor.record_metric(
                instruction_id=instruction_id,
                metric_type=InstructionMetricType.TOKEN_EFFICIENCY,
                value=efficiency,
                context=context,
                session_id=session_id,
                user_id=user_id,
            )
        self.monitor.record_metric(
            instruction_id=instruction_id,
            metric_type=InstructionMetricType.ERROR_RATE,
            value=1.0 if had_error else 0.0,
            context=context,
            session_id=session_id,
            user_id=user_id,
        )
        effectiveness = self._calculate_effectiveness_score(
            response_quality, user_satisfaction, response_time, had_error
        )
        self.monitor.record_metric(
            instruction_id=instruction_id,
            metric_type=InstructionMetricType.INSTRUCTION_EFFECTIVENESS,
            value=effectiveness,
            context=context,
            session_id=session_id,
            user_id=user_id,
        )

    def get_best_instruction_for_task(
        self,
        instruction_type: str,
        framework: Optional[str] = None,
        business_profile: Optional[Dict[str, Any]] = None,
        user_persona: Optional[str] = None,
        task_complexity: str = "medium",
    ) -> Tuple[str, str]:
        """
        Get the best performing instruction for a given task based on historical data

        Args:
            instruction_type: Type of instruction needed
            framework: Framework context
            business_profile: Business profile data
            user_persona: User persona
            task_complexity: Task complexity level

        Returns:
            Tuple of (instruction_id, instruction_content)
        """
        candidates = []
        for instruction_id, info in self.monitor.instruction_registry.items():
            if (
                info.get("type") == instruction_type
                and info.get("framework") == framework
                and info.get("metadata", {}).get("task_complexity") == task_complexity
            ):
                performance = self.monitor.get_instruction_performance(instruction_id)
                if performance and performance.sample_size >= DEFAULT_RETRIES:
                    candidates.append((instruction_id, performance.effectiveness_score))
        if candidates:
            best_instruction_id = max(candidates, key=lambda x: x[1])[0]
            info = self.monitor.instruction_registry[best_instruction_id]
            return best_instruction_id, info["content"]
        return self.get_instruction_with_monitoring(
            instruction_type=instruction_type,
            framework=framework,
            business_profile=business_profile,
            user_persona=user_persona,
            task_complexity=task_complexity,
        )

    def start_instruction_ab_test(
        self,
        test_name: str,
        instruction_type: str,
        framework: Optional[str] = None,
        variant_changes: Optional[Dict[str, Any]] = None,
        duration_days: int = 7,
        traffic_split: float = 0.5,
    ) -> str:
        """
        Start an A/B test for instruction optimization

        Args:
            test_name: Name for the test
            instruction_type: Type of instruction to test
            framework: Framework context
            variant_changes: Changes to make for variant instruction
            duration_days: Test duration
            traffic_split: Traffic percentage for control

        Returns:
            Test ID
        """
        control_id, control_content = self.get_instruction_with_monitoring(
            instruction_type=instruction_type, framework=framework, task_complexity="medium"
        )
        variant_context = variant_changes or {}
        variant_id, variant_content = self.get_instruction_with_monitoring(
            instruction_type=instruction_type,
            framework=framework,
            task_complexity="medium",
            **variant_context,
        )
        test_id = self.monitor.start_ab_test(
            test_name=test_name,
            instruction_a_id=control_id,
            instruction_b_id=variant_id,
            traffic_split=traffic_split,
            duration_days=duration_days,
        )
        logger.info("Started instruction A/B test %s: %s" % (test_id, test_name))
        return test_id

    def get_instruction_analytics(
        self,
        instruction_type: Optional[str] = None,
        framework: Optional[str] = None,
        time_window_days: int = 7,
    ) -> Dict[str, Any]:
        """
        Get analytics for instruction performance

        Args:
            instruction_type: Filter by instruction type
            framework: Filter by framework
            time_window_days: Time window for analysis

        Returns:
            Analytics data
        """
        from datetime import timedelta

        time_window = timedelta(days=time_window_days)
        report = self.monitor.generate_performance_report(
            time_window=time_window, include_ab_tests=True
        )
        if instruction_type or framework:
            filtered_performers = []
            for performer in report.get("top_performing_instructions", []):
                instruction_id = performer["instruction_id"]
                info = self.monitor.instruction_registry.get(instruction_id, {})
                if instruction_type and info.get("type") != instruction_type:
                    continue
                if framework and info.get("framework") != framework:
                    continue
                filtered_performers.append(performer)
            report["filtered_top_performers"] = filtered_performers
        return report

    def optimize_instruction(
        self, instruction_id: str, optimization_type: str = "quality"
    ) -> Dict[str, Any]:
        """
        Generate optimization suggestions for an instruction

        Args:
            instruction_id: ID of instruction to optimize
            optimization_type: Type of optimization (quality, speed, satisfaction)

        Returns:
            Optimization suggestions
        """
        performance = self.monitor.get_instruction_performance(instruction_id)
        if not performance:
            return {"error": "No performance data available"}
        info = self.monitor.instruction_registry.get(instruction_id)
        if not info:
            return {"error": "Instruction not found"}
        suggestions = []
        if (
            optimization_type == "quality"
            and performance.avg_response_quality < CONFIDENCE_THRESHOLD
        ):
            suggestions.append(
                {
                    "type": "specificity",
                    "suggestion": "Add more specific guidance and examples to improve response clarity",
                    "current_score": performance.avg_response_quality,
                    "target_improvement": 0.1,
                }
            )
            suggestions.append(
                {
                    "type": "context",
                    "suggestion": "Include more business context integration for better relevance",
                    "current_score": performance.avg_response_quality,
                    "target_improvement": 0.05,
                }
            )
        if optimization_type == "speed" and performance.avg_response_time > 25.0:
            suggestions.append(
                {
                    "type": "conciseness",
                    "suggestion": "Simplify instruction language to reduce processing time",
                    "current_time": performance.avg_response_time,
                    "target_improvement": 5.0,
                }
            )
        if optimization_type == "satisfaction" and performance.avg_user_satisfaction < 0.75:
            suggestions.append(
                {
                    "type": "persona_adaptation",
                    "suggestion": "Enhance persona-specific adaptations for better user experience",
                    "current_score": performance.avg_user_satisfaction,
                    "target_improvement": 0.1,
                }
            )
        return {
            "instruction_id": instruction_id,
            "current_performance": performance.__dict__,
            "optimization_type": optimization_type,
            "suggestions": suggestions,
            "recommended_ab_test": len(suggestions) > 0,
        }

    def _create_instruction_id(
        self,
        instruction_type: str,
        framework: Optional[str],
        user_persona: Optional[str],
        task_complexity: str,
    ) -> str:
        """Create a unique instruction ID based on parameters"""
        components = [
            instruction_type,
            framework or "generic",
            user_persona or "default",
            task_complexity,
        ]
        return f"instr_{'-'.join(components)}"

    def _calculate_effectiveness_score(
        self,
        quality: Optional[float],
        satisfaction: Optional[float],
        response_time: Optional[float],
        had_error: bool,
    ) -> float:
        """Calculate overall effectiveness score"""
        score = 0.0
        weight_sum = 0.0
        if quality is not None:
            score += quality * 0.4
            weight_sum += 0.4
        if satisfaction is not None:
            score += satisfaction * 0.3
            weight_sum += 0.3
        if response_time is not None:
            speed_score = max(0.0, 1.0 - response_time / 30.0)
            score += speed_score * 0.2
            weight_sum += 0.2
        error_penalty = 0.0 if had_error else 1.0
        score += error_penalty * 0.1
        weight_sum += 0.1
        return score / weight_sum if weight_sum > 0 else 0.0


instruction_manager = InstructionManager()


def get_instruction_manager() -> InstructionManager:
    """Get the global instruction manager instance"""
    return instruction_manager
