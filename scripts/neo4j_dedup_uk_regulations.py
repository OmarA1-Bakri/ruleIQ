"""
Neo4j UKRegulation deduplication and metadata update script.

This script:
1. Merges duplicate UKRegulation nodes (same name, keep the one with more relationships)
2. Merges short-name nodes into their full-name counterparts
3. Updates document_count and total_obligations metadata on all UKRegulation nodes

Uses async neo4j driver v6.x. Requires: neo4j Python package.
"""

import asyncio
from typing import Any

from neo4j import AsyncGraphDatabase

NEO4J_URI = "bolt://localhost:17687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "testpassword123"


# ──────────────────────────────────────────────────────────────────────
# Merge plan: (keeper_element_id, loser_element_id, description)
# These are determined from pre-analysis of relationship counts.
# ──────────────────────────────────────────────────────────────────────

# Same-name duplicates: keep the copy with more relationships
SAME_NAME_MERGES: list[dict[str, Any]] = [
    {
        "name": "UK GDPR",
        "keeper_eid": "4:37794ddc-5e40-447c-93b4-28ef859a3e18:2796",
        "loser_eid": "4:37794ddc-5e40-447c-93b4-28ef859a3e18:574",
        "reason": "keeper has 96 rels vs 53",
    },
    {
        "name": "Companies Act 2006",
        "keeper_eid": "4:37794ddc-5e40-447c-93b4-28ef859a3e18:1027",
        "loser_eid": "4:37794ddc-5e40-447c-93b4-28ef859a3e18:635",
        "reason": "keeper has 3664 rels vs 23",
    },
    {
        "name": "Bribery Act 2010",
        "keeper_eid": "4:37794ddc-5e40-447c-93b4-28ef859a3e18:738",
        "loser_eid": "4:37794ddc-5e40-447c-93b4-28ef859a3e18:1002",
        "reason": "keeper has 13 rels vs 7",
    },
    {
        "name": "Equality Act 2010",
        "keeper_eid": "4:37794ddc-5e40-447c-93b4-28ef859a3e18:650",
        "loser_eid": "4:37794ddc-5e40-447c-93b4-28ef859a3e18:1009",
        "reason": "keeper has 22 rels vs 5",
    },
    {
        "name": "Money Laundering Regulations 2017",
        "keeper_eid": "4:37794ddc-5e40-447c-93b4-28ef859a3e18:699",
        "loser_eid": "4:37794ddc-5e40-447c-93b4-28ef859a3e18:1020",
        "reason": "keeper has 18 rels vs 6",
    },
    {
        "name": "Health and Safety at Work Act 1974",
        "keeper_eid": "4:37794ddc-5e40-447c-93b4-28ef859a3e18:739",
        "loser_eid": "4:37794ddc-5e40-447c-93b4-28ef859a3e18:1014",
        "reason": "keeper has 36 rels vs 6",
    },
    {
        "name": "Regulatory Reform (Fire Safety) Order 2005",
        "keeper_eid": "4:37794ddc-5e40-447c-93b4-28ef859a3e18:813",
        "loser_eid": "4:37794ddc-5e40-447c-93b4-28ef859a3e18:917",
        "reason": "keeper has 20 rels vs 10",
    },
]

# Short-name -> full-name merges: keep the full-name node
SHORT_TO_FULL_MERGES: list[dict[str, Any]] = [
    {
        "short_name": "Bribery Act",
        "full_name": "Bribery Act 2010",
        "loser_eid": "4:37794ddc-5e40-447c-93b4-28ef859a3e18:550",
        "keeper_eid": "4:37794ddc-5e40-447c-93b4-28ef859a3e18:738",
        "reason": "short-name skeleton -> full name",
    },
    {
        "short_name": "Companies Act",
        "full_name": "Companies Act 2006",
        "loser_eid": "4:37794ddc-5e40-447c-93b4-28ef859a3e18:557",
        "keeper_eid": "4:37794ddc-5e40-447c-93b4-28ef859a3e18:1027",
        "reason": "short-name skeleton -> full name",
    },
    {
        "short_name": "Equality Act",
        "full_name": "Equality Act 2010",
        "loser_eid": "4:37794ddc-5e40-447c-93b4-28ef859a3e18:547",
        "keeper_eid": "4:37794ddc-5e40-447c-93b4-28ef859a3e18:650",
        "reason": "short-name skeleton -> full name",
    },
    {
        "short_name": "Modern Slavery Act",
        "full_name": "Modern Slavery Act 2015",
        "loser_eid": "4:37794ddc-5e40-447c-93b4-28ef859a3e18:553",
        "keeper_eid": "4:37794ddc-5e40-447c-93b4-28ef859a3e18:754",
        "reason": "short-name skeleton -> full name",
    },
    {
        "short_name": "Competition Act",
        "full_name": "Competition Act 1998",
        "loser_eid": "4:37794ddc-5e40-447c-93b4-28ef859a3e18:546",
        "keeper_eid": "4:37794ddc-5e40-447c-93b4-28ef859a3e18:893",
        "reason": "short-name skeleton -> full name",
    },
    {
        "short_name": "Terrorism Act",
        "full_name": "Terrorism Act 2000",
        "loser_eid": "4:37794ddc-5e40-447c-93b4-28ef859a3e18:551",
        "keeper_eid": "4:37794ddc-5e40-447c-93b4-28ef859a3e18:956",
        "reason": "short-name skeleton -> full name",
    },
]


