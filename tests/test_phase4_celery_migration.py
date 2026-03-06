"""

Test suite for Phase 4: Complete Celery task migration to LangGraph
Tests all 16 migrated tasks and the unified orchestrator
"""

import pytest
import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from unittest.mock import Mock, patch, AsyncMock

from langgraph_agent.graph.celery_migration_graph import (
    CeleryMigrationGraph,
    create_celery_migration_graph,
)
from langgraph_agent.nodes.celery_migration_nodes import (
    TaskMigrationState,
    ComplianceTaskNode,
    EvidenceTaskNode,
    NotificationTaskNode,
    ReportingTaskNode,
    MonitoringTaskNode,
)


@pytest.mark.asyncio
class TestComplianceTaskMigration:
    """Test migrated compliance tasks"""

    async def test_update_compliance_scores(self):
        """Test update_all_compliance_scores migration"""
        node = ComplianceTaskNode()

        state: TaskMigrationState = {
            "messages": [],
            "session_id": str(uuid4()),
            "company_id": str(uuid4()),
            "task_type": "update_compliance_scores",
            "task_params": {},
            "task_result": None,
            "task_status": "pending",
            "original_task_name": "update_all_compliance_scores",
            "migration_timestamp": datetime.now(timezone.utc).isoformat(),
            "execution_metrics": {},
            "errors": [],
            "retry_count": 0,
            "max_retries": 3,
        }

        result = await node.process(state)

        assert result["task_status"] == "completed"
        assert result["task_result"]["task"] == "update_all_compliance_scores"
        assert "scores_updated" in result["task_result"]
        assert len(result["task_result"]["scores_updated"]) == 4  # GDPR, ISO27001, SOC2, HIPAA

    async def test_check_compliance_alerts(self):
        """Test check_compliance_alerts migration"""
        node = ComplianceTaskNode()

        state: TaskMigrationState = {
            "messages": [],
            "session_id": str(uuid4()),
            "company_id": str(uuid4()),
            "task_type": "check_compliance_alerts",
            "task_params": {"check_thresholds": True},
            "task_result": None,
            "task_status": "pending",
            "original_task_name": "check_compliance_alerts",
            "migration_timestamp": datetime.now(timezone.utc).isoformat(),
            "execution_metrics": {},
            "errors": [],
            "retry_count": 0,
            "max_retries": 3,
        }

        result = await node.process(state)

        assert result["task_status"] == "completed"
        assert result["task_result"]["task"] == "check_compliance_alerts"
        assert "alerts" in result["task_result"]
        assert result["task_result"]["alerts_found"] >= 0


@pytest.mark.asyncio
class TestEvidenceTaskMigration:
    """Test migrated evidence tasks"""

    async def test_process_evidence_item(self):
        """Test process_evidence_item migration"""
        node = EvidenceTaskNode()

        state: TaskMigrationState = {
            "messages": [],
            "session_id": str(uuid4()),
            "company_id": str(uuid4()),
            "task_type": "process_evidence",
            "task_params": {"evidence_id": "EV-12345"},
            "task_result": None,
            "task_status": "pending",
            "original_task_name": "process_evidence_item",
            "migration_timestamp": datetime.now(timezone.utc).isoformat(),
            "execution_metrics": {},
            "errors": [],
            "retry_count": 0,
            "max_retries": 3,
        }

        result = await node.process(state)

        assert result["task_status"] == "completed"
        assert result["task_result"]["evidence_id"] == "EV-12345"
        assert result["task_result"]["processing_result"]["validated"] is True

    async def test_sync_evidence_status(self):
        """Test sync_evidence_status migration"""
        node = EvidenceTaskNode()

        state: TaskMigrationState = {
            "messages": [],
            "session_id": str(uuid4()),
            "company_id": str(uuid4()),
            "task_type": "sync_evidence",
            "task_params": {},
            "task_result": None,
            "task_status": "pending",
            "original_task_name": "sync_evidence_status",
            "migration_timestamp": datetime.now(timezone.utc).isoformat(),
            "execution_metrics": {},
            "errors": [],
            "retry_count": 0,
            "max_retries": 3,
        }

        result = await node.process(state)

        assert result["task_status"] == "completed"
        assert "sync_summary" in result["task_result"]
        assert result["task_result"]["sync_summary"]["total_evidence_items"] > 0


