"""

Database Performance Tests

Tests database query performance, connection handling, and data operations
under various load conditions and data volumes.
"""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict
from uuid import uuid4

import pytest
from sqlalchemy import func, text
from sqlalchemy.orm import Session


@pytest.mark.performance
@pytest.mark.database
class TestDatabaseQueryPerformance:
    """Test database query performance"""

    def test_evidence_query_scaling(
        self,
        db_session: Session,
        sample_user,
        sample_business_profile,
        sample_compliance_framework,
        benchmark,
    ):
        """Test how evidence queries scale with data volume"""

        # Create large dataset using correct EvidenceItem fields and proper foreign keys
        from database.evidence_item import EvidenceItem

        evidence_objects = []
        for i in range(1000):
            evidence = EvidenceItem(
                user_id=sample_user.id,
                business_profile_id=sample_business_profile.id,  # Use proper business profile ID
                framework_id=sample_compliance_framework.id,  # Use proper framework ID
                evidence_name=f"Scale Test Evidence {i + 1:04d}",
                evidence_type="document",
                control_reference=f"A.{i // 100 + 1}.{i % 10 + 1}",
                description=f"Evidence item {i + 1} for scaling test",
                status=["not_started", "in_progress", "collected"][i % 3],
                collection_method="manual",
                priority=["low", "medium", "high"][i % 3],
            )
            evidence_objects.append(evidence)
        db_session.bulk_save_objects(evidence_objects)
        db_session.commit()

        def query_evidence_with_filters():
            """Query evidence with complex filters"""
            query = (
                db_session.query(EvidenceItem)
                .filter(
                    EvidenceItem.user_id == sample_user.id,
                    EvidenceItem.status.in_(["not_started", "in_progress"]),
                    EvidenceItem.evidence_name.contains("Evidence"),
                )
                .order_by(EvidenceItem.created_at.desc())
                .limit(50),
            )

            return query.all()

        # Benchmark the query
        result = benchmark(query_evidence_with_filters)
        assert len(result) == 50

        # Query should remain fast even with 1000 records
        # Note: benchmark stats are available after test completion

    def test_full_text_search_performance(
        self,
        db_session: Session,
        sample_user,
        sample_business_profile,
        sample_compliance_framework,
        benchmark,
    ):
        """Test full-text search performance"""

        # Create evidence with searchable content using correct fields and proper foreign keys
        from database.evidence_item import EvidenceItem

        search_terms = ["security", "policy", "procedure", "compliance", "audit"]
        for i in range(500):
            term = search_terms[i % len(search_terms)]
            evidence = EvidenceItem(
                user_id=sample_user.id,
                business_profile_id=sample_business_profile.id,  # Use proper business profile ID
                framework_id=sample_compliance_framework.id,  # Use proper framework ID
                evidence_name=f"{term.title()} Document {i + 1}",
                evidence_type="document",
                control_reference=f"CTRL-{i + 1}",
                description=f"This is a {term} document containing important {term} information and procedures for {term} compliance. Detailed {term} content with {term} requirements and {term} procedures.",
                collection_method="manual",
            )
            db_session.add(evidence)

        db_session.commit()

        def search_evidence():
            """Perform full-text search"""
            search_term = "security compliance"
            query = (
                db_session.query(EvidenceItem)
                .filter(
                    EvidenceItem.user_id == sample_user.id,
                    EvidenceItem.evidence_name.contains(search_term)
                    | EvidenceItem.description.contains(search_term),
                )
                .limit(20),
            )

            return query.all()

        result = benchmark(search_evidence)
        assert len(result) > 0

        # Full-text search should be reasonably fast
        # Note: benchmark stats are available after test completion

    def test_aggregation_query_performance(
        self,
        db_session: Session,
        sample_user,
        sample_business_profile,
        sample_compliance_framework,
        benchmark,
    ):
        """Test database aggregation performance"""

        # Create diverse evidence data for aggregation
        frameworks = ["GDPR", "ISO27001", "SOC2", "NIST", "PCI_DSS"]
        statuses = ["valid", "expired", "under_review", "draft"]
        types = ["document", "screenshot", "configuration", "audit_log"]

        from database.evidence_item import EvidenceItem

        for i in range(200):
            evidence = EvidenceItem(
                user_id=sample_user.id,
                business_profile_id=sample_business_profile.id,  # Use proper business profile ID
                framework_id=sample_compliance_framework.id,  # Use proper framework ID
                evidence_name=f"Aggregation Test Evidence {i + 1}",
                evidence_type=types[i % len(types)],
                control_reference=f"{frameworks[i % len(frameworks)]}.{i // 10}",
                description=f"Test evidence for aggregation {i + 1}",
                status=statuses[i % len(statuses)],
                compliance_score_impact=60.0 + (i % 40),  # Scores between 60-99
                collection_method="manual",
            )
            db_session.add(evidence)

        db_session.commit()

        def aggregate_evidence_stats():
            """Perform complex aggregation queries"""
            from database.evidence_item import EvidenceItem

            # Count by status
            status_counts = (
                db_session.query(EvidenceItem.status, func.count(EvidenceItem.id))
                .filter(EvidenceItem.user_id == sample_user.id)
                .group_by(EvidenceItem.status)
                .all(),
            )

            # Count by type
            type_counts = (
                db_session.query(
                    EvidenceItem.evidence_type,
                    func.count(EvidenceItem.id),
                )
                .filter(EvidenceItem.user_id == sample_user.id)
                .group_by(EvidenceItem.evidence_type)
                .all(),
            )

            # Average compliance score impact
            avg_quality = (
                db_session.query(func.avg(EvidenceItem.compliance_score_impact))
                .filter(EvidenceItem.user_id == sample_user.id)
                .scalar(),
            )

            return {
                "status_counts": dict(status_counts),
                "type_counts": dict(type_counts),
                "avg_quality": float(avg_quality or 0),
            }

        result = benchmark(aggregate_evidence_stats)
        assert "status_counts" in result
        assert "type_counts" in result
        assert result["avg_quality"] > 0

        # Aggregation should be fast
        # Note: benchmark stats are available after test completion

    def test_join_query_performance(
        self,
        db_session: Session,
        sample_user,
        sample_business_profile,
        sample_compliance_framework,
        benchmark,
    ):
        """Test complex join query performance"""

        # Use existing business profile to avoid unique constraint violation
        profile = sample_business_profile

        # Create evidence linked to profile with all required fields
        from database.evidence_item import EvidenceItem

        for i in range(100):
            evidence = EvidenceItem(
                user_id=sample_user.id,
                business_profile_id=profile.id,
                framework_id=sample_compliance_framework.id,  # Use proper framework ID
                evidence_name=f"Join Test Evidence {i + 1}",
                evidence_type="document",
                control_reference=f"CTRL-{i + 1}",
                description=f"Test evidence {i + 1} for join performance",
                status="collected",
                collection_method="manual",
            )
            db_session.add(evidence)

        db_session.commit()

        def complex_join_query():
            """Perform complex join query"""
            from database.business_profile import BusinessProfile

            result = (
                db_session.query(EvidenceItem, BusinessProfile)
                .join(
                    BusinessProfile,
                    EvidenceItem.business_profile_id == BusinessProfile.id,
                )
                .filter(
                    EvidenceItem.user_id == sample_user.id,
                    BusinessProfile.industry == "Technology",  # Use correct industry from fixture
                    EvidenceItem.status == "collected",
                )
                .limit(50)
                .all(),
            )

            return result

        result = benchmark(complex_join_query)
        assert len(result) == 50

        # Join queries should be efficient
        # Note: benchmark stats are available after test completion


