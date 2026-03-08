"""
Reconcile 442 old Obligation nodes with regulation="Unknown".

These nodes were ingested from legislation.gov.uk but lack regulation classification.
This script:
1. Queries all 442 Unknown Obligation nodes and their text content.
2. Classifies each by keyword matching against known UK regulation categories.
3. Updates the regulation property and creates MANDATED_BY relationships
   to the correct UKRegulation node.
4. Updates skeleton UKRegulation nodes' total_obligations counts to reflect
   actual linked obligations (both Obligation and StructuredObligation).
5. Prints a detailed summary table.

Usage:
    PYTHONIOENCODING=utf-8 python scripts/reconcile_old_obligations.py
"""

import re
import sys
from collections import defaultdict
from typing import Any

from neo4j import GraphDatabase

NEO4J_URI = "bolt://localhost:17687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "testpassword123"

# ---------------------------------------------------------------------------
# Classification rules: ordered list of (regulation_name, keywords)
# Order matters: more specific rules come first to avoid false positives.
# Each keyword is matched case-insensitively against the full obligation text.
# ---------------------------------------------------------------------------
CLASSIFICATION_RULES: list[tuple[str, list[str]]] = [
    # --- NIS Regulations (already handled, but include for completeness) ---
    (
        "Network and Information Systems Regulations 2018",
        [
            "NIS",
            "network and information systems",
            "digital service provider",
            "operator of essential services",
            "competent authority for NIS",
            "EU Regulation 2018/151",
        ],
    ),
    # --- PECR (Privacy and Electronic Communications) ---
    (
        "Privacy and Electronic Communications Regulations 2003",
        [
            "electronic communication",
            "PECR",
            "privacy and electronic",
            "direct marketing",
            "unsolicited communication",
            "e-privacy",
            "cookie",
            "traffic data",
            "location data",
            "subscriber",
        ],
    ),
    # --- Money Laundering Regulations ---
    (
        "Money Laundering Regulations 2017",
        [
            "money laundering",
            "MLR",
            "proceeds of crime",
            "terrorist financing",
            "suspicious activity report",
            "customer due diligence",
            "enhanced due diligence",
            "simplified due diligence",
            "politically exposed",
            "beneficial owner",
            "nominated officer",
        ],
    ),
    # --- Proceeds of Crime Act (separate from MLR) ---
    (
        "Proceeds of Crime Act 2002",
        [
            "Proceeds of Crime Act",
            "confiscation order",
            "restraint order",
            "receivership",
            "recovery order",
            "criminal lifestyle",
            "enforcement authority",
            "unexplained wealth",
            "civil recovery",
            "account forfeiture",
            "listed asset",
            "freezing order",
            "POCA",
            "Crown Court",
            "convicted of an offence",
            "the prosecutor",
            "Director of Public Prosecutions",
            "defendants interest in.*property",
            "section 6.*section 6\\(3\\)",
        ],
    ),
    # --- Bribery Act ---
    (
        "Bribery Act 2010",
        [
            "bribery",
            "Bribery Act",
            "corruption",
            "facilitation payment",
            "improper performance",
        ],
    ),
    # --- Fraud Act ---
    (
        "Fraud Act 2006",
        [
            "Fraud Act",
            "dishonestly",
            "false representation",
            "failing to disclose",
            "abuse of position",
            "fraud by",
            "articles for use in fraud",
        ],
    ),
    # --- Companies Act ---
    (
        "Companies Act 2006",
        [
            "Companies Act",
            "company secretary",
            "directors duties",
            "director's duties",
            "annual return",
            "company register",
            "fiduciary",
            "memorandum of association",
            "articles of association",
            "registrar of companies",
            "registered office",
            "allotment of shares",
            "share capital",
            "annual accounts",
            "company name",
            "overseas entity",
            "confirmation statement",
            "members register",
            "register of members",
            "debenture",
            "company's constitution",
            "companys constitution",
            "resolution",
            "registration of the company",
            "registration of a company",
            "registrar must",
            "delivered to the registrar",
            "the registrar",
            "companys memorandum",
            "company's memorandum",
            "common seal",
            "officer of the company",
            "officer of a company",
            "on behalf of a company",
            "removed from the register",
            "removal.*from the register",
            "overseas entities",
            "register under section",
        ],
    ),
    # --- Equality Act ---
    (
        "Equality Act 2010",
        [
            "Equality Act",
            "protected characteristic",
            "reasonable adjustment",
            "equal pay",
            "discrimination",
            "discriminate against",
            "victimisation",
            "harassment",
            "harass a person",
            "disabled person",
            "gender reassignment",
            "maternity",
            "sexual orientation",
            "race discrimination",
            "direct discrimination",
            "indirect discrimination",
            "public sector equality",
            "socio-economic disadvantage",
            "inequalities of outcome",
        ],
    ),
    # --- Employment Rights Act ---
    (
        "Employment Rights Act 1996",
        [
            "Employment Rights Act",
            "unfair dismissal",
            "redundancy payment",
            "employment tribunal",
            "written statement of employment",
            "itemised pay statement",
            "guarantee payment",
            "employee's rights",
            "employees rights",
        ],
    ),
    # --- Working Time Regulations ---
    (
        "Working Time Regulations 1998",
        [
            "Working Time Regulation",
            "working time",
            "maximum weekly working",
            "rest period",
            "annual leave",
            "night work",
        ],
    ),
    # --- National Minimum Wage ---
    (
        "National Minimum Wage Act 1998",
        [
            "minimum wage",
            "national living wage",
            "National Minimum Wage",
        ],
    ),
    # --- Modern Slavery Act ---
    (
        "Modern Slavery Act 2015",
        [
            "Modern Slavery",
            "slavery",
            "servitude",
            "forced labour",
            "human trafficking",
            "transparency in supply chain",
        ],
    ),
    # --- Health and Safety at Work Act ---
    (
        "Health and Safety at Work Act 1974",
        [
            "health and safety",
            "Health and Safety at Work",
            "workplace safety",
            "RIDDOR",
            "risk assessment",
            "occupational health",
            "safe system of work",
            "personal protective equipment",
            "safety representative",
        ],
    ),
    # --- COSHH ---
    (
        "Control of Substances Hazardous to Health Regulations 2002",
        [
            "COSHH",
            "hazardous substance",
            "hazardous to health",
            "chemical agent",
            "biological agent",
            "exposure limit",
        ],
    ),
    # --- Fire Safety ---
    (
        "Regulatory Reform (Fire Safety) Order 2005",
        [
            "fire safety",
            "Fire Safety Order",
            "fire risk assessment",
            "means of escape",
            "fire-fighting",
            "fire detection",
        ],
    ),
    # --- Environmental ---
    (
        "Climate Change Act 2008",
        [
            "Climate Change Act",
            "carbon budget",
            "greenhouse gas",
            "climate change",
            "carbon emission",
            "net zero",
        ],
    ),
    (
        "Waste Regulations 2011",
        [
            "Waste Regulation",
            "waste management",
            "waste disposal",
            "hazardous waste",
            "waste carrier",
            "duty of care for waste",
        ],
    ),
    # --- Competition ---
    (
        "Competition Act 1998",
        [
            "Competition Act",
            "anti-competitive",
            "abuse of dominant position",
            "chapter I prohibition",
            "chapter II prohibition",
            "competition and markets authority",
            "CMA",
        ],
    ),
    # --- Enterprise Act ---
    (
        "Enterprise Act 2002",
        [
            "Enterprise Act",
            "merger control",
            "market investigation",
            "consumer protection under enterprise",
            "cease to be distinct enterprises",
            "relevant merger situation",
            "turnover in the United Kingdom",
            "Competition Appeal Tribunal",
            "Competition Service",
            "the Tribunal shall consist",
            "consumer claims",
            "specified body may.*bring proceedings",
            "enterprise.*control.*transaction",
            "decision-making authority",
        ],
    ),
    # --- Freedom of Information ---
    (
        "Freedom of Information Act 2000",
        [
            "freedom of information",
            "FOI",
            "right of access to information",
            "public authority disclosure",
        ],
    ),
    # --- Public Interest Disclosure (whistleblowing) ---
    (
        "Public Interest Disclosure Act 1998",
        [
            "public interest disclosure",
            "qualifying disclosure",
            "protected disclosure",
            "whistleblowing",
            "whistleblower",
        ],
    ),
    # --- Contracts (Rights of Third Parties) ---
    (
        "Contracts (Rights of Third Parties) Act 1999",
        [
            "third party",
            "Rights of Third Parties",
            "promisor",
            "promisee",
            "Limitation.*Northern Ireland.*Order",
        ],
    ),
    # --- Corporate Manslaughter ---
    (
        "Corporate Manslaughter and Corporate Homicide Act 2007",
        [
            "corporate manslaughter",
            "corporate homicide",
            "gross negligence manslaughter",
        ],
    ),
    # --- Pensions ---
    (
        "Pensions Act 2008",
        [
            "automatic enrolment",
            "workplace pension",
            "pension scheme employer",
            "Pensions Act 2008",
        ],
    ),
    # --- Terrorism Act ---
    (
        "Terrorism Act 2000",
        [
            "Terrorism Act",
            "terrorist property",
            "proscribed organisation",
            "terrorist investigation",
        ],
    ),
    # --- Data Protection Act 2018 (UK implementation of GDPR) ---
    # NOTE: DPA 2018 is separate from UK GDPR - DPA has Part 3 (law enforcement),
    # Part 4 (intelligence services), and supplementary provisions
    (
        "Data Protection Act 2018",
        [
            "Data Protection Act",
            "data protection principle",
            "information commissioner",
            "Information Commissioner",
            "Commissioner must",
            "Commissioner may",
            "appropriate policy document",
            "law enforcement processing",
            "intelligence service processing",
            "Part 3",
            "Part 4",
        ],
    ),
    # --- UK GDPR (broader GDPR text matching) ---
    (
        "UK GDPR",
        [
            "UK GDPR",
            "GDPR",
            "General Data Protection",
            "personal data",
            "data subject",
            "data controller",
            "data processor",
            "right to erasure",
            "right to rectification",
            "data portability",
            "lawful basis",
            "consent",
            "legitimate interest",
            "special category",
            "data breach",
            "impact assessment",
            "DPIA",
            "supervisory authority",
            "transfer of personal data",
            "third country",
            "adequacy decision",
            "binding corporate rules",
            "controller",
            "processor",
        ],
    ),
    # --- FCA (broad - Financial Conduct Authority) ---
    # This is intentionally broad and placed after more specific FCA rules
    (
        "FCA",
        [
            "Financial Conduct Authority",
            "FCA",
            "conduct of business",
            "client money",
            "approved persons",
            "financial promotion",
            "market abuse",
            "COBS",
            "PRIN",
            "SYSC",
            "MCOB",
            "ICOBS",
            "listing rules",
            "prospectus",
            "transparency",
            "senior manager",
            "certification regime",
            "consumer duty",
            "investment firm",
            "trading venue",
            "systematic internaliser",
            "regulated market",
            "multilateral trading",
            "organised trading",
            "CCP",
            "central counterpart",
            "trade repository",
            "benchmark",
            "administrator",
            "critical benchmark",
            "depositary receipts",
            "UCITS",
            "AIFM",
            "SFTs",
            "total return swap",
            "indirect clearing",
            "counterparty risk",
            "exchange-traded derivative",
            "financial counterpart",
            "non-financial counterpart",
            "supervised contributor",
            "input data",
            "index provider",
            "index.*formula.*calculation",
            "this Order.*communication",
        ],
    ),
    # --- PRA (Prudential Regulation Authority) ---
    (
        "PRA Rulebook - Fundamental Rules",
        [
            "PRA",
            "Prudential Regulation Authority",
            "prudential regulation",
            "capital requirement",
            "solvency",
        ],
    ),
    # --- Senior Managers and Certification Regime ---
    (
        "Senior Managers and Certification Regime (SMCR)",
        [
            "SMCR",
            "Senior Managers and Certification",
            "senior management function",
            "controlled function",
            "fit and proper",
        ],
    ),
    # --- NHS / Health Service (general catch-all for health legislation) ---
    # Many Unknown obligations are from Health and Social Care Acts
    (
        "Health and Social Care Act 2012",
        [
            "health service",
            "National Health Service",
            "NHS",
            "clinical commissioning",
            "NHS Constitution",
            "Health Education England",
            "NHS Commissioning Board",
            "Health and Wellbeing Board",
            "Secretary of State must.*health",
            "care quality",
            "NHS trust",
            "foundation trust",
            "the Board must",
            "patients",
            "public health",
            "local authority.*public health",
            "improving the health",
            "diagnosis of illness",
            "diagnosis or treatment",
            "the mandate",
        ],
    ),
    # --- Investigatory Powers Act (surveillance, warrants) ---
    (
        "Investigatory Powers Act 2016",
        [
            "interception warrant",
            "targeted interception",
            "targeted examination",
            "mutual assistance warrant",
            "bulk acquisition",
            "Investigatory Powers",
            "communications data",
            "equipment interference",
            "judicial commissioner",
            "intercepting authority",
            "warrant under this Chapter",
            "renewal.*warrant",
            "cancel a warrant",
            "source of journalistic information",
        ],
    ),
    # --- Online Safety Act ---
    (
        "Online Safety Act 2023",
        [
            "regulated user-to-user",
            "regulated search service",
            "OFCOM",
            "illegal content",
            "user-generated content",
            "freedom of expression and privacy",
            "online safety",
            "duty of care.*online",
            "Category 1 services",
            "adult users",
            "search content",
            "journalistic content",
            "content of democratic importance",
            "empower.*users",
        ],
    ),
    # --- Insurance Act ---
    (
        "Insurance Act 2015",
        [
            "Insurance Act",
            "fair presentation of the risk",
            "insurer",
            "insured",
            "insurance contract",
            "duty of fair presentation",
            "disadvantageous term",
        ],
    ),
    # --- Consumer protection / Consumer Rights ---
    (
        "Consumer Rights Act 2015",
        [
            "Consumer Rights Act",
            "consumer contract",
            "unfair term",
            "digital content",
            "consumer protection",
            "Consumer Protection Act",
        ],
    ),
    # --- Children and education related legislation ---
    (
        "Children and Families Act 2014",
        [
            "childrens risk assessment",
            "children's risk assessment",
            "safeguarding children",
            "children and families",
            "child protection",
            "education.*Secretary of State",
        ],
    ),
    # --- Financial Services and Markets Act ---
    (
        "Financial Services and Markets Act 2000",
        [
            "FSMA",
            "Financial Services and Markets",
            "regulated activities",
            "authorised person",
            "permission",
            "Part 4A permission",
        ],
    ),
    # --- Criminal Justice Act ---
    (
        "Criminal Justice Act",
        [
            "Criminal Justice Act",
            "criminal justice",
            "accreditation of financial investigators",
            "National Crime Agency",
            "reduction of crime",
        ],
    ),
    # --- Economic Crime ---
    (
        "Economic Crime Act",
        [
            "Economic Crime",
            "economic crime",
            "corporate criminal offence",
            "failure to prevent",
        ],
    ),
]