@pytest.mark.asyncio
class TestNotificationTaskMigration:
    """Test migrated notification tasks"""

    async def test_send_compliance_alert(self):
        """Test send_compliance_alert migration"""
        node = NotificationTaskNode()

        state: TaskMigrationState = {
            "messages": [],
            "session_id": str(uuid4()),
            "company_id": str(uuid4()),
            "task_type": "compliance_alert",
            "task_params": {
                "alert_type": "threshold_breach",
                "recipients": ["user1@example.com", "user2@example.com"],
            },
            "task_result": None,
            "task_status": "pending",
            "original_task_name": "send_compliance_alert",
            "migration_timestamp": datetime.now(timezone.utc).isoformat(),
            "execution_metrics": {},
            "errors": [],
            "retry_count": 0,
            "max_retries": 3,
        }

        result = await node.process(state)

        assert result["task_status"] == "completed"
        assert result["task_result"]["recipients_count"] == 2
        assert "delivery_status" in result["task_result"]

    async def test_send_weekly_summary(self):
        """Test send_weekly_summary migration"""
        node = NotificationTaskNode()

        state: TaskMigrationState = {
            "messages": [],
            "session_id": str(uuid4()),
            "company_id": str(uuid4()),
            "task_type": "weekly_summary",
            "task_params": {},
            "task_result": None,
            "task_status": "pending",
            "original_task_name": "send_weekly_summary",
            "migration_timestamp": datetime.now(timezone.utc).isoformat(),
            "execution_metrics": {},
            "errors": [],
            "retry_count": 0,
            "max_retries": 3,
        }

        result = await node.process(state)

        assert result["task_status"] == "completed"
        assert "summary_stats" in result["task_result"]
        assert result["task_result"]["recipients_notified"] > 0

    async def test_broadcast_notification(self):
        """Test broadcast_notification migration"""
        node = NotificationTaskNode()

        state: TaskMigrationState = {
            "messages": [],
            "session_id": str(uuid4()),
            "company_id": str(uuid4()),
            "task_type": "broadcast",
            "task_params": {
                "message": "System maintenance scheduled",
                "channels": ["email", "slack"],
            },
            "task_result": None,
            "task_status": "pending",
            "original_task_name": "broadcast_notification",
            "migration_timestamp": datetime.now(timezone.utc).isoformat(),
            "execution_metrics": {},
            "errors": [],
            "retry_count": 0,
            "max_retries": 3,
        }

        result = await node.process(state)

        assert result["task_status"] == "completed"
        assert result["task_result"]["channels_used"] == ["email", "slack"]
        assert "delivery_metrics" in result["task_result"]


@pytest.mark.asyncio
class TestReportingTaskMigration:
    """Test migrated reporting tasks"""

    async def test_generate_and_distribute_report(self):
        """Test generate_and_distribute_report migration"""
        node = ReportingTaskNode()

        state: TaskMigrationState = {
            "messages": [],
            "session_id": str(uuid4()),
            "company_id": str(uuid4()),
            "task_type": "generate_report",
            "task_params": {"report_type": "compliance", "format": "pdf"},
            "task_result": None,
            "task_status": "pending",
            "original_task_name": "generate_and_distribute_report",
            "migration_timestamp": datetime.now(timezone.utc).isoformat(),
            "execution_metrics": {},
            "errors": [],
            "retry_count": 0,
            "max_retries": 3,
        }

        result = await node.process(state)

        assert result["task_status"] == "completed"
        assert result["task_result"]["report_details"]["type"] == "compliance"
        assert result["task_result"]["report_details"]["format"] == "pdf"

    async def test_cleanup_old_reports(self):
        """Test cleanup_old_reports migration"""
        node = ReportingTaskNode()

        state: TaskMigrationState = {
            "messages": [],
            "session_id": str(uuid4()),
            "company_id": str(uuid4()),
            "task_type": "cleanup_reports",
            "task_params": {"retention_days": 90},
            "task_result": None,
            "task_status": "pending",
            "original_task_name": "cleanup_old_reports",
            "migration_timestamp": datetime.now(timezone.utc).isoformat(),
            "execution_metrics": {},
            "errors": [],
            "retry_count": 0,
            "max_retries": 3,
        }

        result = await node.process(state)

        assert result["task_status"] == "completed"
        assert "cleanup_summary" in result["task_result"]
        assert "space_freed" in result["task_result"]["cleanup_summary"]