async def verify_node_exists(tx: Any, eid: str, expected_name: str) -> bool:
    """Verify a node exists with the expected element ID and name."""
    result = await tx.run(
        "MATCH (n:UKRegulation) WHERE elementId(n) = $eid RETURN n.name AS name",
        eid=eid,
    )
    record = await result.single()
    if record is None:
        print(f"  [ERROR] Node with eid={eid} not found!")
        return False
    actual_name = record["name"]
    if actual_name != expected_name:
        print(
            f"  [ERROR] Node eid={eid} has name='{actual_name}', "
            f"expected='{expected_name}'"
        )
        return False
    return True


async def get_relationship_count(tx: Any, eid: str) -> int:
    """Count all relationships for a node."""
    result = await tx.run(
        "MATCH (n) WHERE elementId(n) = $eid "
        "OPTIONAL MATCH (n)-[r]-() "
        "RETURN count(r) AS cnt",
        eid=eid,
    )
    record = await result.single()
    return record["cnt"] if record else 0


async def move_relationships_and_delete(
    tx: Any, keeper_eid: str, loser_eid: str
) -> dict[str, int]:
    """
    Move all relationships from loser to keeper, then delete loser.

    For each relationship on the loser node:
    - If incoming: (other)-[r]->(loser) becomes (other)-[r]->(keeper)
    - If outgoing: (loser)-[r]->(other) becomes (keeper)-[r]->(other)

    Also merges useful properties from loser onto keeper (without overwriting).
    Returns counts of moved incoming/outgoing relationships.
    """
    stats = {"incoming_moved": 0, "outgoing_moved": 0}

    # Step 1: Discover distinct INCOMING relationship types on the loser
    result = await tx.run(
        "MATCH (other)-[r]->(loser) WHERE elementId(loser) = $loser_eid "
        "RETURN DISTINCT type(r) AS relType",
        loser_eid=loser_eid,
    )
    in_types = [record["relType"] async for record in result]

    # Move each incoming rel type
    for rel_type in in_types:
        move_result = await tx.run(
            f"MATCH (other)-[r:{rel_type}]->(loser) "
            f"WHERE elementId(loser) = $loser_eid "
            f"WITH other, r, properties(r) AS props "
            f"MATCH (keeper) WHERE elementId(keeper) = $keeper_eid "
            f"CREATE (other)-[r2:{rel_type}]->(keeper) "
            f"SET r2 = props "
            f"DELETE r "
            f"RETURN count(r2) AS moved",
            loser_eid=loser_eid,
            keeper_eid=keeper_eid,
        )
        record = await move_result.single()
        moved = record["moved"] if record else 0
        stats["incoming_moved"] += moved
        if moved > 0:
            print(f"    Moved {moved} incoming {rel_type} relationships")

    # Step 2: Discover distinct OUTGOING relationship types on the loser
    result = await tx.run(
        "MATCH (loser)-[r]->(other) WHERE elementId(loser) = $loser_eid "
        "RETURN DISTINCT type(r) AS relType",
        loser_eid=loser_eid,
    )
    out_types = [record["relType"] async for record in result]

    # Move each outgoing rel type
    for rel_type in out_types:
        move_result = await tx.run(
            f"MATCH (loser)-[r:{rel_type}]->(other) "
            f"WHERE elementId(loser) = $loser_eid "
            f"WITH other, r, properties(r) AS props "
            f"MATCH (keeper) WHERE elementId(keeper) = $keeper_eid "
            f"CREATE (keeper)-[r2:{rel_type}]->(other) "
            f"SET r2 = props "
            f"DELETE r "
            f"RETURN count(r2) AS moved",
            loser_eid=loser_eid,
            keeper_eid=keeper_eid,
        )
        record = await move_result.single()
        moved = record["moved"] if record else 0
        stats["outgoing_moved"] += moved
        if moved > 0:
            print(f"    Moved {moved} outgoing {rel_type} relationships")

    # Step 3: Merge useful properties from loser to keeper (don't overwrite)
    await tx.run(
        "MATCH (loser) WHERE elementId(loser) = $loser_eid "
        "MATCH (keeper) WHERE elementId(keeper) = $keeper_eid "
        "WITH loser, keeper, properties(loser) AS lp "
        "SET keeper.document_count = COALESCE(keeper.document_count, lp.document_count) "
        "SET keeper.total_obligations = COALESCE(keeper.total_obligations, lp.total_obligations) "
        "SET keeper.urls = COALESCE(keeper.urls, lp.urls) "
        "SET keeper.loaded_at = COALESCE(keeper.loaded_at, lp.loaded_at) "
        "SET keeper.jurisdiction = COALESCE(keeper.jurisdiction, lp.jurisdiction) "
        "SET keeper.effective_date = COALESCE(keeper.effective_date, lp.effective_date) "
        "SET keeper.full_name = COALESCE(keeper.full_name, lp.full_name) "
        "SET keeper.summary = COALESCE(keeper.summary, lp.summary) "
        "SET keeper.authority = COALESCE(keeper.authority, lp.authority) "
        "SET keeper.source = COALESCE(keeper.source, lp.source) "
        "SET keeper.source_url = COALESCE(keeper.source_url, lp.source_url)",
        loser_eid=loser_eid,
        keeper_eid=keeper_eid,
    )

    # Step 4: Safety net -- delete any remaining relationships on loser
    await tx.run(
        "MATCH (loser) WHERE elementId(loser) = $loser_eid "
        "OPTIONAL MATCH (loser)-[r]-() "
        "DELETE r",
        loser_eid=loser_eid,
    )

    # Step 5: Delete the loser node
    await tx.run(
        "MATCH (loser) WHERE elementId(loser) = $loser_eid DELETE loser",
        loser_eid=loser_eid,
    )

    print(f"    Deleted loser node (eid={loser_eid})")
    return stats


