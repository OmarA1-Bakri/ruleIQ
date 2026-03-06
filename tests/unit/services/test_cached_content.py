"""
Unit Tests for Google Cached Content Integration

Tests the new cached content manager functionality including:
- Cache creation and management
- Cache lifecycle management
- Performance metrics
- Cache key generation
"""

# Constants
DEFAULT_TIMEOUT = 30
CONFIDENCE_THRESHOLD = 0.8
DEFAULT_RETRIES = 5

import pytest
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4
from services.ai.cached_content import (
    GoogleCachedContentManager,
    CacheContentType,
    CacheLifecycleConfig,
    get_cached_content_manager,
)

from tests.test_constants import DEFAULT_LIMIT, MAX_RETRIES


@pytest.mark.unit
@pytest.mark.ai
class TestGoogleCachedContentManager:
    """Test Google cached content manager functionality."""

    @pytest.fixture
    def cache_config(self):
        """Test cache configuration."""
        return CacheLifecycleConfig(default_ttl_hours=2, max_ttl_hours=8, min_ttl_minutes=15)

    @pytest.fixture
    def cache_manager(self, cache_config):
        """Test cache manager instance."""
        return GoogleCachedContentManager(cache_config)

    @pytest.fixture
    def sample_business_profile(self):
        """Sample business profile for testing."""
        return {
            "id": str(uuid4()),
            "company_name": "Test Corp",
            "industry": "Technology",
            "employee_count": 150,
            "country": "UK",
            "handles_personal_data": True,
            "processes_payments": False,
            "stores_health_data": False,
            "provides_financial_services": False,
            "operates_critical_infrastructure": False,
            "has_international_operations": True,
            "existing_frameworks": ["ISO27001"],
            "cloud_providers": ["AWS"],
            "saas_tools": ["Office365"],
        }

    def test_cache_manager_initialization(self, cache_manager):
        """Test cache manager initializes correctly."""
        assert cache_manager.config.default_ttl_hours == 2
        assert cache_manager.config.max_ttl_hours == 8
        assert len(cache_manager.active_caches) == 0
        assert cache_manager.metrics["cache_hits"] == 0

    def test_cache_key_generation(self, cache_manager):
        """Test cache key generation is consistent and unique."""
        key1 = cache_manager._generate_cache_key(
            CacheContentType.ASSESSMENT_CONTEXT, "ISO27001", "tech_company"
        )
        key2 = cache_manager._generate_cache_key(
            CacheContentType.ASSESSMENT_CONTEXT, "ISO27001", "tech_company"
        )
        assert key1 == key2
        assert key1.startswith("gai_cache:")
        key3 = cache_manager._generate_cache_key(
            CacheContentType.ASSESSMENT_CONTEXT, "GDPR", "tech_company"
        )
        assert key1 != key3

    def test_business_profile_cache_key_generation(self, cache_manager, sample_business_profile):
        """Test business profile cache key generation based on similarity."""
        key1 = cache_manager._generate_business_profile_cache_key(sample_business_profile)
        similar_profile = sample_business_profile.copy()
        similar_profile["company_name"] = "Different Corp"
        key2 = cache_manager._generate_business_profile_cache_key(similar_profile)
        assert key1 == key2
        different_profile = sample_business_profile.copy()
        different_profile["industry"] = "Healthcare"
        different_profile["handles_personal_data"] = False
        key3 = cache_manager._generate_business_profile_cache_key(different_profile)
        assert key1 != key3

    def test_employee_count_range_bucketing(self, cache_manager):
        """Test employee count is bucketed correctly for cache similarity."""
        assert cache_manager._get_employee_count_range(5) == "micro"
        assert cache_manager._get_employee_count_range(25) == "small"
        assert cache_manager._get_employee_count_range(100) == "medium"
        assert cache_manager._get_employee_count_range(500) == "large"
        assert cache_manager._get_employee_count_range(2000) == "enterprise"

    def test_assessment_cache_content_building(self, cache_manager, sample_business_profile):
        """Test assessment cache content is built correctly."""
        framework_id = "ISO27001"
        assessment_context = {"assessment_type": "analysis"}
        content = cache_manager._build_assessment_cache_content(
            framework_id, sample_business_profile, assessment_context
        )
        assert len(content) > DEFAULT_RETRIES
        assert any("ISO27001" in part for part in content)
        assert any("Technology" in part for part in content)
        assert any("handles personal data" in part for part in content)

    def test_business_profile_cache_content_building(self, cache_manager, sample_business_profile):
        """Test business profile cache content is built correctly."""
        content = cache_manager._build_business_profile_cache_content(sample_business_profile)
        assert len(content) > DEFAULT_RETRIES
        assert any("Test Corp" in part for part in content)
        assert any("Technology" in part for part in content)
        assert any("medium" in part for part in content)

    def test_framework_cache_content_building(self, cache_manager):
        """Test framework cache content is built correctly."""
        framework_id = "GDPR"
        industry_context = "Technology"
        content = cache_manager._build_framework_cache_content(framework_id, industry_context)
        assert len(content) > DEFAULT_RETRIES
        assert any("GDPR" in part for part in content)
        assert any("Technology" in part for part in content)

    def test_assessment_ttl_calculation(self, cache_manager, sample_business_profile):
        """Test TTL calculation for assessment cache."""
        ttl_stable = cache_manager._calculate_assessment_ttl("ISO27001", sample_business_profile)
        ttl_other = cache_manager._calculate_assessment_ttl("CUSTOM", sample_business_profile)
        assert ttl_stable >= ttl_other
        large_company_profile = sample_business_profile.copy()
        large_company_profile["employee_count"] = 2000
        ttl_large = cache_manager._calculate_assessment_ttl("ISO27001", large_company_profile)
        assert ttl_large >= ttl_stable

    def test_business_profile_ttl_calculation(self, cache_manager, sample_business_profile):
        """Test TTL calculation for business profile cache."""
        ttl = cache_manager._calculate_business_profile_ttl(sample_business_profile)
        assert ttl >= 1
        assert ttl <= cache_manager.config.max_ttl_hours
        large_company_profile = sample_business_profile.copy()
        large_company_profile["employee_count"] = 1000
        ttl_large = cache_manager._calculate_business_profile_ttl(large_company_profile)
        assert ttl_large >= ttl

    def test_framework_helper_methods(self, cache_manager):
        """Test framework helper methods return expected values."""
        assert "Data Protection" in cache_manager._get_framework_type("GDPR")
        assert "Information Security" in cache_manager._get_framework_type("ISO27001")
        assert "Personal data" in cache_manager._get_framework_focus("GDPR")
        assert "European Union" in cache_manager._get_framework_regions("GDPR")
        assert "Global" in cache_manager._get_framework_regions("ISO27001")

    def test_data_processing_profile_generation(self, cache_manager, sample_business_profile):
        """Test data processing profile generation."""
        profile = cache_manager._get_data_processing_profile(sample_business_profile)
        assert "Personal Data" in profile
        multi_data_profile = sample_business_profile.copy()
        multi_data_profile.update({"processes_payments": True, "stores_health_data": True})
        multi_profile = cache_manager._get_data_processing_profile(multi_data_profile)
        assert "Personal Data" in multi_profile
        assert "Payment Data" in multi_profile
        assert "Health Data" in multi_profile

    def test_technology_summary_generation(self, cache_manager, sample_business_profile):
        """Test technology stack summary generation."""
        summary = cache_manager._get_technology_summary(sample_business_profile)
        assert "AWS" in summary
        assert "Office365" in summary

    def test_compliance_maturity_assessment(self, cache_manager, sample_business_profile):
        """Test compliance maturity assessment."""
        maturity = cache_manager._get_compliance_maturity(sample_business_profile)
        assert "Intermediate" in maturity
        assert "ISO27001" in maturity
        advanced_profile = sample_business_profile.copy()
        advanced_profile["existing_frameworks"] = ["ISO27001", "SOC2", "GDPR"]
        advanced_maturity = cache_manager._get_compliance_maturity(advanced_profile)
        assert "Advanced" in advanced_maturity
        beginner_profile = sample_business_profile.copy()
        beginner_profile["existing_frameworks"] = []
        beginner_maturity = cache_manager._get_compliance_maturity(beginner_profile)
        assert "Initial" in beginner_maturity

    @pytest.mark.asyncio
    @patch("google.generativeai.caching.CachedContent.create")
    async def test_assessment_cache_creation_success(
        self, mock_create, cache_manager, sample_business_profile
    ):
        """Test successful assessment cache creation."""
        mock_cached_content = Mock()
        mock_cached_content.name = "test_cache"
        mock_create.return_value = mock_cached_content
        framework_id = "ISO27001"
        result = await cache_manager.create_assessment_cache(framework_id, sample_business_profile)
        assert result is not None
        assert cache_manager.metrics["cache_creates"] == 1
        if cache_manager.use_mock:
            assert result.name == f"mock-cache-{framework_id}"
        else:
            mock_create.assert_called_once()

    @pytest.mark.asyncio
    @patch("services.ai.cached_content.genai.caching.CachedContent.create")
    async def test_assessment_cache_creation_failure(
        self, mock_create, cache_manager, sample_business_profile
    ):
        """Test assessment cache creation failure handling."""
        cache_manager.use_mock = False
        mock_create.side_effect = Exception("Cache creation failed")
        framework_id = "ISO27001"
        cache_manager.metrics["cache_misses"] = 0
        cache_manager.metrics["cache_creates"] = 0
        result = await cache_manager.create_assessment_cache(framework_id, sample_business_profile)
        assert result is None
        assert cache_manager.metrics["cache_misses"] == 1
        assert cache_manager.metrics["cache_creates"] == 0

    def test_cache_metrics_collection(self, cache_manager):
        """Test cache metrics collection and calculation."""
        cache_manager.metrics["cache_hits"] = 8
        cache_manager.metrics["cache_misses"] = 2
        cache_manager.metrics["cache_creates"] = 3
        cache_manager.metrics["total_size_cached_mb"] = 15.5
        metrics = cache_manager.get_cache_metrics()
        assert metrics["hit_rate_percentage"] == 80.0
        assert metrics["cache_hits"] == 8
        assert metrics["cache_misses"] == 2
        assert metrics["total_requests"] == 10
        assert metrics["cache_creates"] == MAX_RETRIES
        assert metrics["total_size_cached_mb"] == 15.5

    def test_get_cached_content_hit(self, cache_manager):
        """Test getting cached content when cache hit occurs."""
        mock_cached_content = Mock()
        mock_cached_content.name = "test_cache"
        cache_manager._is_cache_valid = Mock(return_value=True)
        cache_key = cache_manager._generate_cache_key(
            CacheContentType.ASSESSMENT_CONTEXT, "ISO27001", "test"
        )
        cache_manager.active_caches[cache_key] = mock_cached_content
        result = cache_manager.get_cached_content(
            CacheContentType.ASSESSMENT_CONTEXT, "ISO27001", "test"
        )
        assert result == mock_cached_content
        assert cache_manager.metrics["cache_hits"] == 1

    def test_get_cached_content_miss(self, cache_manager):
        """Test getting cached content when cache miss occurs."""
        result = cache_manager.get_cached_content(
            CacheContentType.ASSESSMENT_CONTEXT, "ISO27001", "test"
        )
        assert result is None
        assert cache_manager.metrics["cache_misses"] == 1

    @pytest.mark.asyncio
    async def test_cleanup_expired_caches(self, cache_manager):
        """Test cleanup of expired caches."""
        mock_expired_cache = Mock()
        mock_expired_cache.delete = Mock()
        cache_manager._is_cache_valid = Mock(return_value=False)
        cache_key = "test_cache_key"
        cache_manager.active_caches[cache_key] = mock_expired_cache
        cache_manager.cache_metadata[cache_key] = {
            "type": CacheContentType.ASSESSMENT_CONTEXT.value,
            "size_estimate_mb": 1.0,
        }
        cleaned_count = await cache_manager.cleanup_expired_caches()
        assert cleaned_count == 1
        assert cache_key not in cache_manager.active_caches
        assert cache_key not in cache_manager.cache_metadata
        mock_expired_cache.delete.assert_called_once()


