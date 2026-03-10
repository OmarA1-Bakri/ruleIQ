#!/usr/bin/env python3
"""
Load SMCR (Senior Managers and Certification Regime) StructuredObligation nodes
into Neo4j and link them to the UKRegulation node and UK Jurisdiction.

SMCR is an FCA/PRA regime for UK financial services firms with 3 pillars:
1. Senior Managers Regime
2. Certification Regime
3. Conduct Rules (Individual + Senior Manager)

This script:
- Checks for existing SMCR-related UKRegulation nodes
- Creates one if none exists
- Creates 18 StructuredObligation nodes covering all 3 pillars
- Links obligations via MANDATED_BY to the UKRegulation node
- Links obligations via ENFORCED_IN to the UK Jurisdiction node
"""

import asyncio
import logging
import sys
from typing import Any, Dict, List

from neo4j import AsyncGraphDatabase

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("smcr_loader")

# -- Connection details for local Neo4j --
NEO4J_URI = "bolt://localhost:17687"
NEO4J_USERNAME = "neo4j"
NEO4J_PASSWORD = "testpassword123"
NEO4J_DATABASE = "neo4j"


# ---------------------------------------------------------------------------
# Obligation data
# ---------------------------------------------------------------------------

SMCR_OBLIGATIONS: List[Dict[str, Any]] = [
    # =========================================================================
    # PILLAR 1: Senior Managers Regime (5 obligations)
    # =========================================================================
    {
        "id": "FCA_SMCR_SM1_OBL_001",
        "obligation_id": "OBL-001",
        "pillar": "Senior Managers Regime",
        "description": (
            "Firms must ensure that every person who performs a Senior Management "
            "Function (SMF) has been approved by the FCA and/or PRA before "
            "commencing the role. Applications must include a Statement of "
            "Responsibilities, a scope of responsibilities map, and evidence of "
            "fitness and propriety."
        ),
        "requirement_type": "mandatory",
        "applicable_to": [
            "FCA-regulated firms",
            "PRA-regulated firms",
            "senior managers",
        ],
        "controls": [
            "SMF application and approval process",
            "Pre-appointment due diligence",
            "Fitness and propriety assessment",
            "Regulatory reference checks",
        ],
        "penalties": (
            "FCA/PRA may refuse approval, impose conditions, or take enforcement "
            "action against the firm. Fines are unlimited and the firm may face "
            "public censure."
        ),
    },
    {
        "id": "FCA_SMCR_SM2_OBL_002",
        "obligation_id": "OBL-002",
        "pillar": "Senior Managers Regime",
        "description": (
            "Each approved Senior Manager must have a Statement of Responsibilities "
            "(SoR) that clearly sets out what the senior manager is responsible and "
            "accountable for. The SoR must be kept up to date and submitted to the "
            "FCA/PRA whenever there is a significant change."
        ),
        "requirement_type": "mandatory",
        "applicable_to": [
            "FCA-regulated firms",
            "PRA-regulated firms",
            "senior managers",
        ],
        "controls": [
            "Statements of Responsibilities register",
            "Annual review of SoRs",
            "Change notification process to FCA/PRA",
            "Board-level oversight of SoR allocation",
        ],
        "penalties": (
            "Failure to maintain accurate SoRs may result in enforcement action "
            "against the firm, including unlimited fines, public censure, and "
            "potential withdrawal of the senior manager's approval."
        ),
    },
    {
        "id": "FCA_SMCR_SM3_OBL_003",
        "obligation_id": "OBL-003",
        "pillar": "Senior Managers Regime",
        "description": (
            "Firms must maintain a Management Responsibilities Map (MRM) that "
            "provides a comprehensive picture of the firm's management and "
            "governance arrangements, including clear allocation of all prescribed "
            "responsibilities and overall responsibilities."
        ),
        "requirement_type": "mandatory",
        "applicable_to": [
            "FCA-regulated firms",
            "PRA-regulated firms",
        ],
        "controls": [
            "Management Responsibilities Map document",
            "Annual MRM review and update cycle",
            "Governance committee oversight",
            "Handover procedures for role changes",
        ],
        "penalties": (
            "FCA/PRA may take enforcement action for failure to maintain an "
            "accurate MRM. Penalties include unlimited fines, public censure, "
            "and restrictions on business activities."
        ),
    },
    {
        "id": "FCA_SMCR_SM4_OBL_004",
        "obligation_id": "OBL-004",
        "pillar": "Senior Managers Regime",
        "description": (
            "Under the Duty of Responsibility, if a firm contravenes a relevant "
            "requirement and a Senior Manager was responsible for the area in "
            "which the contravention occurred, the Senior Manager is guilty of "
            "misconduct unless they can demonstrate they took reasonable steps "
            "to prevent the contravention."
        ),
        "requirement_type": "mandatory",
        "applicable_to": [
            "FCA-regulated firms",
            "PRA-regulated firms",
            "senior managers",
        ],
        "controls": [
            "Reasonable steps documentation framework",
            "Decision audit trail and record-keeping",
            "Escalation and whistleblowing procedures",
            "Regular compliance monitoring and reporting",
        ],
        "penalties": (
            "Individual Senior Managers face personal liability including "
            "unlimited fines, prohibition orders banning them from the "
            "financial services industry, and public censure. Criminal "
            "prosecution is possible in serious cases."
        ),
    },
    {
        "id": "FCA_SMCR_SM5_OBL_005",
        "obligation_id": "OBL-005",
        "pillar": "Senior Managers Regime",
        "description": (
            "Firms must allocate all Prescribed Responsibilities (PRs) to "
            "appropriate Senior Managers. PRs include responsibility for the "
            "firm's compliance with SMCR requirements, financial crime prevention, "
            "and ensuring the firm's governing body is informed of its regulatory "
            "obligations. No PR may be left unallocated."
        ),
        "requirement_type": "mandatory",
        "applicable_to": [
            "FCA-regulated firms",
            "PRA-regulated firms",
            "senior managers",
        ],
        "controls": [
            "Prescribed Responsibilities allocation matrix",
            "Gap analysis to ensure no PR is unallocated",
            "Board approval of PR allocations",
            "Regular review of PR assignments on personnel changes",
        ],
        "penalties": (
            "Failure to allocate PRs may result in enforcement action against "
            "the firm including unlimited fines, requirements to take specific "
            "remedial action, and potential restriction of permissions."
        ),
    },
    # =========================================================================
    # PILLAR 2: Certification Regime (5 obligations)
    # =========================================================================
    {
        "id": "FCA_SMCR_CR1_OBL_006",
        "obligation_id": "OBL-006",
        "pillar": "Certification Regime",
        "description": (
            "Firms must identify all staff performing Certification Functions "
            "(significant-harm functions) and assess them as fit and proper "
            "before allowing them to perform the function. This includes roles "
            "such as client-dealing functions, algorithmic trading functions, "
            "and material risk-taker functions."
        ),
        "requirement_type": "mandatory",
        "applicable_to": [
            "FCA-regulated firms",
            "PRA-regulated firms",
            "certification staff",
        ],
        "controls": [
            "Certification Functions role mapping",
            "Initial fit and proper assessment",
            "Criminal records and credit checks",
            "Role-specific competency evaluation",
        ],
        "penalties": (
            "Firms allowing uncertified staff to perform certification functions "
            "face enforcement action including unlimited fines, public censure, "
            "and potential restriction of business permissions."
        ),
    },
    {
        "id": "FCA_SMCR_CR2_OBL_007",
        "obligation_id": "OBL-007",
        "pillar": "Certification Regime",
        "description": (
            "Firms must re-assess the fitness and propriety of all Certification "
            "Function holders at least annually. The annual assessment must "
            "consider the person's honesty, integrity and reputation; competence "
            "and capability; and financial soundness."
        ),
        "requirement_type": "mandatory",
        "applicable_to": [
            "FCA-regulated firms",
            "PRA-regulated firms",
            "certification staff",
        ],
        "controls": [
            "Annual certification assessment process",
            "Fit and proper questionnaire",
            "Performance review integration",
            "Annual certification register update",
        ],
        "penalties": (
            "Failure to conduct annual certifications may lead to enforcement "
            "action against the firm. Staff performing certification functions "
            "without valid certification are in breach of regulatory requirements."
        ),
    },
    {
        "id": "FCA_SMCR_CR3_OBL_008",
        "obligation_id": "OBL-008",
        "pillar": "Certification Regime",
        "description": (
            "Firms must issue certificates to each person they have assessed as "
            "fit and proper to perform a Certification Function. Certificates "
            "are valid for a maximum of 12 months and must not be issued if the "
            "firm is not satisfied the person is fit and proper."
        ),
        "requirement_type": "mandatory",
        "applicable_to": [
            "FCA-regulated firms",
            "PRA-regulated firms",
            "certification staff",
        ],
        "controls": [
            "Certificate issuance workflow",
            "Certificate expiry tracking system",
            "Refusal and revocation procedures",
            "Secure certificate record storage",
        ],
        "penalties": (
            "Issuing certificates without proper assessment or allowing expired "
            "certificates constitutes a regulatory breach. The FCA may impose "
            "unlimited fines and require the firm to cease the relevant activity."
        ),
    },
    {
        "id": "FCA_SMCR_CR4_OBL_009",
        "obligation_id": "OBL-009",
        "pillar": "Certification Regime",
        "description": (
            "Firms must obtain regulatory references from all previous employers "
            "covering at least the last 6 years before appointing anyone to a "
            "Certification Function or Senior Management Function. Firms must "
            "also provide regulatory references when requested by other firms."
        ),
        "requirement_type": "mandatory",
        "applicable_to": [
            "FCA-regulated firms",
            "PRA-regulated firms",
            "certification staff",
            "senior managers",
        ],
        "controls": [
            "Regulatory reference request process",
            "Six-year employment history verification",
            "Regulatory reference provision procedure",
            "Reference record retention for 6 years",
        ],
        "penalties": (
            "Failure to obtain or provide regulatory references may result in "
            "enforcement action. Providing false or misleading references is a "
            "serious breach that can lead to unlimited fines and criminal prosecution."
        ),
    },
    {
        "id": "FCA_SMCR_CR5_OBL_010",
        "obligation_id": "OBL-010",
        "pillar": "Certification Regime",
        "description": (
            "Firms must maintain a directory of certified staff and make it "
            "publicly available. The directory must include each certified "
            "person's name, the certification function they perform, and their "
            "certification status. This directory must be updated within a "
            "reasonable period of any changes."
        ),
        "requirement_type": "mandatory",
        "applicable_to": [
            "FCA-regulated firms",
            "PRA-regulated firms",
        ],
        "controls": [
            "Public certification directory",
            "Directory update workflow",
            "Data accuracy verification checks",
            "Access controls and publication schedule",
        ],
        "penalties": (
            "Failure to maintain or publish the directory may result in "
            "enforcement action including fines and public censure. Inaccurate "
            "directory information undermines market integrity."
        ),
    },
    # =========================================================================
    # PILLAR 3: Conduct Rules -- Individual Conduct Rules (5 obligations)
    # =========================================================================
    {
        "id": "FCA_SMCR_ICR1_OBL_011",
        "obligation_id": "OBL-011",
        "pillar": "Conduct Rules - Individual",
        "description": (
            "Individual Conduct Rule 1: You must act with integrity. All staff "
            "within the scope of SMCR (which includes almost all employees of "
            "FCA-regulated firms) must act honestly, ethically, and with "
            "integrity in all their professional dealings."
        ),
        "requirement_type": "mandatory",
        "applicable_to": [
            "FCA-regulated firms",
            "PRA-regulated firms",
            "senior managers",
            "certification staff",
        ],
        "controls": [
            "Code of conduct and ethics policy",
            "Integrity training programme",
            "Whistleblowing and speak-up policy",
            "Misconduct investigation procedure",
        ],
        "penalties": (
            "Individuals breaching conduct rules face personal enforcement "
            "action including fines, suspension, or prohibition from the "
            "financial services industry. Firms face fines for failing to "
            "ensure staff compliance."
        ),
    },
    {
        "id": "FCA_SMCR_ICR2_OBL_012",
        "obligation_id": "OBL-012",
        "pillar": "Conduct Rules - Individual",
        "description": (
            "Individual Conduct Rule 2: You must act with due skill, care and "
            "diligence. Staff must maintain an appropriate level of professional "
            "knowledge and act competently in performing their roles, taking "
            "reasonable care in all activities."
        ),
        "requirement_type": "mandatory",
        "applicable_to": [
            "FCA-regulated firms",
            "PRA-regulated firms",
            "senior managers",
            "certification staff",
        ],
        "controls": [
            "Competency framework and skills matrix",
            "Continuing professional development programme",
            "Performance management system",
            "Supervision and oversight arrangements",
        ],
        "penalties": (
            "Breaches may result in individual fines, prohibition orders, and "
            "public censure. Firms failing to ensure staff competence may face "
            "unlimited fines and business restrictions."
        ),
    },
    {
        "id": "FCA_SMCR_ICR3_OBL_013",
        "obligation_id": "OBL-013",
        "pillar": "Conduct Rules - Individual",
        "description": (
            "Individual Conduct Rule 3: You must be open and cooperative with "
            "the FCA, PRA, and other regulators, and must disclose appropriately "
            "any information of which the regulator would reasonably expect "
            "notice."
        ),
        "requirement_type": "mandatory",
        "applicable_to": [
            "FCA-regulated firms",
            "PRA-regulated firms",
            "senior managers",
            "certification staff",
        ],
        "controls": [
            "Regulatory notification procedures",
            "Information disclosure policy",
            "Regulatory engagement framework",
            "Record-keeping of regulatory interactions",
        ],
        "penalties": (
            "Failure to be open and cooperative is treated as a serious breach. "
            "Penalties include unlimited fines, prohibition orders, and in "
            "serious cases criminal prosecution for misleading regulators."
        ),
    },
    {
        "id": "FCA_SMCR_ICR4_OBL_014",
        "obligation_id": "OBL-014",
        "pillar": "Conduct Rules - Individual",
        "description": (
            "Individual Conduct Rule 4: You must pay due regard to the interests "
            "of customers and treat them fairly. This includes ensuring that "
            "products and services are suitable, communications are clear, and "
            "vulnerable customers receive appropriate support."
        ),
        "requirement_type": "mandatory",
        "applicable_to": [
            "FCA-regulated firms",
            "PRA-regulated firms",
            "senior managers",
            "certification staff",
        ],
        "controls": [
            "Treating Customers Fairly framework",
            "Suitability assessment process",
            "Vulnerable customer identification policy",
            "Customer outcome monitoring dashboard",
        ],
        "penalties": (
            "Breaches may result in individual fines, suspension, or prohibition. "
            "Firms may face unlimited fines, redress requirements, and restrictions "
            "on selling certain products."
        ),
    },
    {
        "id": "FCA_SMCR_ICR5_OBL_015",
        "obligation_id": "OBL-015",
        "pillar": "Conduct Rules - Individual",
        "description": (
            "Individual Conduct Rule 5: You must observe proper standards of "
            "market conduct. Staff must not engage in market abuse, insider "
            "dealing, or any activity that undermines market integrity, and must "
            "comply with all applicable market conduct rules."
        ),
        "requirement_type": "mandatory",
        "applicable_to": [
            "FCA-regulated firms",
            "PRA-regulated firms",
            "senior managers",
            "certification staff",
        ],
        "controls": [
            "Market conduct policy",
            "Personal account dealing rules",
            "Insider dealing and market abuse monitoring",
            "Trade surveillance systems",
        ],
        "penalties": (
            "Market conduct breaches carry severe penalties including unlimited "
            "fines, prohibition orders, and criminal prosecution for market "
            "abuse (up to 7 years imprisonment under the Financial Services "
            "Act 2012)."
        ),
    },
    # =========================================================================
    # PILLAR 3: Conduct Rules -- Senior Manager Conduct Rules (3 obligations)
    # =========================================================================
    {
        "id": "FCA_SMCR_SMCR1_OBL_016",
        "obligation_id": "OBL-016",
        "pillar": "Conduct Rules - Senior Manager",
        "description": (
            "Senior Manager Conduct Rule 1 (SC1): You must take reasonable steps "
            "to ensure that the business of the firm for which you are responsible "
            "is controlled effectively. This includes establishing and maintaining "
            "appropriate systems, controls, and risk management frameworks."
        ),
        "requirement_type": "mandatory",
        "applicable_to": [
            "FCA-regulated firms",
            "PRA-regulated firms",
            "senior managers",
        ],
        "controls": [
            "Internal control framework (Three Lines of Defence)",
            "Risk management committee structure",
            "Management information and MI dashboards",
            "Internal audit programme",
        ],
        "penalties": (
            "Senior Managers face personal liability for control failures in "
            "their area. Penalties include unlimited personal fines, prohibition "
            "orders, and public censure. The FCA has fined individuals over "
            "GBP 1 million for control failures."
        ),
    },
    {
        "id": "FCA_SMCR_SMCR2_OBL_017",
        "obligation_id": "OBL-017",
        "pillar": "Conduct Rules - Senior Manager",
        "description": (
            "Senior Manager Conduct Rule 2 (SC2): You must take reasonable steps "
            "to ensure that the business of the firm for which you are responsible "
            "complies with the relevant requirements and standards of the "
            "regulatory system. This includes proactively identifying regulatory "
            "changes and ensuring timely implementation."
        ),
        "requirement_type": "mandatory",
        "applicable_to": [
            "FCA-regulated firms",
            "PRA-regulated firms",
            "senior managers",
        ],
        "controls": [
            "Regulatory change management process",
            "Compliance monitoring programme",
            "Regulatory horizon scanning",
            "Compliance reporting to governing body",
        ],
        "penalties": (
            "Failure to ensure regulatory compliance in their area exposes "
            "Senior Managers to personal enforcement action including unlimited "
            "fines, prohibition orders, and public censure."
        ),
    },
    {
        "id": "FCA_SMCR_SMCR3_OBL_018",
        "obligation_id": "OBL-018",
        "pillar": "Conduct Rules - Senior Manager",
        "description": (
            "Senior Manager Conduct Rules 3 and 4 (SC3/SC4): You must ensure "
            "that any delegation of your responsibilities is to an appropriate "
            "person and that you oversee the discharge of the delegated "
            "responsibility effectively. You must also disclose appropriately "
            "any information of which the FCA or PRA would reasonably expect "
            "notice, including matters relating to regulatory concerns."
        ),
        "requirement_type": "mandatory",
        "applicable_to": [
            "FCA-regulated firms",
            "PRA-regulated firms",
            "senior managers",
        ],
        "controls": [
            "Delegation framework and authority matrix",
            "Delegated authority monitoring and reporting",
            "Regulatory disclosure and notification procedures",
            "Escalation policy for regulatory concerns",
        ],
        "penalties": (
            "Inappropriate delegation or failure to disclose regulatory concerns "
            "may result in personal enforcement action against the Senior Manager "
            "including unlimited fines, prohibition orders, and criminal "
            "prosecution in cases of deliberate concealment."
        ),
    },
]


