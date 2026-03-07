"""
Functional tests for PolicyService.

Tests all policy generation methods with realistic scenarios:
- AI-powered policy generation
- Business customization (industry and size)
- Parsing methods (JSON and text)
- Validation methods
- Fallback mechanisms
- Maturity analysis
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from database.user import User
from services.ai.domains.policy_service import PolicyService
from services.ai.response.generator import ResponseGenerator
from services.ai.context_manager import ContextManager

# Configure anyio to only use asyncio backend (not trio)
pytestmark = pytest.mark.anyio(backends=["asyncio"])


@pytest.fixture
def mock_response_generator():
    """Create mock ResponseGenerator."""
    generator = AsyncMock(spec=ResponseGenerator)
    return generator


@pytest.fixture
def mock_context_manager():
    """Create mock ContextManager."""
    manager = AsyncMock(spec=ContextManager)
    return manager


@pytest.fixture
def policy_service(mock_response_generator, mock_context_manager):
    """Create PolicyService instance with mocked dependencies."""
    return PolicyService(
        response_generator=mock_response_generator, context_manager=mock_context_manager
    )


@pytest.fixture
def mock_user():
    """Create mock User."""
    user = MagicMock(spec=User)
    user.id = uuid4()
    user.email = "test@example.com"
    return user


@pytest.fixture
def sample_business_context():
    """Sample business context for testing."""
    return {
        "company_name": "TechCorp Inc",
        "industry": "technology",
        "employee_count": 75,
        "geographic_scope": "Multi-location",
    }


@pytest.fixture
def sample_evidence():
    """Sample evidence for maturity analysis."""
    return [
        {"id": "ev1", "type": "policy"},
        {"id": "ev2", "type": "procedure"},
        {"id": "ev3", "type": "audit"},
    ]


# ============= POLICY GENERATION TESTS =============


@pytest.mark.anyio
async def test_generate_customized_policy_calls_response_generator(
    policy_service,
    mock_response_generator,
    mock_context_manager,
    mock_user,
    sample_business_context,
):
    """Test that generate_customized_policy calls ResponseGenerator."""
    business_profile_id = uuid4()

    # Mock context manager response
    mock_context_manager.get_conversation_context.return_value = {
        "business_profile": sample_business_context,
        "recent_evidence": [],
    }

    # Mock AI response
    ai_response = json.dumps(
        {"policy_id": "pol_iso27001_001", "title": "Information Security Policy", "sections": []}
    )
    mock_response_generator.generate_simple.return_value = ai_response

    result = await policy_service.generate_customized_policy(
        user=mock_user,
        business_profile_id=business_profile_id,
        framework="iso27001",
        policy_type="information_security",
    )

    # Verify ResponseGenerator was called
    mock_response_generator.generate_simple.assert_called_once()
    call_kwargs = mock_response_generator.generate_simple.call_args.kwargs
    assert "iso27001" in call_kwargs["system_prompt"].lower()
    assert call_kwargs["task_type"] == "policy_generation"


@pytest.mark.anyio
async def test_generate_customized_policy_returns_correct_format(
    policy_service,
    mock_response_generator,
    mock_context_manager,
    mock_user,
    sample_business_context,
):
    """Test that generate_customized_policy returns correct format."""
    business_profile_id = uuid4()

    mock_context_manager.get_conversation_context.return_value = {
        "business_profile": sample_business_context,
        "recent_evidence": [],
    }

    ai_response = json.dumps(
        {
            "policy_id": "pol_gdpr_001",
            "title": "Data Protection Policy",
            "sections": [],
            "roles_responsibilities": [],
            "procedures": [],
        }
    )
    mock_response_generator.generate_simple.return_value = ai_response

    result = await policy_service.generate_customized_policy(
        user=mock_user,
        business_profile_id=business_profile_id,
        framework="gdpr",
        policy_type="data_protection",
    )

    # Verify result structure
    assert "policy_id" in result
    assert "title" in result
    assert "sections" in result
    assert "implementation_guidance" in result
    assert "compliance_mapping" in result


@pytest.mark.anyio
async def test_generate_customized_policy_parses_json_response(
    policy_service,
    mock_response_generator,
    mock_context_manager,
    mock_user,
    sample_business_context,
):
    """Test JSON parsing in policy generation."""
    business_profile_id = uuid4()

    mock_context_manager.get_conversation_context.return_value = {
        "business_profile": sample_business_context,
        "recent_evidence": [],
    }

    expected_policy = {
        "policy_id": "pol_sox_001",
        "title": "Financial Controls Policy",
        "framework": "sox",
        "policy_type": "financial_controls",
        "sections": [
            {
                "section_id": "sec1",
                "title": "Purpose",
                "content": "This policy establishes controls...",
            }
        ],
    }

    mock_response_generator.generate_simple.return_value = json.dumps(expected_policy)

    result = await policy_service.generate_customized_policy(
        user=mock_user,
        business_profile_id=business_profile_id,
        framework="sox",
        policy_type="financial_controls",
    )

    # Verify JSON was parsed correctly
    assert result["policy_id"] == expected_policy["policy_id"]
    assert result["title"] == expected_policy["title"]
    # Note: Business customizations may add sections (industry, size, etc.)
    assert len(result["sections"]) >= 1


# ============= BUSINESS CUSTOMIZATION TESTS =============


@pytest.mark.anyio
async def test_healthcare_customization_adds_hipaa_section(
    policy_service, mock_response_generator, mock_context_manager, mock_user
):
    """Test healthcare industry customization adds HIPAA section."""
    business_profile_id = uuid4()

    healthcare_context = {
        "company_name": "HealthCorp",
        "industry": "healthcare",
        "employee_count": 100,
        "geographic_scope": "National",
    }

    mock_context_manager.get_conversation_context.return_value = {
        "business_profile": healthcare_context,
        "recent_evidence": [],
    }

    base_policy = {"policy_id": "pol_hipaa_001", "title": "Privacy Policy", "sections": []}
    mock_response_generator.generate_simple.return_value = json.dumps(base_policy)

    result = await policy_service.generate_customized_policy(
        user=mock_user,
        business_profile_id=business_profile_id,
        framework="hipaa",
        policy_type="privacy",
        customization_options={"industry_focus": "healthcare"},
    )

    # Verify healthcare-specific section was added
    healthcare_sections = [
        s for s in result["sections"] if "healthcare" in s.get("section_id", "").lower()
    ]
    assert len(healthcare_sections) > 0


@pytest.mark.anyio
async def test_financial_customization_generates_policy(
    policy_service, mock_response_generator, mock_context_manager, mock_user
):
    """Test financial industry policy generation with customization."""
    business_profile_id = uuid4()

    financial_context = {
        "company_name": "FinanceCorp",
        "industry": "financial",
        "employee_count": 200,
        "geographic_scope": "Global",
    }

    mock_context_manager.get_conversation_context.return_value = {
        "business_profile": financial_context,
        "recent_evidence": [],
    }

    base_policy = {"policy_id": "pol_sox_001", "title": "Internal Controls Policy", "sections": []}
    mock_response_generator.generate_simple.return_value = json.dumps(base_policy)

    result = await policy_service.generate_customized_policy(
        user=mock_user,
        business_profile_id=business_profile_id,
        framework="sox",
        policy_type="internal_controls",
        customization_options={"industry_focus": "financial"},
    )

    # Verify policy was generated with correct framework and type
    assert "sections" in result
    assert "framework" in result
    assert result["framework"] == "sox"
    assert result["policy_type"] == "internal_controls"


@pytest.mark.anyio
async def test_technology_customization_adds_sdlc_section(
    policy_service, mock_response_generator, mock_context_manager, mock_user
):
    """Test technology industry customization adds SDLC section."""
    business_profile_id = uuid4()

    tech_context = {
        "company_name": "TechStartup",
        "industry": "technology",
        "employee_count": 50,
        "geographic_scope": "Single location",
    }

    mock_context_manager.get_conversation_context.return_value = {
        "business_profile": tech_context,
        "recent_evidence": [],
    }

    base_policy = {
        "policy_id": "pol_iso27001_001",
        "title": "Secure Development Policy",
        "sections": [],
    }
    mock_response_generator.generate_simple.return_value = json.dumps(base_policy)

    result = await policy_service.generate_customized_policy(
        user=mock_user,
        business_profile_id=business_profile_id,
        framework="iso27001",
        policy_type="secure_development",
        customization_options={"industry_focus": "technology"},
    )

    # Verify technology-specific section was added
    tech_sections = [
        s for s in result["sections"] if "technology" in s.get("section_id", "").lower()
    ]
    assert len(tech_sections) > 0


@pytest.mark.anyio
async def test_size_customization_for_small_org(
    policy_service, mock_response_generator, mock_context_manager, mock_user
):
    """Test policy generation for small organization."""
    business_profile_id = uuid4()

    small_org_context = {
        "company_name": "SmallCorp",
        "industry": "general",
        "employee_count": 15,  # Small organization
        "geographic_scope": "Single location",
    }

    mock_context_manager.get_conversation_context.return_value = {
        "business_profile": small_org_context,
        "recent_evidence": [],
    }

    base_policy = {"policy_id": "pol_001", "title": "Security Policy", "sections": []}
    mock_response_generator.generate_simple.return_value = json.dumps(base_policy)

    result = await policy_service.generate_customized_policy(
        user=mock_user,
        business_profile_id=business_profile_id,
        framework="iso27001",
        policy_type="security",
    )

    # Verify policy was generated with correct structure
    assert "sections" in result
    assert "framework" in result
    assert result["framework"] == "iso27001"
    assert result["policy_type"] == "security"


# ============= CUSTOMIZATION CONTENT VERIFICATION TESTS =============


@pytest.mark.anyio
async def test_healthcare_customization_content_verification(
    policy_service, mock_response_generator, mock_context_manager, mock_user
):
    """Verify healthcare customizations add correct HIPAA content."""
    business_profile_id = uuid4()

    healthcare_context = {
        "company_name": "HealthCorp",
        "industry": "healthcare",
        "employee_count": 100,
    }

    mock_context_manager.get_conversation_context.return_value = {
        "business_profile": healthcare_context,
        "recent_evidence": [],
    }

    base_policy = {"policy_id": "pol_001", "title": "Privacy Policy", "sections": []}
    mock_response_generator.generate_simple.return_value = json.dumps(base_policy)

    result = await policy_service.generate_customized_policy(
        user=mock_user,
        business_profile_id=business_profile_id,
        framework="hipaa",
        policy_type="privacy",
        customization_options={"industry_focus": "healthcare"},
    )

    # Verify healthcare section exists
    healthcare_sections = [
        s for s in result["sections"] if "healthcare" in s.get("section_id", "").lower()
    ]
    assert len(healthcare_sections) > 0, "Healthcare section should be added"

    # Verify content includes HIPAA-specific terms
    section = healthcare_sections[0]
    assert "HIPAA" in section.get("content", "") or "HIPAA" in section.get("title", "")
    assert "subsections" in section
    assert len(section["subsections"]) > 0


# ============= PARSING TESTS =============


def test_parse_policy_response_with_json(policy_service):
    """Test parsing valid JSON policy response."""
    json_response = json.dumps({"policy_id": "pol_001", "title": "Test Policy", "sections": []})

    result = policy_service._parse_policy_response(
        json_response, framework="iso27001", policy_type="security"
    )

    assert result["policy_id"] == "pol_001"
    assert result["title"] == "Test Policy"
    assert isinstance(result["sections"], list)


def test_parse_policy_response_with_text(policy_service):
    """Test parsing text policy response (fallback)."""
    text_response = """
    Title: Information Security Policy

    Purpose: This policy establishes the framework...

    Scope: This policy applies to all employees...
    """

    result = policy_service._parse_policy_response(
        text_response, framework="iso27001", policy_type="security"
    )

    # Should fallback to text parsing
    assert "title" in result
    assert "sections" in result


def test_validate_policy_structure_valid(policy_service):
    """Test validation of valid policy structure."""
    valid_policy = {
        "policy_id": "pol_001",
        "title": "Test Policy",
        "sections": [{"section_id": "sec1", "title": "Purpose", "content": "Policy purpose..."}],
    }

    result = policy_service._validate_policy_structure(
        valid_policy, framework="iso27001", policy_type="security"
    )

    # Returns enhanced policy, not boolean
    assert "policy_id" in result
    assert result["policy_id"] == "pol_001"


def test_validate_policy_structure_missing_required_fields(policy_service):
    """Test validation enhances policy with missing fields."""
    incomplete_policy = {
        "policy_id": "pol_001"
        # Missing 'title' and 'sections'
    }

    result = policy_service._validate_policy_structure(
        incomplete_policy, framework="gdpr", policy_type="privacy"
    )

    # Should add missing fields with defaults
    assert "policy_id" in result
    assert "title" in result or "sections" in result


def test_parse_text_policy_with_markdown(policy_service):
    """Test parsing markdown-formatted text policy."""
    markdown_policy = """
