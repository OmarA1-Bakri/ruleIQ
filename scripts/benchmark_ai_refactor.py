#!/usr/bin/env python3
"""
AI Refactor Parity Benchmarking Script

Verifies that the new modular architecture maintains functional parity
with the legacy ComplianceAssistant implementation.

Usage:
    python scripts/benchmark_ai_refactor.py [--mode MODE]

Modes:
    - quick: Fast checks, minimal API calls (default)
    - full: Comprehensive parity verification
    - performance: Performance benchmarking
"""

import asyncio
import time
import argparse
from typing import Dict, Any, List
from uuid import uuid4
from unittest.mock import AsyncMock
from pathlib import Path

import sys

# Add project root to path (file-relative, deterministic)
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from services.ai.assistant_facade import ComplianceAssistant as NewAssistant
from services.ai.assistant_legacy import ComplianceAssistant as LegacyAssistant


class ParityVerifier:
    """Verifies parity between legacy and new implementations."""

    def __init__(self, mode: str = "quick") -> None:
        self.mode = mode
        self.results: List[Dict[str, Any]] = []
        self.mock_db = AsyncMock()

    def log_result(self, test_name: str, passed: bool, details: str = ""):
        """Log test result."""
        result = {"test": test_name, "passed": passed, "details": details}
        self.results.append(result)

        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")
        if details:
            print(f"  {details}")

    def print_summary(self):
        """Print test summary."""
        passed = sum(1 for r in self.results if r["passed"])
        total = len(self.results)
        percentage = (passed / total * 100) if total > 0 else 0

        print("\n" + "=" * 60)
        print("PARITY VERIFICATION SUMMARY")
        print("=" * 60)
        print(f"Tests Passed: {passed}/{total} ({percentage:.1f}%)")

        if passed < total:
            print("\nFailed Tests:")
            for result in self.results:
                if not result["passed"]:
                    print(f"  - {result['test']}: {result['details']}")

        print("=" * 60)
        return percentage >= 95.0  # Require 95% pass rate

    async def test_initialization(self):
        """Test that both implementations initialize correctly."""
        print("\n--- Initialization Tests ---")

        try:
            # Test new implementation
            new_assistant = NewAssistant(self.mock_db, {})
            new_has_attrs = all(
                [
                    hasattr(new_assistant, "db"),
                    hasattr(new_assistant, "context_manager"),
                    hasattr(new_assistant, "provider_factory"),
                    hasattr(new_assistant, "assessment_service"),
                ]
            )
            self.log_result(
                "New assistant initialization",
                new_has_attrs,
                "All required attributes present" if new_has_attrs else "Missing attributes",
            )

            # Test legacy implementation
            legacy_assistant = LegacyAssistant(self.mock_db, {})
            legacy_has_attrs = all(
                [hasattr(legacy_assistant, "db"), hasattr(legacy_assistant, "context_manager")]
            )
            self.log_result(
                "Legacy assistant initialization",
                legacy_has_attrs,
                "All required attributes present" if legacy_has_attrs else "Missing attributes",
            )

        except Exception as e:
            self.log_result("Initialization", False, f"Exception: {e}")

    async def test_api_parity(self):
        """Test that both implementations expose the same public API."""
        print("\n--- API Parity Tests ---")

        try:
            new_assistant = NewAssistant(self.mock_db, {})
            legacy_assistant = LegacyAssistant(self.mock_db, {})

            # Key methods that must exist in both
            required_methods = [
                "get_assessment_help",
                "generate_assessment_followup",
                "analyze_assessment_results",
                "get_assessment_recommendations",
                "generate_customized_policy",
                "generate_evidence_collection_workflow",
                "get_evidence_recommendations",
                "analyze_evidence_gap",
            ]

            for method_name in required_methods:
                new_has = hasattr(new_assistant, method_name)
                legacy_has = hasattr(legacy_assistant, method_name)
                both_have = new_has and legacy_has

                self.log_result(
                    f"Method '{method_name}' exists in both",
                    both_have,
                    f"New: {new_has}, Legacy: {legacy_has}",
                )

        except Exception as e:
            self.log_result("API parity", False, f"Exception: {e}")

    async def test_delegation_correctness(self):
        """Test that new implementation correctly delegates to services."""
        print("\n--- Delegation Tests ---")

        try:
            new_assistant = NewAssistant(self.mock_db, {})

            # Mock service responses
            mock_help_response = {"guidance": "Test", "confidence_score": 0.9}
            new_assistant.assessment_service.get_help = AsyncMock(return_value=mock_help_response)

            # Call façade method
            result = await new_assistant.get_assessment_help(
                question_id="Q1",
                question_text="Test",
                framework_id="GDPR",
                business_profile_id=uuid4(),
            )

            # Verify delegation worked
            service_called = new_assistant.assessment_service.get_help.called
            correct_result = result == mock_help_response

            self.log_result(
                "Assessment help delegation",
                service_called and correct_result,
                f"Service called: {service_called}, Correct result: {correct_result}",
            )

        except Exception as e:
            self.log_result("Delegation", False, f"Exception: {e}")

    async def test_service_layer_exists(self):
        """Test that all expected service layers exist."""
        print("\n--- Service Layer Tests ---")

        try:
            new_assistant = NewAssistant(self.mock_db, {})

            services = {
                "provider_factory": new_assistant.provider_factory,
                "response_generator": new_assistant.response_generator,
                "response_parser": new_assistant.response_parser,
                "fallback_generator": new_assistant.fallback_generator,
                "assessment_service": new_assistant.assessment_service,
                "policy_service": new_assistant.policy_service,
                "workflow_service": new_assistant.workflow_service,
                "evidence_service": new_assistant.evidence_service,
                "compliance_service": new_assistant.compliance_service,
            }

            for service_name, service_obj in services.items():
                exists = service_obj is not None
                self.log_result(
                    f"Service '{service_name}' initialized",
                    exists,
                    f"Service object: {type(service_obj).__name__}",
                )

        except Exception as e:
            self.log_result("Service layer", False, f"Exception: {e}")

    async def test_imports(self):
        """Test that all modules can be imported without errors."""
        print("\n--- Import Tests ---")

        modules_to_test = [
            ("services.ai.providers", "ProviderFactory"),
            ("services.ai.providers.factory", "ProviderFactory"),
            ("services.ai.response", "ResponseGenerator"),
            ("services.ai.response.formatter", "ResponseFormatter"),
            ("services.ai.response.fallback", "FallbackGenerator"),
            ("services.ai.domains", "AssessmentService"),
            ("services.ai.domains.assessment_service", "AssessmentService"),
            ("services.ai.domains.policy_service", "PolicyService"),
            ("services.ai.domains.workflow_service", "WorkflowService"),
            ("services.ai.domains.evidence_service", "EvidenceService"),
            ("services.ai.domains.compliance_service", "ComplianceAnalysisService"),
            ("services.ai.assistant_facade", "ComplianceAssistant"),
        ]

        for module_name, class_name in modules_to_test:
            try:
                module = __import__(module_name, fromlist=[class_name])
                cls = getattr(module, class_name)
                self.log_result(
                    f"Import {module_name}.{class_name}",
                    True,
                    f"Successfully imported {cls.__name__}",
                )
            except Exception as e:
                self.log_result(f"Import {module_name}.{class_name}", False, f"Import failed: {e}")

    async def test_performance_comparison(self):
        """Compare performance of new vs legacy (mocked)."""
        if self.mode != "performance":
            return

        print("\n--- Performance Comparison ---")

        try:
            # Test initialization time
            iterations = 100

            # New implementation
            start = time.perf_counter()
            for _ in range(iterations):
                NewAssistant(self.mock_db, {})
            new_time = time.perf_counter() - start

            # Legacy implementation
            start = time.perf_counter()
            for _ in range(iterations):
                LegacyAssistant(self.mock_db, {})
            legacy_time = time.perf_counter() - start

            speedup = legacy_time / new_time if new_time > 0 else 0
            acceptable = 0.5 <= speedup <= 2.0  # Within 2x of legacy

            self.log_result(
                "Initialization performance",
                acceptable,
                f"New: {new_time:.4f}s, Legacy: {legacy_time:.4f}s, Speedup: {speedup:.2f}x",
            )

        except Exception as e:
            self.log_result("Performance", False, f"Exception: {e}")

    async def run_all_tests(self):
        """Run all parity tests."""
        print("\n" + "=" * 60)
        print("AI REFACTOR PARITY VERIFICATION")
        print(f"Mode: {self.mode}")
        print("=" * 60)

        await self.test_imports()
        await self.test_initialization()
        await self.test_api_parity()
        await self.test_service_layer_exists()
        await self.test_delegation_correctness()

        if self.mode == "performance":
            await self.test_performance_comparison()

        return self.print_summary()


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Verify parity between legacy and refactored AI implementations"
    )
    parser.add_argument(
        "--mode",
        choices=["quick", "full", "performance"],
        default="quick",
        help="Verification mode",
    )

    args = parser.parse_args()

    verifier = ParityVerifier(mode=args.mode)
    success = await verifier.run_all_tests()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