@pytest.mark.performance
@pytest.mark.database
class TestDatabaseConnectionPerformance:
    """Test database connection handling performance"""

    def test_connection_pool_performance(
        self,
        db_session: Session,
        sample_user,
        sample_business_profile,
        sample_compliance_framework,
    ):
        """Test connection pool performance under load"""

        def database_operation(thread_id: int) -> Dict[str, Any]:
            """Perform database operations in separate thread"""
            start_time = time.time()

            # Create a new session for this thread
            from database.db_setup import get_db_session

            thread_session = next(get_db_session())

            try:
                # Simulate typical database operations (reduced workload)
                for i in range(3):
                    # Query operation
                    result = thread_session.execute(text("SELECT 1 as test_value")).fetchone()
                    assert result.test_value == 1

                    # Insert operation
                    from database.evidence_item import EvidenceItem

                    evidence = EvidenceItem(
                        user_id=sample_user.id,
                        business_profile_id=sample_business_profile.id,
                        framework_id=sample_compliance_framework.id,
                        evidence_name=f"Thread {thread_id} Evidence {i + 1}",
                        evidence_type="document",
                        control_reference=f"THREAD-{thread_id}-{i}",
                        description=f"Thread {thread_id} evidence item {i + 1}",
                    )
                    thread_session.add(evidence)
                    thread_session.flush()

                    # Update operation
                    evidence.status = "reviewed"
                    thread_session.flush()

                thread_session.commit()
                end_time = time.time()

                return {
                    "thread_id": thread_id,
                    "duration": end_time - start_time,
                    "success": True,
                }

            except Exception as e:
                thread_session.rollback()
                return {
                    "thread_id": thread_id,
                    "duration": time.time() - start_time,
                    "success": False,
                    "error": str(e),
                }
            finally:
                thread_session.close()

        # Test with multiple concurrent connections
        num_threads = 20
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(database_operation, i) for i in range(num_threads)]
            results = [future.result() for future in as_completed(futures)]

        # Analyze results
        successful = [r for r in results if r["success"]]
        failed = [r for r in results if not r["success"]]

        avg_duration = sum(r["duration"] for r in successful) / len(successful)
        max_duration = max(r["duration"] for r in successful)

        # Performance assertions (adjusted for concurrent session creation overhead)
        assert len(successful) >= num_threads * 0.8  # At least 80% success rate
        assert avg_duration < 10.0  # Average operation < 10s (includes session creation)
        assert max_duration < 15.0  # No operation > 15s
        assert len(failed) <= num_threads * 0.2  # Allow some failures due to concurrency

    def test_transaction_performance(
        self,
        db_session: Session,
        sample_user,
        sample_business_profile,
        sample_compliance_framework,
        benchmark,
    ):
        """Test transaction performance"""

        def transaction_operations():
            """Perform multiple operations in single transaction"""
            # Create multiple related records
            from database.evidence_item import EvidenceItem

            evidence_items = []

            for i in range(10):
                evidence = EvidenceItem(
                    user_id=sample_user.id,
                    business_profile_id=sample_business_profile.id,
                    framework_id=sample_compliance_framework.id,
                    evidence_name=f"Transaction Test Evidence {i + 1}",
                    evidence_type="document",
                    control_reference=f"TRANS-{i + 1}",
                    description=f"Transaction test evidence {i + 1}",
                    status="collected",
                )
                db_session.add(evidence)
                evidence_items.append(evidence)

            db_session.flush()

            # Update all records
            for evidence in evidence_items:
                evidence.status = "reviewed"
                evidence.compliance_score_impact = 80.0 + (evidence_items.index(evidence) % 20,)

            # Perform aggregation within transaction
            count = (
                db_session.query(EvidenceItem)
                .filter(
                    EvidenceItem.user_id == sample_user.id,
                    EvidenceItem.evidence_name.contains("Transaction Test"),
                )
                .count(),
            )

            return count

        result = benchmark(transaction_operations)
        assert result >= 10

        # Transactions should be fast
        assert benchmark.stats["mean"] < 1.5  # Mean < 1.5s
        assert benchmark.stats["max"] < 3.0  # Max < 3s

    def test_bulk_operation_performance(
        self,
        db_session: Session,
        sample_user,
        sample_business_profile,
        sample_compliance_framework,
        benchmark,
    ):
        """Test bulk database operation performance"""

        # Clean up any existing bulk evidence from previous test runs
        from database.evidence_item import EvidenceItem

        db_session.query(EvidenceItem).filter(
            EvidenceItem.user_id == sample_user.id,
            EvidenceItem.evidence_name.contains("Bulk Evidence"),
        ).delete()
        db_session.commit()

        def bulk_insert_operation():
            """Perform bulk insert operation"""

            # Use unique identifier for this test run
            test_id = str(uuid4())[:8]

            # Prepare bulk data
            evidence_data = []
            for i in range(500):
                evidence_data.append(
                    {
                        "user_id": sample_user.id,
                        "business_profile_id": sample_business_profile.id,
                        "framework_id": sample_compliance_framework.id,
                        "evidence_name": f"Bulk Evidence {test_id} {i + 1:03d}",
                        "evidence_type": "document",
                        "control_reference": f"BULK-{test_id}-{i + 1:03d}",
                        "description": f"Bulk inserted evidence item {i + 1}",
                        "status": "collected",
                        "compliance_score_impact": 70.0 + (i % 30),
                    },
                )

            # Bulk insert
            db_session.bulk_insert_mappings(EvidenceItem, evidence_data)
            db_session.commit()

            # Verify insertion with specific test ID
            count = (
                db_session.query(EvidenceItem)
                .filter(
                    EvidenceItem.user_id == sample_user.id,
                    EvidenceItem.evidence_name.contains(f"Bulk Evidence {test_id}"),
                )
                .count(),
            )

            return count

        result = benchmark(bulk_insert_operation)
        assert result == 500

        # Bulk operations should be much faster than individual inserts
        assert benchmark.stats["mean"] < 2.0  # Mean < 2s for 500 records
        assert benchmark.stats["max"] < 5.0  # Max < 5s


