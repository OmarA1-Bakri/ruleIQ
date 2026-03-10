#!/usr/bin/env python3
"""
Load FCA Consumer Duty StructuredObligation nodes into Neo4j.

Creates the UKRegulation node for FCA Consumer Duty (PS22/9, effective July 2023)
and populates it with 24 StructuredObligation nodes covering:
  - Principle 12 (the overarching Consumer Duty principle)
  - 3 Cross-cutting rules
  - 4 Outcomes with sub-requirements

Each obligation is linked to:
  - The UKRegulation node via MANDATED_BY
  - The UK Jurisdiction node via ENFORCED_IN
"""

import asyncio
import sys
from pathlib import Path
from typing import Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from neo4j import AsyncGraphDatabase


NEO4J_URI = "bolt://localhost:17687"
NEO4J_AUTH = ("neo4j", "testpassword123")

CONSUMER_DUTY_REGULATION = {
    "name": "FCA Consumer Duty",
    "full_title": "FCA Consumer Duty (PS22/9) - A New Consumer Duty",
    "reference": "PS22/9, FG22/5",
    "effective_date": "2023-07-31",
    "authority": "Financial Conduct Authority",
    "description": (
        "The Consumer Duty sets higher and clearer standards of consumer protection "
        "across financial services and requires firms to put their customers' needs first. "
        "It introduces a new Principle 12 requiring firms to act to deliver good outcomes "
        "for retail customers, supported by cross-cutting rules and four outcome areas."
    ),
    "handbook_sections": [
        "PRIN 2A (The Consumer Duty)",
        "PROD (Product Intervention and Product Governance)",
        "FEES (Fees Manual)",
    ],
}

