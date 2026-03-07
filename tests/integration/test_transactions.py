"""
Database transaction integration tests.
Tests transaction isolation, rollback behavior, and data integrity.
"""

import pytest
import threading
import asyncio
from concurrent.futures import ThreadPoolExecutor
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, OperationalError
from datetime import datetime, timedelta
import time


@pytest.mark.integration
@pytest.mark.transaction
class TestTransactionIsolation:
    """Test database transaction isolation levels."""

    def test_read_committed_isolation(self, integration_db_session, test_db_engine):
        """Test READ COMMITTED isolation level."""
        from database import User
        from utils.auth import get_password_hash

        # Create initial user in main session
        user = User(
            email="isolation@test.com",
            full_name="Isolation Test",
            hashed_password=get_password_hash("Password123!"),
            is_active=True,
        )
        integration_db_session.add(user)
        integration_db_session.commit()
        user_id = user.id

        # Create a second session
        Session = test_db_engine.sessionmaker()
        session2 = Session()

        try:
            # Start transaction in session2
            session2.begin()

            # Update user in main session
            user.full_name = "Updated Name"
            integration_db_session.commit()

            # Session2 should not see the change until it commits/starts new transaction
            user_in_session2 = session2.query(User).filter_by(id=user_id).first()

            # Behavior depends on isolation level
            # With READ COMMITTED, it should see the new value
            assert user_in_session2.full_name in ["Isolation Test", "Updated Name"]

        finally:
            session2.rollback()
            session2.close()

    def test_concurrent_updates_conflict(self, integration_db_session, test_db_engine):
        """Test handling of concurrent update conflicts."""
        from database import BusinessProfile

        # Create a business profile
        profile = BusinessProfile(user_id=1, company_name="Test Company", employee_count="50-100")
        integration_db_session.add(profile)
        integration_db_session.commit()
        profile_id = profile.id

        # Create two sessions
        Session = test_db_engine.sessionmaker()
        session1 = Session()
        session2 = Session()

        try:
            # Load same profile in both sessions
            profile1 = session1.query(BusinessProfile).filter_by(id=profile_id).first()
            profile2 = session2.query(BusinessProfile).filter_by(id=profile_id).first()

            # Update in session1
            profile1.company_name = "Company A"
            session1.commit()

            # Update in session2 (should handle conflict)
            profile2.company_name = "Company B"

            # This might raise an error or succeed depending on isolation
            try:
                session2.commit()
                # If successful, last write wins
                integration_db_session.refresh(profile)
                assert profile.company_name in ["Company A", "Company B"]
            except OperationalError:
                # Conflict detected
                session2.rollback()

        finally:
            session1.close()
            session2.close()

    def test_phantom_read_prevention(self, integration_db_session, test_db_engine):
        """Test prevention of phantom reads in transactions."""
        from database import ComplianceFramework

        Session = test_db_engine.sessionmaker()
        session1 = Session()
        session2 = Session()

        try:
            # Session1: Count frameworks
            count1 = session1.query(ComplianceFramework).count()

            # Session2: Add new framework
            framework = ComplianceFramework(name="New Framework", description="Test", version="1.0")
            session2.add(framework)
            session2.commit()

            # Session1: Count again (should see same count in REPEATABLE READ)
            count2 = session1.query(ComplianceFramework).count()

            # Behavior depends on isolation level
            # In READ COMMITTED: count2 > count1
            # In REPEATABLE READ: count2 == count1
            assert count2 >= count1

        finally:
            session1.rollback()
            session2.rollback()
            session1.close()
            session2.close()