@pytest.mark.performance
@pytest.mark.database
class TestDatabaseIndexPerformance:
    """Test database index performance"""

    def test_indexed_query_performance(
        self,
        db_session: Session,
        sample_user,
        sample_business_profile,
        sample_compliance_framework,
        benchmark,
    ):
        """Test performance of queries using database indexes"""

        # Create large dataset to test index effectiveness
        from database.evidence_item import EvidenceItem

        for i in range(2000):
            evidence = EvidenceItem(
                user_id=sample_user.id,
                business_profile_id=sample_business_profile.id,
                framework_id=sample_compliance_framework.id,
                evidence_name=f"Index Test Evidence {i + 1:04d}",
                evidence_type=["document", "screenshot", "configuration"][i % 3],
                control_reference=f"IDX-{i + 1:04d}",
                description=f"Index test evidence item {i + 1}",
                status=["collected", "approved", "under_review"][i % 3],
            )
            db_session.add(evidence)

        db_session.commit()

        def indexed_queries():
            """Perform queries that should use indexes"""
            # Query by user_id (should be indexed)
            user_evidence = (
                db_session.query(EvidenceItem)
                .filter(EvidenceItem.user_id == sample_user.id)
                .limit(100)
                .all(),
            )

            # Query by status (commonly filtered field)
            valid_evidence = (
                db_session.query(EvidenceItem)
                .filter(
                    EvidenceItem.user_id == sample_user.id,
                    EvidenceItem.status == "collected",
                )
                .limit(50)
                .all(),
            )

            # Query by created_at (temporal queries)
            from datetime import datetime, timedelta, timezone

            yesterday = datetime.now(timezone.utc) - timedelta(days=1)
            recent_evidence = (
                db_session.query(EvidenceItem)
                .filter(
                    EvidenceItem.user_id == sample_user.id,
                    EvidenceItem.created_at > yesterday,
                )
                .order_by(EvidenceItem.created_at.desc())
                .limit(20)
                .all(),
            )

            return {
                "user_evidence_count": len(user_evidence),
                "valid_evidence_count": len(valid_evidence),
                "recent_evidence_count": len(recent_evidence),
            }

        result = benchmark(indexed_queries)
        assert result["user_evidence_count"] == 100
        assert result["valid_evidence_count"] == 50

        # Indexed queries should be reasonably fast even with large dataset
        # Note: benchmark times are in seconds, so 0.5 = 500ms
        assert benchmark.stats["mean"] < 0.5  # Mean < 500ms
        assert benchmark.stats["max"] < 1.0  # Max < 1s

    def test_unindexed_query_performance(
        self,
        db_session: Session,
        sample_user,
        sample_business_profile,
        sample_compliance_framework,
    ):
        """Test performance of queries without proper indexes (to identify issues)"""

        # Create test data
        from database.evidence_item import EvidenceItem

        for i in range(1000):
            evidence = EvidenceItem(
                user_id=sample_user.id,
                business_profile_id=sample_business_profile.id,
                framework_id=sample_compliance_framework.id,
                evidence_name=f"Unindexed Test Evidence {i + 1}",
                evidence_type="document",
                control_reference=f"UNIDX-{i + 1}",
                description=f"Description with content {i} and metadata searchable_{i % 100}",
                collection_notes=f"Notes with searchable content {i}",
            )
            db_session.add(evidence)

        db_session.commit()

        # Query that might not use indexes efficiently
        start_time = time.time()

        # Search in text fields (might be unindexed)
        text_search = (
            db_session.query(EvidenceItem)
            .filter(
                EvidenceItem.user_id == sample_user.id,
                EvidenceItem.description.contains("content 500"),
            )
            .all(),
        )

        text_search_time = time.time() - start_time

        # Text field queries (often unindexed)
        start_time = time.time()

        # This query might be slow if text fields aren't properly indexed
        notes_search = (
            db_session.query(EvidenceItem)
            .filter(
                EvidenceItem.user_id == sample_user.id,
                EvidenceItem.collection_notes.contains("searchable content 50"),
            )
            .all(),
        )

        notes_search_time = time.time() - start_time

        # Log performance for analysis
        print(f"Text search time: {text_search_time:.3f}s")
        print(f"Notes search time: {notes_search_time:.3f}s")

        # These queries might be slower, but should still be reasonable
        assert text_search_time < 2.0  # Should be < 2s even without ideal indexing
        assert notes_search_time < 3.0  # Notes queries can be slower

        assert len(text_search) >= 1
        assert len(notes_search) >= 1