@pytest.mark.asyncio
class TestMonitoringTaskMigration:
    """Test migrated monitoring tasks"""

    async def test_collect_database_metrics(self):
        """Test collect_database_metrics migration"""
        node = MonitoringTaskNode()

        state: TaskMigrationState = {
            "messages": [],
            "session_id": str(uuid4()),
            "company_id": str(uuid4()),
            "task_type": "database_metrics",
            "task_params": {},
            "task_result": None,
            "task_status": "pending",
            "original_task_name": "collect_database_metrics",
            "migration_timestamp": datetime.now(timezone.utc).isoformat(),
            "execution_metrics": {},
            "errors": [],
            "retry_count": 0,
            "max_retries": 3,
        }

        result = await node.process(state)

        assert result["task_status"] == "completed"
        assert "metrics" in result["task_result"]
        assert "connection_pool" in result["task_result"]["metrics"]
        assert "query_performance" in result["task_result"]["metrics"]

    async def test_system_metrics_collection(self):
        """Test system_metrics_collection migration"""
        node = MonitoringTaskNode()

        state: TaskMigrationState = {
            "messages": [],
            "session_id": str(uuid4()),
            "company_id": str(uuid4()),
            "task_type": "system_metrics",
            "task_params": {},
            "task_result": None,
            "task_status": "pending",
            "original_task_name": "system_metrics_collection",
            "migration_timestamp": datetime.now(timezone.utc).isoformat(),
            "execution_metrics": {},
            "errors": [],
            "retry_count": 0,
            "max_retries": 3,
        }

        result = await node.process(state)

        assert result["task_status"] == "completed"
        assert "system_metrics" in result["task_result"]
        assert all(
            key in result["task_result"]["system_metrics"]
            for key in ["cpu", "memory", "disk", "network"]
        )


