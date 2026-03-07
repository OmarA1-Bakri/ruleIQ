"""
End-to-End Workflow Testing for ComplianceGPT

This module tests complete user journeys, error state handling,
audit workflows, and reporting functionality.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
import requests


@pytest.mark.e2e
class TestCompleteComplianceJourney:
    """Test complete compliance implementation journeys from start to finish"""

    def test_new_business_complete_gdpr_journey(
        self, client, authenticated_headers, mock_ai_client
    ):
        """Test complete GDPR compliance journey for a new business"""
        mock_ai_client.generate_content.return_value.text = ("Generated compliance content",)

        # 1. Business registration and profile creation
        business_profile = {
            "company_name": "Tech Startup Ltd",
            "industry": "Technology",
            "employee_count": 15,
            "country": "UK",
            "handles_personal_data": True,
            "processes_payments": True,
            "has_international_operations": False,
            "cloud_providers": ["AWS", "Google Cloud"],
            "saas_tools": ["Salesforce", "Slack"],
            "existing_frameworks": [],
            "compliance_budget": "£10K-£25K",
            "compliance_timeline": "6 months",
        }

        profile_response = client.post(
            "/api/business-profiles",
            headers=authenticated_headers,
            json=business_profile,
        )
        assert profile_response.status_code == 201
        profile_response.json()["id"]

        # 2. Initial compliance assessment
        assessment_response = client.post(
            "/api/assessments",
            headers=authenticated_headers,
            json={"session_type": "compliance_scoping"},
        )
        assert assessment_response.status_code == 201
        session_id = assessment_response.json()["id"]

        # 3. Complete assessment questionnaire
        assessment_responses = [
            {"question_id": "data_processing", "response": "yes"},
            {"question_id": "data_types", "response": "customer_data,employee_data"},
            {"question_id": "data_storage", "response": "cloud"},
            {"question_id": "data_sharing", "response": "third_parties"},
            {"question_id": "security_measures", "response": "basic"},
            {"question_id": "staff_training", "response": "none"},
            {"question_id": "incident_response", "response": "informal"},
            {"question_id": "privacy_policy", "response": "outdated"},
        ]

        for response_data in assessment_responses:
            response = client.post(
                f"/api/assessments/{session_id}/responses",
                headers=authenticated_headers,
                json=response_data,
            )
            assert response.status_code == 200

        # 4. Get framework recommendations
        recommendations_response = client.get(
            f"/api/assessments/{session_id}/recommendations",
            headers=authenticated_headers,
        )
        assert recommendations_response.status_code == 200

        recommendations = recommendations_response.json()["recommendations"]
        gdpr_recommendation = next(
            (r for r in recommendations if "GDPR" in r["framework"]["name"]),
            None,
        )
        assert gdpr_recommendation is not None, "GDPR should be recommended"
        assert gdpr_recommendation["priority"] == "High"

        # 5. Generate GDPR policies
        gdpr_framework_id = gdpr_recommendation["framework"]["id"]

        policy_response = client.post(
            "/api/policies/generate",
            headers=authenticated_headers,
            json={
                "framework_id": gdpr_framework_id,
                "customizations": {
                    "company_name": business_profile["company_name"],
                    "industry": business_profile["industry"],
                },
            },
        )
        assert policy_response.status_code == 201
        policy_response.json()["id"]

        # 6. Create implementation plan
        plan_response = client.post(
            "/api/implementation/plans",
            headers=authenticated_headers,
            json={"framework_id": gdpr_framework_id},
        )
        assert plan_response.status_code == 201
        plan_id = plan_response.json()["id"]

        plan_data = plan_response.json()
        assert plan_data["total_phases"] >= 3
        assert plan_data["estimated_duration_weeks"] >= 12  # Realistic timeline

        # 7. Start implementation - complete first few tasks
        plan_details = client.get(
            f"/api/implementation/plans/{plan_id}",
            headers=authenticated_headers,
        )
        tasks = plan_details.json()["tasks"]

        for i, task in enumerate(tasks[:3]):  # Complete first 3 tasks
            task_update = client.patch(
                f"/api/implementation/plans/{plan_id}/tasks/{task['id']}",
                headers=authenticated_headers,
                json={
                    "status": "completed",
                    "actual_start": datetime.now(timezone.utc).isoformat(),
                    "actual_end": datetime.now(timezone.utc).isoformat(),
                    "notes": f"Completed task {i + 1}",
                },
            )
            assert task_update.status_code == 200

        # 8. Set up evidence collection
        evidence_response = client.get(
            f"/api/evidence/requirements?framework_id={gdpr_framework_id}",
            headers=authenticated_headers,
        )
        assert evidence_response.status_code == 200

        evidence_requirements = evidence_response.json()["requirements"]
        assert len(evidence_requirements) > 0

        # Create evidence items
        for requirement in evidence_requirements[:2]:  # Create first 2 evidence items
            evidence_create = client.post(
                "/api/evidence",
                headers=authenticated_headers,
                json={
                    "framework_id": gdpr_framework_id,
                    "control_id": requirement["control_id"],
                    "evidence_type": "document",
                    "title": f"Evidence for {requirement['title']}",
                    "collection_method": "manual",
                },
            )
            assert evidence_create.status_code == 201

        # 9. Check readiness assessment
        readiness_response = client.get(
            "/api/readiness/assessment",
            headers=authenticated_headers,
        )
        assert readiness_response.status_code == 200

        readiness_data = readiness_response.json()
        assert 0 <= readiness_data["overall_score"] <= 100
        assert readiness_data["risk_level"] in ["Low", "Medium", "High", "Critical"]

        # Initial score should be low-medium for new business
        assert readiness_data["overall_score"] < 80, "New business should have room for improvement"

        # 10. Generate compliance report
        report_response = client.post(
            "/api/readiness/reports",
            headers=authenticated_headers,
            json={
                "title": "Initial GDPR Compliance Assessment",
                "framework": "GDPR",
                "report_type": "gap_analysis",
                "format": "pdf",
            },
        )
        assert report_response.status_code == 201

        report_data = report_response.json()
        assert "report_id" in report_data
        assert "download_url" in report_data

        # Verify complete journey created all necessary components
        final_dashboard = client.get("/api/dashboard", headers=authenticated_headers)
        assert final_dashboard.status_code == 200

        dashboard_data = final_dashboard.json()
        assert "active_frameworks" in dashboard_data
        assert "implementation_progress" in dashboard_data
        assert "next_actions" in dashboard_data

    def test_existing_business_framework_migration_journey(
        self, client, authenticated_headers, mock_ai_client
    ):
        """Test journey for business migrating from one framework to another"""
        mock_ai_client.generate_content.return_value.text = "Migration guidance content"

        # Business with existing basic compliance
        existing_business = {
            "company_name": "Established Corp Ltd",
            "industry": "Financial Services",
            "employee_count": 150,
            "country": "UK",
            "handles_personal_data": True,
            "provides_financial_services": True,
            "existing_frameworks": ["Basic Data Protection"],
            "planned_frameworks": ["GDPR", "FCA Guidelines"],
            "compliance_budget": "£50K-£100K",
            "compliance_timeline": "12 months",
        }

        profile_response = client.post(
            "/api/business-profiles",
            headers=authenticated_headers,
            json=existing_business,
        )
        assert profile_response.status_code == 201

        # Get migration recommendations
        migration_response = client.post(
            "/api/frameworks/migration-plan",
            headers=authenticated_headers,
            json={
                "current_frameworks": existing_business["existing_frameworks"],
                "target_frameworks": existing_business["planned_frameworks"],
            },
        )

        if migration_response.status_code == 200:
            migration_plan = migration_response.json()
            assert "migration_steps" in migration_plan
            assert "effort_estimate" in migration_plan
            assert "risk_assessment" in migration_plan


@pytest.mark.e2e
class TestErrorStateHandling:
    """Test comprehensive error state handling and recovery"""

    def test_network_interruption_recovery(self, client, authenticated_headers):
        """Test system behavior during network interruptions"""
        # Simulate network timeout during assessment
        session_response = client.post(
            "/api/assessments",
            headers=authenticated_headers,
            json={"session_type": "compliance_scoping"},
        )
        session_id = session_response.json()["id"]

        # Submit response that might be interrupted
        with patch("requests.post") as mock_post:
            mock_post.side_effect = TimeoutError("Network timeout")

            response = client.post(
                f"/api/assessments/{session_id}/responses",
                headers=authenticated_headers,
                json={
                    "question_id": "data_processing",
                    "response": "yes",
                    "auto_save": True,
                },
            )

            # System should handle gracefully
            assert response.status_code in [
                200,
                408,
                503,
            ], "Should handle network issues gracefully"

        # Verify session state is recoverable
        recovery_response = client.get(
            f"/api/assessments/{session_id}",
            headers=authenticated_headers,
        )
        assert recovery_response.status_code == 200

        session_data = recovery_response.json()
        assert session_data["status"] in [
            "in_progress",
            "draft",
        ], "Session should be recoverable"

    def test_invalid_data_graceful_handling(self, client, authenticated_headers):
        """Test graceful handling of invalid or corrupted data"""
        # Test with malformed JSON
        invalid_requests = [
            {"company_name": None, "industry": None},  # Null values
            {"company_name": "A" * 1000},  # Too long
            {"employee_count": "not_a_number"},  # Wrong type
            {},  # Empty object,
        ]

        for invalid_data in invalid_requests:
            response = client.post(
                "/api/business-profiles",
                headers=authenticated_headers,
                json=invalid_data,
            )

            # Should return proper error codes, not crash
            assert response.status_code in [
                400,
                422,
            ], f"Should handle invalid data: {invalid_data}"

            # Error messages should be helpful
            if response.status_code == 422:
                error_data = response.json()
                # FastAPI returns validation errors in 'detail' field
                assert "detail" in error_data
                assert isinstance(error_data["detail"], list)
                assert len(error_data["detail"]) > 0

    def test_concurrent_user_conflict_resolution(self, client, authenticated_headers):
        """Test handling of concurrent user modifications"""
        # Create business profile
        business_data = {
            "company_name": "Concurrent Test Ltd",
            "industry": "Technology",
            "employee_count": 25,
        }

        profile_response = client.post(
            "/api/business-profiles",
            headers=authenticated_headers,
            json=business_data,
        )
        profile_id = profile_response.json()["id"]

        # Simulate concurrent updates
        update_1 = {"employee_count": 30, "version": 1}
        update_2 = {
            "industry": "FinTech",
            "version": 1,
        }  # Same version - potential conflict

        response_1 = client.patch(
            f"/api/business-profiles/{profile_id}",
            headers=authenticated_headers,
            json=update_1,
        )

        response_2 = client.patch(
            f"/api/business-profiles/{profile_id}",
            headers=authenticated_headers,
            json=update_2,
        )

        # One should succeed, one should handle conflict
        status_codes = [response_1.status_code, response_2.status_code]
        assert 200 in status_codes, "At least one update should succeed"

        if 409 in status_codes:  # Conflict detected
            conflict_response = (response_1 if response_1.status_code == 409 else response_2,)
            conflict_data = conflict_response.json()
            assert "conflict" in conflict_data["error"]["message"].lower()

    def test_external_service_failure_fallback(self, client, authenticated_headers, mock_ai_client):
        """Test fallback behavior when external services fail"""
        # Mock AI service failure
        mock_ai_client.generate_content.side_effect = Exception(
            "AI service unavailable",
        )

        frameworks_response = client.get(
            "/api/frameworks",
            headers=authenticated_headers,
        )
        if frameworks_response.status_code == 200:
            frameworks_data = frameworks_response.json()
            # Handle both list and dict response formats
            if isinstance(frameworks_data, list) and len(frameworks_data) > 0:
                framework_id = frameworks_data[0]["id"]
            elif isinstance(frameworks_data, dict) and "frameworks" in frameworks_data:
                framework_id = frameworks_data["frameworks"][0]["id"]
            else:
                framework_id = None

            # Only attempt policy generation if we have a valid framework_id
            if framework_id:
                # Attempt policy generation with AI failure
                policy_response = client.post(
                    "/api/policies/generate",
                    headers=authenticated_headers,
                    json={"framework_id": framework_id},
                )

                # Should provide graceful fallback
                if policy_response.status_code == 503:
                    error_data = policy_response.json()
                    assert "ai service" in error_data["error"]["message"].lower()
                    assert "try again" in error_data["error"]["message"].lower()
                elif policy_response.status_code == 200:
                    # Should provide template-based fallback
                    policy_data = policy_response.json()
                    assert "content" in policy_data
                    assert ("template" in policy_data.get("generation_method", "").lower(),)


@pytest.mark.e2e
class TestAuditWorkflows:
    """Test audit trail and compliance reporting workflows"""

    def test_comprehensive_audit_trail(self, client, authenticated_headers, mock_ai_client):
        """Test that all user actions are properly audited"""
        mock_ai_client.generate_content.return_value.text = "Audit test content"

        # Perform series of auditable actions
        auditable_actions = []

        # 1. Create business profile
        profile_response = client.post(
            "/api/business-profiles",
            headers=authenticated_headers,
            json={
                "company_name": "Audit Test Corp",
                "industry": "Technology",
                "employee_count": 50,
            },
        )
        assert profile_response.status_code == 201
        auditable_actions.append(
            ("create_business_profile", profile_response.json()["id"]),
        )

        # 2. Generate policy
        frameworks_response = client.get(
            "/api/frameworks",
            headers=authenticated_headers,
        )
        if frameworks_response.status_code == 200:
            frameworks_data = frameworks_response.json()
            # Handle both list and dict response formats
            if isinstance(frameworks_data, list) and len(frameworks_data) > 0:
                framework_id = frameworks_data[0]["id"]
            elif isinstance(frameworks_data, dict) and "frameworks" in frameworks_data:
                framework_id = frameworks_data["frameworks"][0]["id"]
            else:
                framework_id = None

            # Only attempt policy generation if we have a valid framework_id
            if framework_id:
                policy_response = client.post(
                    "/api/policies/generate",
                    headers=authenticated_headers,
                    json={"framework_id": framework_id},
                )
                if policy_response.status_code == 201:
                    policy_id = policy_response.json()["id"]
                    auditable_actions.append(("generate_policy", policy_id))

                    # 3. Approve policy
                    approval_response = client.patch(
                        f"/api/policies/{policy_id}/status",
                        headers=authenticated_headers,
                        json={"status": "approved", "approved": True},
                    )
                    if approval_response.status_code == 200:
                        auditable_actions.append(("approve_policy", policy_id))

        # 4. Check audit trail
        audit_response = client.get("/api/audit/trail", headers=authenticated_headers)

        if audit_response.status_code == 200:
            audit_trail = audit_response.json()["audit_entries"]

            # Verify all actions are recorded
            recorded_actions = [entry["action"] for entry in audit_trail]
            for action_type, _resource_id in auditable_actions:
                assert any(action_type in action for action in recorded_actions), (
                    f"Action {action_type} should be in audit trail"
                )

            # Verify audit entries have required fields
            for entry in audit_trail:
                required_fields = [
                    "timestamp",
                    "user_id",
                    "action",
                    "resource_type",
                    "resource_id",
                ]
                for field in required_fields:
                    assert field in entry, f"Audit entry missing required field: {field}"

                # Verify timestamp format
                assert "T" in entry["timestamp"], "Timestamp should be in ISO format"

    def test_compliance_report_generation(
        self, client, authenticated_headers, sample_business_profile_data
    ):
        """Test comprehensive compliance reporting"""
        # Setup business context
        profile_response = client.post(
            "/api/business-profiles",
            headers=authenticated_headers,
            json=sample_business_profile_data,
        )
        assert profile_response.status_code == 201

        # Generate different types of reports
        report_types = [
            {
                "title": "Executive Summary Report",
                "report_type": "executive",
                "format": "pdf",
                "include_evidence": False,
                "include_recommendations": True,
            },
            {
                "title": "Detailed Compliance Report",
                "report_type": "detailed",
                "format": "pdf",
                "include_evidence": True,
                "include_recommendations": True,
            },
            {
                "title": "Audit Preparation Report",
                "report_type": "audit",
                "format": "docx",
                "include_evidence": True,
                "include_recommendations": False,
            },
        ]

        generated_reports = []
        for report_config in report_types:
            report_response = client.post(
                "/api/readiness/reports",
                headers=authenticated_headers,
                json=report_config,
            )

            if report_response.status_code == 201:
                report_data = report_response.json()
                generated_reports.append(report_data)

                # Verify report structure
                assert "report_id" in report_data
                assert "download_url" in report_data
                assert "status" in report_data

                # Check report accessibility
                download_response = client.get(
                    f"/api/readiness/reports/{report_data['report_id']}/download",
                    headers=authenticated_headers,
                )
                assert download_response.status_code in [
                    200,
                    202,
                ], "Report should be accessible"

        assert len(generated_reports) >= 2, "Should successfully generate multiple report types"

    def test_regulatory_submission_preparation(self, client, authenticated_headers, mock_ai_client):
        """Test preparation of materials for regulatory submissions"""
        mock_ai_client.generate_content.return_value.text = ("Regulatory submission content",)

        # Create comprehensive business setup
        business_profile = {
            "company_name": "RegSubmission Corp",
            "industry": "Financial Services",
            "employee_count": 200,
            "handles_personal_data": True,
            "provides_financial_services": True,
            "has_international_operations": True,
        }

        profile_response = client.post(
            "/api/business-profiles",
            headers=authenticated_headers,
            json=business_profile,
        )
        assert profile_response.status_code == 201

        # Generate regulatory submission package
        submission_response = client.post(
            "/api/regulatory/submission-package",
            headers=authenticated_headers,
            json={
                "submission_type": "ico_accountability_documentation",
                "frameworks": ["GDPR"],
                "include_policies": True,
                "include_procedures": True,
                "include_evidence": True,
                "include_training_records": True,
            },
        )

        if submission_response.status_code == 201:
            submission_data = submission_response.json()

            # Verify submission package completeness
            assert "package_id" in submission_data
            assert "included_documents" in submission_data
            assert "checklist" in submission_data

            # Verify required documents are included
            included_docs = submission_data["included_documents"]
            required_doc_types = [
                "policies",
                "procedures",
                "evidence",
                "training_records",
            ]

            for doc_type in required_doc_types:
                assert any(doc_type in doc["type"] for doc in included_docs), (
                    f"Submission should include {doc_type}"
                )


@pytest.mark.e2e
class TestBusinessContinuityWorkflows:
    """Test business continuity and disaster recovery scenarios"""

    def test_data_backup_and_recovery(
        self, client, authenticated_headers, sample_business_profile_data
    ):
        """Test data backup and recovery procedures"""
        # Create substantial business data
        profile_response = client.post(
            "/api/business-profiles",
            headers=authenticated_headers,
            json=sample_business_profile_data,
        )
        assert profile_response.status_code == 201
        profile_response.json()["id"]

        # Create assessment data
        assessment_response = client.post(
            "/api/assessments",
            headers=authenticated_headers,
            json={"session_type": "compliance_scoping"},
        )
        assessment_response.json()["id"]

        # Request data export (backup)
        export_response = client.post(
            "/api/data/export",
            headers=authenticated_headers,
            json={
                "export_type": "complete_backup",
                "format": "json",
                "include_documents": True,
            },
        )

        if export_response.status_code == 201:
            export_data = export_response.json()
            assert "export_id" in export_data
            assert "download_url" in export_data

            # Verify export completeness
            export_details = client.get(
                f"/api/data/exports/{export_data['export_id']}",
                headers=authenticated_headers,
            )

            if export_details.status_code == 200:
                details = export_details.json()
                assert "business_profiles" in details["included_data"]
                assert "assessments" in details["included_data"]

    def test_compliance_deadline_management(self, client, authenticated_headers):
        """Test compliance deadline tracking and alerts"""
        # Set up compliance deadlines
        deadline_response = client.post(
            "/api/compliance/deadlines",
            headers=authenticated_headers,
            json={
                "deadline_type": "gdpr_compliance_review",
                "due_date": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
                "framework": "GDPR",
                "priority": "High",
                "description": "Annual GDPR compliance review",
            },
        )

        if deadline_response.status_code == 201:
            # Check deadline alerts
            alerts_response = client.get(
                "/api/compliance/alerts",
                headers=authenticated_headers,
            )

            if alerts_response.status_code == 200:
                alerts = alerts_response.json()["alerts"]

                # Should have upcoming deadline alert
                deadline_alerts = [alert for alert in alerts if "deadline" in alert["type"]]
                assert len(deadline_alerts) > 0, "Should alert about upcoming deadlines"

    def test_multi_framework_coordination(self, client, authenticated_headers, mock_ai_client):
        """Test coordination across multiple compliance frameworks"""
        mock_ai_client.generate_content.return_value.text = (
            "Multi-framework coordination content",
        )

        # Business requiring multiple frameworks
        complex_business = {
            "company_name": "Multi-Framework Corp",
            "industry": "Healthcare Technology",
            "employee_count": 100,
            "handles_personal_data": True,
            "stores_health_data": True,
            "provides_financial_services": False,
            "has_international_operations": True,
            "planned_frameworks": ["GDPR", "HIPAA", "ISO 27001"],
        }

        profile_response = client.post(
            "/api/business-profiles",
            headers=authenticated_headers,
            json=complex_business,
        )
        assert profile_response.status_code == 201

        # Get multi-framework coordination plan
        coordination_response = client.post(
            "/api/frameworks/coordination-plan",
            headers=authenticated_headers,
            json={
                "frameworks": complex_business["planned_frameworks"],
                "business_context": complex_business,
            },
        )

        if coordination_response.status_code == 200:
            coordination_plan = coordination_response.json()

            # Verify coordination elements
            assert "framework_overlaps" in coordination_plan
            assert "shared_controls" in coordination_plan
            assert "implementation_sequence" in coordination_plan
            assert "resource_optimization" in coordination_plan

            # Verify identifies overlaps
            overlaps = coordination_plan["framework_overlaps"]
            assert len(overlaps) > 0, "Should identify framework overlaps"

            # Verify suggests implementation sequence
            sequence = coordination_plan["implementation_sequence"]
            assert len(sequence) == len(complex_business["planned_frameworks"]), (
                "Should provide sequence for all frameworks"
            )