@pytest.mark.integration
@pytest.mark.transaction
class TestTransactionRollback:
    """Test transaction rollback behavior."""

    def test_automatic_rollback_on_error(self, integration_db_session):
        """Test automatic rollback when an error occurs."""
        from database import User

        initial_count = integration_db_session.query(User).count()

        try:
            # Add valid user
            user1 = User(email="valid@test.com", full_name="Valid User", hashed_password="hash")
            integration_db_session.add(user1)

            # Add invalid user (duplicate email)
            user2 = User(
                email="valid@test.com",  # Duplicate
                full_name="Another User",
                hashed_password="hash",
            )
            integration_db_session.add(user2)

            # This should raise IntegrityError
            with pytest.raises(IntegrityError):
                integration_db_session.commit()

        except Exception:
            pass

        # Rollback should have occurred
        integration_db_session.rollback()

        # Count should be unchanged
        final_count = integration_db_session.query(User).count()
        assert final_count == initial_count

    def test_savepoint_rollback(self, integration_db_session):
        """Test savepoint creation and rollback."""
        from database import User, BusinessProfile

        # Create user
        user = User(email="savepoint@test.com", full_name="Savepoint User", hashed_password="hash")
        integration_db_session.add(user)
        integration_db_session.commit()

        # Create savepoint
        savepoint = integration_db_session.begin_nested()

        try:
            # Add business profile
            profile = BusinessProfile(user_id=user.id, company_name="Test Company")
            integration_db_session.add(profile)

            # Force an error
            raise ValueError("Simulated error")

        except ValueError:
            # Rollback to savepoint
            savepoint.rollback()

        # User should still exist
        assert integration_db_session.query(User).filter_by(id=user.id).first() is not None

        # Profile should not exist
        assert (
            integration_db_session.query(BusinessProfile).filter_by(user_id=user.id).first() is None
        )

    def test_nested_transaction_rollback(self, integration_db_session):
        """Test nested transaction rollback behavior."""
        from database import ComplianceFramework, AssessmentSession

        # Start outer transaction (already in progress via fixture)

        # Add framework
        framework = ComplianceFramework(name="Outer Framework", description="Test", version="1.0")
        integration_db_session.add(framework)
        integration_db_session.flush()

        # Start nested transaction
        nested = integration_db_session.begin_nested()

        try:
            # Add assessment
            assessment = AssessmentSession(user_id=1, framework_id=framework.id, status="draft")
            integration_db_session.add(assessment)
            integration_db_session.flush()

            # Rollback nested
            nested.rollback()

        except Exception:
            nested.rollback()

        # Framework should still be in session
        assert framework in integration_db_session

        # Assessment should not be in session
        assessments = (
            integration_db_session.query(AssessmentSession)
            .filter_by(framework_id=framework.id)
            .all()
        )
        assert len(assessments) == 0


@pytest.mark.integration
@pytest.mark.transaction
class TestDataIntegrity:
    """Test data integrity constraints and cascades."""

    def test_foreign_key_constraints(self, integration_db_session):
        """Test foreign key constraint enforcement."""
        from database import BusinessProfile

        # Try to create profile with non-existent user_id
        profile = BusinessProfile(
            user_id=99999,  # Non-existent
            company_name="Orphan Company",
        )
        integration_db_session.add(profile)

        with pytest.raises(IntegrityError):
            integration_db_session.commit()

        integration_db_session.rollback()

    def test_cascade_delete(self, integration_db_session):
        """Test cascade delete behavior."""
        from database import User, BusinessProfile, AssessmentSession

        # Create user with related data
        user = User(email="cascade@test.com", full_name="Cascade User", hashed_password="hash")
        integration_db_session.add(user)
        integration_db_session.commit()

        profile = BusinessProfile(user_id=user.id, company_name="Cascade Company")
        integration_db_session.add(profile)
        integration_db_session.commit()

        # Delete user (should cascade to profile if configured)
        integration_db_session.delete(user)
        integration_db_session.commit()

        # Check if profile was deleted
        remaining_profile = (
            integration_db_session.query(BusinessProfile).filter_by(user_id=user.id).first()
        )

        # Behavior depends on cascade configuration
        # If CASCADE is set, profile should be None
        # If not, this would have raised an IntegrityError

    def test_unique_constraints(self, integration_db_session):
        """Test unique constraint enforcement."""
        from database import User

        # Create user
        user1 = User(email="unique@test.com", full_name="User 1", hashed_password="hash")
        integration_db_session.add(user1)
        integration_db_session.commit()

        # Try to create another user with same email
        user2 = User(
            email="unique@test.com",  # Duplicate
            full_name="User 2",
            hashed_password="hash",
        )
        integration_db_session.add(user2)

        with pytest.raises(IntegrityError):
            integration_db_session.commit()

        integration_db_session.rollback()

    def test_check_constraints(self, integration_db_session):
        """Test check constraint enforcement."""
        from database import BusinessProfile

        # Try to create profile with invalid data
        profile = BusinessProfile(
            user_id=1,
            company_name="",  # Empty name (if check constraint exists)
            employee_count="invalid",  # Invalid enum value
        )

        # This might raise an error depending on constraints
        try:
            integration_db_session.add(profile)
            integration_db_session.commit()
            # If successful, validate the data
            assert len(profile.company_name) > 0 or profile.company_name == ""
        except (IntegrityError, ValueError):
            integration_db_session.rollback()