# ---------------------------------------------------------------------------
# 24 Consumer Duty StructuredObligation definitions
# ---------------------------------------------------------------------------
OBLIGATIONS: list[dict[str, Any]] = [
    # ===== PRINCIPLE 12 (the overarching principle) =====
    {
        "id": "FCA_Consumer_Duty_Principle12_OBL_001",
        "obligation_id": "OBL-001",
        "description": (
            "Principle 12: A firm must act to deliver good outcomes for retail customers. "
            "This is the overarching principle of the Consumer Duty and applies to all "
            "FCA-regulated firms providing products and services to retail customers."
        ),
        "requirement_type": "mandatory",
        "applicable_to": ["FCA-regulated firms", "retail financial services"],
        "controls": [
            "Board-level Consumer Duty champion appointed",
            "Annual Consumer Duty outcomes assessment",
            "Consumer Duty implementation plan with milestones",
            "Regular MI reporting on customer outcomes",
        ],
        "penalties": (
            "FCA enforcement powers include public censure, financial penalties (unlimited), "
            "variation or cancellation of permissions, and consumer redress schemes under "
            "s404 FSMA 2000."
        ),
    },
    {
        "id": "FCA_Consumer_Duty_Principle12_OBL_002",
        "obligation_id": "OBL-002",
        "description": (
            "Firms must consider the needs, characteristics, and objectives of their "
            "customers, including those with characteristics of vulnerability, at every "
            "stage of the product or service lifecycle."
        ),
        "requirement_type": "mandatory",
        "applicable_to": ["FCA-regulated firms", "retail financial services"],
        "controls": [
            "Customer segmentation and vulnerability assessment framework",
            "Target market identification and monitoring procedures",
            "Product lifecycle governance framework",
        ],
        "penalties": (
            "FCA enforcement powers include public censure, financial penalties (unlimited), "
            "variation or cancellation of permissions, and consumer redress schemes."
        ),
    },
    {
        "id": "FCA_Consumer_Duty_Principle12_OBL_003",
        "obligation_id": "OBL-003",
        "description": (
            "The governing body of a firm (such as the board) must review and approve "
            "an assessment of whether the firm is delivering good outcomes for its "
            "customers that are consistent with the Consumer Duty at least annually."
        ),
        "requirement_type": "mandatory",
        "applicable_to": ["FCA-regulated firms", "retail financial services"],
        "controls": [
            "Annual board-level Consumer Duty assessment report",
            "Board minutes documenting Consumer Duty review",
            "Remediation action tracking and escalation process",
        ],
        "penalties": (
            "FCA enforcement powers include public censure, financial penalties (unlimited), "
            "and individual accountability under the Senior Managers and Certification Regime."
        ),
    },

    # ===== CROSS-CUTTING RULE 1: ACT IN GOOD FAITH =====
    {
        "id": "FCA_Consumer_Duty_CrossCutting_GoodFaith_OBL_004",
        "obligation_id": "OBL-004",
        "description": (
            "Cross-cutting rule: A firm must act in good faith towards retail customers. "
            "This means firms must not seek to exploit customers' behavioural biases, "
            "lack of knowledge, or characteristics of vulnerability. Firms must act "
            "honestly and with integrity."
        ),
        "requirement_type": "mandatory",
        "applicable_to": ["FCA-regulated firms", "retail financial services"],
        "controls": [
            "Staff conduct standards and training on good faith obligations",
            "Sales practices review and monitoring programme",
            "Complaints root cause analysis linked to good faith assessment",
            "Whistleblowing procedures covering Consumer Duty breaches",
        ],
        "penalties": (
            "FCA enforcement powers include public censure, financial penalties (unlimited), "
            "variation or cancellation of permissions, and consumer redress schemes."
        ),
    },
    {
        "id": "FCA_Consumer_Duty_CrossCutting_GoodFaith_OBL_005",
        "obligation_id": "OBL-005",
        "description": (
            "Firms must not exploit customers' behavioural biases, such as sludge practices "
            "that deter customers from acting in their own interests, or pressure selling "
            "techniques, or unreasonable barriers to switching, cancelling, or making claims."
        ),
        "requirement_type": "mandatory",
        "applicable_to": ["FCA-regulated firms", "retail financial services"],
        "controls": [
            "Customer journey review for sludge practices",
            "Switching and cancellation process assessment",
            "Claims handling timeliness and ease monitoring",
        ],
        "penalties": (
            "FCA enforcement powers include public censure, financial penalties (unlimited), "
            "variation or cancellation of permissions."
        ),
    },

    # ===== CROSS-CUTTING RULE 2: AVOID FORESEEABLE HARM =====
    {
        "id": "FCA_Consumer_Duty_CrossCutting_AvoidHarm_OBL_006",
        "obligation_id": "OBL-006",
        "description": (
            "Cross-cutting rule: A firm must avoid causing foreseeable harm to retail "
            "customers. Firms must act proactively to identify and address risks of "
            "harm to customers before it occurs, not just react to harm after the event."
        ),
        "requirement_type": "mandatory",
        "applicable_to": ["FCA-regulated firms", "retail financial services"],
        "controls": [
            "Foreseeable harm risk assessment framework",
            "Product and service risk of harm register",
            "Proactive customer outcome monitoring and early warning indicators",
            "Incident and near-miss reporting linked to customer harm",
        ],
        "penalties": (
            "FCA enforcement powers include public censure, financial penalties (unlimited), "
            "variation or cancellation of permissions, and consumer redress schemes."
        ),
    },
    {
        "id": "FCA_Consumer_Duty_CrossCutting_AvoidHarm_OBL_007",
        "obligation_id": "OBL-007",
        "description": (
            "Where a firm identifies that its conduct, products, or services are causing "
            "or may cause foreseeable harm to retail customers, it must take appropriate "
            "action promptly to address the issue and remediate affected customers."
        ),
        "requirement_type": "mandatory",
        "applicable_to": ["FCA-regulated firms", "retail financial services"],
        "controls": [
            "Remediation policy and procedures",
            "Affected customer identification and outreach processes",
            "Compensation and redress calculation methodology",
        ],
        "penalties": (
            "FCA enforcement powers include public censure, financial penalties (unlimited), "
            "and consumer redress schemes under s404 FSMA 2000."
        ),
    },

    # ===== CROSS-CUTTING RULE 3: ENABLE/SUPPORT CUSTOMERS =====
    {
        "id": "FCA_Consumer_Duty_CrossCutting_EnableSupport_OBL_008",
        "obligation_id": "OBL-008",
        "description": (
            "Cross-cutting rule: A firm must enable and support retail customers to "
            "pursue their financial objectives. Firms must empower customers to make "
            "good decisions and must not create unreasonable barriers that prevent "
            "customers from acting in their own interests."
        ),
        "requirement_type": "mandatory",
        "applicable_to": ["FCA-regulated firms", "retail financial services"],
        "controls": [
            "Customer empowerment strategy and action plan",
            "Barrier identification and removal programme",
            "Accessibility assessment for all customer touchpoints",
            "Vulnerable customer support framework",
        ],
        "penalties": (
            "FCA enforcement powers include public censure, financial penalties (unlimited), "
            "variation or cancellation of permissions."
        ),
    },
    {
        "id": "FCA_Consumer_Duty_CrossCutting_EnableSupport_OBL_009",
        "obligation_id": "OBL-009",
        "description": (
            "Firms must ensure that the support they provide to customers, including "
            "those with characteristics of vulnerability, enables them to realise the "
            "benefits of the products and services they have purchased and to act in "
            "their own interests."
        ),
        "requirement_type": "mandatory",
        "applicable_to": ["FCA-regulated firms", "retail financial services"],
        "controls": [
            "Vulnerability identification and response procedures",
            "Reasonable adjustments policy for vulnerable customers",
            "Customer benefit realisation monitoring",
        ],
        "penalties": (
            "FCA enforcement powers include public censure, financial penalties (unlimited), "
            "and consumer redress schemes."
        ),
    },

    # ===== OUTCOME 1: PRODUCTS AND SERVICES =====
    {
        "id": "FCA_Consumer_Duty_ProductsServices_OBL_010",
        "obligation_id": "OBL-010",
        "description": (
            "Outcome 1 - Products and Services: Products and services must be designed "
            "to meet the needs, characteristics, and objectives of a specified target "
            "market of customers. Manufacturers must identify a target market at a "
            "sufficiently granular level."
        ),
        "requirement_type": "mandatory",
        "applicable_to": ["FCA-regulated firms", "retail financial services"],
        "controls": [
            "Product governance framework with target market definition",
            "Product approval process with Consumer Duty assessment",
            "Ongoing product review and monitoring procedures",
            "Distribution strategy aligned with target market",
        ],
        "penalties": (
            "FCA enforcement powers include public censure, financial penalties (unlimited), "
            "product intervention powers under FCA PROD rules, and consumer redress schemes."
        ),
    },
    {
        "id": "FCA_Consumer_Duty_ProductsServices_OBL_011",
        "obligation_id": "OBL-011",
        "description": (
            "Manufacturers must carry out appropriate testing of products and services "
            "before bringing them to market, including scenario analysis, to ensure they "
            "will function as expected and deliver good outcomes for customers in the "
            "identified target market."
        ),
        "requirement_type": "mandatory",
        "applicable_to": ["FCA-regulated firms", "retail financial services"],
        "controls": [
            "Pre-launch product testing procedures including scenario analysis",
            "Customer outcome modelling for target market segments",
            "Post-launch monitoring and review schedule",
        ],
        "penalties": (
            "FCA enforcement powers include public censure, financial penalties (unlimited), "
            "and product intervention powers."
        ),
    },
    {
        "id": "FCA_Consumer_Duty_ProductsServices_OBL_012",
        "obligation_id": "OBL-012",
        "description": (
            "Distributors must have in place appropriate distribution arrangements to "
            "ensure products and services are distributed to customers in the identified "
            "target market and must not distribute products outside the target market "
            "without the manufacturer's consent and appropriate safeguards."
        ),
        "requirement_type": "mandatory",
        "applicable_to": ["FCA-regulated firms", "retail financial services"],
        "controls": [
            "Distribution strategy documentation and review",
            "Distributor due diligence and oversight framework",
            "Target market monitoring in distribution channels",
        ],
        "penalties": (
            "FCA enforcement powers include public censure, financial penalties (unlimited), "
            "and variation or cancellation of permissions."
        ),
    },
    {
        "id": "FCA_Consumer_Duty_ProductsServices_OBL_013",
        "obligation_id": "OBL-013",
        "description": (
            "Firms must review products and services on a regular basis to ensure they "
            "continue to offer fair value, meet the needs of the target market, and "
            "deliver good outcomes. Products causing harm must be amended or withdrawn."
        ),
        "requirement_type": "mandatory",
        "applicable_to": ["FCA-regulated firms", "retail financial services"],
        "controls": [
            "Periodic product review schedule and methodology",
            "Product withdrawal and wind-down procedures",
            "Customer impact assessment for product changes",
        ],
        "penalties": (
            "FCA enforcement powers include public censure, financial penalties (unlimited), "
            "and product intervention powers under PROD rules."
        ),
    },

    # ===== OUTCOME 2: PRICE AND VALUE =====
    {
        "id": "FCA_Consumer_Duty_PriceValue_OBL_014",
        "obligation_id": "OBL-014",
        "description": (
            "Outcome 2 - Price and Value: The price of products and services must "
            "represent fair value in the context of the overall benefits provided to "
            "retail customers. Firms must carry out a fair value assessment considering "
            "the nature and quality of the product or service."
        ),
        "requirement_type": "mandatory",
        "applicable_to": ["FCA-regulated firms", "retail financial services"],
        "controls": [
            "Fair value assessment framework covering all products and services",
            "Value assessment methodology with defined criteria",
            "Regular value assessment review and documentation",
            "Pricing governance committee or equivalent oversight",
        ],
        "penalties": (
            "FCA enforcement powers include public censure, financial penalties (unlimited), "
            "product intervention powers, and consumer redress schemes."
        ),
    },
    {
        "id": "FCA_Consumer_Duty_PriceValue_OBL_015",
        "obligation_id": "OBL-015",
        "description": (
            "Manufacturers must assess the relationship between the total price to the "
            "customer (including all charges, fees, and costs in the distribution chain) "
            "and the total benefits that the product or service provides, considering "
            "the needs of the target market."
        ),
        "requirement_type": "mandatory",
        "applicable_to": ["FCA-regulated firms", "retail financial services"],
        "controls": [
            "Total cost of ownership analysis for each product",
            "Distribution chain cost transparency and monitoring",
            "Benchmarking against market comparators",
        ],
        "penalties": (
            "FCA enforcement powers include public censure, financial penalties (unlimited), "
            "and product intervention powers."
        ),
    },
    {
        "id": "FCA_Consumer_Duty_PriceValue_OBL_016",
        "obligation_id": "OBL-016",
        "description": (
            "Firms must identify and address pricing practices that could undermine "
            "fair value, including differential pricing that disadvantages loyal or "
            "long-standing customers without clear justification (the loyalty penalty)."
        ),
        "requirement_type": "mandatory",
        "applicable_to": ["FCA-regulated firms", "retail financial services"],
        "controls": [
            "Differential pricing analysis and justification documentation",
            "Loyalty penalty assessment and monitoring",
            "Customer cohort pricing outcome analysis",
        ],
        "penalties": (
            "FCA enforcement powers include public censure, financial penalties (unlimited), "
            "and consumer redress schemes."
        ),
    },

    # ===== OUTCOME 3: CONSUMER UNDERSTANDING =====
    {
        "id": "FCA_Consumer_Duty_ConsumerUnderstanding_OBL_017",
        "obligation_id": "OBL-017",
        "description": (
            "Outcome 3 - Consumer Understanding: Firms must ensure their communications "
            "equip retail customers with the information they need, at the right time, "
            "to make effective, timely, and properly informed decisions about financial "
            "products and services."
        ),
        "requirement_type": "mandatory",
        "applicable_to": ["FCA-regulated firms", "retail financial services"],
        "controls": [
            "Communications standards and testing framework",
            "Customer understanding monitoring and measurement",
            "Plain language policy for all customer-facing materials",
            "Communication channel appropriateness assessment",
        ],
        "penalties": (
            "FCA enforcement powers include public censure, financial penalties (unlimited), "
            "variation or cancellation of permissions, and consumer redress schemes."
        ),
    },
    {
        "id": "FCA_Consumer_Duty_ConsumerUnderstanding_OBL_018",
        "obligation_id": "OBL-018",
        "description": (
            "Communications must be clear, fair, and not misleading. Key information "
            "must be prominent and must not be obscured by less important information. "
            "Firms must tailor communications to the characteristics of the target "
            "market, including any characteristics of vulnerability."
        ),
        "requirement_type": "mandatory",
        "applicable_to": ["FCA-regulated firms", "retail financial services"],
        "controls": [
            "Financial promotions review and approval process",
            "Key information prominence testing",
            "Tailored communications for vulnerable customer segments",
        ],
        "penalties": (
            "FCA enforcement powers include public censure, financial penalties (unlimited), "
            "and variation or cancellation of permissions."
        ),
    },
    {
        "id": "FCA_Consumer_Duty_ConsumerUnderstanding_OBL_019",
        "obligation_id": "OBL-019",
        "description": (
            "Firms must test and monitor the effectiveness of their communications to "
            "ensure that customers can understand the information provided and use it "
            "to make informed decisions. Where testing reveals that communications are "
            "not effective, firms must adapt them."
        ),
        "requirement_type": "mandatory",
        "applicable_to": ["FCA-regulated firms", "retail financial services"],
        "controls": [
            "Communications effectiveness testing programme (A/B testing, user panels)",
            "Customer comprehension surveys and feedback analysis",
            "Iterative communication design and improvement process",
        ],
        "penalties": (
            "FCA enforcement powers include public censure, financial penalties (unlimited), "
            "and variation or cancellation of permissions."
        ),
    },

    # ===== OUTCOME 4: CONSUMER SUPPORT =====
    {
        "id": "FCA_Consumer_Duty_ConsumerSupport_OBL_020",
        "obligation_id": "OBL-020",
        "description": (
            "Outcome 4 - Consumer Support: Firms must provide a level of support that "
            "meets customers' needs throughout the life of the product or service. "
            "Support must enable customers to realise the benefits of products and "
            "services and act in their own interests."
        ),
        "requirement_type": "mandatory",
        "applicable_to": ["FCA-regulated firms", "retail financial services"],
        "controls": [
            "Customer support standards and service level agreements",
            "Multi-channel support availability assessment",
            "Support quality monitoring and continuous improvement",
            "Post-sale support framework aligned with product lifecycle",
        ],
        "penalties": (
            "FCA enforcement powers include public censure, financial penalties (unlimited), "
            "variation or cancellation of permissions, and consumer redress schemes."
        ),
    },
    {
        "id": "FCA_Consumer_Duty_ConsumerSupport_OBL_021",
        "obligation_id": "OBL-021",
        "description": (
            "Firms must ensure that the level of support provided to customers is "
            "at least as good as the level of support provided during the sales "
            "process. The same friction or barriers must not exist in post-sale "
            "support that do not exist in pre-sale interactions."
        ),
        "requirement_type": "mandatory",
        "applicable_to": ["FCA-regulated firms", "retail financial services"],
        "controls": [
            "Pre-sale vs post-sale support parity assessment",
            "Customer effort score monitoring across touchpoints",
            "Post-sale friction and barrier identification reviews",
        ],
        "penalties": (
            "FCA enforcement powers include public censure, financial penalties (unlimited), "
            "and variation or cancellation of permissions."
        ),
    },
    {
        "id": "FCA_Consumer_Duty_ConsumerSupport_OBL_022",
        "obligation_id": "OBL-022",
        "description": (
            "Firms must not create unreasonable barriers for customers to switch "
            "products, make a claim, make a complaint, cancel a contract, or access "
            "their money. Processes for these actions must be at least as easy as "
            "the process to buy the product or service."
        ),
        "requirement_type": "mandatory",
        "applicable_to": ["FCA-regulated firms", "retail financial services"],
        "controls": [
            "Switching and cancellation ease-of-use assessment",
            "Claims process accessibility and timeliness monitoring",
            "Complaints handling performance standards",
        ],
        "penalties": (
            "FCA enforcement powers include public censure, financial penalties (unlimited), "
            "and consumer redress schemes under s404 FSMA 2000."
        ),
    },
    {
        "id": "FCA_Consumer_Duty_ConsumerSupport_OBL_023",
        "obligation_id": "OBL-023",
        "description": (
            "Firms must ensure they have appropriate support for customers with "
            "characteristics of vulnerability and must make reasonable adjustments "
            "to ensure vulnerable customers can access the same outcomes as other "
            "customers."
        ),
        "requirement_type": "mandatory",
        "applicable_to": ["FCA-regulated firms", "retail financial services"],
        "controls": [
            "Vulnerable customer identification and recording procedures",
            "Reasonable adjustments policy and implementation",
            "Staff training on vulnerability indicators and support",
            "Outcomes monitoring disaggregated by vulnerability status",
        ],
        "penalties": (
            "FCA enforcement powers include public censure, financial penalties (unlimited), "
            "and variation or cancellation of permissions."
        ),
    },

    # ===== MONITORING AND GOVERNANCE =====
    {
        "id": "FCA_Consumer_Duty_Governance_OBL_024",
        "obligation_id": "OBL-024",
        "description": (
            "Firms must monitor customer outcomes across all four outcome areas and "
            "maintain adequate management information (MI) to identify whether retail "
            "customers are receiving good outcomes. Where evidence suggests poor "
            "outcomes, firms must investigate the root causes and take action."
        ),
        "requirement_type": "mandatory",
        "applicable_to": ["FCA-regulated firms", "retail financial services"],
        "controls": [
            "Consumer Duty MI dashboard covering all four outcomes",
            "Outcome metrics definition and threshold setting",
            "Root cause analysis process for poor outcome indicators",
            "Escalation and remediation procedures for identified issues",
        ],
        "penalties": (
            "FCA enforcement powers include public censure, financial penalties (unlimited), "
            "variation or cancellation of permissions, imposition of requirements, "
            "and consumer redress schemes under s404 FSMA 2000."
        ),
    },
]