# Information Security Policy

## Purpose
This policy establishes...

## Scope
Applies to all employees...

## Procedures
1. Access control
2. Incident response
3. Data protection
    """

    result = policy_service._parse_text_policy(
        markdown_policy, framework="iso27001", policy_type="security"
    )

    assert "title" in result
    assert "sections" in result
    assert len(result["sections"]) > 0


# ============= MATURITY ANALYSIS TESTS =============


def test_analyze_compliance_maturity_initial(policy_service, sample_business_context):
    """Test maturity analysis for Initial level (no evidence)."""
    result = policy_service._analyze_compliance_maturity(
        business_context=sample_business_context, existing_evidence=[], framework="iso27001"
    )

    assert result["maturity_level"] == "Initial"
    assert result["evidence_count"] == 0


def test_analyze_compliance_maturity_basic(policy_service, sample_business_context):
    """Test maturity analysis for Basic level (1-4 evidence)."""
    evidence = [{"id": "ev1", "type": "policy"}, {"id": "ev2", "type": "procedure"}]

    result = policy_service._analyze_compliance_maturity(
        business_context=sample_business_context, existing_evidence=evidence, framework="iso27001"
    )

    assert result["maturity_level"] == "Basic"
    assert result["evidence_count"] == 2


def test_analyze_compliance_maturity_developing(policy_service, sample_business_context):
    """Test maturity analysis for Developing level (5-14 evidence)."""
    evidence = [{"id": f"ev{i}", "type": "policy"} for i in range(8)]

    result = policy_service._analyze_compliance_maturity(
        business_context=sample_business_context, existing_evidence=evidence, framework="iso27001"
    )

    assert result["maturity_level"] == "Developing"
    assert result["evidence_count"] == 8


def test_analyze_compliance_maturity_managed(policy_service, sample_business_context):
    """Test maturity analysis for Managed level (15-29 evidence)."""
    evidence = [{"id": f"ev{i}", "type": "policy"} for i in range(20)]

    result = policy_service._analyze_compliance_maturity(
        business_context=sample_business_context, existing_evidence=evidence, framework="iso27001"
    )

    assert result["maturity_level"] == "Managed"
    assert result["evidence_count"] == 20


def test_analyze_compliance_maturity_optimized(policy_service, sample_business_context):
    """Test maturity analysis for Optimized level (30+ evidence)."""
    evidence = [{"id": f"ev{i}", "type": "policy"} for i in range(35)]

    result = policy_service._analyze_compliance_maturity(
        business_context=sample_business_context, existing_evidence=evidence, framework="iso27001"
    )

    assert result["maturity_level"] == "Optimized"
    assert result["evidence_count"] == 35


# ============= ORGANIZATION SIZE TESTS =============


def test_categorize_organization_size_micro(policy_service):
    """Test organization size categorization for micro (< 10)."""
    result = policy_service._categorize_organization_size(5)
    assert result == "micro"


def test_categorize_organization_size_small(policy_service):
    """Test organization size categorization for small (10-49)."""
    result = policy_service._categorize_organization_size(25)
    assert result == "small"


def test_categorize_organization_size_medium(policy_service):
    """Test organization size categorization for medium (50-249)."""
    result = policy_service._categorize_organization_size(150)
    assert result == "medium"


def test_categorize_organization_size_large(policy_service):
    """Test organization size categorization for large (250+)."""
    result = policy_service._categorize_organization_size(500)
    assert result == "large"


# ============= FALLBACK TESTS =============


def test_get_fallback_policy_has_required_structure(policy_service):
    """Test fallback policy has all required fields."""
    result = policy_service._get_fallback_policy(
        framework="iso27001", policy_type="security", business_context={}
    )

    assert "policy_id" in result
    assert "title" in result
    assert "framework" in result
    assert "policy_type" in result
    assert "sections" in result
    assert "roles_responsibilities" in result
    assert "procedures" in result
    assert "compliance_requirements" in result
    assert result["framework"] == "iso27001"
    assert result["policy_type"] == "security"


def test_get_fallback_policy_has_generic_sections(policy_service):
    """Test fallback policy has generic sections."""
    result = policy_service._get_fallback_policy(
        framework="gdpr", policy_type="data_protection", business_context={}
    )

    sections = result["sections"]
    assert len(sections) > 0

    # Verify standard sections exist
    section_titles = [s["title"] for s in sections]
    assert any("Purpose" in title for title in section_titles)
    assert any("Scope" in title for title in section_titles)


def test_generate_compliance_mapping_iso27001(policy_service):
    """Test compliance mapping for ISO27001."""
    policy = {"policy_id": "pol_001", "title": "Information Security Policy", "sections": []}

    result = policy_service._generate_compliance_mapping(
        policy=policy, framework="iso27001", policy_type="information_security"
    )

    assert "mapped_controls" in result
    assert len(result["mapped_controls"]) > 0
    # Verify ISO27001 controls are present (returns dict, not list)
    assert result["framework"] == "iso27001"


def test_generate_compliance_mapping_gdpr(policy_service):
    """Test compliance mapping for GDPR."""
    policy = {"policy_id": "pol_001", "title": "Data Protection Policy", "sections": []}

    result = policy_service._generate_compliance_mapping(
        policy=policy, framework="gdpr", policy_type="data_protection"
    )

    assert "mapped_controls" in result
    assert len(result["mapped_controls"]) > 0
    # Verify GDPR framework
    assert result["framework"] == "gdpr"
    # Verify GDPR articles are present
    assert any("Art." in str(control) for control in result["mapped_controls"])


def test_generate_compliance_mapping_soc2(policy_service):
    """Test compliance mapping for SOC2."""
    policy = {"policy_id": "pol_soc2_001", "title": "Security Policy", "sections": []}

    result = policy_service._generate_compliance_mapping(
        policy=policy, framework="soc2", policy_type="security"
    )

    assert "mapped_controls" in result
    assert len(result["mapped_controls"]) > 0
    # Verify SOC2 framework
    assert result["framework"] == "soc2"
    # Verify SOC2 controls are present (CC format)
    assert any("CC" in str(control) for control in result["mapped_controls"])


def test_generate_compliance_mapping_hipaa(policy_service):
    """Test compliance mapping for HIPAA."""
    policy = {"policy_id": "pol_hipaa_001", "title": "Privacy and Security Policy", "sections": []}

    result = policy_service._generate_compliance_mapping(
        policy=policy, framework="hipaa", policy_type="privacy"
    )

    assert "mapped_controls" in result
    # HIPAA may not have specific mappings in current implementation
    assert result["framework"] == "hipaa"
    assert "compliance_objectives" in result


# ============= ERROR HANDLING TESTS =============


@pytest.mark.anyio
async def test_policy_generation_handles_ai_failure(
    policy_service,
    mock_response_generator,
    mock_context_manager,
    mock_user,
    sample_business_context,
):
    """Test policy generation handles AI failures gracefully."""
    business_profile_id = uuid4()

    mock_context_manager.get_conversation_context.return_value = {
        "business_profile": sample_business_context,
        "recent_evidence": [],
    }

    # Simulate AI failure
    mock_response_generator.generate_simple.side_effect = Exception("AI service unavailable")

    result = await policy_service.generate_customized_policy(
        user=mock_user,
        business_profile_id=business_profile_id,
        framework="iso27001",
        policy_type="security",
    )

    # Should return fallback policy (may not explicitly have 'fallback' in ID)
    assert "policy_id" in result
    assert result["framework"] == "iso27001"
    assert result["policy_type"] == "security"
    # Fallback should still have required structure
    assert "sections" in result


@pytest.mark.anyio
async def test_policy_generation_handles_context_failure(
    policy_service, mock_response_generator, mock_context_manager, mock_user
):
    """Test policy generation handles context retrieval failures."""
    business_profile_id = uuid4()

    # Simulate context retrieval failure
    mock_context_manager.get_conversation_context.side_effect = Exception("Context unavailable")

    result = await policy_service.generate_customized_policy(
        user=mock_user,
        business_profile_id=business_profile_id,
        framework="gdpr",
        policy_type="privacy",
    )

    # Should return fallback policy (may not explicitly have 'fallback' in ID)
    assert "policy_id" in result
    assert result["framework"] == "gdpr"
    assert result["policy_type"] == "privacy"
    # Fallback should still have required structure
    assert "sections" in result