async def run_same_name_merges(session: Any) -> None:
    """Merge duplicate nodes that have the exact same name."""
    print("\n" + "=" * 70)
    print("PHASE 1: Merging same-name duplicates")
    print("=" * 70)

    for merge in SAME_NAME_MERGES:
        name = merge["name"]
        keeper_eid = merge["keeper_eid"]
        loser_eid = merge["loser_eid"]
        reason = merge["reason"]

        print(f"\n--- Merging '{name}' ({reason}) ---")

        # Merge transaction
        tx = await session.begin_transaction()
        try:
            keeper_ok = await verify_node_exists(tx, keeper_eid, name)
            loser_ok = await verify_node_exists(tx, loser_eid, name)

            if not keeper_ok or not loser_ok:
                print(f"  [SKIP] Validation failed for '{name}', skipping.")
                await tx.rollback()
                continue

            keeper_rels = await get_relationship_count(tx, keeper_eid)
            loser_rels = await get_relationship_count(tx, loser_eid)
            print(f"  Keeper: eid={keeper_eid}, rels={keeper_rels}")
            print(f"  Loser:  eid={loser_eid}, rels={loser_rels}")

            stats = await move_relationships_and_delete(
                tx, keeper_eid, loser_eid
            )
            print(
                f"  Result: moved {stats['incoming_moved']} incoming, "
                f"{stats['outgoing_moved']} outgoing"
            )
            await tx.commit()
        except Exception as exc:
            await tx.rollback()
            print(f"  [ERROR] Transaction failed: {exc}")
            raise

        # Post-verification (read-only)
        tx = await session.begin_transaction()
        try:
            final_rels = await get_relationship_count(tx, keeper_eid)
            print(f"  Verification: keeper now has {final_rels} relationships")

            result = await tx.run(
                "MATCH (n:UKRegulation) WHERE elementId(n) = $eid "
                "RETURN count(n) AS cnt",
                eid=loser_eid,
            )
            record = await result.single()
            if record["cnt"] > 0:
                print("  [ERROR] Loser node still exists!")
            else:
                print("  [OK] Loser node successfully deleted")
        finally:
            await tx.rollback()