async def load_consumer_duty_obligations() -> dict[str, int]:
    """
    Create the FCA Consumer Duty UKRegulation node and 24 StructuredObligation
    nodes, linking each to the regulation and the UK Jurisdiction.
    """
    driver = AsyncGraphDatabase.driver(NEO4J_URI, auth=NEO4J_AUTH)
    stats = {"regulation": 0, "obligations_created": 0, "relationships_created": 0}

    try:
        async with driver.session() as session:
            # ------------------------------------------------------------------
            # 1. Ensure the UK Jurisdiction node exists
            # ------------------------------------------------------------------
            await session.run(
                """
                MERGE (uk:Jurisdiction {code: 'UK'})
                SET uk.name = 'United Kingdom'
                """
            )
            print("[1/3] Ensured UK Jurisdiction node exists.")

            # ------------------------------------------------------------------
            # 2. Create the FCA Consumer Duty UKRegulation node
            # ------------------------------------------------------------------
            reg = CONSUMER_DUTY_REGULATION
            await session.run(
                """
                MERGE (r:UKRegulation {name: $name})
                SET r.full_title = $full_title,
                    r.reference = $reference,
                    r.effective_date = $effective_date,
                    r.authority = $authority,
                    r.description = $description,
                    r.handbook_sections = $handbook_sections,
                    r.loaded_at = datetime()
                WITH r
                MATCH (uk:Jurisdiction {code: 'UK'})
                MERGE (r)-[:GOVERNED_BY]->(uk)
                """,
                name=reg["name"],
                full_title=reg["full_title"],
                reference=reg["reference"],
                effective_date=reg["effective_date"],
                authority=reg["authority"],
                description=reg["description"],
                handbook_sections=reg["handbook_sections"],
            )
            stats["regulation"] = 1
            stats["relationships_created"] += 1
            print(f"[2/3] Created UKRegulation node: '{reg['name']}'")

            # ------------------------------------------------------------------
            # 3. Create StructuredObligation nodes and link them
            # ------------------------------------------------------------------
            for obl in OBLIGATIONS:
                await session.run(
                    """
                    MERGE (o:StructuredObligation {id: $id})
                    SET o.obligation_id = $obligation_id,
                        o.description = $description,
                        o.requirement_type = $requirement_type,
                        o.applicable_to = $applicable_to,
                        o.controls = $controls,
                        o.penalties = $penalties,
                        o.created_at = datetime()
                    WITH o
                    MATCH (r:UKRegulation {name: $reg_name})
                    MERGE (o)-[:MANDATED_BY]->(r)
                    WITH o
                    MATCH (uk:Jurisdiction {code: 'UK'})
                    MERGE (o)-[:ENFORCED_IN]->(uk)
                    """,
                    id=obl["id"],
                    obligation_id=obl["obligation_id"],
                    description=obl["description"],
                    requirement_type=obl["requirement_type"],
                    applicable_to=obl["applicable_to"],
                    controls=obl["controls"],
                    penalties=obl["penalties"],
                    reg_name=CONSUMER_DUTY_REGULATION["name"],
                )
                stats["obligations_created"] += 1
                stats["relationships_created"] += 2  # MANDATED_BY + ENFORCED_IN

            print(f"[3/3] Created {stats['obligations_created']} StructuredObligation nodes.")

        # ------------------------------------------------------------------
        # 4. Verification queries
        # ------------------------------------------------------------------
        async with driver.session() as session:
            # Verify regulation node exists
            result = await session.run(
                "MATCH (r:UKRegulation {name: $name}) RETURN r.name as name, r.description as desc",
                name=CONSUMER_DUTY_REGULATION["name"],
            )
            reg_record = await result.single()
            if reg_record:
                print(f"\nVERIFICATION - UKRegulation node: {reg_record['name']}")
            else:
                print("\nERROR - UKRegulation node NOT found!")

            # Count linked obligations
            result2 = await session.run(
                """
                MATCH (o:StructuredObligation)-[:MANDATED_BY]->(r:UKRegulation {name: $name})
                RETURN count(o) as count
                """,
                name=CONSUMER_DUTY_REGULATION["name"],
            )
            count_record = await result2.single()
            print(
                f"VERIFICATION - StructuredObligation nodes linked: "
                f"{count_record['count']}"
            )

            # Count ENFORCED_IN links
            result3 = await session.run(
                """
                MATCH (o:StructuredObligation)-[:MANDATED_BY]->(r:UKRegulation {name: $name})
                MATCH (o)-[:ENFORCED_IN]->(j:Jurisdiction {code: 'UK'})
                RETURN count(o) as count
                """,
                name=CONSUMER_DUTY_REGULATION["name"],
            )
            enforced_record = await result3.single()
            print(
                f"VERIFICATION - Obligations ENFORCED_IN UK: "
                f"{enforced_record['count']}"
            )

            # List all obligation IDs
            result4 = await session.run(
                """
                MATCH (o:StructuredObligation)-[:MANDATED_BY]->(r:UKRegulation {name: $name})
                RETURN o.id as id, o.obligation_id as obl_id,
                       substring(o.description, 0, 80) as desc_preview
                ORDER BY o.id
                """,
                name=CONSUMER_DUTY_REGULATION["name"],
            )
            records = [record async for record in result4]
            print(f"\nAll {len(records)} Consumer Duty obligations:")
            for rec in records:
                print(f"  {rec['id']} ({rec['obl_id']}): {rec['desc_preview']}...")

    finally:
        await driver.close()

    print(f"\nSUMMARY: {stats}")
    return stats


if __name__ == "__main__":
    asyncio.run(load_consumer_duty_obligations())
