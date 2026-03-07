#!/usr/bin/env python3
"""
Update all test files to use AuraDB instead of local Docker Neo4j.
This script should be run carefully as test environments might need different configs.
"""

import os


def update_neo4j_urls(file_path, dry_run=True):
    """Update Neo4j URLs in a file from bolt://localhost to AuraDB."""

    replacements = {
        r"bolt://localhost:7688": "neo4j+s://12e71bc4.databases.neo4j.io",
        r"bolt://localhost:7687": "neo4j+s://12e71bc4.databases.neo4j.io",
        r'"bolt://localhost:7688"': '"neo4j+s://12e71bc4.databases.neo4j.io"',
        r'"bolt://localhost:7687"': '"neo4j+s://12e71bc4.databases.neo4j.io"',
        r"'bolt://localhost:7688'": "'neo4j+s://12e71bc4.databases.neo4j.io'",
        r"'bolt://localhost:7687'": "'neo4j+s://12e71bc4.databases.neo4j.io'",
    }

    try:
        with open(file_path, "r") as f:
            content = f.read()

        changes_made = False

        for pattern, replacement in replacements.items():
            if pattern in content:
                content = content.replace(pattern, replacement)
                changes_made = True
                print(f"  ✓ Replaced {pattern}")

        if changes_made:
            if not dry_run:
                with open(file_path, "w") as f:
                    f.write(content)
                print(f"  ✅ Updated {file_path}")
            else:
                print(f"  🔍 Would update {file_path}")
            return True
        else:
            print(f"  ⏭️  No changes needed for {file_path}")
            return False

    except Exception as e:
        print(f"  ❌ Error processing {file_path}: {e}")
        return False


def main():
    """Main function to update all test files."""

    print("🔄 Neo4j Test Configuration Update Script")
    print("=========================================")
    print()

    # Files that need updating based on search results
    files_to_update = [
        # Services
        "services/ai/automation_scorer.py",
        "services/ai/temporal_tracker.py",
        "services/ai/compliance_ingestion_pipeline.py",
        "services/ai/test_ingestion_integration.py",
        "services/ai/evaluation/tools/ingestion_fixed.py",
        "services/ai/evaluation/tests/test_neo4j_setup.py",
        "services/ai/evaluation/tests/test_neo4j_connection.py",
        "services/ai/evaluation/infrastructure/neo4j_setup.py",
        "services/compliance/uk_compliance_ingestion_pipeline.py",
        "services/agentic_rag.py",
        "services/scrapers/regulation_scraper.py",
        # Tests
        "tests/test_complete_integration.py",
        "tests/test_master_integration.py",
        "tests/test_iq_integration.py",
        "tests/test_ingest.py",
        "tests/test_golden_standalone.py",
        "tests/test_uk_compliance_integration.py",
        "tests/test_evidence_orchestrator_v2.py",
        "tests/test_direct_connection.py",
        "tests/test_golden_with_env.py",
        "tests/test_ingestion_simple.py",
        "tests/test_master_integration_runner.py",
        "tests/mocks/mock_services.py",
        "tests/test_neo4j_basic.py",
        "tests/setup_test_environment.py",
    ]

    # Check if running in dry-run mode
    import sys

    dry_run = "--dry-run" in sys.argv or "-d" in sys.argv

    if dry_run:
        print("🔍 Running in DRY-RUN mode (no files will be modified)")
    else:
        print("⚠️  Running in LIVE mode (files will be modified)")
        response = input("Are you sure you want to proceed? (yes/no): ")
        if response.lower() != "yes":
            print("❌ Aborted")
            return

    print()

    updated_count = 0
    for file_path in files_to_update:
        if os.path.exists(file_path):
            print(f"Processing {file_path}:")
            if update_neo4j_urls(file_path, dry_run):
                updated_count += 1
            print()
        else:
            print(f"⏭️  File not found: {file_path}")

    print(f"\n📊 Summary: {updated_count} files {'would be' if dry_run else 'were'} updated")

    if dry_run:
        print("\n💡 To apply changes, run without --dry-run flag:")
        print("   python scripts/update-test-neo4j-config.py")
    else:
        print("\n✅ Update complete!")
        print("\n⚠️  Important next steps:")
        print("1. Update Doppler secrets with AuraDB password")
        print("2. Run: ./scripts/doppler-neo4j-setup.sh")
        print("3. Test the connection")


if __name__ == "__main__":
    main()