# Precompile regex patterns for rules that contain regex metacharacters
_COMPILED_RULES: list[tuple[str, list[re.Pattern[str]]]] = []
for reg_name, keywords in CLASSIFICATION_RULES:
    patterns = []
    for kw in keywords:
        # If keyword contains regex metacharacters (like .*), compile as regex
        # Otherwise compile as a literal (escaped) pattern
        if any(c in kw for c in r".*+?[](){}|\\^$"):
            patterns.append(re.compile(kw, re.IGNORECASE))
        else:
            patterns.append(re.compile(re.escape(kw), re.IGNORECASE))
    _COMPILED_RULES.append((reg_name, patterns))


def classify_obligation(text: str) -> str:
    """
    Classify an obligation by its text content.

    Returns the regulation name if a match is found, or "Unclassified".
    Uses case-insensitive keyword matching with early termination
    (first matching rule wins).
    """
    if not text:
        return "Unclassified"

    for reg_name, patterns in _COMPILED_RULES:
        for pattern in patterns:
            if pattern.search(text):
                return reg_name

    return "Unclassified"


def run_reconciliation() -> None:
    """Main reconciliation logic."""
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    try:
        with driver.session() as session:
            # ------------------------------------------------------------------
            # STEP 0: Baseline state
            # ------------------------------------------------------------------
            print("=" * 75)
            print("STEP 0 - BASELINE STATE")
            print("=" * 75)

            result = session.run(
                "MATCH (o:Obligation) RETURN o.regulation AS reg, count(o) AS cnt ORDER BY cnt DESC"
            )
            baseline = list(result)
            print("\nObligation nodes by regulation:")
            for rec in baseline:
                print(f"  {rec['reg']}: {rec['cnt']}")

            result = session.run(
                "MATCH (o:Obligation) "
                "WHERE o.regulation IN ['Unknown', 'Unclassified'] "
                "RETURN o.regulation AS reg, count(o) AS cnt "
                "ORDER BY cnt DESC"
            )
            pending_counts = {rec["reg"]: rec["cnt"] for rec in result}
            unknown_count = sum(pending_counts.values())
            for reg, cnt in pending_counts.items():
                print(f"\n  {reg}: {cnt}")
            print(f"\nTotal obligations to (re-)classify: {unknown_count}")

            if unknown_count == 0:
                print("Nothing to do. Exiting.")
                return

            # ------------------------------------------------------------------
            # STEP 1: Query ALL Unknown/Unclassified obligations
            # ------------------------------------------------------------------
            print("\n" + "=" * 75)
            print("STEP 1 - QUERYING ALL UNKNOWN/UNCLASSIFIED OBLIGATIONS")
            print("=" * 75)

            result = session.run(
                "MATCH (o:Obligation) "
                "WHERE o.regulation IN ['Unknown', 'Unclassified'] "
                "RETURN o.id AS id, o.text AS text "
                "ORDER BY o.id"
            )
            obligations: list[dict[str, Any]] = [
                {"id": rec["id"], "text": rec["text"] or ""} for rec in result
            ]
            print(f"Fetched {len(obligations)} Unknown/Unclassified obligation nodes.")

            # ------------------------------------------------------------------
            # STEP 2: Classify each obligation by text content
            # ------------------------------------------------------------------
            print("\n" + "=" * 75)
            print("STEP 2 - CLASSIFYING OBLIGATIONS BY TEXT CONTENT")
            print("=" * 75)

            classification_map: dict[str, str] = {}  # obligation_id -> regulation_name
            regulation_counts: dict[str, int] = defaultdict(int)

            for obl in obligations:
                reg = classify_obligation(obl["text"])
                classification_map[obl["id"]] = reg
                regulation_counts[reg] += 1

            print("\nClassification results:")
            for reg_name, count in sorted(regulation_counts.items(), key=lambda x: -x[1]):
                print(f"  {reg_name:<65} {count:>4}")
            print(f"  {'TOTAL':<65} {sum(regulation_counts.values()):>4}")

            # Show samples of Unclassified for debugging
            unclassified = [
                obl for obl in obligations if classification_map[obl["id"]] == "Unclassified"
            ]
            if unclassified:
                print(f"\nSamples of {len(unclassified)} Unclassified obligations:")
                for obl in unclassified[:15]:
                    text_preview = obl["text"][:200]
                    print(f"  id={obl['id']}")
                    print(f"    text: {text_preview}")
                    print()

            # ------------------------------------------------------------------
            # STEP 3: Group obligations by target regulation for batch updates
            # ------------------------------------------------------------------
            print("\n" + "=" * 75)
            print("STEP 3 - UPDATING REGULATION PROPERTY AND CREATING RELATIONSHIPS")
            print("=" * 75)

            # Group obligation IDs by their target regulation
            reg_to_ids: dict[str, list[str]] = defaultdict(list)
            for obl_id, reg_name in classification_map.items():
                reg_to_ids[reg_name].append(obl_id)

            total_updated = 0
            total_rels_created = 0
            total_rels_deleted = 0

            for reg_name, obl_ids in sorted(reg_to_ids.items()):
                if reg_name == "Unclassified":
                    # Still update the regulation property but do not link
                    result = session.run(
                        "UNWIND $ids AS oblId "
                        "MATCH (o:Obligation {id: oblId}) "
                        "SET o.regulation = 'Unclassified', "
                        "    o.regulation_inferred_at = datetime() "
                        "RETURN count(o) AS updated",
                        ids=obl_ids,
                    )
                    updated = result.single()["updated"]
                    total_updated += updated
                    print(f"  Unclassified: updated {updated} obligations (no MANDATED_BY link)")
                    continue

                # Step 3a: Ensure UKRegulation node exists (MERGE)
                session.run(
                    "MERGE (r:UKRegulation {name: $name}) ON CREATE SET r.loaded_at = datetime()",
                    name=reg_name,
                )

                # Step 3b: Delete any existing MANDATED_BY to wrong targets
                result = session.run(
                    "UNWIND $ids AS oblId "
                    "MATCH (o:Obligation {id: oblId})-[rel:MANDATED_BY]->(r:UKRegulation) "
                    "WHERE r.name <> $regName "
                    "DELETE rel "
                    "RETURN count(rel) AS deleted",
                    ids=obl_ids,
                    regName=reg_name,
                )
                deleted = result.single()["deleted"]
                total_rels_deleted += deleted

                # Step 3c: Update regulation property and create MANDATED_BY
                result = session.run(
                    "UNWIND $ids AS oblId "
                    "MATCH (o:Obligation {id: oblId}) "
                    "SET o.regulation = $regName, "
                    "    o.regulation_inferred_at = datetime() "
                    "WITH o "
                    "MATCH (r:UKRegulation {name: $regName}) "
                    "MERGE (o)-[:MANDATED_BY]->(r) "
                    "RETURN count(o) AS updated",
                    ids=obl_ids,
                    regName=reg_name,
                )
                updated = result.single()["updated"]
                total_updated += updated
                total_rels_created += updated

                print(
                    f"  {reg_name:<60} "
                    f"updated={len(obl_ids):>3}, "
                    f"rels_created={updated:>3}, "
                    f"old_rels_deleted={deleted:>2}"
                )

            print(f"\nTotal updated: {total_updated}")
            print(f"Total MANDATED_BY relationships created: {total_rels_created}")
            print(f"Total old MANDATED_BY relationships deleted: {total_rels_deleted}")

            # ------------------------------------------------------------------
            # STEP 4: Update skeleton UKRegulation node metadata
            # ------------------------------------------------------------------
            print("\n" + "=" * 75)
            print("STEP 4 - UPDATING UKRegulation METADATA (total_obligations)")
            print("=" * 75)

            result = session.run(
                "MATCH (reg:UKRegulation) "
                "OPTIONAL MATCH (so:StructuredObligation)-[:MANDATED_BY]->(reg) "
                "OPTIONAL MATCH (o:Obligation)-[:MANDATED_BY]->(reg) "
                "WITH reg, "
                "     count(DISTINCT so) AS structured_count, "
                "     count(DISTINCT o) AS old_count, "
                "     count(DISTINCT so) + count(DISTINCT o) AS actual_total "
                "SET reg.total_obligations = actual_total "
                "RETURN reg.name AS name, "
                "       structured_count, old_count, actual_total, "
                "       reg.document_count AS doc_count "
                "ORDER BY actual_total DESC"
            )
            print(
                f"\n  {'Regulation':<65} {'Structured':>10} {'Old':>5} {'Total':>6} {'DocCnt':>6}"
            )
            print(f"  {'-' * 65} {'-' * 10} {'-' * 5} {'-' * 6} {'-' * 6}")
            for rec in result:
                doc_cnt = rec["doc_count"]
                dc_str = str(doc_cnt) if doc_cnt is not None else "NULL"
                print(
                    f"  {rec['name']:<65} "
                    f"{rec['structured_count']:>10} "
                    f"{rec['old_count']:>5} "
                    f"{rec['actual_total']:>6} "
                    f"{dc_str:>6}"
                )

            # ------------------------------------------------------------------
            # STEP 5: Final verification and summary
            # ------------------------------------------------------------------
            print("\n" + "=" * 75)
            print("STEP 5 - VERIFICATION AND SUMMARY")
            print("=" * 75)

            # Check remaining Unknown obligations
            result = session.run(
                "MATCH (o:Obligation {regulation: 'Unknown'}) RETURN count(o) AS cnt"
            )
            remaining_unknown = result.single()["cnt"]
            print(f"\n  Remaining Unknown obligations: {remaining_unknown}")

            # Count Unclassified
            result = session.run(
                "MATCH (o:Obligation {regulation: 'Unclassified'}) RETURN count(o) AS cnt"
            )
            unclassified_count = result.single()["cnt"]
            print(f"  Unclassified obligations: {unclassified_count}")

            # Count classified (not Unknown, not Unclassified, not NIS)
            result = session.run(
                "MATCH (o:Obligation) "
                "WHERE o.regulation <> 'Unknown' "
                "AND o.regulation <> 'Unclassified' "
                "RETURN o.regulation AS reg, count(o) AS cnt "
                "ORDER BY cnt DESC"
            )
            print("\n  Obligations by regulation (final state):")
            print(f"  {'Regulation':<65} {'Count':>5}")
            print(f"  {'-' * 65} {'-' * 5}")
            grand_total = 0
            for rec in result:
                print(f"  {rec['reg']:<65} {rec['cnt']:>5}")
                grand_total += rec["cnt"]
            if unclassified_count > 0:
                print(f"  {'Unclassified':<65} {unclassified_count:>5}")
                grand_total += unclassified_count
            print(f"  {'TOTAL':<65} {grand_total:>5}")

            # Verify MANDATED_BY relationships
            result = session.run(
                "MATCH (o:Obligation)-[:MANDATED_BY]->(r:UKRegulation) "
                "RETURN r.name AS reg, count(o) AS cnt "
                "ORDER BY cnt DESC"
            )
            print("\n  MANDATED_BY relationships (Obligation -> UKRegulation):")
            total_linked = 0
            for rec in result:
                print(f"    {rec['reg']:<60} {rec['cnt']:>5}")
                total_linked += rec["cnt"]
            print(f"    {'TOTAL linked':<60} {total_linked:>5}")

            # Success summary
            success = remaining_unknown == 0
            classified_count = unknown_count - unclassified_count
            classification_rate = (
                (classified_count / unknown_count * 100) if unknown_count > 0 else 0
            )
            print("\n" + "=" * 75)
            print("FINAL SUMMARY")
            print("=" * 75)
            print(f"  Input Unknown obligations:  {unknown_count}")
            print(f"  Successfully classified:    {classified_count}")
            print(f"  Left Unclassified:          {unclassified_count}")
            print(f"  Classification rate:        {classification_rate:.1f}%")
            print(f"  Remaining 'Unknown':        {remaining_unknown}")
            print(f"  MANDATED_BY rels created:   {total_rels_created}")
            print(f"  Old wrong rels deleted:     {total_rels_deleted}")
            print(f"  Status: {'SUCCESS' if success else 'NEEDS REVIEW'}")

    finally:
        driver.close()
        print("\nDriver closed.")


if __name__ == "__main__":
    # Ensure UTF-8 output on all platforms
    if sys.stdout.encoding != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    run_reconciliation()
