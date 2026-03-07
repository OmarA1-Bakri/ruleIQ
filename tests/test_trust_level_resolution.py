"""
Test suite for TrustLevel enum resolution and import conflicts.

This test suite verifies that all TrustLevel enums can be imported and used
without conflicts, ensuring proper separation between:
- Agent autonomy levels (IntEnum 0-3)
- Database storage enums (IntEnum 0-3)
- User trust relationship levels (str Enum)
"""

import pytest
from enum import IntEnum


class TestTrustLevelResolution:
    """Test TrustLevel enum imports and functionality."""

    def test_agent_autonomy_trust_level_import(self):
        """Test agent autonomy TrustLevel can be imported from trust_algorithm."""
        from services.agents.trust_algorithm import TrustLevel

        # Verify it's an IntEnum
        assert issubclass(TrustLevel, IntEnum)

        # Verify correct values for agent autonomy
        assert TrustLevel.L0_OBSERVED == 0
        assert TrustLevel.L1_ASSISTED == 1
        assert TrustLevel.L2_SUPERVISED == 2
        assert TrustLevel.L3_AUTONOMOUS == 3

        # Verify string representations
        assert TrustLevel.L0_OBSERVED.name == "L0_OBSERVED"
        assert TrustLevel.L1_ASSISTED.name == "L1_ASSISTED"
        assert TrustLevel.L2_SUPERVISED.name == "L2_SUPERVISED"
        assert TrustLevel.L3_AUTONOMOUS.name == "L3_AUTONOMOUS"

    def test_database_storage_trust_level_import(self):
        """Test database storage TrustLevelEnum can be imported from trust_metrics."""
        from models.trust_metrics import TrustLevelEnum

        # Verify it's an IntEnum
        assert issubclass(TrustLevelEnum, IntEnum)

        # Verify correct values for database storage
        assert TrustLevelEnum.L0_OBSERVED == 0
        assert TrustLevelEnum.L1_ASSISTED == 1
        assert TrustLevelEnum.L2_SUPERVISED == 2
        assert TrustLevelEnum.L3_AUTONOMOUS == 3

        # Verify string representations
        assert TrustLevelEnum.L0_OBSERVED.name == "L0_OBSERVED"
        assert TrustLevelEnum.L1_ASSISTED.name == "L1_ASSISTED"
        assert TrustLevelEnum.L2_SUPERVISED.name == "L2_SUPERVISED"
        assert TrustLevelEnum.L3_AUTONOMOUS.name == "L3_AUTONOMOUS"

    def test_user_trust_relationship_import(self):
        """Test user trust relationship TrustLevel can be imported from context_service."""
        from services.context_service import TrustLevel as UserTrustLevel

        # Verify it's a str Enum (not IntEnum)
        assert not issubclass(UserTrustLevel, IntEnum)

        # Verify correct values for user trust relationships
        assert UserTrustLevel.UNKNOWN == "unknown"
        assert UserTrustLevel.SKEPTICAL == "skeptical"
        assert UserTrustLevel.CAUTIOUS == "cautious"
        assert UserTrustLevel.TRUSTING == "trusting"
        assert UserTrustLevel.DELEGATING == "delegating"

        # Verify string representations
        assert UserTrustLevel.UNKNOWN.name == "UNKNOWN"
        assert UserTrustLevel.SKEPTICAL.name == "SKEPTICAL"
        assert UserTrustLevel.CAUTIOUS.name == "CAUTIOUS"
        assert UserTrustLevel.TRUSTING.name == "TRUSTING"
        assert UserTrustLevel.DELEGATING.name == "DELEGATING"

    def test_agent_autonomy_vs_database_storage_compatibility(self):
        """Test that agent autonomy and database storage enums have compatible values."""
        from services.agents.trust_algorithm import TrustLevel as AgentTrustLevel
        from models.trust_metrics import TrustLevelEnum

        # Values should be identical for compatibility
        assert AgentTrustLevel.L0_OBSERVED.value == TrustLevelEnum.L0_OBSERVED.value
        assert AgentTrustLevel.L1_ASSISTED.value == TrustLevelEnum.L1_ASSISTED.value
        assert AgentTrustLevel.L2_SUPERVISED.value == TrustLevelEnum.L2_SUPERVISED.value
        assert AgentTrustLevel.L3_AUTONOMOUS.value == TrustLevelEnum.L3_AUTONOMOUS.value

        # Names should be identical
        assert AgentTrustLevel.L0_OBSERVED.name == TrustLevelEnum.L0_OBSERVED.name
        assert AgentTrustLevel.L1_ASSISTED.name == TrustLevelEnum.L1_ASSISTED.name
        assert AgentTrustLevel.L2_SUPERVISED.name == TrustLevelEnum.L2_SUPERVISED.name
        assert AgentTrustLevel.L3_AUTONOMOUS.name == TrustLevelEnum.L3_AUTONOMOUS.name

    def test_user_trust_vs_agent_autonomy_separation(self):
        """Test that user trust levels are properly separated from agent autonomy levels."""
        from services.agents.trust_algorithm import TrustLevel as AgentTrustLevel
        from services.context_service import TrustLevel as UserTrustLevel

        # These should be completely different enums
        assert AgentTrustLevel != UserTrustLevel

        # Agent levels are integers, user levels are strings
        assert isinstance(AgentTrustLevel.L0_OBSERVED.value, int)
        assert isinstance(UserTrustLevel.UNKNOWN.value, str)

        # No overlapping names or values
        agent_names = {level.name for level in AgentTrustLevel}
        user_names = {level.name for level in UserTrustLevel}
        assert agent_names.isdisjoint(user_names)

    def test_all_enums_can_be_imported_simultaneously(self):
        """Test that all TrustLevel enums can be imported in the same module without conflicts."""
        # Import all three enums
        from services.agents.trust_algorithm import TrustLevel as AgentTrustLevel
        from models.trust_metrics import TrustLevelEnum as DBTrustLevel
        from services.context_service import TrustLevel as UserTrustLevel

        # Verify they are all different classes
        assert AgentTrustLevel != DBTrustLevel
        assert AgentTrustLevel != UserTrustLevel
        assert DBTrustLevel != UserTrustLevel

        # Verify they can all be instantiated
        agent_level = AgentTrustLevel.L1_ASSISTED
        db_level = DBTrustLevel.L2_SUPERVISED
        user_level = UserTrustLevel.TRUSTING

        assert agent_level.value == 1
        assert db_level.value == 2
        assert user_level.value == "trusting"

    def test_agent_services_can_import_correct_trust_level(self):
        """Test that agent services can import the correct TrustLevel without conflicts."""
        # Test imports that were previously failing
        try:
            from services.agents.orchestrator import OrchestratorService
            from services.agents.trust_manager import TrustManager
            from services.agents.session_manager import SessionManager
            from services.agents.decision_tracker import DecisionTracker

            # If we get here without ImportError, the imports are working
            assert True
        except ImportError as e:
            pytest.fail(f"Agent service imports failed: {e}")

    def test_context_service_trust_level_functionality(self):
        """Test that context service TrustLevel works correctly."""
        from services.context_service import UserContextService, TrustLevel as UserTrustLevel

        # Test enum values
        assert UserTrustLevel.UNKNOWN.value == "unknown"
        assert UserTrustLevel.SKEPTICAL.value == "skeptical"
        assert UserTrustLevel.CAUTIOUS.value == "cautious"
        assert UserTrustLevel.TRUSTING.value == "trusting"
        assert UserTrustLevel.DELEGATING.value == "delegating"

        # Test service can be instantiated
        service = UserContextService()
        assert service is not None
        assert hasattr(service, "cache_service")

    def test_trust_algorithm_functionality(self):
        """Test that trust algorithm works with its TrustLevel enum."""
        from services.agents.trust_algorithm import TrustProgressionAlgorithm, TrustLevel

        # Test algorithm can be instantiated
        algorithm = TrustProgressionAlgorithm("test-user", TrustLevel.L0_OBSERVED)
        assert algorithm.user_id == "test-user"
        assert algorithm.current_trust_level == TrustLevel.L0_OBSERVED

        # Test trust score calculation
        score = algorithm.calculate_trust_score()
        assert hasattr(score, "overall_score")
        assert hasattr(score, "approval_rate")
        assert hasattr(score, "success_rate")

    def test_database_models_with_trust_levels(self):
        """Test that database models work with TrustLevelEnum."""
        from models.trust_metrics import TrustMetrics, TrustLevelEnum

        # Test model can be created with trust level
        metrics = TrustMetrics(
            user_id="test-user",
            current_trust_level=TrustLevelEnum.L1_ASSISTED.value,
            trust_score=75.0,
        )
        assert metrics.user_id == "test-user"
        assert metrics.current_trust_level == 1
        assert metrics.trust_score == 75.0

    def test_enum_value_conversion_compatibility(self):
        """Test that enum values can be converted between compatible types."""
        from services.agents.trust_algorithm import TrustLevel as AgentTrustLevel
        from models.trust_metrics import TrustLevelEnum

        # Test conversion between agent and database enums
        agent_level = AgentTrustLevel.L2_SUPERVISED
        db_level = TrustLevelEnum.L2_SUPERVISED

        # Values should be equal
        assert agent_level.value == db_level.value

        # Should be able to convert int to enum
        level_from_int = AgentTrustLevel(2)
        assert level_from_int == AgentTrustLevel.L2_SUPERVISED

        level_from_db = AgentTrustLevel(db_level.value)
        assert level_from_db == agent_level