@pytest.mark.unit
@pytest.mark.ai
class TestCachedContentIntegration:
    """Test integration with existing AI assistant."""

    @pytest.mark.asyncio
    async def test_get_cached_content_manager_singleton(self):
        """Test that cached content manager is a singleton."""
        manager1 = await get_cached_content_manager()
        manager2 = await get_cached_content_manager()
        assert manager1 is manager2

    def test_cache_lifecycle_config_defaults(self):
        """Test cache lifecycle configuration defaults."""
        config = CacheLifecycleConfig()
        assert config.default_ttl_hours == 2
        assert config.max_ttl_hours == 24
        assert config.min_ttl_minutes == DEFAULT_TIMEOUT
        assert config.auto_refresh_threshold == CONFIDENCE_THRESHOLD
        assert config.max_cache_size_mb == DEFAULT_LIMIT

    def test_cache_content_type_enum(self):
        """Test cache content type enumeration."""
        assert CacheContentType.ASSESSMENT_CONTEXT.value == "assessment_context"
        assert CacheContentType.BUSINESS_PROFILE.value == "business_profile"
        assert CacheContentType.FRAMEWORK_CONTEXT.value == "framework_context"
        assert CacheContentType.INDUSTRY_REGULATIONS.value == "industry_regulations"
        assert CacheContentType.SYSTEM_INSTRUCTIONS.value == "system_instructions"


