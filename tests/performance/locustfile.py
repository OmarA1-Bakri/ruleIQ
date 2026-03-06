"""
Comprehensive performance testing scenarios for RuleIQ backend
including user workflows, AI operations, and system stress testing.
"""

import json
import random
import time
from uuid import uuid4
from locust import HttpUser, SequentialTaskSet, between, events, task
from locust.runners import MasterRunner
import logging

logger = logging.getLogger(__name__)
SAMPLE_COMPANIES = [
    "TechCorp Solutions",
    "DataFlow Systems",
    "SecureNet Ltd",
    "InnovateTech",
    "CloudFirst Inc",
    "CyberShield Co",
    "MetaData Analytics",
    "StreamlineTech",
]
SAMPLE_INDUSTRIES = [
    "Technology",
    "Financial Services",
    "Healthcare",
    "Manufacturing",
    "Retail",
    "Education",
    "Professional Services",
    "Media",
]
SAMPLE_QUESTIONS = [
    "What are the GDPR requirements for data processing?",
    "How do we implement ISO 27001 controls?",
    "What evidence is needed for SOC 2 audit?",
    "How to handle data breach notifications?",
    "What are the penalties for non-compliance?",
]


class AuthenticatedUser(HttpUser):
    """Base class for authenticated user scenarios"""

    def on_start(self):
        """Setup authentication for user session"""
        self.user_data = {
            "email": f"loadtest-{uuid4()}@example.com",
            "password": "LoadTest123!",
            "full_name": f"Load Test User {random.randint(1000, 9999)}",
        }
        register_response = self.client.post("/api/auth/register", json=self.user_data)
        if register_response.status_code == HTTP_CREATED:
            self.user_id = register_response.json()["user_id"]
        login_response = self.client.post(
            "/api/auth/login",
            json={"email": self.user_data["email"], "password": self.user_data["password"]},
        )
        if login_response.status_code == HTTP_OK:
            self.access_token = login_response.json()["access_token"]
            self.headers = {"Authorization": f"Bearer {self.access_token}"}
        else:
            self.headers = {}