async def run_short_to_full_merges(session: Any) -> None:
    """Merge short-name nodes into their full-name counterparts."""
    print("\n" + "=" * 70)
    print("PHASE 2: Merging short-name -> full-name")
    print("=" * 70)

    for merge in SHORT_TO_FULL_MERGES:
        short_name = merge["short_name"]
        full_name = merge["full_name"]
        keeper_eid = merge["keeper_eid"]
        loser_eid = merge["loser_eid"]
        reason = merge["reason"]

        print(f"\n--- Merging '{short_name}' -> '{full_name}' ({reason}) ---")

        # Merge transaction
        tx = await session.begin_transaction()
        try:
            keeper_ok = await verify_node_exists(tx, keeper_eid, full_name)
            loser_ok = await verify_node_exists(tx, loser_eid, short_name)

            if not keeper_ok or not loser_ok:
                print("  [SKIP] Validation failed, skipping.")
                await tx.rollback()
                continue

            keeper_rels = await get_relationship_count(tx, keeper_eid)
            loser_rels = await get_relationship_count(tx, loser_eid)
            print(
                f"  Keeper ({full_name}): eid={keeper_eid}, rels={keeper_rels}"
            )
            print(
                f"  Loser  ({short_name}): eid={loser_eid}, rels={loser_rels}"
            )

            stats = await move_relationships_and_delete(
                tx, keeper_eid, loser_eid
            )
            print(
                f"  Result: moved {stats['incoming_moved']} incoming, "
                f"{stats['outgoing_moved']} outgoing"
            )
            await tx.commit()
        except Exception as exc:
            await tx.rollback()
            print(f"  [ERROR] Transaction failed: {exc}")
            raise

        # Post-verification (read-only)
        tx = await session.begin_transaction()
        try:
            final_rels = await get_relationship_count(tx, keeper_eid)
            print(f"  Verification: keeper now has {final_rels} relationships")

            result = await tx.run(
                "MATCH (n:UKRegulation) WHERE elementId(n) = $eid "
                "RETURN count(n) AS cnt",
                eid=loser_eid,
            )
            record = await result.single()
            if record["cnt"] > 0:
                print("  [ERROR] Loser node still exists!")
            else:
                print("  [OK] Loser node successfully deleted")
        finally:
            await tx.rollback()


async def update_metadata(session: Any) -> None:
    """
    Update document_count and total_obligations on every UKRegulation node.

    Sets these to the count of incoming MANDATED_BY relationships,
    but only if the property is currently NULL.
    """
    print("\n" + "=" * 70)
    print("PHASE 3: Updating metadata (document_count, total_obligations)")
    print("=" * 70)

    tx = await session.begin_transaction()
    try:
        result = await tx.run(
            "MATCH (reg:UKRegulation) "
            "OPTIONAL MATCH (ob)-[:MANDATED_BY]->(reg) "
            "WITH reg, count(ob) AS obligationCount "
            "WHERE reg.document_count IS NULL OR reg.total_obligations IS NULL "
            "SET reg.document_count = COALESCE(reg.document_count, obligationCount) "
            "SET reg.total_obligations = COALESCE(reg.total_obligations, obligationCount) "
            "RETURN reg.name AS name, obligationCount, "
            "       reg.document_count AS doc_count, "
            "       reg.total_obligations AS total_obs "
            "ORDER BY reg.name"
        )
        updated = 0
        async for record in result:
            updated += 1
            print(
                f"  Updated '{record['name']}': "
                f"obligations={record['obligationCount']}, "
                f"doc_count={record['doc_count']}, "
                f"total_obs={record['total_obs']}"
            )

        if updated == 0:
            print("  No nodes needed metadata updates (all already populated).")
        else:
            print(f"  Updated metadata on {updated} nodes.")

        await tx.commit()
    except Exception as exc:
        await tx.rollback()
        print(f"  [ERROR] Metadata update failed: {exc}")
        raise


