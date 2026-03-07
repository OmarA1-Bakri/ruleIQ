"""
Test IQ Agent integration with enhanced Neo4j compliance data.
"""

import asyncio
import os
from dotenv import load_dotenv
import logging
from services.ai.iq_neo4j_integration import IQNeo4jIntegration
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
load_dotenv()


async def test_iq_neo4j_integration():
    """Test the IQ Neo4j integration with real compliance data."""
    neo4j_uri = "bolt://localhost:7688"
    neo4j_user = "neo4j"
    neo4j_password = "ruleiq123"
    integration = IQNeo4jIntegration(neo4j_uri, neo4j_user, neo4j_password)
    try:
        logger.info("\n" + "=" * 60)
        logger.info("TEST 1: Risk Assessment for Fintech Company")
        logger.info("=" * 60)
        fintech_profile = {
            "industry": "finance",
            "sub_industry": "fintech",
            "country": "UK",
            "processes_payments": True,
            "stores_customer_data": True,
            "has_eu_customers": True,
            "has_us_customers": True,
            "annual_revenue": 25000000,
            "employee_count": 100,
            "certifications": ["ISO27001"],
        }
        risk_assessment = await integration.assess_compliance_risk(fintech_profile)
        logger.info("\n📊 Risk Assessment Results:")
        logger.info("  Total Regulations: %s" % risk_assessment["total_regulations"])
        logger.info("  Average Risk Score: %s" % risk_assessment["average_risk_score"])
        logger.info("  High Risk Count: %s" % risk_assessment["high_risk_count"])
        logger.info("  Risk Level: %s" % risk_assessment["risk_level"])
        logger.info("  Automation Potential: %s" % risk_assessment["automation_potential"])
        logger.info(
            "  Estimated Timeline: %s months" % risk_assessment["estimated_implementation_months"]
        )
        if risk_assessment["critical_regulations"]:
            logger.info("\n🔴 Critical Regulations:")
            for reg in risk_assessment["critical_regulations"][:5]:
                logger.info(
                    "    - %s (Risk: %s)" % (reg["title"], reg["risk"]),
                )
        if risk_assessment["top_controls"]:
            logger.info("\n🛡️ Top Recommended Controls:")
            for control in risk_assessment["top_controls"][:5]:
                logger.info("    - %s" % control)
        logger.info("\n" + "=" * 60)
        logger.info("TEST 2: Compliance Roadmap Generation")
        logger.info("=" * 60)
        roadmap = await integration.get_compliance_roadmap(fintech_profile)
        logger.info("\n📋 Compliance Roadmap (%s items):" % len(roadmap))
        current_phase = None
        for item in roadmap[:10]:
            if item["phase"] != current_phase:
                current_phase = item["phase"]
                logger.info("\n  %s:" % current_phase)
            logger.info("    • %s" % item["title"])
            logger.info("      Risk: %s, Timeline: %s" % (item["risk_score"], item["timeline"]))
            logger.info("      Reason: %s" % item["reason"])
        logger.info("\n" + "=" * 60)
        logger.info("TEST 3: Control Overlap Analysis")
        logger.info("=" * 60)
        top_reg_ids = [reg["id"] for reg in risk_assessment["applicable_regulations"][:10]]
        if top_reg_ids:
            overlaps = await integration.find_control_overlaps(top_reg_ids)
            logger.info("\n🔄 Control Overlap Analysis:")
            logger.info("  Total Unique Controls: %s" % overlaps["total_unique_controls"])
            logger.info("  Overlapping Controls: %s" % overlaps["overlapping_control_count"])
            logger.info("  Efficiency Gain: %s%" % overlaps["efficiency_gain_percentage"])
            if overlaps["overlapping_controls"]:
                logger.info("\n  Top Overlapping Controls:")
                for control in overlaps["overlapping_controls"][:5]:
                    logger.info(
                        "    • %s (covers %s regulations)"
                        % (control["control"], control["regulation_count"])
                    )
        logger.info("\n" + "=" * 60)
        logger.info("TEST 4: Enforcement Pattern Analysis")
        logger.info("=" * 60)
        enforcement = await integration.analyze_enforcement_patterns("finance", 365)
        logger.info("\n⚖️ Enforcement Analysis for Finance Industry:")
        logger.info("  Total Industry Penalties: $%s" % enforcement["total_industry_penalties"])
        if enforcement["trending_violations"]:
            logger.info("\n  Trending Violations:")
            for violation in enforcement["trending_violations"]:
                logger.info("    • %s" % violation)
        if enforcement["high_risk_areas"]:
            logger.info("\n  High Risk Areas:")
            for area in enforcement["high_risk_areas"][:3]:
                logger.info("    • %s" % area["regulation"])
                logger.info(
                    "      Cases: %s, Total Penalties: $%s"
                    % (area["enforcement_count"], area["total_penalties"])
                )
        logger.info("\n" + "=" * 60)
        logger.info("TEST 5: Automation Opportunities")
        logger.info("=" * 60)
        if top_reg_ids:
            automation = await integration.get_automation_opportunities(top_reg_ids)
            logger.info("\n🤖 Automation Analysis:")
            logger.info(
                "  Average Automation Potential: %s" % automation["average_automation_potential"]
            )
            logger.info(
                "  High Automation Candidates: %s" % len(automation["high_automation_candidates"])
            )
            efficiency = automation["estimated_efficiency_gain"]
            logger.info("\n  Estimated Efficiency Gains:")
            logger.info(
                "    • Hours Saved Annually: %s" % efficiency["estimated_hours_saved_annually"]
            )
            logger.info("    • Cost Savings: %s" % efficiency["estimated_cost_savings"])
            logger.info("    • Efficiency Improvement: %s" % efficiency["efficiency_improvement"])
            if automation["implementation_roadmap"]:
                logger.info("\n  Automation Roadmap:")
                for phase in automation["implementation_roadmap"]:
                    logger.info("    %s (%s):" % (phase["phase"], phase["timeline"]))
                    logger.info(
                        "      Items: %s, Impact: %s"
                        % (len(phase["items"]), phase["expected_impact"])
                    )
        logger.info("\n" + "=" * 60)
        logger.info("TEST 6: Healthcare Company Assessment")
        logger.info("=" * 60)
        healthcare_profile = {
            "industry": "healthcare",
            "country": "UK",
            "processes_payments": False,
            "stores_customer_data": True,
            "has_eu_customers": True,
            "annual_revenue": 50000000,
            "employee_count": 250,
            "handles_health_data": True,
        }
        health_assessment = await integration.assess_compliance_risk(healthcare_profile)
        logger.info("\n🏥 Healthcare Risk Assessment:")
        logger.info("  Total Regulations: %s" % health_assessment["total_regulations"])
        logger.info("  Risk Level: %s" % health_assessment["risk_level"])
        logger.info("  High Risk Count: %s" % health_assessment["high_risk_count"])
        logger.info("\n" + "=" * 60)
        logger.info("✅ ALL INTEGRATION TESTS COMPLETED SUCCESSFULLY")
        logger.info("=" * 60)
    except Exception as e:
        logger.error("Test failed: %s" % e)
        import traceback

        traceback.print_exc()
    finally:
        await integration.close()


if __name__ == "__main__":
    asyncio.run(test_iq_neo4j_integration())