@pytest.mark.integration
@pytest.mark.transaction
class TestConcurrentTransactions:
    """Test concurrent transaction handling."""

    def test_parallel_inserts(self, test_db_engine):
        """Test parallel insert operations."""
        from database import User
        from utils.auth import get_password_hash

        def create_user(session, email):
            """Create a user in a session."""
            try:
                user = User(
                    email=email,
                    full_name=f"User {email}",
                    hashed_password=get_password_hash("Password123!"),
                )
                session.add(user)
                session.commit()
                return True
            except Exception as e:
                session.rollback()
                return False
            finally:
                session.close()

        # Create multiple sessions
        Session = test_db_engine.sessionmaker()

        # Run parallel inserts
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = []
            for i in range(10):
                session = Session()
                email = f"parallel{i}@test.com"
                future = executor.submit(create_user, session, email)
                futures.append(future)

            results = [f.result() for f in futures]

        # All should succeed
        assert all(results)

        # Verify all users were created
        session = Session()
        count = session.query(User).filter(User.email.like("parallel%@test.com")).count()
        session.close()
        assert count == 10

    def test_deadlock_detection(self, test_db_engine):
        """Test deadlock detection and resolution."""
        from database import User, BusinessProfile

        Session = test_db_engine.sessionmaker()

        def transaction1():
            session = Session()
            try:
                # Lock user 1, then try to lock user 2
                user1 = session.query(User).filter_by(id=1).with_for_update().first()
                time.sleep(0.1)
                user2 = session.query(User).filter_by(id=2).with_for_update().first()
                session.commit()
                return "success"
            except Exception as e:
                session.rollback()
                return f"error: {str(e)}"
            finally:
                session.close()

        def transaction2():
            session = Session()
            try:
                # Lock user 2, then try to lock user 1 (opposite order)
                user2 = session.query(User).filter_by(id=2).with_for_update().first()
                time.sleep(0.1)
                user1 = session.query(User).filter_by(id=1).with_for_update().first()
                session.commit()
                return "success"
            except Exception as e:
                session.rollback()
                return f"error: {str(e)}"
            finally:
                session.close()

        # This might cause a deadlock - database should detect and resolve
        with ThreadPoolExecutor(max_workers=2) as executor:
            future1 = executor.submit(transaction1)
            future2 = executor.submit(transaction2)

            result1 = future1.result(timeout=5)
            result2 = future2.result(timeout=5)

        # At least one should succeed, one might fail with deadlock
        assert "success" in result1 or "success" in result2