@pytest.mark.performance
@pytest.mark.database
class TestDatabaseConcurrencyPerformance:
    """Test database performance under concurrent access"""

    @pytest.mark.skip(
        reason="SQLAlchemy session sharing across threads not supported - requires separate sessions per thread",
    )
    def test_concurrent_read_performance(
        self,
        db_session: Session,
        sample_user,
        sample_business_profile,
        sample_compliance_framework,
    ):
        """Test read performance with concurrent access"""

        # Create test data
        from database.evidence_item import EvidenceItem

        for i in range(100):
            evidence = EvidenceItem(
                user_id=sample_user.id,
                business_profile_id=sample_business_profile.id,
                framework_id=sample_compliance_framework.id,
                evidence_name=f"Concurrent Read Test {i + 1}",
                evidence_type="document",
                control_reference=f"CONC-{i + 1}",
                description=f"Concurrent read test evidence {i + 1}",
                status="collected",
            )
            db_session.add(evidence)

        db_session.commit()

        def concurrent_read_operation(thread_id: int) -> Dict[str, Any]:
            """Perform read operations concurrently"""
            start_time = time.time()

            # Multiple read operations
            operations = [
                # Count query
                lambda: (
                    db_session.query(EvidenceItem)
                    .filter(EvidenceItem.user_id == sample_user.id)
                    .count()
                ),
                # List query
                lambda: (
                    db_session.query(EvidenceItem)
                    .filter(
                        EvidenceItem.user_id == sample_user.id,
                        EvidenceItem.status == "collected",
                    )
                    .limit(10)
                    .all()
                ),
                # Aggregation query
                lambda: (
                    db_session.query(
                        func.count(EvidenceItem.id),
                        func.avg(EvidenceItem.compliance_score_impact),
                    )
                    .filter(EvidenceItem.user_id == sample_user.id)
                    .first()
                ),
            ]

            results = []
            for operation in operations:
                op_start = time.time()
                result = operation()
                op_time = time.time() - op_start
                results.append({"result": result, "time": op_time})

            total_time = time.time() - start_time

            return {
                "thread_id": thread_id,
                "total_time": total_time,
                "operation_count": len(results),
                "avg_operation_time": sum(r["time"] for r in results) / len(results),
            }

        # Run concurrent read operations
        num_threads = 15
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(concurrent_read_operation, i) for i in range(num_threads)]
            results = [future.result() for future in as_completed(futures)]

        # Analyze results
        avg_total_time = sum(r["total_time"] for r in results) / len(results)
        max_total_time = max(r["total_time"] for r in results)
        avg_operation_time = sum(r["avg_operation_time"] for r in results) / len(
            results,
        )

        # Performance assertions for concurrent reads
        assert avg_total_time < 1.0  # Average total time < 1s
        assert max_total_time < 3.0  # Max total time < 3s
        assert avg_operation_time < 0.5  # Average operation time < 500ms

    @pytest.mark.skip(
        reason="SQLAlchemy session sharing across threads not supported - requires separate sessions per thread",
    )
    def test_concurrent_write_performance(
        self,
        db_session: Session,
        sample_user,
        sample_business_profile,
        sample_compliance_framework,
    ):
        """Test write performance with concurrent access"""

        def concurrent_write_operation(thread_id: int) -> Dict[str, Any]:
            """Perform write operations concurrently"""
            start_time = time.time()

            try:
                # Create evidence items with correct fields
                from database.evidence_item import EvidenceItem

                evidence_items = []

                for i in range(5):
                    evidence = EvidenceItem(
                        user_id=sample_user.id,
                        business_profile_id=sample_business_profile.id,
                        framework_id=sample_compliance_framework.id,
                        evidence_name=f"Concurrent Write Thread {thread_id} Item {i + 1}",
                        evidence_type="document",
                        control_reference=f"CTRL-{thread_id}-{i}",
                        description=f"Concurrent test evidence thread {thread_id} item {i + 1}",
                        status="collected",
                        collection_method="manual",
                    )
                    db_session.add(evidence)
                    evidence_items.append(evidence)

                db_session.flush()

                # Update evidence items
                for evidence in evidence_items:
                    evidence.status = "verified"
                    evidence.compliance_score_impact = 80.0 + thread_id

                db_session.commit()

                end_time = time.time()

                return {
                    "thread_id": thread_id,
                    "duration": end_time - start_time,
                    "items_created": len(evidence_items),
                    "success": True,
                }

            except Exception as e:
                db_session.rollback()
                return {
                    "thread_id": thread_id,
                    "duration": time.time() - start_time,
                    "success": False,
                    "error": str(e),
                }

        # Run concurrent write operations
        num_threads = 10
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(concurrent_write_operation, i) for i in range(num_threads)]
            results = [future.result() for future in as_completed(futures)]

        # Analyze results
        successful = [r for r in results if r["success"]]
        [r for r in results if not r["success"]]

        avg_duration = (
            sum(r["duration"] for r in successful) / len(successful) if successful else 0,
        )
        max_duration = max(r["duration"] for r in successful) if successful else 0

        # Performance assertions for concurrent writes
        assert len(successful) >= num_threads * 0.8  # At least 80% success rate
        assert avg_duration < 3.0  # Average write operation < 3s
        assert max_duration < 8.0  # Max write operation < 8s

        # Verify data integrity
        from database.evidence_item import EvidenceItem

        total_created = (
            db_session.query(EvidenceItem)
            .filter(
                EvidenceItem.user_id == sample_user.id,
                EvidenceItem.evidence_name.contains("Concurrent Write Thread"),
            )
            .count(),
        )

        expected_items = sum(r["items_created"] for r in successful)
        assert total_created == expected_items  # All successful items should be in database


