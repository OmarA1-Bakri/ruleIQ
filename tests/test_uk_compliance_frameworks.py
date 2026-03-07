"""

# Constants


Test specifications for UK compliance frameworks integration.

Following Agent Operating Protocol: Tests first, implementation after approval.
"""

import pytest
from datetime import datetime
from database.compliance_framework import ComplianceFramework
from services.compliance_loader import UKComplianceLoader
from api.schemas.compliance import UKFrameworkSchema

from tests.test_constants import DEFAULT_LIMIT, HTTP_CREATED, HTTP_OK, MAX_RETRIES


class TestUKComplianceFrameworksLoading:
    """Test suite for loading UK-specific compliance frameworks"""

    @pytest.fixture
    def uk_frameworks_data(self):
        """Sample UK compliance frameworks data for testing"""
        return [
            {
                "name": "ICO_GDPR_UK",
                "display_name": "UK GDPR (ICO Implementation)",
                "description": "Data Protection Act 2018 & UK GDPR requirements as enforced by ICO",
                "category": "Data Protection",
                "applicable_indu": ["all"],
                "employee_thresh": 1,
                "revenue_thresho": "£0+",
                "geographic_scop": ["UK", "England", "Scotland", "Wales", "Northern Ireland"],
                "key_requirement": [
                    "Lawful basis for processing",
                    "Data subject rights",
                    "Data Protection Impact Assessments",
                    "Breach notification (72 hours to ICO)",
                    "Privacy by design",
                ],
                "control_domains": ["Access Control", "Data Minimization", "Consent Management"],
                "evidence_types": ["Policies", "Procedures", "Training Records", "Audit Logs"],
                "complexity_scor": 8,
                "implementation_": 16,
                "estimated_cost_": "£15,000-£75,000",
            },
            {
                "name": "FCA_REGULATORY",
                "display_name": "FCA Regulatory Requirements",
                "description": "Financial Conduct Authority requirements for financial services",
                "category": "Financial Services",
                "applicable_indu": ["financial_services", "fintech", "banking", "insurance"],
                "employee_thresh": 1,
                "revenue_thresho": "£0+",
                "geographic_scop": ["UK"],
                "key_requirement": [
                    "Senior Managers & Certification Regime (SM&CR)",
                    "Customer treatment (TCF)",
                    "Operational resilience",
                    "Financial crime prevention",
                    "Data governance",
                ],
                "complexity_scor": 9,
                "implementation_": 24,
                "estimated_cost_": "£25,000-£150,000",
            },
        ]

    def test_load_uk_frameworks_success(self, uk_frameworks_data):
        """Test successful loading of UK compliance frameworks"""
        loader = UKComplianceLoader()
        result = loader.load_frameworks(uk_frameworks_data)
        assert result.success is True
        assert len(result.loaded_frameworks) == 2
        assert "ICO_GDPR_UK" in [fw.name for fw in result.loaded_frameworks]
        assert "FCA_REGULATORY" in [fw.name for fw in result.loaded_frameworks]

    def test_uk_gdpr_framework_structure(self, uk_frameworks_data):
        """Test UK GDPR framework has correct structure"""
        loader = UKComplianceLoader()
        gdpr_data = uk_frameworks_data[0]
        framework = loader.create_framework(gdpr_data)
        assert framework.name == "ICO_GDPR_UK"
        assert framework.category == "Data Protection"
        assert "UK" in framework.geographic_scop
        assert framework.complexity_scor == 8
        assert "Lawful basis for processing" in framework.key_requirement

    def test_fca_framework_financial_specific(self, uk_frameworks_data):
        """Test FCA framework has financial services specifics"""
        loader = UKComplianceLoader()
        fca_data = uk_frameworks_data[1]
        framework = loader.create_framework(fca_data)
        assert framework.name == "FCA_REGULATORY"
        assert framework.category == "Financial Services"
        assert "fintech" in framework.applicable_indu
        assert framework.complexity_scor == 9
        assert "SM&CR" in str(framework.key_requirement)

    def test_framework_validation_errors(self):
        """Test framework validation catches errors"""
        loader = UKComplianceLoader()
        invalid_data = {"name": "", "category": "Data Protection"}
        with pytest.raises(ValueError, match="Framework name cannot be empty"):
            loader.create_framework(invalid_data)

    def test_duplicate_framework_handling(self, uk_frameworks_data):
        """Test handling of duplicate framework names"""
        loader = UKComplianceLoader()
        result1 = loader.load_frameworks([uk_frameworks_data[0]])
        assert result1.success is True
        result2 = loader.load_frameworks([uk_frameworks_data[0]])
        assert result2.success is True
        assert len(result2.skipped_frameworks) == 1
        assert result2.skipped_frameworks[0] == "ICO_GDPR_UK"


