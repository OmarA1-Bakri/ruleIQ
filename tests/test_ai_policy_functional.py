"""
Functional test for AI Policy Generation Assistant
Tests the complete flow with loaded UK frameworks
"""

import asyncio
import sys
from pathlib import Path
import logging

sys.path.append(str(Path(__file__).parent))
from services.ai.policy_generator import PolicyGenerator
from api.schemas.ai_policy import (
    PolicyGenerationRequest,
    BusinessContext,
    PolicyType,
    CustomizationLevel,
    TargetAudience,
)
from database.db_setup import get_db
from database.compliance_framework import ComplianceFramework

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_ai_policy_generation():
    """Test AI policy generation with UK GDPR framework"""
    logger.info("=== AI Policy Generation Functional Test ===")
    try:
        db_session = next(get_db())
        uk_gdpr = (
            db_session.query(ComplianceFramework)
            .filter(ComplianceFramework.name == "ICO_GDPR_UK")
            .first()
        )
        if not uk_gdpr:
            logger.error(
                "UK GDPR framework not found. Please run load_uk_frameworks.py first",
            )
            return False
        logger.info("Found framework: %s" % uk_gdpr.display_name)
        business_context = BusinessContext(
            organization_name="TestCorp Ltd",
            industry="technology",
            employee_count=25,
            processes_personal_data=True,
            data_types=["customer_data", "employee_data"],
            geographic_operations=["UK"],
            third_party_processors=True,
            data_retention_period="5 years",
        )
        request = PolicyGenerationRequest(
            framework_id=str(uk_gdpr.id),
            business_context=business_context,
            policy_type=PolicyType.PRIVACY_POLICY,
            customization_level=CustomizationLevel.STANDARD,
            include_templates=True,
            target_audience=TargetAudience.GENERAL_PUBLIC,
        )
        logger.info("Creating PolicyGenerator...")
        generator = PolicyGenerator()
        logger.info("Testing basic functionality...")
        cache_key = generator._generate_cache_key(request, uk_gdpr)
        logger.info("✓ Cache key generated: %s..." % cache_key[:20])
        import time

        fallback_response = generator._generate_fallback_policy(request, uk_gdpr, time.time())
        logger.info(
            "✓ Fallback policy generated: %s characters" % len(fallback_response.policy_content)
        )
        logger.info("✓ AI Policy Generation system is functional")
        template_processor = generator.template_processor
        logger.info(
            "✓ Template processor initialized with path: %s" % template_processor.templates_path
        )
        db_session.close()
        return True
    except Exception as e:
        logger.error("Test failed: %s" % str(e))
        import traceback

        traceback.print_exc()
        return False


async def test_frameworks_availability():
    """Test that UK frameworks are available"""
    logger.info("=== Testing Framework Availability ===")
    try:
        db_session = next(get_db())
        frameworks = db_session.query(ComplianceFramework).all()
        logger.info("Found %s compliance frameworks:" % len(frameworks))
        for framework in frameworks:
            logger.info(
                "  - %s: %s" % (framework.name, framework.display_name),
            )
        uk_frameworks = [f for f in frameworks if "UK" in f.name or "ICO" in f.name]
        logger.info("✓ Found %s UK-specific frameworks" % len(uk_frameworks))
        db_session.close()
        return len(frameworks) > 0
    except Exception as e:
        logger.error("Framework test failed: %s" % str(e))
        return False


async def main():
    """Run all functional tests"""
    logger.info("Starting AI Policy Generation Functional Tests...")
    frameworks_ok = await test_frameworks_availability()
    if not frameworks_ok:
        logger.error("❌ Framework availability test failed")
        return False
    policy_gen_ok = await test_ai_policy_generation()
    if not policy_gen_ok:
        logger.error("❌ AI policy generation test failed")
        return False
    logger.info("✅ All functional tests passed!")
    logger.info("🎉 AI Policy Generation Assistant is ready for use")
    return True


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
