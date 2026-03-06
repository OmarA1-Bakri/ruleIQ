#!/usr/bin/env python3
"""Simple database setup for tests"""

import asyncio
import os
import sys
from sqlalchemy import create_engine, text

# Set environment variables
os.environ["ENV"] = "testing"
os.environ["DATABASE_URL"] = (
    "postgresql://neondb_owner:npg_s0JhnfGNy3Ze@ep-wild-grass-a8o37wq8-pooler.eastus2.azure.neon.tech/neondb?sslmode=require",
)

sys.path.append(os.path.dirname(os.path.abspath(__file__)))


async def setup_database():
    """Setup database using Alembic migrations"""
    import subprocess

    # First, clean any existing schema
    sync_db_url = os.environ["DATABASE_URL"]
    engine = create_engine(sync_db_url)

    try:
        with engine.connect() as conn:
            # Drop all types first
            conn.execute(text("DROP TYPE IF EXISTS integrationstatus CASCADE"))
            conn.execute(text("DROP TYPE IF EXISTS evidencestatus CASCADE"))
            conn.execute(text("DROP TYPE IF EXISTS reportstatus CASCADE"))
            conn.execute(text("DROP TYPE IF EXISTS implementationstatus CASCADE"))
            conn.execute(text("DROP TYPE IF EXISTS auditentitytype CASCADE"))
            conn.execute(text("DROP TYPE IF EXISTS auditaction CASCADE"))
            conn.execute(text("DROP TYPE IF EXISTS userroleenum CASCADE"))
            conn.execute(text("DROP TYPE IF EXISTS userpersona CASCADE"))
            conn.execute(text("DROP TYPE IF EXISTS assessmentstatus CASCADE"))
            conn.execute(text("DROP TYPE IF EXISTS planupdatereason CASCADE"))
            conn.execute(text("DROP TYPE IF EXISTS planstatus CASCADE"))
            conn.execute(text("DROP TYPE IF EXISTS evidencepriority CASCADE"))
            conn.execute(text("DROP TYPE IF EXISTS evidencecollectionstatus CASCADE"))
            conn.execute(text("DROP TYPE IF EXISTS collectionmethod CASCADE"))
            conn.execute(text("DROP TYPE IF EXISTS regulatoryregion CASCADE"))
            conn.execute(text("DROP TYPE IF EXISTS regulatorystatus CASCADE"))

            # Drop alembic version table to start fresh
            conn.execute(text("DROP TABLE IF EXISTS alembic_version CASCADE"))
            conn.commit()
        print("✓ Cleaned existing database schema")
    except Exception as e:
        print(f"Warning during cleanup: {e}")

    # Run Alembic migrations
    result = subprocess.run(
        ["alembic", "upgrade", "head"],
        capture_output=True,
        text=True,
    )

    if result.returncode == 0:
        print("✓ Successfully ran Alembic migrations")
        print(result.stdout)
    else:
        print("✗ Failed to run Alembic migrations")
        print(result.stderr)
        return False

    # Import after migrations are done
    from database.db_setup import Base, _init_async_db, get_async_db
    from database.user import User
    from services.auth_service import hash_password

    # Initialize async database
    _init_async_db()

    # Create a test user
    async for db in get_async_db():
        try:
            # Check if test user exists
            from sqlalchemy import select

            result = await db.execute(
                select(User).where(User.email == "test@example.com"),
            )
            user = result.scalar_one_or_none()

            if not user:
                # Create test user
                test_user = User(
                    email="test@example.com",
                    password_hash=hash_password("testpassword123"),
                    full_name="Test User",
                    role="user",
                    is_active=True,
                    is_verified=True,
                )
                db.add(test_user)
                await db.commit()
                print("✓ Created test user: test@example.com")
            else:
                print("✓ Test user already exists")

            return True
        except Exception as e:
            print(f"✗ Error creating test user: {e}")
            await db.rollback()
            return False


if __name__ == "__main__":
    success = asyncio.run(setup_database())
    sys.exit(0 if success else 1)