class TestUKFrameworkAPIIntegration:
    """Test API integration for UK frameworks"""

    def test_get_uk_frameworks_endpoint(self, client, db_session):
        """Test GET /api/v1/compliance/frameworks?region=UK"""
        uk_framework = ComplianceFramework(
            name="ICO_GDPR_UK",
            display_name="UK GDPR",
            description="UK implementation",
            category="Data Protection",
            geographic_scop=["UK"],
        )
        db_session.add(uk_framework)
        db_session.commit()
        response = client.get("/api/v1/compliance/frameworks?region=UK")
        assert response.status_code == HTTP_OK
        data = response.json()
        assert len(data["frameworks"]) >= 1
        assert any(fw["name"] == "ICO_GDPR_UK" for fw in data["frameworks"])

    def test_framework_assessment_compatibility(self, client, db_session):
        """Test frameworks work with assessment endpoints"""
        uk_framework = ComplianceFramework(
            name="ICO_GDPR_UK",
            display_name="UK GDPR",
            description="UK implementation",
            category="Data Protection",
            geographic_scop=["UK"],
            key_requirement=["Data Protection", "Consent Management"],
        )
        db_session.add(uk_framework)
        db_session.commit()
        assessment_data = {
            "business_profile_id": "test-profile-id",
            "framework_ids": [str(uk_framework.id)],
            "assessment_type": "initial",
        }
        response = client.post("/api/v1/assessments/", json=assessment_data)
        assert response.status_code == HTTP_CREATED
        assert response.json()["framework_count"] == 1


class TestUKComplianceFrameworksDataIntegrity:
    """Test data integrity and mappings for UK frameworks"""

    def test_iso27001_template_mapping(self):
        """Test ISO 27001 templates map correctly to UK frameworks"""
        from services.iso27001_mapper import ISO27001UKMapper

        mapper = ISO27001UKMapper()
        uk_gdpr_controls = mapper.map_iso_to_uk_gdpr(["A.5.1.1", "A.8.2.1", "A.12.6.1"])
        assert len(uk_gdpr_controls) == MAX_RETRIES
        assert "Data Protection by Design" in uk_gdpr_controls[0]["uk_requirement"]

    def test_framework_versioning(self):
        """Test framework versioning for UK regulatory updates"""
        framework = ComplianceFramework(
            name="ICO_GDPR_UK", version="1.0", description="Initial UK GDPR implementation"
        )
        updated_framework = framework.create_new_version("1.1", "Updated for ICO guidance 2024")
        assert updated_framework.version == "1.1"
        assert "ICO guidance 2024" in updated_framework.description
        assert updated_framework.name == framework.name

    def test_geographic_scope_validation(self):
        """Test geographic scope validation for UK frameworks"""
        from services.geographic_validator import GeographicValidator

        validator = GeographicValidator()
        assert validator.validate_uk_scope(["UK"]) is True
        assert validator.validate_uk_scope(["England", "Scotland"]) is True
        assert validator.validate_uk_scope(["EU", "Germany"]) is False
        assert validator.validate_uk_scope([]) is False


class TestUKFrameworksPerformance:
    """Performance tests for UK frameworks loading"""

    def test_bulk_framework_loading_performance(self, uk_frameworks_data):
        """Test bulk loading performance meets SLA requirements"""
        import time

        loader = UKComplianceLoader()
        bulk_data = uk_frameworks_data * 25
        start_time = time.time()
        result = loader.load_frameworks(bulk_data)
        load_time = time.time() - start_time
        assert load_time < 2.0
        assert result.success is True
        assert len(result.loaded_frameworks) == 50

    def test_framework_query_performance(self, db_session):
        """Test framework queries meet performance SLA"""
        import time

        for i in range(DEFAULT_LIMIT):
            framework = ComplianceFramework(
                name=f"UK_FRAMEWORK_{i}",
                display_name=f"UK Framework {i}",
                description="Test framework",
                category="Test",
                geographic_scop=["UK"],
            )
            db_session.add(framework)
        db_session.commit()
        start_time = time.time()
        frameworks = (
            db_session.query(ComplianceFramework)
            .filter(ComplianceFramework.geographic_scop.contains(["UK"]))
            .all(),
        )
        query_time = time.time() - start_time
        assert query_time < 0.1
        assert len(frameworks) == DEFAULT_LIMIT
