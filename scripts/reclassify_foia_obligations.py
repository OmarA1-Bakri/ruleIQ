"""
Reclassify misclassified FOIA obligations from UK GDPR to Freedom of Information Act 2000.

Problem: Several StructuredObligation nodes are linked via MANDATED_BY to "UK GDPR"
but their content (description, article_reference) clearly belongs to the
Freedom of Information Act 2000.

Solution:
1. Query all StructuredObligation nodes linked to UK GDPR whose text or
   article_reference indicates they belong to FOIA.
2. Delete MANDATED_BY relationship to UK GDPR for each.
3. MERGE a UKRegulation node for "Freedom of Information Act 2000" with correct
   properties (jurisdiction, regulatory_body, effective_date).
4. Create new MANDATED_BY relationships to "Freedom of Information Act 2000".
5. Print before/after counts for verification.
"""

from neo4j import GraphDatabase

NEO4J_URI = "bolt://localhost:17687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "testpassword123"

# FOIA keywords used to identify misclassified obligations
FOIA_KEYWORDS = [
    "freedom of information",
    "foia",
    "right of access to information held by public authorities",
]

# The article_reference value that definitively marks FOIA obligations
FOIA_ARTICLE_REFERENCE = "freedom-of-information-act-2000"

# Properties for the FOIA UKRegulation node
FOIA_REGULATION_PROPS = {
    "jurisdiction": "UK",
    "regulatory_body": "ICO",
    "effective_date": "2000-11-30",
}


def find_foia_obligations(session) -> list[dict]:
    """Find StructuredObligation nodes linked to UK GDPR that belong to FOIA.

    Uses two detection strategies:
    1. article_reference == 'freedom-of-information-act-2000'
    2. Description contains FOIA-specific keywords (freedom of information, foia, etc.)

    Excludes obligations whose article_reference points to a different regulation
    (e.g. enterprise-act-2002) even if they mention 'public authority'.
    """
    result = session.run(
        """
        MATCH (o:StructuredObligation)-[:MANDATED_BY]->(r:UKRegulation {name: 'UK GDPR'})
        WHERE o.article_reference = $foiaRef
           OR toLower(o.description) CONTAINS 'freedom of information'
           OR toLower(o.description) CONTAINS 'foia'
           OR toLower(o.description) CONTAINS 'right of access to information held by public authorities'
        RETURN o.obligation_id AS obligation_id,
               o.description AS description,
               o.article_reference AS article_reference,
               o.section AS section,
               elementId(o) AS element_id
        ORDER BY o.obligation_id
        """,
        foiaRef=FOIA_ARTICLE_REFERENCE,
    )
    candidates = result.data()

    # Filter: only include obligations whose article_reference is FOIA
    # or whose description clearly matches FOIA keywords AND article_reference
    # is not pointing to a different known regulation.
    foia_obligations = []
    non_foia_refs = {
        "enterprise-act-2002",
        "companies-act-2006",
        "data-protection-act-2018",
    }

    for obl in candidates:
        art_ref = (obl.get("article_reference") or "").lower().strip()
        desc_lower = (obl.get("description") or "").lower()

        # If article_reference explicitly says FOIA, it's FOIA
        if art_ref == FOIA_ARTICLE_REFERENCE:
            foia_obligations.append(obl)
            continue

        # If article_reference points to a different regulation, skip
        if art_ref in non_foia_refs:
            continue

        # If description contains strong FOIA keywords and no conflicting ref
        has_foia_keyword = any(kw in desc_lower for kw in FOIA_KEYWORDS)
        if has_foia_keyword and art_ref not in non_foia_refs:
            foia_obligations.append(obl)

    return foia_obligations


def get_regulation_obligation_count(session, reg_name: str) -> int:
    """Count obligations linked to a UKRegulation by name."""
    result = session.run(
        """
        MATCH (o:StructuredObligation)-[:MANDATED_BY]->(r:UKRegulation {name: $name})
        RETURN count(o) AS cnt
        """,
        name=reg_name,
    )
    return result.single()["cnt"]