async def main() -> None:
    """Main loader function."""
    logger.info("Connecting to Neo4j at %s", NEO4J_URI)
    driver = AsyncGraphDatabase.driver(
        NEO4J_URI,
        auth=(NEO4J_USERNAME, NEO4J_PASSWORD),
    )

    try:
        # Verify connectivity
        async with driver.session(database=NEO4J_DATABASE) as session:
            result = await session.run("RETURN 1 AS ok")
            record = await result.single()
            if record and record["ok"] == 1:
                logger.info("Neo4j connection verified successfully.")
            else:
                logger.error("Neo4j connection check returned unexpected result.")
                return

        # -----------------------------------------------------------------
        # Step 1: Check for existing SMCR UKRegulation node
        # -----------------------------------------------------------------
        async with driver.session(database=NEO4J_DATABASE) as session:
            check_query = (
                "MATCH (r:UKRegulation) "
                "WHERE r.name CONTAINS 'SMCR' OR r.name CONTAINS 'Senior Manager' "
                "RETURN r.name AS name, labels(r) AS labels"
            )
            result = await session.run(check_query)
            records = [record async for record in result]

            if records:
                logger.info(
                    "Found existing SMCR-related UKRegulation node(s): %s",
                    [r["name"] for r in records],
                )
            else:
                logger.info("No SMCR-related UKRegulation node found. Will create one.")

        # -----------------------------------------------------------------
        # Step 2: Ensure UK Jurisdiction node exists
        # -----------------------------------------------------------------
        async with driver.session(database=NEO4J_DATABASE) as session:
            jurisdiction_query = """
            MERGE (uk:Jurisdiction {code: 'UK'})
            SET uk.name = 'United Kingdom',
                uk.regulatory_body = 'FCA, PRA, ICO, HMRC',
                uk.last_updated = datetime()
            RETURN uk.code AS code
            """
            result = await session.run(jurisdiction_query)
            record = await result.single()
            logger.info("UK Jurisdiction node ensured (code=%s).", record["code"])

        # -----------------------------------------------------------------
        # Step 3: Create or merge the SMCR UKRegulation node
        # -----------------------------------------------------------------
        async with driver.session(database=NEO4J_DATABASE) as session:
            regulation_query = """
            MERGE (r:UKRegulation {name: 'Senior Managers and Certification Regime (SMCR)'})
            SET r.short_name = 'SMCR',
                r.regulator = 'FCA / PRA',
                r.effective_date = date('2016-03-07'),
                r.extended_to_all_firms = date('2019-12-09'),
                r.legislation_basis = 'Financial Services and Markets Act 2000 (as amended by the Financial Services (Banking Reform) Act 2013)',
                r.description = 'The Senior Managers and Certification Regime (SMCR) is a regulatory framework introduced by the FCA and PRA to strengthen individual accountability in UK financial services. It replaced the Approved Persons Regime and comprises three pillars: the Senior Managers Regime, the Certification Regime, and the Conduct Rules.',
                r.applies_to = 'All FCA solo-regulated firms, PRA-regulated firms, and insurers',
                r.pillars = ['Senior Managers Regime', 'Certification Regime', 'Conduct Rules'],
                r.risk_rating = 'critical',
                r.penalty_framework = 'Unlimited fines, prohibition orders, public censure, criminal prosecution',
                r.url = 'https://www.fca.org.uk/firms/senior-managers-certification-regime',
                r.loaded_at = datetime()
            WITH r
            MATCH (uk:Jurisdiction {code: 'UK'})
            MERGE (r)-[:GOVERNED_BY]->(uk)
            RETURN r.name AS name
            """
            result = await session.run(regulation_query)
            record = await result.single()
            logger.info("UKRegulation node ensured: %s", record["name"])

        # -----------------------------------------------------------------
        # Step 4: Create StructuredObligation nodes and link them
        # -----------------------------------------------------------------
        obligations_created = 0
        async with driver.session(database=NEO4J_DATABASE) as session:
            for obl in SMCR_OBLIGATIONS:
                obl_query = """
                MERGE (o:StructuredObligation {id: $id})
                SET o.obligation_id = $obligation_id,
                    o.pillar = $pillar,
                    o.description = $description,
                    o.requirement_type = $requirement_type,
                    o.applicable_to = $applicable_to,
                    o.controls = $controls,
                    o.penalties = $penalties,
                    o.created_at = datetime()
                WITH o
                MATCH (r:UKRegulation {name: 'Senior Managers and Certification Regime (SMCR)'})
                MERGE (o)-[:MANDATED_BY]->(r)
                WITH o
                MATCH (uk:Jurisdiction {code: 'UK'})
                MERGE (o)-[:ENFORCED_IN]->(uk)
                RETURN o.id AS id
                """
                result = await session.run(obl_query, parameters=obl)
                record = await result.single()
                if record:
                    obligations_created += 1
                    logger.info(
                        "  Created obligation %s (%s): %s",
                        record["id"],
                        obl["obligation_id"],
                        obl["pillar"],
                    )

        logger.info(
            "Successfully created %d StructuredObligation nodes for SMCR.",
            obligations_created,
        )

        # -----------------------------------------------------------------
        # Step 5: Link IQ Persona to SMCR if it exists
        # -----------------------------------------------------------------
        async with driver.session(database=NEO4J_DATABASE) as session:
            iq_link_query = """
            MATCH (iq:IQPersona {id: 'IQ_CCO_2025'})
            MATCH (r:UKRegulation {name: 'Senior Managers and Certification Regime (SMCR)'})
            MERGE (iq)-[:UK_EXPERTISE]->(r)
            RETURN iq.name AS iq_name
            """
            result = await session.run(iq_link_query)
            record = await result.single()
            if record:
                logger.info(
                    "Linked IQ persona (%s) to SMCR regulation.",
                    record["iq_name"],
                )
            else:
                logger.info(
                    "No IQ persona node found -- skipping IQ-to-SMCR link."
                )

        # -----------------------------------------------------------------
        # Step 6: Verification queries
        # -----------------------------------------------------------------
        async with driver.session(database=NEO4J_DATABASE) as session:
            # Count StructuredObligation nodes for SMCR
            verify_count_query = """
            MATCH (o:StructuredObligation)-[:MANDATED_BY]->(r:UKRegulation)
            WHERE r.name CONTAINS 'SMCR'
            RETURN count(o) AS obligation_count
            """
            result = await session.run(verify_count_query)
            record = await result.single()
            logger.info(
                "VERIFICATION: %d StructuredObligation nodes linked to SMCR.",
                record["obligation_count"],
            )

            # Count by pillar
            verify_pillar_query = """
            MATCH (o:StructuredObligation)-[:MANDATED_BY]->(r:UKRegulation)
            WHERE r.name CONTAINS 'SMCR'
            RETURN o.pillar AS pillar, count(o) AS count
            ORDER BY pillar
            """
            result = await session.run(verify_pillar_query)
            records = [record async for record in result]
            logger.info("VERIFICATION by pillar:")
            for rec in records:
                logger.info("  %s: %d obligations", rec["pillar"], rec["count"])

            # Verify ENFORCED_IN relationship
            verify_jurisdiction_query = """
            MATCH (o:StructuredObligation)-[:ENFORCED_IN]->(j:Jurisdiction {code: 'UK'})
            WHERE o.id STARTS WITH 'FCA_SMCR'
            RETURN count(o) AS enforced_count
            """
            result = await session.run(verify_jurisdiction_query)
            record = await result.single()
            logger.info(
                "VERIFICATION: %d obligations linked to UK Jurisdiction via ENFORCED_IN.",
                record["enforced_count"],
            )

            # Verify MANDATED_BY relationship
            verify_mandated_query = """
            MATCH (o:StructuredObligation)-[:MANDATED_BY]->(r:UKRegulation)
            WHERE o.id STARTS WITH 'FCA_SMCR'
            RETURN count(o) AS mandated_count
            """
            result = await session.run(verify_mandated_query)
            record = await result.single()
            logger.info(
                "VERIFICATION: %d obligations linked to UKRegulation via MANDATED_BY.",
                record["mandated_count"],
            )

            # Show a sample obligation
            sample_query = """
            MATCH (o:StructuredObligation)-[:MANDATED_BY]->(r:UKRegulation)
            WHERE r.name CONTAINS 'SMCR'
            RETURN o.id AS id, o.obligation_id AS obl_id, o.pillar AS pillar,
                   left(o.description, 120) AS description_preview
            ORDER BY o.obligation_id
            """
            result = await session.run(sample_query)
            records = [record async for record in result]
            logger.info("ALL %d SMCR obligations:", len(records))
            for rec in records:
                logger.info(
                    "  [%s] %s | %s | %s...",
                    rec["obl_id"],
                    rec["id"],
                    rec["pillar"],
                    rec["description_preview"],
                )

        logger.info("SMCR obligation loading complete.")

    except Exception as e:
        logger.error("Error during SMCR loading: %s", e, exc_info=True)
        raise
    finally:
        await driver.close()
        logger.info("Neo4j driver closed.")


if __name__ == "__main__":
    asyncio.run(main())