class UserOnboardingFlow(SequentialTaskSet):
    """Sequential task set for complete user onboarding workflow"""

    def __init__(self, parent):
        super().__init__(parent)
        self.business_profile_id = None
        self.assessment_id = None

    @task
    def create_business_profile(self):
        """Create business profile"""
        profile_data = {
            "company_name": random.choice(SAMPLE_COMPANIES),
            "industry": random.choice(SAMPLE_INDUSTRIES),
            "employee_count": random.choice([10, 25, 50, 100, 250, 500]),
            "revenue_range": random.choice(["<1M", "1M-10M", "10M-50M", "50M+"]),
            "location": random.choice(["UK", "EU", "US", "Global"]),
            "description": "Load test company for performance testing",
            "data_processing": {
                "processes_personal_data": True,
                "data_types": ["customer_data", "employee_data"],
                "storage_locations": ["cloud", "on_premise"],
            },
        }
        with self.client.post(
            "/api/business-profiles",
            json=profile_data,
            headers=self.parent.headers,
            catch_response=True,
        ) as response:
            if response.status_code == HTTP_CREATED:
                self.business_profile_id = response.json()["id"]
                response.success()
            else:
                response.failure(f"Failed to create business profile: {response.status_code}")

    @task
    def start_assessment(self):
        """Start compliance assessment"""
        if not self.business_profile_id:
            return
        assessment_data = {
            "business_profile_id": self.business_profile_id,
            "assessment_type": "compliance_scoping",
            "frameworks_of_interest": random.sample(["GDPR", "ISO 27001", "SOC 2"], 2),
        }
        with self.client.post(
            "/api/assessments",
            json=assessment_data,
            headers=self.parent.headers,
            catch_response=True,
        ) as response:
            if response.status_code == HTTP_CREATED:
                self.assessment_id = response.json()["session_id"]
                response.success()
            else:
                response.failure(f"Failed to start assessment: {response.status_code}")

    @task
    def complete_assessment(self):
        """Complete assessment with responses"""
        if not self.assessment_id:
            return
        questions = [
            {"question_id": "data_processing", "response": "yes"},
            {"question_id": "data_types", "response": ["personal_data", "financial_data"]},
            {"question_id": "international_transfers", "response": "yes"},
            {"question_id": "security_measures", "response": ["encryption", "access_controls"]},
            {"question_id": "compliance_experience", "response": "basic"},
        ]
        for question in questions:
            response_data = {
                **question,
                "details": "Load test response",
                "move_to_next_stage": True,
            }
            self.client.post(
                f"/api/assessments/{self.assessment_id}/responses",
                json=response_data,
                headers=self.parent.headers,
                name="/api/assessments/[id]/responses",
            )
        with self.client.post(
            f"/api/assessments/{self.assessment_id}/complete",
            headers=self.parent.headers,
            catch_response=True,
            name="/api/assessments/[id]/complete",
        ) as response:
            if response.status_code == HTTP_OK:
                response.success()
            else:
                response.failure(f"Failed to complete assessment: {response.status_code}")

    @task
    def get_recommendations(self):
        """Get framework recommendations"""
        if not self.business_profile_id:
            return
        with self.client.get(
            f"/api/frameworks/recommendations/{self.business_profile_id}",
            headers=self.parent.headers,
            catch_response=True,
            name="/api/frameworks/recommendations/[id]",
        ) as response:
            if response.status_code == HTTP_OK:
                recommendations = response.json()
                if len(recommendations) > 0:
                    response.success()
                else:
                    response.failure("No recommendations returned")
            else:
                response.failure(f"Failed to get recommendations: {response.status_code}")


class ComplianceUser(AuthenticatedUser):
    """User focused on compliance workflows"""

    wait_time = between(1, 3)
    tasks = [UserOnboardingFlow]

    @task(3)
    def create_evidence_item(self):
        """Create evidence items"""
        evidence_types = ["document", "screenshot", "configuration", "audit_log"]
        evidence_data = {
            "title": f"Load Test Evidence {random.randint(1000, 9999)}",
            "description": "Evidence item created during load testing",
            "evidence_type": random.choice(evidence_types),
            "source": "manual",
            "framework_mappings": [
                f"ISO27001.A.{random.randint(5, 18)}.{random.randint(1, 5)}.{random.randint(1, 10)}"
            ],
            "tags": ["load_test", "performance"],
            "metadata": {"created_by": "load_test", "version": "1.0", "test_data": True},
        }
        self.client.post("/api/evidence", json=evidence_data, headers=self.headers)

    @task(2)
    def search_evidence(self):
        """Search evidence items"""
        search_terms = ["security", "policy", "procedure", "control", "audit"]
        params = {
            "q": random.choice(search_terms),
            "evidence_type": random.choice(["document", "screenshot"]),
            "page": random.randint(1, 3),
            "page_size": random.choice([10, 20, 50]),
        }
        self.client.get("/api/evidence/search", params=params, headers=self.headers)

    @task(1)
    def get_dashboard(self):
        """Access user dashboard"""
        self.client.get("/api/users/dashboard", headers=self.headers)

    @task(1)
    def get_compliance_status(self):
        """Check compliance status"""
        self.client.get("/api/compliance/status", headers=self.headers)