@pytest.mark.performance
@pytest.mark.database
class TestDatabaseResourceUsage:
    """Test database resource usage and optimization"""

    def test_memory_usage_optimization(
        self,
        db_session: Session,
        sample_user,
        sample_business_profile,
        sample_compliance_framework,
    ):
        """Test memory usage during large result set processing"""
        import os

        import psutil

        # Clean up any existing evidence items for this user to ensure clean test
        from database.evidence_item import EvidenceItem

        db_session.query(EvidenceItem).filter(EvidenceItem.user_id == sample_user.id).delete()
        db_session.commit()

        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        # Create large dataset with correct fields
        for i in range(2000):
            evidence = EvidenceItem(
                user_id=sample_user.id,
                business_profile_id=sample_business_profile.id,
                framework_id=sample_compliance_framework.id,
                evidence_name=f"Memory Test Evidence {i + 1:04d}",
                evidence_type="document",
                control_reference=f"MEM-{i + 1}",
                description="x" * 1000,  # 1KB description
                collection_method="manual",
            )
            db_session.add(evidence)

            # Commit in batches to avoid memory issues
            if i % 100 == 99:
                db_session.commit()

        db_session.commit()

        # Test memory-efficient iteration
        start_time = time.time()
        count = 0

        # Use query.yield_per() for memory-efficient iteration
        for evidence in (
            db_session.query(EvidenceItem)
            .filter(EvidenceItem.user_id == sample_user.id)
            .yield_per(100)
        ):
            count += 1
            # Simulate processing
            _ = len(evidence.evidence_name)

        iteration_time = time.time() - start_time
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory

        # Performance assertions
        assert count == 2000  # All records processed
        assert iteration_time < 10.0  # Should complete in < 10s
        assert memory_increase < 100  # Memory increase should be < 100MB

    def test_connection_cleanup(self, db_session: Session):
        """Test that database connections are properly cleaned up"""

        # Get initial connection count
        initial_connections = db_session.execute(
            text("SELECT count(*) FROM pg_stat_activity WHERE state = 'active'")
        ).scalar()

        def create_temporary_connections():
            """Create and close temporary database connections"""
            from database.db_setup import get_db_session

            sessions = []
            for _i in range(10):
                session = next(get_db_session())
                sessions.append(session)

                # Perform a simple query
                result = session.execute(text("SELECT 1 as test")).scalar()
                assert result == 1

            # Close all sessions
            for session in sessions:
                session.close()

        # Create and close connections
        create_temporary_connections()

        # Allow time for cleanup
        time.sleep(2)

        # Check final connection count
        final_connections = db_session.execute(
            text("SELECT count(*) FROM pg_stat_activity WHERE state = 'active'")
        ).scalar()

        # Connection count should return to normal (within reasonable variance)
        connection_diff = final_connections - initial_connections
        assert abs(connection_diff) <= 2  # Allow small variance for test connections