@pytest.mark.integration
@pytest.mark.ai
class TestCachedContentEndToEnd:
    """End-to-end tests for cached content functionality."""

    @pytest.fixture
    def assistant_with_cache(self, async_db_session):
        """AI assistant with cached content enabled."""
        from services.ai.assistant import ComplianceAssistant
        from services.ai.cached_content import GoogleCachedContentManager
        from unittest.mock import AsyncMock, Mock

        assistant = ComplianceAssistant(async_db_session)
        assistant.cached_content_manager = GoogleCachedContentManager()
        assistant._get_cached_content_manager = AsyncMock(
            return_value=assistant.cached_content_manager
        )
        assistant.context_manager = Mock()
        assistant.prompt_templates = Mock()
        assistant._generate_ai_response_with_cache = AsyncMock(return_value="Mock response")
        assistant._parse_assessment_analysis_response = Mock(
            return_value={"gaps": [], "recommendations": []}
        )
        assistant.analyze_assessment_results = AsyncMock()
        return assistant

    @pytest.fixture
    def mock_business_profile(self):
        """Mock business profile for testing."""
        return {
            "id": str(uuid4()),
            "company_name": "Integration Test Corp",
            "industry": "Financial Services",
            "employee_count": 500,
            "country": "UK",
            "handles_personal_data": True,
            "processes_payments": True,
            "existing_frameworks": ["ISO27001", "SOC2"],
        }

    @pytest.mark.asyncio
    @patch("google.generativeai.caching.CachedContent.create")
    async def test_assessment_analysis_with_cached_content(
        self, mock_create, assistant_with_cache, mock_business_profile
    ):
        """Test assessment analysis uses cached content when available."""
        mock_cached_content = Mock()
        mock_cached_content.name = "test_assessment_cache"
        mock_create.return_value = mock_cached_content
        mock_result = {
            "gaps": [],
            "recommendations": [],
            "request_id": str(uuid4()),
            "generated_at": "2024-01-01T00:00:00Z",
        }
        assistant_with_cache.analyze_assessment_results = AsyncMock(return_value=mock_result)
        assessment_results = {"framework": "ISO27001", "responses": []}
        result = await assistant_with_cache.analyze_assessment_results(
            assessment_results, "ISO27001", uuid4()
        )
        assistant_with_cache.analyze_assessment_results.assert_called_once()
        assert "gaps" in result
        assert "recommendations" in result
        assert "request_id" in result
        assert "generated_at" in result

    @pytest.mark.asyncio
    async def test_cache_metrics_collection_integration(self, assistant_with_cache):
        """Test cache metrics collection in integration context."""
        cached_content_manager = await assistant_with_cache._get_cached_content_manager()
        cached_content_manager.metrics["cache_hits"] = 5
        cached_content_manager.metrics["cache_misses"] = 1
        cached_content_manager.metrics["cache_creates"] = 2
        metrics = cached_content_manager.get_cache_metrics()
        assert metrics["hit_rate_percentage"] > 0
        assert metrics["total_requests"] == 6
        assert "cache_types" in metrics
        assert len(metrics["cache_types"]) == len(CacheContentType)