class AIAssistantUser(AuthenticatedUser):
    """User focused on AI assistant interactions"""

    wait_time = between(2, 5)

    @task(5)
    def ask_compliance_question(self):
        """Ask compliance questions to AI assistant"""
        question = random.choice(SAMPLE_QUESTIONS)
        chat_data = {
            "message": question,
            "conversation_id": getattr(self, "conversation_id", None),
            "context": {
                "framework": random.choice(["GDPR", "ISO 27001", "SOC 2"]),
                "urgency": random.choice(["low", "medium", "high"]),
            },
        }
        with self.client.post(
            "/api/chat/send", json=chat_data, headers=self.headers, catch_response=True
        ) as response:
            if response.status_code == HTTP_OK:
                result = response.json()
                if not hasattr(self, "conversation_id"):
                    self.conversation_id = result.get("conversation_id")
                response.success()
            else:
                response.failure(f"AI chat failed: {response.status_code}")

    @task(2)
    def get_chat_history(self):
        """Retrieve chat conversation history"""
        if hasattr(self, "conversation_id"):
            self.client.get(
                f"/api/chat/conversations/{self.conversation_id}/messages",
                headers=self.headers,
                name="/api/chat/conversations/[id]/messages",
            )

    @task(1)
    def start_new_conversation(self):
        """Start a new chat conversation"""
        conversation_data = {
            "title": f"Load Test Conversation {random.randint(1000, 9999)}",
            "context": {
                "business_profile_id": getattr(self, "business_profile_id", None),
                "frameworks": ["GDPR"],
            },
        }
        with self.client.post(
            "/api/chat/conversations",
            json=conversation_data,
            headers=self.headers,
            catch_response=True,
        ) as response:
            if response.status_code == HTTP_CREATED:
                self.conversation_id = response.json()["conversation_id"]
                response.success()
            else:
                response.failure(f"Failed to create conversation: {response.status_code}")


class ReportingUser(AuthenticatedUser):
    """User focused on reporting and analytics"""

    wait_time = between(3, 8)

    @task(3)
    def generate_compliance_report(self):
        """Generate compliance reports"""
        report_data = {
            "report_type": random.choice(
                ["gap_analysis", "readiness_assessment", "evidence_summary"]
            ),
            "frameworks": random.sample(["GDPR", "ISO 27001", "SOC 2"], random.randint(1, 2)),
            "format": random.choice(["pdf", "html", "json"]),
            "include_sections": ["summary", "findings", "recommendations"],
            "filters": {"date_range": {"start": "2024-01-01", "end": "2024-12-31"}},
        }
        with self.client.post(
            "/api/reports/generate", json=report_data, headers=self.headers, catch_response=True
        ) as response:
            if response.status_code == 202:
                task_id = response.json().get("task_id")
                if task_id:
                    self.check_report_status(task_id)
                response.success()
            else:
                response.failure(f"Report generation failed: {response.status_code}")

    def check_report_status(self, task_id):
        """Check report generation status"""
        max_checks = 10
        for _ in range(max_checks):
            with self.client.get(
                f"/api/reports/status/{task_id}",
                headers=self.headers,
                name="/api/reports/status/[id]",
                catch_response=True,
            ) as response:
                if response.status_code == HTTP_OK:
                    status = response.json().get("status")
                    if status == "completed":
                        response.success()
                        return
                    elif status == "failed":
                        response.failure("Report generation failed")
                        return
                    time.sleep(2)
                else:
                    response.failure(f"Status check failed: {response.status_code}")
                    return

    @task(2)
    def get_analytics_dashboard(self):
        """Access analytics dashboard"""
        params = {
            "time_range": random.choice(["7d", "30d", "90d", "1y"]),
            "metrics": ["compliance_score", "evidence_count", "framework_coverage"],
        }
        self.client.get("/api/analytics/dashboard", params=params, headers=self.headers)

    @task(1)
    def export_data(self):
        """Export compliance data"""
        export_data = {
            "data_type": random.choice(["evidence", "assessments", "audit_trail"]),
            "format": random.choice(["csv", "json", "excel"]),
            "date_range": {"start": "2024-01-01", "end": "2024-12-31"},
        }
        self.client.post("/api/export", json=export_data, headers=self.headers)