def main() -> None:
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    try:
        with driver.session() as session:
            # ------------------------------------------------------------------
            # STEP 0: Baseline counts
            # ------------------------------------------------------------------
            print("=" * 70)
            print("STEP 0 -- BASELINE STATE")
            print("=" * 70)

            gdpr_before = get_regulation_obligation_count(session, "UK GDPR")
            foia_before = get_regulation_obligation_count(
                session, "Freedom of Information Act 2000"
            )

            print(f"\n  UK GDPR obligations:                       {gdpr_before}")
            print(f"  Freedom of Information Act 2000 obligations: {foia_before}")

            # ------------------------------------------------------------------
            # STEP 1: Identify misclassified FOIA obligations
            # ------------------------------------------------------------------
            print("\n" + "=" * 70)
            print("STEP 1 -- IDENTIFY MISCLASSIFIED FOIA OBLIGATIONS")
            print("=" * 70)

            foia_obligations = find_foia_obligations(session)
            print(f"\nFound {len(foia_obligations)} FOIA obligation(s) linked to UK GDPR:\n")

            if not foia_obligations:
                print("  No misclassified FOIA obligations found. Nothing to do.")
                return

            for obl in foia_obligations:
                desc_trunc = (obl["description"] or "")[:120]
                print(f"  [{obl['obligation_id']}] article_ref={obl['article_reference']}")
                print(f"    desc: {desc_trunc}...")
                print()

            # ------------------------------------------------------------------
            # STEP 2: MERGE the FOIA UKRegulation node with correct properties
            # ------------------------------------------------------------------
            print("=" * 70)
            print("STEP 2 -- MERGE FOIA REGULATION NODE")
            print("=" * 70)

            result = session.run(
                """
                MERGE (r:UKRegulation {name: 'Freedom of Information Act 2000'})
                ON CREATE SET
                    r.jurisdiction = $jurisdiction,
                    r.regulatory_body = $regulatory_body,
                    r.effective_date = $effective_date
                ON MATCH SET
                    r.jurisdiction = $jurisdiction,
                    r.regulatory_body = $regulatory_body,
                    r.effective_date = $effective_date
                RETURN elementId(r) AS eid, r.name AS name
                """,
                **FOIA_REGULATION_PROPS,
            )
            foia_reg = result.single()
            print(
                f"\n  FOIA regulation node: name={foia_reg['name']!r}, elementId={foia_reg['eid']}"
            )
            print(f"  Properties set: {FOIA_REGULATION_PROPS}")

            # ------------------------------------------------------------------
            # STEP 3: Reclassify -- delete old rels, create new ones
            # ------------------------------------------------------------------
            print("\n" + "=" * 70)
            print("STEP 3 -- RECLASSIFY OBLIGATIONS")
            print("=" * 70)

            element_ids = [obl["element_id"] for obl in foia_obligations]

            # Delete MANDATED_BY rels to UK GDPR for these specific obligations
            result = session.run(
                """
                UNWIND $elementIds AS oblEid
                MATCH (o:StructuredObligation)-[rel:MANDATED_BY]->(r:UKRegulation {name: 'UK GDPR'})
                WHERE elementId(o) = oblEid
                DELETE rel
                RETURN count(rel) AS deleted
                """,
                elementIds=element_ids,
            )
            deleted_count = result.single()["deleted"]
            print(f"\n  Deleted {deleted_count} MANDATED_BY relationship(s) to UK GDPR.")

            # Create new MANDATED_BY rels to FOIA
            result = session.run(
                """
                MATCH (target:UKRegulation {name: 'Freedom of Information Act 2000'})
                UNWIND $elementIds AS oblEid
                MATCH (o:StructuredObligation) WHERE elementId(o) = oblEid
                MERGE (o)-[:MANDATED_BY]->(target)
                RETURN count(*) AS created
                """,
                elementIds=element_ids,
            )
            created_count = result.single()["created"]
            print(
                f"  Created/merged {created_count} MANDATED_BY relationship(s) to Freedom of Information Act 2000."
            )

            # ------------------------------------------------------------------
            # STEP 4: Verification
            # ------------------------------------------------------------------
            print("\n" + "=" * 70)
            print("STEP 4 -- VERIFICATION")
            print("=" * 70)

            gdpr_after = get_regulation_obligation_count(session, "UK GDPR")
            foia_after = get_regulation_obligation_count(session, "Freedom of Information Act 2000")

            print(f"\n  {'Metric':<50s} {'Before':>8s} {'After':>8s} {'Delta':>8s}")
            print(f"  {'-' * 50} {'-' * 8} {'-' * 8} {'-' * 8}")
            print(
                f"  {'UK GDPR obligations':<50s} {gdpr_before:>8d} {gdpr_after:>8d} {gdpr_after - gdpr_before:>+8d}"
            )
            print(
                f"  {'Freedom of Information Act 2000 obligations':<50s} {foia_before:>8d} {foia_after:>8d} {foia_after - foia_before:>+8d}"
            )

            # Verify the reclassified obligations are now linked to FOIA
            result = session.run(
                """
                UNWIND $elementIds AS oblEid
                MATCH (o:StructuredObligation) WHERE elementId(o) = oblEid
                OPTIONAL MATCH (o)-[:MANDATED_BY]->(r:UKRegulation)
                RETURN o.obligation_id AS id, collect(r.name) AS linked_regulations
                ORDER BY o.obligation_id
                """,
                elementIds=element_ids,
            )
            verification = result.data()

            print("\n  Reclassified obligation linkages:")
            all_correct = True
            for v in verification:
                linked = v["linked_regulations"]
                ok = "Freedom of Information Act 2000" in linked and "UK GDPR" not in linked
                status = "OK" if ok else "ISSUE"
                if not ok:
                    all_correct = False
                print(f"    [{status}] {v['id']} -> {linked}")

            # Verify FOIA regulation node properties
            result = session.run(
                """
                MATCH (r:UKRegulation {name: 'Freedom of Information Act 2000'})
                RETURN r.jurisdiction AS jurisdiction,
                       r.regulatory_body AS regulatory_body,
                       r.effective_date AS effective_date
                """
            )
            foia_props = result.single()
            print("\n  FOIA regulation node properties:")
            print(f"    jurisdiction:    {foia_props['jurisdiction']}")
            print(f"    regulatory_body: {foia_props['regulatory_body']}")
            print(f"    effective_date:  {foia_props['effective_date']}")

            # ------------------------------------------------------------------
            # SUMMARY
            # ------------------------------------------------------------------
            print("\n" + "=" * 70)
            print("SUMMARY")
            print("=" * 70)
            reclassified = len(foia_obligations)
            expected_gdpr = gdpr_before - reclassified
            success = (
                all_correct
                and gdpr_after == expected_gdpr
                and deleted_count == reclassified
                and created_count == reclassified
            )
            print(f"  Obligations reclassified:    {reclassified}")
            print(f"  MANDATED_BY rels deleted:    {deleted_count}")
            print(f"  MANDATED_BY rels created:    {created_count}")
            print(
                f"  UK GDPR count:               {gdpr_before} -> {gdpr_after} (expected {expected_gdpr})"
            )
            print(f"  FOIA count:                  {foia_before} -> {foia_after}")
            print(f"  All linkages correct:        {all_correct}")
            print(f"  Status:                      {'SUCCESS' if success else 'NEEDS REVIEW'}")

    finally:
        driver.close()


if __name__ == "__main__":
    main()