async def final_verification(session: Any) -> None:
    """Run final verification queries to confirm the dedup results."""
    print("\n" + "=" * 70)
    print("FINAL VERIFICATION")
    print("=" * 70)

    tx = await session.begin_transaction()
    try:
        # Total node count
        result = await tx.run(
            "MATCH (n:UKRegulation) RETURN count(n) AS cnt"
        )
        record = await result.single()
        print(f"\n  Total UKRegulation nodes: {record['cnt']}")

        # Total relationship count
        result = await tx.run(
            "MATCH (n:UKRegulation)-[r]-() RETURN count(r) AS cnt"
        )
        record = await result.single()
        print(f"  Total relationships: {record['cnt']}")

        # Check for remaining duplicates (excluding Unknown)
        result = await tx.run(
            "MATCH (n:UKRegulation) "
            "WITH n.name AS name, collect(elementId(n)) AS eids, count(*) AS cnt "
            "WHERE cnt > 1 "
            "RETURN name, cnt, eids "
            "ORDER BY name"
        )
        dupes_found = False
        async for record in result:
            if record["name"] == "Unknown":
                continue
            dupes_found = True
            print(
                f"  [WARN] Remaining duplicate: '{record['name']}' "
                f"({record['cnt']} copies)"
            )

        if not dupes_found:
            print(
                "  [OK] No remaining duplicates (excluding 'Unknown' nodes)"
            )

        # Full listing of all remaining nodes
        print("\n  All UKRegulation nodes after dedup:")
        header = f"  {'Name':<60} {'Rels':>5} {'DocCnt':>6} {'TotObs':>6}"
        print(header)
        print(f"  {'-'*60} {'-'*5} {'-'*6} {'-'*6}")

        result = await tx.run(
            "MATCH (n:UKRegulation) "
            "OPTIONAL MATCH (n)-[r]-() "
            "WITH n, count(r) AS relCount "
            "RETURN n.name AS name, relCount, "
            "       n.document_count AS doc_count, "
            "       n.total_obligations AS total_obs "
            "ORDER BY n.name"
        )
        async for record in result:
            name = record["name"]
            rels = record["relCount"]
            dc = record["doc_count"]
            to_val = record["total_obs"]
            dc_str = str(dc) if dc is not None else "NULL"
            to_str = str(to_val) if to_val is not None else "NULL"
            print(f"  {name:<60} {rels:>5} {dc_str:>6} {to_str:>6}")

        # Check expected keeper nodes exist (exactly 1 copy each)
        expected_names = [
            "UK GDPR",
            "Companies Act 2006",
            "Bribery Act 2010",
            "Equality Act 2010",
            "Money Laundering Regulations 2017",
            "Health and Safety at Work Act 1974",
            "Regulatory Reform (Fire Safety) Order 2005",
            "Modern Slavery Act 2015",
            "Competition Act 1998",
            "Terrorism Act 2000",
        ]
        print("\n  Checking expected keeper nodes exist:")
        for name in expected_names:
            result = await tx.run(
                "MATCH (n:UKRegulation {name: $name}) "
                "RETURN count(n) AS cnt",
                name=name,
            )
            record = await result.single()
            if record["cnt"] == 1:
                print(f"    [OK] '{name}' exists (1 copy)")
            elif record["cnt"] == 0:
                print(f"    [ERROR] '{name}' NOT FOUND!")
            else:
                print(
                    f"    [WARN] '{name}' has {record['cnt']} copies"
                )

        # Verify short-name nodes are gone
        short_names = [
            "Bribery Act",
            "Companies Act",
            "Equality Act",
            "Modern Slavery Act",
            "Competition Act",
            "Terrorism Act",
        ]
        print("\n  Checking short-name nodes were removed:")
        for name in short_names:
            result = await tx.run(
                "MATCH (n:UKRegulation {name: $name}) "
                "RETURN count(n) AS cnt",
                name=name,
            )
            record = await result.single()
            if record["cnt"] == 0:
                print(f"    [OK] '{name}' removed")
            else:
                print(
                    f"    [ERROR] '{name}' still exists "
                    f"({record['cnt']} copies)"
                )

    finally:
        await tx.rollback()  # read-only, no commit needed


async def main() -> None:
    """Main entry point for the deduplication script."""
    print("Neo4j UKRegulation Deduplication Script")
    print(f"Connecting to {NEO4J_URI}...")

    driver = AsyncGraphDatabase.driver(
        NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD)
    )

    try:
        # Verify connectivity
        async with driver.session() as session:
            tx = await session.begin_transaction()
            try:
                result = await tx.run("RETURN 1 AS ok")
                record = await result.single()
                assert record["ok"] == 1
                print("Connected successfully.\n")
            finally:
                await tx.rollback()

        # Phase 1: Same-name duplicates
        async with driver.session() as session:
            await run_same_name_merges(session)

        # Phase 2: Short-name to full-name merges
        async with driver.session() as session:
            await run_short_to_full_merges(session)

        # Phase 3: Metadata updates
        async with driver.session() as session:
            await update_metadata(session)

        # Final verification
        async with driver.session() as session:
            await final_verification(session)

    finally:
        await driver.close()
        print("\nDone. Driver closed.")


if __name__ == "__main__":
    asyncio.run(main())