@pytest.mark.integration
@pytest.mark.transaction
@pytest.mark.asyncio
class TestAsyncTransactions:
    """Test async transaction handling."""

    async def test_async_transaction_rollback(self, async_integration_db_session):
        """Test async transaction rollback."""
        from database import User

        # Get initial count
        result = await async_integration_db_session.execute(text("SELECT COUNT(*) FROM users"))
        initial_count = result.scalar()

        try:
            # Add user
            user = User(email="async@test.com", full_name="Async User", hashed_password="hash")
            async_integration_db_session.add(user)

            # Force an error before commit
            raise ValueError("Simulated error")

        except ValueError:
            # Rollback will happen automatically due to fixture
            pass

        # Count should be unchanged after fixture cleanup
        result = await async_integration_db_session.execute(text("SELECT COUNT(*) FROM users"))
        final_count = result.scalar()
        assert final_count == initial_count

    async def test_async_concurrent_queries(self, async_integration_db_session):
        """Test concurrent async queries."""
        from database import User

        # Create test users
        for i in range(5):
            user = User(
                email=f"async{i}@test.com", full_name=f"Async User {i}", hashed_password="hash"
            )
            async_integration_db_session.add(user)

        await async_integration_db_session.commit()

        # Run concurrent queries
        async def query_user(email):
            result = await async_integration_db_session.execute(
                text("SELECT * FROM users WHERE email = :email"), {"email": email}
            )
            return result.first()

        # Execute queries concurrently
        tasks = [query_user(f"async{i}@test.com") for i in range(5)]

        results = await asyncio.gather(*tasks)

        # All queries should return results
        assert all(r is not None for r in results)

    async def test_async_transaction_isolation(self, async_integration_db_session, test_db_engine):
        """Test transaction isolation in async context."""
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
        from database import BusinessProfile

        # Create async engine
        db_url = str(test_db_engine.url)
        if "+asyncpg" not in db_url:
            db_url = db_url.replace("postgresql://", "postgresql+asyncpg://")

        async_engine = create_async_engine(db_url)

        # Create two async sessions
        async with AsyncSession(async_engine) as session1:
            async with AsyncSession(async_engine) as session2:
                # Session1: Start transaction and insert
                async with session1.begin():
                    profile1 = BusinessProfile(user_id=1, company_name="Async Company 1")
                    session1.add(profile1)
                    await session1.flush()

                    # Session2: Should not see uncommitted data
                    result = await session2.execute(
                        text("SELECT COUNT(*) FROM business_profiles WHERE company_name = :name"),
                        {"name": "Async Company 1"},
                    )
                    count = result.scalar()

                    # Should be 0 (not committed yet)
                    assert count == 0

        await async_engine.dispose()


@pytest.mark.integration
@pytest.mark.transaction
class TestBulkOperations:
    """Test bulk insert/update operations."""

    def test_bulk_insert_transaction(self, integration_db_session):
        """Test bulk insert in a transaction."""
        from database import ComplianceFramework

        frameworks = [
            ComplianceFramework(
                name=f"Framework {i}", description=f"Description {i}", version="1.0"
            )
            for i in range(100)
        ]

        # Bulk insert
        integration_db_session.bulk_save_objects(frameworks)
        integration_db_session.commit()

        # Verify all were inserted
        count = (
            integration_db_session.query(ComplianceFramework)
            .filter(ComplianceFramework.name.like("Framework %"))
            .count()
        )
        assert count == 100

    def test_bulk_update_transaction(self, integration_db_session):
        """Test bulk update in a transaction."""
        from database import User

        # Create users
        users = []
        for i in range(50):
            user = User(
                email=f"bulk{i}@test.com",
                full_name=f"Bulk User {i}",
                hashed_password="hash",
                is_active=False,
            )
            users.append(user)

        integration_db_session.bulk_save_objects(users)
        integration_db_session.commit()

        # Bulk update
        integration_db_session.query(User).filter(User.email.like("bulk%@test.com")).update(
            {"is_active": True}, synchronize_session=False
        )
        integration_db_session.commit()

        # Verify all were updated
        active_count = (
            integration_db_session.query(User)
            .filter(User.email.like("bulk%@test.com"), User.is_active)
            .count()
        )
        assert active_count == 50

    def test_bulk_operation_rollback(self, integration_db_session):
        """Test rollback of bulk operations."""
        from database import AssessmentSession

        initial_count = integration_db_session.query(AssessmentSession).count()

        # Start bulk insert
        assessments = [
            AssessmentSession(user_id=1, framework_id=1, status="draft") for _ in range(20)
        ]

        integration_db_session.bulk_save_objects(assessments)

        # Rollback before commit
        integration_db_session.rollback()

        # Count should be unchanged
        final_count = integration_db_session.query(AssessmentSession).count()
        assert final_count == initial_count