class StressTestUser(AuthenticatedUser):
    """High-intensity user for stress testing"""

    wait_time = between(0.1, 0.5)

    @task(10)
    def rapid_api_calls(self):
        """Make rapid API calls to test system limits"""
        endpoints = [
            "/api/users/profile",
            "/api/business-profiles",
            "/api/evidence/stats",
            "/api/frameworks",
            "/api/compliance/status",
        ]
        endpoint = random.choice(endpoints)
        self.client.get(endpoint, headers=self.headers)

    @task(5)
    def concurrent_evidence_creation(self):
        """Create evidence items rapidly"""
        evidence_data = {
            "title": f"Stress Test Evidence {random.randint(10000, 99999)}",
            "description": "Rapid evidence creation for stress testing",
            "evidence_type": "document",
            "source": "automated",
            "tags": ["stress_test"],
        }
        self.client.post("/api/evidence", json=evidence_data, headers=self.headers)

    @task(3)
    def bulk_operations(self):
        """Perform bulk operations"""
        bulk_data = {
            "evidence_ids": [str(uuid4()) for _ in range(10)],
            "status": "reviewed",
            "reason": "Bulk stress test update",
        }
        self.client.post("/api/evidence/bulk-update", json=bulk_data, headers=self.headers)


class LightLoad(AuthenticatedUser):
    """Light load testing - normal user behavior"""

    weight = 3
    tasks = [ComplianceUser, AIAssistantUser]


class MediumLoad(AuthenticatedUser):
    """Medium load testing - active user behavior"""

    weight = 2
    tasks = [ComplianceUser, AIAssistantUser, ReportingUser]


class HeavyLoad(AuthenticatedUser):
    """Heavy load testing - intensive operations"""

    weight = 1
    tasks = [ReportingUser, StressTestUser]


@events.request.add_listener
def request_handler(
    request_type, name, response_time, response_length, exception, context, **kwargs
):
    """Log slow requests and errors"""
    if response_time > 5000:
        logger.info("SLOW REQUEST: %s %s took %sms" % (request_type, name, response_time))
    if exception:
        logger.info("ERROR: %s %s failed with %s" % (request_type, name, exception))


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Setup test environment"""
    logger.info("Starting ComplianceGPT Performance Tests")
    logger.info("Target host: %s" % environment.host)
    if isinstance(environment.runner, MasterRunner):
        logger.info("Running distributed load test")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Cleanup after tests"""
    logger.info("Performance test completed")
    stats = environment.stats
    logger.info("Total requests: %s" % stats.total.num_requests)
    logger.info("Total failures: %s" % stats.total.num_failures)
    logger.info("Average response time: %sms" % stats.total.avg_response_time)
    logger.info("95th percentile: %sms" % stats.total.get_response_time_percentile(0.95))


class ChatWebSocketUser(HttpUser):
    """Test WebSocket chat performance"""

    def on_start(self):
        self.user_data = {
            "email": f"ws-test-{uuid4()}@example.com",
            "password": "WSTest123!",
            "full_name": "WebSocket Test User",
        }
        self.client.post("/api/auth/register", json=self.user_data)
        login_response = self.client.post(
            "/api/auth/login",
            json={"email": self.user_data["email"], "password": self.user_data["password"]},
        )
        if login_response.status_code == HTTP_OK:
            self.token = login_response.json()["access_token"]

    @task
    def websocket_chat_session(self):
        """Test WebSocket chat performance"""
        try:
            import websocket

            def on_message(ws, message):
                data = json.loads(message)
                if data.get("type") == "response":
                    ws.close()

            def on_open(ws):
                question = {
                    "type": "question",
                    "message": random.choice(SAMPLE_QUESTIONS),
                    "token": self.token,
                }
                ws.send(json.dumps(question))

            ws_url = self.host.replace("http", "ws") + "/ws/chat"
            ws = websocket.WebSocketApp(ws_url, on_message=on_message, on_open=on_open)
            ws.run_forever(timeout=30)
        except ImportError:
            self.client.post(
                "/api/chat/send",
                json={"message": random.choice(SAMPLE_QUESTIONS)},
                headers={"Authorization": f"Bearer {self.token}"},
            )


