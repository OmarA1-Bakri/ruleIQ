"""
Fix StructuredObligation -> UKRegulation links.

Problem: 157 StructuredObligation nodes are linked via MANDATED_BY to 19
UKRegulation nodes with name='Unknown'. Their descriptions are UK GDPR content.

Solution:
1. Identify the correct UK GDPR node (the one that already has obligations linked).
2. Sample obligation descriptions to confirm they are indeed GDPR-related.
3. Delete all MANDATED_BY rels from StructuredObligation -> UKRegulation(name='Unknown').
4. Create new MANDATED_BY rels from those obligations to the correct UK GDPR node.
5. Delete all orphaned UKRegulation(name='Unknown') nodes.
6. Verify final state.
"""

import asyncio
import sys

from neo4j import AsyncGraphDatabase

NEO4J_URI = "bolt://localhost:17687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "testpassword123"


async def main() -> None:
    driver = AsyncGraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    try:
        async with driver.session() as session:
            # ----------------------------------------------------------------
            # STEP 0: Baseline counts
            # ----------------------------------------------------------------
            print("=" * 70)
            print("STEP 0 — BASELINE STATE")
            print("=" * 70)

            # Count all UKRegulation nodes
            result = await session.run(
                "MATCH (r:UKRegulation) RETURN r.name AS name, elementId(r) AS eid, count{(r)<-[:MANDATED_BY]-()} AS oblCount ORDER BY oblCount DESC"
            )
            uk_regs = await result.data()
            print(f"\nAll UKRegulation nodes ({len(uk_regs)} total):")
            for row in uk_regs:
                print(f"  name={row['name']!r:30s}  elementId={row['eid']}  linkedObligations={row['oblCount']}")

            # Count Unknown nodes
            result = await session.run(
                "MATCH (r:UKRegulation {name: 'Unknown'}) RETURN count(r) AS cnt"
            )
            unknown_count = (await result.single())["cnt"]
            print(f"\nUKRegulation(name='Unknown') count: {unknown_count}")

            # Count obligations linked to Unknown
            result = await session.run(
                "MATCH (o:StructuredObligation)-[:MANDATED_BY]->(r:UKRegulation {name: 'Unknown'}) "
                "RETURN count(DISTINCT o) AS oblCount, count(*) AS relCount"
            )
            row = await result.single()
            unknown_obl_count = row["oblCount"]
            unknown_rel_count = row["relCount"]
            print(f"StructuredObligations linked to Unknown: {unknown_obl_count} (via {unknown_rel_count} rels)")

            # ----------------------------------------------------------------
            # STEP 1: Identify the correct UK GDPR node
            # ----------------------------------------------------------------
            print("\n" + "=" * 70)
            print("STEP 1 — IDENTIFY CORRECT UK GDPR NODE")
            print("=" * 70)

            result = await session.run(
                "MATCH (r:UKRegulation) WHERE r.name = 'UK GDPR' OR r.name = 'UK_GDPR' OR r.name CONTAINS 'GDPR' "
                "RETURN r.name AS name, elementId(r) AS eid, count{(r)<-[:MANDATED_BY]-()} AS oblCount "
                "ORDER BY oblCount DESC"
            )
            gdpr_nodes = await result.data()
            print(f"\nGDPR-related UKRegulation nodes ({len(gdpr_nodes)}):")
            for row in gdpr_nodes:
                print(f"  name={row['name']!r:30s}  elementId={row['eid']}  linkedObligations={row['oblCount']}")

            if not gdpr_nodes:
                print("ERROR: No UK GDPR node found! Aborting.")
                return

            # Pick the one with the most existing obligations
            target_gdpr = gdpr_nodes[0]
            target_eid = target_gdpr["eid"]
            target_name = target_gdpr["name"]
            target_existing_count = target_gdpr["oblCount"]
            print(f"\n>>> Target UK GDPR node: name={target_name!r}, elementId={target_eid}, existing obligations={target_existing_count}")

            # ----------------------------------------------------------------
            # STEP 2: Sample obligation descriptions to verify GDPR content
            # ----------------------------------------------------------------
            print("\n" + "=" * 70)
            print("STEP 2 — SAMPLE OBLIGATION DESCRIPTIONS (verify GDPR content)")
            print("=" * 70)

            result = await session.run(
                "MATCH (o:StructuredObligation)-[:MANDATED_BY]->(r:UKRegulation {name: 'Unknown'}) "
                "RETURN o.obligation_id AS id, o.description AS desc, o.section AS section "
                "ORDER BY rand() LIMIT 25"
            )
            samples = await result.data()
            gdpr_keywords = [
                "gdpr", "data protection", "personal data", "data subject",
                "controller", "processor", "lawful basis", "consent",
                "right to", "erasure", "rectification", "portability",
                "supervisory authority", "dpa", "ico", "information commissioner",
                "data breach", "impact assessment", "dpia", "processing",
                "legitimate interest", "special category", "transfer",
                "privacy", "article", "uk gdpr",
            ]

            non_gdpr_samples = []
            print(f"\nSampling {len(samples)} obligations linked to Unknown:")
            for s in samples:
                desc_lower = (s["desc"] or "").lower()
                section_lower = (s["section"] or "").lower()
                combined = desc_lower + " " + section_lower
                is_gdpr = any(kw in combined for kw in gdpr_keywords)
                marker = "GDPR" if is_gdpr else "NON-GDPR?"
                truncated = (s["desc"] or "")[:120]
                print(f"  [{marker}] id={s['id']}, section={s['section']}, desc={truncated}...")
                if not is_gdpr:
                    non_gdpr_samples.append(s)

            if non_gdpr_samples:
                print(f"\nWARNING: {len(non_gdpr_samples)} samples did NOT match GDPR keywords.")
                print("Full descriptions of non-GDPR samples:")
                for s in non_gdpr_samples:
                    print(f"  id={s['id']}")
                    print(f"  section={s['section']}")
                    print(f"  desc={s['desc']}")
                    print()
                # Still proceed — the user confirmed these are GDPR obligations
                print("Proceeding anyway as user confirmed all 157 are GDPR content.")
            else:
                print("\nAll sampled obligations contain GDPR-related keywords. Confirmed.")

            # Also check: do any of the 157 already link to the target UK GDPR node?
            result = await session.run(
                "MATCH (o:StructuredObligation)-[:MANDATED_BY]->(r:UKRegulation {name: 'Unknown'}) "
                "WHERE EXISTS { (o)-[:MANDATED_BY]->(t:UKRegulation) WHERE elementId(t) = $targetEid } "
                "RETURN count(o) AS cnt",
                targetEid=target_eid,
            )
            already_linked = (await result.single())["cnt"]
            print(f"\nObligations already also linked to target UK GDPR: {already_linked}")

            # ----------------------------------------------------------------
            # STEP 3: Collect obligation IDs, then relink
            # ----------------------------------------------------------------
            print("\n" + "=" * 70)
            print("STEP 3 — RELINK OBLIGATIONS: Unknown -> UK GDPR")
            print("=" * 70)

            # Collect all obligation elementIds linked to Unknown
            result = await session.run(
                "MATCH (o:StructuredObligation)-[:MANDATED_BY]->(r:UKRegulation {name: 'Unknown'}) "
                "RETURN DISTINCT elementId(o) AS eid"
            )
            obl_eids = [record["eid"] async for record in result]
            print(f"\nCollected {len(obl_eids)} unique obligation elementIds to relink.")

            # Delete MANDATED_BY rels to Unknown
            result = await session.run(
                "MATCH (o:StructuredObligation)-[rel:MANDATED_BY]->(r:UKRegulation {name: 'Unknown'}) "
                "DELETE rel "
                "RETURN count(rel) AS deleted"
            )
            deleted_rels = (await result.single())["deleted"]
            print(f"Deleted {deleted_rels} MANDATED_BY relationships to Unknown nodes.")

            # Create new MANDATED_BY rels to the target UK GDPR node
            # Use UNWIND + elementId matching for efficiency
            result = await session.run(
                "MATCH (target:UKRegulation) WHERE elementId(target) = $targetEid "
                "UNWIND $oblEids AS oblEid "
                "MATCH (o:StructuredObligation) WHERE elementId(o) = oblEid "
                "MERGE (o)-[:MANDATED_BY]->(target) "
                "RETURN count(*) AS created",
                targetEid=target_eid,
                oblEids=obl_eids,
            )
            created_rels = (await result.single())["created"]
            print(f"Created/merged {created_rels} MANDATED_BY relationships to UK GDPR node.")

            # ----------------------------------------------------------------
            # STEP 4: Delete orphaned Unknown nodes
            # ----------------------------------------------------------------
            print("\n" + "=" * 70)
            print("STEP 4 — DELETE ORPHANED UNKNOWN NODES")
            print("=" * 70)

            # Check if Unknown nodes have any remaining relationships
            result = await session.run(
                "MATCH (r:UKRegulation {name: 'Unknown'}) "
                "OPTIONAL MATCH (r)-[rel]-() "
                "RETURN elementId(r) AS eid, count(rel) AS relCount"
            )
            unknown_status = await result.data()
            for row in unknown_status:
                print(f"  Unknown node {row['eid']}: {row['relCount']} remaining relationships")

            # Delete the Unknown nodes (DETACH DELETE to handle any straggling rels)
            result = await session.run(
                "MATCH (r:UKRegulation {name: 'Unknown'}) "
                "DETACH DELETE r "
                "RETURN count(r) AS deleted"
            )
            deleted_nodes = (await result.single())["deleted"]
            print(f"\nDeleted {deleted_nodes} UKRegulation(name='Unknown') nodes.")

            # ----------------------------------------------------------------
            # STEP 5: Verify final state
            # ----------------------------------------------------------------
            print("\n" + "=" * 70)
            print("STEP 5 — VERIFICATION")
            print("=" * 70)

            # Remaining Unknown nodes
            result = await session.run(
                "MATCH (r:UKRegulation {name: 'Unknown'}) RETURN count(r) AS cnt"
            )
            remaining_unknown = (await result.single())["cnt"]
            print(f"\nRemaining UKRegulation(name='Unknown'): {remaining_unknown}")

            # UK GDPR obligations count
            result = await session.run(
                "MATCH (r:UKRegulation) WHERE elementId(r) = $targetEid "
                "RETURN count{(r)<-[:MANDATED_BY]-()} AS oblCount",
                targetEid=target_eid,
            )
            final_gdpr_count = (await result.single())["oblCount"]
            print(f"UK GDPR node obligations (target): {final_gdpr_count}")
            print(f"  Expected: ~{target_existing_count} + {len(obl_eids)} = ~{target_existing_count + len(obl_eids)}")

            # All UKRegulation nodes final state
            result = await session.run(
                "MATCH (r:UKRegulation) RETURN r.name AS name, elementId(r) AS eid, count{(r)<-[:MANDATED_BY]-()} AS oblCount ORDER BY oblCount DESC"
            )
            final_regs = await result.data()
            print(f"\nAll UKRegulation nodes after fix ({len(final_regs)} total):")
            for row in final_regs:
                print(f"  name={row['name']!r:30s}  elementId={row['eid']}  linkedObligations={row['oblCount']}")

            # Check for any duplicate UK GDPR node
            gdpr_final = [r for r in final_regs if "GDPR" in (r["name"] or "").upper()]
            if len(gdpr_final) > 1:
                print(f"\nNOTE: {len(gdpr_final)} GDPR-related nodes still exist (duplicates).")
                print("The second copy may need cleanup in a future task.")

            # Success summary
            print("\n" + "=" * 70)
            print("SUMMARY")
            print("=" * 70)
            success = remaining_unknown == 0 and final_gdpr_count >= target_existing_count + len(obl_eids) - already_linked
            print(f"  Unknown nodes removed: {deleted_nodes}")
            print(f"  MANDATED_BY rels deleted: {deleted_rels}")
            print(f"  MANDATED_BY rels created/merged: {created_rels}")
            print(f"  UK GDPR final obligation count: {final_gdpr_count}")
            print(f"  Status: {'SUCCESS' if success else 'NEEDS REVIEW'}")

    finally:
        await driver.close()


if __name__ == "__main__":
    asyncio.run(main())
