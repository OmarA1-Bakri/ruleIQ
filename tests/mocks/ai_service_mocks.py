"""

Comprehensive AI Service Mocks for Testing

Provides realistic mock implementations for all AI services used in the application,
including ComplianceAssistant, AI assessment endpoints, and external AI providers.
"""

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from services.ai.exceptions import (
    AIContentFilterException,
    AIQuotaExceededException,
    AIServiceException,
    AITimeoutException,
)


class MockComplianceAssistant:
    """Mock implementation of ComplianceAssistant with realistic responses"""

    def __init__(self, db_session=None, fail_rate: float = 0.0, delay_ms: int = 100):
        """
        Initialize mock with configurable failure rate and response delay

        Args:
            db_session: Database session (not used in mock)
            fail_rate: Probability of failure (0.0 = never fail, 1.0 = always fail)
            delay_ms: Response delay in milliseconds
        """
        self.db_session = db_session
        self.fail_rate = fail_rate
        self.delay_ms = delay_ms
        self.call_count = 0

    async def _simulate_delay(self):
        """Simulate AI processing delay"""
        if self.delay_ms > 0:
            await asyncio.sleep(self.delay_ms / 1000)

    def _should_fail(self) -> bool:
        """Determine if this call should fail based on fail_rate"""
        import random

        return random.random() < self.fail_rate

    async def get_question_help(
        self,
        question_id: str,
        question_text: str,
        framework_id: str,
        section_id: Optional[str] = None,
        user_context: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Mock AI question help with realistic responses"""
        await self._simulate_delay()
        self.call_count += 1

        if self._should_fail():
            raise AIServiceException("Mock AI service failure")

        # Generate contextual response based on question
        guidance = self._generate_contextual_guidance(question_text, framework_id)

        return {
            "guidance": guidance,
            "confidence_score": 0.85 + (hash(question_id) % 15) / 100,  # 0.85-0.99
            "related_topics": self._get_related_topics(framework_id),
            "follow_up_suggestions": self._get_follow_up_suggestions(question_text),
            "source_references": self._get_source_references(framework_id),
            "request_id": f"mock-{uuid4().hex[:8]}",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    async def generate_followup_questions(
        self,
        question_id: str,
        question_text: str,
        user_answer: str,
        assessment_context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Mock AI follow-up question generation"""
        await self._simulate_delay()
        self.call_count += 1

        if self._should_fail():
            raise AIServiceException("Mock follow-up generation failure")

        framework_id = assessment_context.get("framework_id", "gdpr")

        # Generate contextual follow-up questions
        follow_ups = self._generate_followup_questions(
            question_text,
            user_answer,
            framework_id,
        )

        return {
            "follow_up_questions": follow_ups,
            "reasoning": f"Based on your answer '{user_answer}', we need more specific information to provide accurate compliance guidance.",
            "request_id": f"mock-followup-{uuid4().hex[:8]}",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    async def analyze_assessment_results(
        self,
        framework_id: str,
        business_profile_id: str,
        assessment_results: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Mock AI assessment analysis"""
        await self._simulate_delay()
        self.call_count += 1

        if self._should_fail():
            raise AIServiceException("Mock analysis failure")

        completion = assessment_results.get("completion_percentage", 0)
        answers = assessment_results.get("answers", {})

        return {
            "gaps": self._identify_gaps(answers, framework_id),
            "recommendations": self._generate_recommendations(completion, framework_id),
            "risk_assessment": self._assess_risk_level(completion, answers),
            "compliance_insights": self._generate_insights(answers, framework_id),
            "evidence_requirements": self._suggest_evidence(answers, framework_id),
            "request_id": f"mock-analysis-{uuid4().hex[:8]}",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    async def get_personalized_recommendations(
        self,
        gaps: List[Dict],
        business_profile: Dict[str, Any],
        timeline_preferences: str = "standard",
    ) -> Dict[str, Any]:
        """Mock personalized recommendations"""
        await self._simulate_delay()
        self.call_count += 1

        if self._should_fail():
            raise AIServiceException("Mock recommendations failure")

        industry = business_profile.get("industry", "technology")
        size = business_profile.get("size", "small")

        return {
            "recommendations": self._generate_personalized_recommendations(
                gaps,
                industry,
                size,
            ),
            "implementation_plan": self._create_implementation_plan(
                timeline_preferences,
            ),
            "success_metrics": self._define_success_metrics(gaps),
            "request_id": f"mock-rec-{uuid4().hex[:8]}",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def _generate_contextual_guidance(self, question_text: str, framework_id: str) -> str:
        """Generate contextual guidance based on question and framework"""
        question_lower = question_text.lower()

        if framework_id.lower() == "gdpr":
            if "personal data" in question_lower:
                return "Personal data under GDPR includes any information relating to an identified or identifiable natural person. This includes names, email addresses, IP addresses, and even pseudonymized data that can be linked back to an individual."
            elif "consent" in question_lower:
                return "GDPR requires that consent be freely given, specific, informed, and unambiguous. It must be as easy to withdraw consent as it is to give it, and consent cannot be bundled with other terms."
            elif "breach" in question_lower:
                return "Data breaches must be reported to supervisory authorities within 72 hours of becoming aware of the breach. If the breach poses a high risk to individuals, they must also be notified without undue delay."

        elif framework_id.lower() == "iso27001":
            if "risk" in question_lower:
                return "ISO 27001 requires a systematic approach to risk management. Organizations must identify information security risks, assess their likelihood and impact, and implement appropriate controls to mitigate them."
            elif "control" in question_lower:
                return "ISO 27001 controls are safeguards implemented to reduce information security risks. The standard provides 114 controls across 14 categories, but organizations should select controls based on their risk assessment."

        # Default guidance
        return f"This question relates to {framework_id} compliance requirements. Proper implementation requires understanding the specific context of your organization and the applicable regulatory requirements."

    def _get_related_topics(self, framework_id: str) -> List[str]:
        """Get related topics for the framework"""
        topics_map = {
            "gdpr": [
                "Data Protection",
                "Privacy Rights",
                "Consent Management",
                "Data Minimization",
            ],
            "iso27001": [
                "Information Security",
                "Risk Management",
                "Access Control",
                "Incident Management",
            ],
            "sox": [
                "Financial Controls",
                "Internal Auditing",
                "Financial Reporting",
                "Corporate Governance",
            ],
            "hipaa": [
                "Protected Health Information",
                "Administrative Safeguards",
                "Physical Safeguards",
                "Technical Safeguards",
            ],
        }
        return topics_map.get(
            framework_id.lower(),
            ["Compliance", "Risk Management", "Controls"],
        )

    def _get_follow_up_suggestions(self, question_text: str) -> List[str]:
        """Generate follow-up suggestions based on question"""
        question_lower = question_text.lower()

        if "data" in question_lower:
            return [
                "What types of data do you collect?",
                "How do you secure this data?",
                "Who has access to this data?",
            ]
        elif "policy" in question_lower:
            return [
                "How often is this policy reviewed?",
                "Who is responsible for policy compliance?",
                "How do you train staff on this policy?",
            ]
        else:
            return [
                "What is your current implementation status?",
                "What challenges do you face with this requirement?",
                "Do you have documented procedures for this?",
            ]

    def _get_source_references(self, framework_id: str) -> List[str]:
        """Get source references for the framework"""
        references_map = {
            "gdpr": ["GDPR Article 5", "GDPR Article 6", "ICO Guidance"],
            "iso27001": ["ISO 27001:2022", "ISO 27002:2022", "NIST Framework"],
            "sox": ["SOX Section 404", "PCAOB Standards", "SEC Guidance"],
            "hipaa": ["45 CFR 164", "HHS Guidance", "NIST 800-66"],
        }
        return references_map.get(
            framework_id.lower(),
            [f"{framework_id} Standards", "Regulatory Guidance"],
        )

    def _generate_followup_questions(
        self, question_text: str, user_answer: str, framework_id: str
    ) -> List[Dict]:
        """Generate contextual follow-up questions"""
        questions = []

        if user_answer.lower() in ["yes", "true"]:
            if "personal data" in question_text.lower():
                questions.append(
                    {
                        "id": f"ai-{uuid4().hex[:8]}",
                        "text": "What types of personal data do you process?",
                        "type": "multiple_choice",
                        "options": [
                            "Names and contact details",
                            "Financial information",
                            "Health data",
                            "Biometric data",
                        ],
                        "validation": {"required": True},
                        "metadata": {
                            "source": "ai",
                            "reasoning": "Need to understand data types for risk assessment",
                        },
                    },
                )
                questions.append(
                    {
                        "id": f"ai-{uuid4().hex[:8]}",
                        "text": "What is your legal basis for processing this data?",
                        "type": "multiple_choice",
                        "options": [
                            "Consent",
                            "Contract",
                            "Legal obligation",
                            "Legitimate interest",
                        ],
                        "validation": {"required": True},
                        "metadata": {
                            "source": "ai",
                            "reasoning": "Legal basis is required for GDPR compliance",
                        },
                    },
                )

        return questions

    def _identify_gaps(self, answers: Dict, framework_id: str) -> List[Dict]:
        """Identify compliance gaps based on answers"""
        gaps = []

        # Analyze answers for common gaps
        if framework_id.lower() == "gdpr":
            if answers.get("has_privacy_policy") == "no":
                gaps.append(
                    {
                        "type": "missing_policy",
                        "description": "Privacy policy is missing or incomplete",
                        "priority": "high",
                        "control_reference": "GDPR Article 13",
                    },
                )

            if answers.get("conducts_dpia") == "no":
                gaps.append(
                    {
                        "type": "missing_assessment",
                        "description": "Data Protection Impact Assessment not conducted",
                        "priority": "medium",
                        "control_reference": "GDPR Article 35",
                    },
                )

        return gaps

    def _generate_recommendations(self, completion: float, framework_id: str) -> List[Dict]:
        """Generate recommendations based on completion and framework"""
        recommendations = []

        if completion < 50:
            recommendations.append(
                {
                    "id": f"rec-{uuid4().hex[:8]}",
                    "title": "Complete Assessment",
                    "description": "Continue with the assessment to identify all compliance requirements",
                    "priority": "high",
                    "category": "Assessment",
                },
            )

        recommendations.append(
            {
                "id": f"rec-{uuid4().hex[:8]}",
                "title": f"Implement {framework_id} Controls",
                "description": f"Implement the required controls for {framework_id} compliance",
                "priority": "medium",
                "category": "Implementation",
            },
        )

        return recommendations

    def _assess_risk_level(self, completion: float, answers: Dict) -> Dict:
        """Assess risk level based on completion and answers"""
        risk_score = max(0, 100 - completion)

        if risk_score > 70:
            level = "high"
        elif risk_score > 40:
            level = "medium"
        else:
            level = "low"

        return {
            "level": level,
            "score": risk_score,
            "factors": (
                ["Incomplete assessment", "Missing controls"]
                if risk_score > 50
                else ["Minor gaps identified"],
            ),
        }

    def _generate_insights(self, answers: Dict, framework_id: str) -> List[str]:
        """Generate compliance insights"""
        insights = [
            f"Your organization shows good progress toward {framework_id} compliance",
            "Focus on documentation and policy development",
            "Regular training and awareness programs are recommended",
        ]
        return insights

    def _suggest_evidence(self, answers: Dict, framework_id: str) -> List[Dict]:
        """Suggest required evidence"""
        evidence = [
            {
                "type": "policy_document",
                "description": f"{framework_id} compliance policy",
                "priority": "high",
            },
            {
                "type": "training_records",
                "description": "Staff training documentation",
                "priority": "medium",
            },
        ]
        return evidence

    def _generate_personalized_recommendations(
        self, gaps: List[Dict], industry: str, size: str
    ) -> List[Dict]:
        """Generate personalized recommendations"""
        recommendations = []

        for gap in gaps:
            rec = {
                "id": f"rec-{uuid4().hex[:8]}",
                "title": f"Address {gap.get('type', 'compliance gap')}",
                "description": gap.get("description", "Compliance gap identified"),
                "priority": gap.get("priority", "medium"),
                "category": "Remediation",
                "industry_specific": industry,
                "size_appropriate": size,
                "estimated_effort": "Medium",
                "timeline": "2-4 weeks",
            }
            recommendations.append(rec)

        return recommendations

    def _create_implementation_plan(self, timeline: str) -> Dict:
        """Create implementation plan"""
        weeks_map = {"urgent": 2, "standard": 8, "extended": 16}
        total_weeks = weeks_map.get(timeline, 8)

        return {
            "phases": [
                {
                    "name": "Assessment and Planning",
                    "duration_weeks": max(1, total_weeks // 4),
                    "tasks": [
                        "Gap analysis",
                        "Resource planning",
                        "Timeline development",
                    ],
                },
                {
                    "name": "Implementation",
                    "duration_weeks": max(2, total_weeks // 2),
                    "tasks": [
                        "Policy development",
                        "Control implementation",
                        "Training delivery",
                    ],
                },
                {
                    "name": "Validation and Monitoring",
                    "duration_weeks": max(1, total_weeks // 4),
                    "tasks": ["Testing", "Documentation", "Monitoring setup"],
                },
            ],
            "total_timeline_weeks": total_weeks,
            "resource_requirements": [
                "Project manager",
                "Compliance specialist",
                "Technical resources",
            ],
        }

    def _define_success_metrics(self, gaps: List[Dict]) -> List[Dict]:
        """Define success metrics"""
        return [
            {"metric": "Gap closure rate", "target": "100%"},
            {"metric": "Policy completion", "target": "100%"},
            {"metric": "Staff training completion", "target": "95%"},
            {"metric": "Control implementation", "target": "100%"},
        ]


class MockAIServiceFailures:
    """Mock AI service that simulates various failure scenarios"""

    @staticmethod
    def timeout_service():
        """Returns a service that always times out"""
        mock = MockComplianceAssistant(fail_rate=1.0)

        async def timeout_method(*args, **kwargs):
            raise AITimeoutException(timeout_seconds=30.0)

        mock.get_question_help = timeout_method
        mock.generate_followup_questions = timeout_method
        mock.analyze_assessment_results = timeout_method
        return mock

    @staticmethod
    def quota_exceeded_service():
        """Returns a service that always hits quota limits"""
        mock = MockComplianceAssistant(fail_rate=1.0)

        async def quota_method(*args, **kwargs):
            raise AIQuotaExceededException(quota_type="API requests")

        mock.get_question_help = quota_method
        mock.generate_followup_questions = quota_method
        mock.analyze_assessment_results = quota_method
        return mock

    @staticmethod
    def content_filter_service():
        """Returns a service that triggers content filtering"""
        mock = MockComplianceAssistant(fail_rate=1.0)

        async def filter_method(*args, **kwargs):
            raise AIContentFilterException(
                filter_reason="Inappropriate content detected",
            )

        mock.get_question_help = filter_method
        return mock


# Global mock instances for easy access
default_mock_assistant = MockComplianceAssistant()
timeout_mock_assistant = MockAIServiceFailures.timeout_service()
quota_mock_assistant = MockAIServiceFailures.quota_exceeded_service()
filter_mock_assistant = MockAIServiceFailures.content_filter_service()