class DatabaseStressUser(AuthenticatedUser):
    """Test database operations under load"""

    wait_time = between(0.5, 2)

    @task(5)
    def complex_evidence_search(self):
        """Perform complex search queries"""
        search_params = {
            "q": "security policy governance",
            "evidence_type": ["document", "screenshot"],
            "framework": ["ISO27001", "GDPR"],
            "status": ["valid", "reviewed"],
            "date_range": {"start": "2024-01-01", "end": "2024-12-31"},
            "sort_by": "relevance",
            "page": random.randint(1, 10),
            "page_size": 50,
        }
        self.client.get("/api/evidence/search", params=search_params, headers=self.headers)

    @task(3)
    def aggregate_analytics(self):
        """Request analytics that require database aggregation"""
        analytics_params = {
            "metrics": ["compliance_trends", "framework_coverage", "evidence_quality"],
            "group_by": ["framework", "status", "date"],
            "time_range": "90d",
        }
        self.client.get("/api/analytics/aggregate", params=analytics_params, headers=self.headers)

    @task(2)
    def concurrent_updates(self):
        """Perform concurrent data updates"""
        for _ in range(5):
            evidence_data = {
                "title": f"Concurrent Update {random.randint(1000, 9999)}",
                "status": random.choice(["valid", "expired", "under_review"]),
                "quality_score": random.randint(60, 100),
            }
            create_response = self.client.post(
                "/api/evidence", json=evidence_data, headers=self.headers
            )
            if create_response.status_code == HTTP_CREATED:
                evidence_id = create_response.json()["id"]
                update_data = {"status": "reviewed", "notes": "Concurrent update test"}
                self.client.patch(
                    f"/api/evidence/{evidence_id}",
                    json=update_data,
                    headers=self.headers,
                    name="/api/evidence/[id]",
                )


class PeakTrafficScenario(AuthenticatedUser):
    """Simulate peak traffic scenarios"""

    def on_start(self):
        super().on_start()
        self.scenario_start_time = time.time()

    @task(10)
    def morning_rush_pattern(self):
        """Simulate morning rush hour user behavior"""
        self.client.get("/api/users/dashboard", headers=self.headers)
        self.client.get("/api/evidence?page=1&page_size=10", headers=self.headers)
        self.client.get("/api/compliance/status", headers=self.headers)

    @task(5)
    def deadline_crunch_pattern(self):
        """Simulate behavior during compliance deadlines"""
        report_data = {
            "report_type": "readiness_assessment",
            "frameworks": ["GDPR"],
            "format": "pdf",
            "priority": "urgent",
        }
        self.client.post("/api/reports/generate", json=report_data, headers=self.headers)
        for _ in range(3):
            evidence_data = {
                "title": f"Deadline Evidence {random.randint(1000, 9999)}",
                "evidence_type": "document",
                "urgent": True,
            }
            self.client.post("/api/evidence", json=evidence_data, headers=self.headers)


if __name__ == "__main__":
    logger.info("ComplianceGPT Performance Test Suite")
    logger.info("Usage: locust -f locustfile.py --host=http://localhost:8000")
    logger.info("Available user classes:")
    logger.info("- ComplianceUser: Standard compliance workflows")
    logger.info("- AIAssistantUser: AI chat and assistance")
    logger.info("- ReportingUser: Report generation and analytics")
    logger.info("- StressTestUser: High-intensity stress testing")
    logger.info("- ChatWebSocketUser: WebSocket performance testing")
    logger.info("- DatabaseStressUser: Database operation stress testing")
    logger.info("- PeakTrafficScenario: Peak traffic simulation")