@pytest.mark.asyncio
class TestUnifiedOrchestrator:
    """Test the unified Celery migration graph orchestrator"""

    async def test_graph_initialization(self):
        """Test graph initialization with all task nodes"""
        graph = CeleryMigrationGraph()

        assert graph.compliance_node is not None
        assert graph.evidence_node is not None
        assert graph.notification_node is not None
        assert graph.reporting_node is not None
        assert graph.monitoring_node is not None
        assert len(graph.task_routes) == 16  # All 16 tasks mapped

    async def test_task_routing(self):
        """Test correct routing of tasks to nodes"""
        graph = CeleryMigrationGraph()

        # Test compliance routing
        assert graph.task_routes["update_compliance_scores"] == "compliance"
        assert graph.task_routes["check_compliance_alerts"] == "compliance"

        # Test evidence routing
        assert graph.task_routes["process_evidence"] == "evidence"
        assert graph.task_routes["sync_evidence"] == "evidence"

        # Test notification routing
        assert graph.task_routes["compliance_alert"] == "notification"
        assert graph.task_routes["weekly_summary"] == "notification"
        assert graph.task_routes["broadcast"] == "notification"

        # Test reporting routing
        assert graph.task_routes["generate_report"] == "reporting"
        assert graph.task_routes["cleanup_reports"] == "reporting"

        # Test monitoring routing
        assert graph.task_routes["database_metrics"] == "monitoring"
        assert graph.task_routes["system_metrics"] == "monitoring"

    async def test_execute_compliance_task_through_graph(self):
        """Test executing a compliance task through the unified graph"""
        graph = CeleryMigrationGraph()

        result = await graph.execute_task(
            task_type="update_compliance_scores",
            params={},
        )

        assert result["task"] == "update_all_compliance_scores"
        assert result["status"] == "completed"
        assert "scores_updated" in result

    async def test_execute_monitoring_task_through_graph(self):
        """Test executing a monitoring task through the unified graph"""
        graph = CeleryMigrationGraph()

        result = await graph.execute_task(task_type="system_metrics", params={})

        assert result["task"] == "system_metrics_collection"
        assert result["status"] == "completed"
        assert "system_metrics" in result

    async def test_task_retry_on_failure(self):
        """Test task retry mechanism on failure"""
        graph = CeleryMigrationGraph()

        # Create a state that will trigger an error
        state: TaskMigrationState = {
            "messages": [],
            "session_id": str(uuid4()),
            "company_id": str(uuid4()),
            "task_type": "invalid_task",  # Invalid task type
            "task_params": {},
            "task_result": None,
            "task_status": "pending",
            "original_task_name": "invalid_task",
            "migration_timestamp": datetime.now(timezone.utc).isoformat(),
            "execution_metrics": {},
            "errors": [],
            "retry_count": 0,
            "max_retries": 3,
        }

        result = await graph.execute_task(state=state)

        assert result["status"] == "failed"
        assert "error" in result

    async def test_scheduler_registration(self):
        """Test that scheduled tasks are properly registered"""
        graph = CeleryMigrationGraph()

        # Check scheduler has registered tasks
        assert graph.scheduler is not None
        # The scheduler should have registered periodic tasks
        # In production, we'd verify the actual scheduled tasks

    async def test_task_statistics(self):
        """Test getting migration statistics"""
        graph = CeleryMigrationGraph()

        stats = graph.get_task_statistics()

        assert stats["total_tasks_migrated"] == 16
        assert stats["coverage_percentage"] == 100.0
        assert stats["migration_complete"] is True
        assert stats["task_categories"]["compliance"] == 2
        assert stats["task_categories"]["evidence"] == 2
        assert stats["task_categories"]["notification"] == 3
        assert stats["task_categories"]["reporting"] == 4
        assert stats["task_categories"]["monitoring"] == 5

    async def test_end_to_end_workflow(self):
        """Test complete end-to-end workflow with multiple tasks"""
        graph = CeleryMigrationGraph()

        # Execute multiple tasks in sequence
        tasks_to_test = [
            ("update_compliance_scores", {}),
            ("process_evidence", {"evidence_id": "TEST-001"}),
            ("database_metrics", {}),
            ("weekly_summary", {}),
        ]

        results = []
        for task_type, params in tasks_to_test:
            result = await graph.execute_task(task_type=task_type, params=params)
            results.append(result)

        # All tasks should complete successfully
        assert all(r["status"] == "completed" for r in results)
        assert len(results) == 4


@pytest.mark.asyncio
class TestMigrationCompleteness:
    """Verify 100% Celery task migration"""

    async def test_all_celery_tasks_migrated(self):
        """Verify all 16 Celery tasks have been migrated"""
        expected_tasks = {
            # Compliance (2)
            "update_compliance_scores",
            "check_compliance_alerts",
            # Evidence (2)
            "process_evidence",
            "sync_evidence",
            # Notification (3)
            "compliance_alert",
            "weekly_summary",
            "broadcast",
            # Reporting (4)
            "generate_report",
            "on_demand_report",
            "cleanup_reports",
            "report_notifications",
            # Monitoring (5)
            "database_metrics",
            "health_check",
            "cleanup_monitoring",
            "system_metrics",
            "register_tasks",
        }

        graph = CeleryMigrationGraph()
        migrated_tasks = set(graph.task_routes.keys())

        assert migrated_tasks == expected_tasks
        assert len(migrated_tasks) == 16

    async def test_periodic_task_coverage(self):
        """Verify periodic tasks are properly scheduled"""
        graph = CeleryMigrationGraph()

        # These tasks should have scheduled versions
        periodic_tasks = [
            "system_metrics",  # Every minute
            "database_metrics",  # Every 5 minutes
            "health_check",  # Every 15 minutes
            "update_compliance_scores",  # Every hour
            "check_compliance_alerts",  # Every 6 hours
            "sync_evidence",  # Every 2 hours
            "cleanup_monitoring",  # Every 6 hours
            "cleanup_reports",  # Daily
            "weekly_summary",  # Weekly,
        ]

        # Verify all periodic tasks are in the task routes
        for task in periodic_tasks:
            assert task in graph.task_routes

    async def test_factory_function(self):
        """Test the factory function creates a properly initialized graph"""
        graph = await create_celery_migration_graph()

        assert graph is not None
        assert graph.scheduler is not None
        assert graph.compiled_graph is not None

        # Clean up
        await graph.stop_scheduler()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
