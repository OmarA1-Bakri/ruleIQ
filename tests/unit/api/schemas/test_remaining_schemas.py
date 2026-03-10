"""Tests for api.schemas: compliance, quality_analysis, evidence_classification,
evidence_collection, and iq_agent schemas."""
import pytest
from datetime import datetime
from uuid import uuid4

# ── compliance.py ────────────────────────────────────────────────
from api.schemas.compliance import (
    FrameworkCategory,
    GeographicRegion,
    UKFrameworkSchema,
    FrameworkResponse,
    FrameworkListResponse,
    FrameworkLoadRequest,
    FrameworkLoadResponse,
    FrameworkQueryParams,
)

# ── quality_analysis.py ─────────────────────────────────────────
from api.schemas.quality_analysis import (
    QualityScoreBreakdown,
    TraditionalScoreBreakdown,
    AIAnalysisResult,
    QualityAnalysisResponse,
    DuplicateCandidate,
    DuplicateDetectionRequest,
    DuplicateDetectionResponse,
    DuplicateGroup,
    BatchDuplicateDetectionRequest,
    BatchDuplicateDetectionResponse,
    QualityBenchmarkRequest,
    QualityBenchmarkResponse,
    QualityTrendRequest,
    QualityTrendResponse,
)

# ── evidence_classification.py ──────────────────────────────────
from api.schemas.evidence_classification import (
    EvidenceClassificationRequest,
    EvidenceClassificationResponse,
    BulkClassificationRequest,
    ClassificationResult,
    BulkClassificationResponse,
    ControlMappingRequest,
    ControlMappingResponse,
    ClassificationStatsResponse,
)

# ── evidence_collection.py ──────────────────────────────────────
from api.schemas.evidence_collection import (
    CollectionPlanCreate,
    AutomationOpportunities,
    EvidenceTaskResponse,
    CollectionPlanResponse,
    CollectionPlanSummary,
    TaskStatusUpdate,
    AutomationRecommendation,
    AutomationRecommendationsResponse,
)

# ── iq_agent.py ─────────────────────────────────────────────────
from api.schemas.iq_agent import (
    ComplianceQueryRequest,
    GraphContext,
    ComplianceSummary,
    ActionPlan,
    ComplianceArtifacts,
    ComplianceEvidence,
    NextAction,
    IQAgentResponse,
    MemoryStoreRequest,
    MemoryRetrievalRequest,
    MemoryNode,
    MemoryRetrievalResponse,
    GraphInitializationRequest,
    GraphInitializationResponse,
    HealthCheckResponse,
)


# ══════════════════════════════════════════════════════════════════
#  COMPLIANCE SCHEMAS
# ══════════════════════════════════════════════════════════════════

class TestComplianceEnums:
    def test_framework_category(self):
        assert len(FrameworkCategory) == 5
        assert FrameworkCategory.DATA_PROTECTION is not None
        assert FrameworkCategory.FINANCIAL_SERVICES is not None
        assert FrameworkCategory.GENERAL is not None

    def test_geographic_region(self):
        assert len(GeographicRegion) >= 7
        assert GeographicRegion.UK is not None
        assert GeographicRegion.ENGLAND is not None
        assert GeographicRegion.EU is not None
        assert GeographicRegion.GLOBAL is not None


class TestUKFrameworkSchema:
    def test_minimal(self):
        r = UKFrameworkSchema(
            name="gdpr", display_name="GDPR",
            description="General Data Protection Regulation",
            category=FrameworkCategory.DATA_PROTECTION,
        )
        assert r.complexity_score == 1
        assert r.implementation_time_weeks == 12
        assert r.version == "1.0"
        assert r.is_active is True
        assert r.geographic_scope == [GeographicRegion.UK]

    def test_no_uk_scope_rejected(self):
        with pytest.raises(Exception):
            UKFrameworkSchema(
                name="global", display_name="Global",
                description="A global framework with no UK scope",
                category=FrameworkCategory.GENERAL,
                geographic_scope=[GeographicRegion.EU, GeographicRegion.GLOBAL],
            )

    def test_complexity_range(self):
        base = dict(
            name="x", display_name="X", description="Description here",
            category=FrameworkCategory.GENERAL,
        )
        UKFrameworkSchema(**base, complexity_score=1)
        UKFrameworkSchema(**base, complexity_score=10)
        with pytest.raises(Exception):
            UKFrameworkSchema(**base, complexity_score=0)
        with pytest.raises(Exception):
            UKFrameworkSchema(**base, complexity_score=11)

    def test_version_pattern(self):
        base = dict(
            name="x", display_name="X", description="Description here",
            category=FrameworkCategory.GENERAL,
        )
        UKFrameworkSchema(**base, version="2.0")
        UKFrameworkSchema(**base, version="1.0.1")
        with pytest.raises(Exception):
            UKFrameworkSchema(**base, version="v1.0")

    def test_short_description(self):
        with pytest.raises(Exception):
            UKFrameworkSchema(
                name="x", display_name="X", description="Short",
                category=FrameworkCategory.GENERAL,
            )


class TestFrameworkResponse:
    def test_valid(self):
        r = FrameworkResponse(
            id="f1", name="gdpr", display_name="GDPR",
            description="Data protection", category="DATA_PROTECTION",
            geographic_scope=["UK"], complexity_score=5,
            version="1.0", is_active=True,
            created_at="2024-01-01", updated_at="2024-01-01",
        )
        assert r.id == "f1"


class TestFrameworkListResponse:
    def test_valid(self):
        r = FrameworkListResponse(
            frameworks=[], total_count=0, filtered_count=0,
        )
        assert r.region is None
        assert r.category is None


class TestFrameworkLoadRequest:
    def test_empty_frameworks_rejected(self):
        with pytest.raises(Exception):
            FrameworkLoadRequest(frameworks=[])

    def test_valid(self):
        fw = UKFrameworkSchema(
            name="x", display_name="X", description="Description here",
            category=FrameworkCategory.GENERAL,
        )
        r = FrameworkLoadRequest(frameworks=[fw])
        assert r.overwrite_existing is False


class TestFrameworkLoadResponse:
    def test_valid(self):
        r = FrameworkLoadResponse(
            success=True, loaded_count=1, skipped_count=0,
            error_count=0, loaded_frameworks=["GDPR"],
            skipped_frameworks=[], errors=[], total_processed=1,
        )
        assert r.total_processed == 1


class TestFrameworkQueryParams:
    def test_defaults(self):
        r = FrameworkQueryParams()
        assert r.active_only is True
        assert r.complexity_min is None

    def test_valid_complexity_range(self):
        r = FrameworkQueryParams(complexity_min=3, complexity_max=7)
        assert r.complexity_min == 3

    def test_invalid_complexity_range(self):
        with pytest.raises(Exception):
            FrameworkQueryParams(complexity_min=8, complexity_max=3)


# ══════════════════════════════════════════════════════════════════
#  QUALITY ANALYSIS SCHEMAS
# ══════════════════════════════════════════════════════════════════

class TestQualityScoreBreakdown:
    def test_valid(self):
        r = QualityScoreBreakdown(
            completeness=80, clarity=90, currency=70,
            verifiability=85, relevance=95, sufficiency=75,
        )
        assert r.completeness == 80

    def test_out_of_range(self):
        with pytest.raises(Exception):
            QualityScoreBreakdown(
                completeness=101, clarity=90, currency=70,
                verifiability=85, relevance=95, sufficiency=75,
            )


class TestTraditionalScoreBreakdown:
    def test_valid(self):
        r = TraditionalScoreBreakdown(
            completeness=80, freshness=90,
            content_quality=85, relevance=95,
        )
        assert r.freshness == 90


class TestAIAnalysisResult:
    def test_valid(self):
        scores = QualityScoreBreakdown(
            completeness=80, clarity=90, currency=70,
            verifiability=85, relevance=95, sufficiency=75,
        )
        r = AIAnalysisResult(
            scores=scores, overall_score=82.5, ai_confidence=90,
        )
        assert r.strengths == []
        assert r.weaknesses == []


class TestQualityAnalysisResponse:
    def test_valid(self):
        trad = TraditionalScoreBreakdown(
            completeness=80, freshness=90, content_quality=85, relevance=95,
        )
        scores = QualityScoreBreakdown(
            completeness=80, clarity=90, currency=70,
            verifiability=85, relevance=95, sufficiency=75,
        )
        ai = AIAnalysisResult(scores=scores, overall_score=82.5, ai_confidence=90)
        r = QualityAnalysisResponse(
            evidence_id=uuid4(), evidence_name="Policy Doc",
            overall_score=82.5, traditional_scores=trad,
            ai_analysis=ai, scoring_method="hybrid",
            confidence=90, analysis_timestamp="2024-01-01",
        )
        assert r.scoring_method == "hybrid"


class TestDuplicateDetection:
    def test_candidate(self):
        r = DuplicateCandidate(
            candidate_id=uuid4(), candidate_name="Doc A",
            similarity_score=85.0, similarity_type="content",
            reasoning="Very similar", recommendation="merge",
        )
        assert r.similarity_score == 85.0

    def test_request_defaults(self):
        r = DuplicateDetectionRequest(evidence_id=uuid4())
        assert r.similarity_threshold == 80.0
        assert r.max_candidates == 20

    def test_request_threshold_range(self):
        with pytest.raises(Exception):
            DuplicateDetectionRequest(evidence_id=uuid4(), similarity_threshold=40)

    def test_response(self):
        r = DuplicateDetectionResponse(
            evidence_id=uuid4(), evidence_name="Doc",
            duplicates_found=0, duplicates=[],
            analysis_timestamp="2024-01-01",
        )
        assert r.duplicates_found == 0

    def test_batch_request(self):
        ids = [uuid4(), uuid4()]
        r = BatchDuplicateDetectionRequest(evidence_ids=ids)
        assert r.similarity_threshold == 80.0

    def test_batch_request_too_few(self):
        with pytest.raises(Exception):
            BatchDuplicateDetectionRequest(evidence_ids=[uuid4()])

    def test_batch_response(self):
        r = BatchDuplicateDetectionResponse(
            total_items=10, duplicate_groups=[],
            potential_duplicates=2, unique_items=8,
            analysis_summary="Some duplicates",
            analysis_timestamp="2024-01-01",
        )
        assert r.unique_items == 8


class TestQualityBenchmark:
    def test_request_defaults(self):
        r = QualityBenchmarkRequest()
        assert r.framework is None
        assert r.evidence_type is None

    def test_response(self):
        r = QualityBenchmarkResponse(
            user_average_score=75, benchmark_score=80,
            percentile_rank=60, score_distribution={"80-90": 5},
        )
        assert r.improvement_areas == []


class TestQualityTrend:
    def test_request_defaults(self):
        r = QualityTrendRequest()
        assert r.days == 30

    def test_request_range(self):
        with pytest.raises(Exception):
            QualityTrendRequest(days=5)
        with pytest.raises(Exception):
            QualityTrendRequest(days=400)

    def test_response(self):
        r = QualityTrendResponse(
            period_days=30, trend_direction="improving",
            average_score_change=5.0, daily_scores=[],
        )
        assert r.insights == []


# ══════════════════════════════════════════════════════════════════
#  EVIDENCE CLASSIFICATION SCHEMAS
# ══════════════════════════════════════════════════════════════════

class TestEvidenceClassificationSchemas:
    def test_classification_request(self):
        r = EvidenceClassificationRequest(evidence_id=uuid4())
        assert r.force_reclassify is False

    def test_classification_response(self):
        r = EvidenceClassificationResponse(
            evidence_id=uuid4(), current_type="policy",
            ai_classification={"type": "procedure", "confidence": 85},
            apply_suggestion=True, confidence=85,
            suggested_controls=["A.5.1"], reasoning="Content matches",
        )
        assert r.confidence == 85

    def test_bulk_request(self):
        ids = [uuid4() for _ in range(5)]
        r = BulkClassificationRequest(evidence_ids=ids)
        assert r.force_reclassify is False
        assert r.apply_high_confidence is True
        assert r.confidence_threshold == 70

    def test_bulk_request_empty(self):
        with pytest.raises(Exception):
            BulkClassificationRequest(evidence_ids=[])

    def test_bulk_request_too_many(self):
        ids = [uuid4() for _ in range(51)]
        with pytest.raises(Exception):
            BulkClassificationRequest(evidence_ids=ids)

    def test_classification_result(self):
        r = ClassificationResult(
            evidence_id=uuid4(), success=True, current_type="policy",
        )
        assert r.suggested_type is None
        assert r.applied is False

    def test_bulk_response(self):
        r = BulkClassificationResponse(
            total_processed=5, successful_classifications=4,
            failed_classifications=1, results=[],
        )
        assert r.auto_applied == 0

    def test_control_mapping_request(self):
        r = ControlMappingRequest(evidence_id=uuid4())
        assert r.frameworks == ["ISO27001", "SOC2", "GDPR"]

    def test_control_mapping_response(self):
        r = ControlMappingResponse(
            evidence_id=uuid4(), evidence_type="policy",
            framework_mappings={"ISO27001": ["A.5.1"]},
            confidence_scores={"ISO27001": 90},
            reasoning="Direct mapping",
        )
        assert "ISO27001" in r.framework_mappings

    def test_stats_response(self):
        r = ClassificationStatsResponse(
            total_evidence=100, classified_evidence=80,
            unclassified_evidence=20, classification_accuracy=90.0,
            type_distribution={"policy": 40, "procedure": 40},
            confidence_distribution={"high": 60, "medium": 20},
            recent_classifications=15,
        )
        assert r.classification_accuracy == 90.0


# ══════════════════════════════════════════════════════════════════
#  EVIDENCE COLLECTION SCHEMAS
# ══════════════════════════════════════════════════════════════════

class TestEvidenceCollectionSchemas:
    def test_collection_plan_create(self):
        r = CollectionPlanCreate(framework="ISO27001")
        assert r.target_completion_weeks == 12
        assert r.include_existing_evidence is False

    def test_collection_plan_create_range(self):
        with pytest.raises(Exception):
            CollectionPlanCreate(framework="X", target_completion_weeks=0)
        with pytest.raises(Exception):
            CollectionPlanCreate(framework="X", target_completion_weeks=53)

    def test_automation_opportunities(self):
        r = AutomationOpportunities(
            total_tasks=20, automatable_tasks=12,
            automation_percentage=60.0, effort_savings_hours=40.0,
            effort_savings_percentage=50.0,
            recommended_tools=["Tool A"],
        )
        assert r.automatable_tasks == 12

    def test_evidence_task_response(self):
        r = EvidenceTaskResponse(
            task_id="t1", framework="GDPR", control_id="Art.5",
            evidence_type="document", title="Privacy Policy",
            description="Create privacy policy", priority="HIGH",
            automation_level="manual", estimated_effort_hours=8.0,
            status="pending", created_at=datetime.now(),
        )
        assert r.dependencies == []
        assert r.assigned_to is None
        assert r.metadata == {}

    def test_collection_plan_response(self):
        auto = AutomationOpportunities(
            total_tasks=1, automatable_tasks=0,
            automation_percentage=0, effort_savings_hours=0,
            effort_savings_percentage=0, recommended_tools=[],
        )
        r = CollectionPlanResponse(
            plan_id="p1", business_profile_id="bp1",
            framework="ISO27001", total_tasks=1,
            estimated_total_hours=10.0,
            completion_target_date=datetime.now(),
            tasks=[], automation_opportunities=auto,
            created_at=datetime.now(),
        )
        assert r.total_tasks == 1

    def test_collection_plan_summary(self):
        r = CollectionPlanSummary(
            plan_id="p1", framework="GDPR", total_tasks=10,
            completed_tasks=5, estimated_total_hours=80.0,
            completion_target_date=datetime.now(),
            status="in_progress", created_at=datetime.now(),
        )
        assert r.completed_tasks == 5

    def test_task_status_update(self):
        r = TaskStatusUpdate(status="completed")
        assert r.completion_notes is None

    def test_automation_recommendation(self):
        r = AutomationRecommendation(
            evidence_type="access_logs", automation_level="high",
            effort_reduction="70%", success_rate="95%",
            recommended_tools=["SIEM"],
        )
        assert r.evidence_type == "access_logs"

    def test_automation_recommendations_response(self):
        r = AutomationRecommendationsResponse(
            framework="ISO27001", automation_opportunities=[],
            recommended_tools=["Tool"], estimated_time_savings=20.0,
        )
        assert r.estimated_time_savings == 20.0


# ══════════════════════════════════════════════════════════════════
#  IQ AGENT SCHEMAS
# ══════════════════════════════════════════════════════════════════

class TestIQAgentSchemas:
    def test_compliance_query_request(self):
        r = ComplianceQueryRequest(query="What is GDPR?")
        assert r.include_graph_analysis is True
        assert r.include_recommendations is True
        assert r.context is None

    def test_query_request_empty(self):
        with pytest.raises(Exception):
            ComplianceQueryRequest(query="")

    def test_graph_context(self):
        r = GraphContext(
            nodes_traversed=10, patterns_detected=[],
            memories_accessed=["mem1"], learnings_applied=2,
        )
        assert r.nodes_traversed == 10

    def test_compliance_summary(self):
        r = ComplianceSummary(
            risk_posture="HIGH", compliance_score=0.6,
            top_gaps=["Gap 1"], immediate_actions=["Action 1"],
        )
        assert r.compliance_score == 0.6

    def test_compliance_summary_max_items(self):
        r = ComplianceSummary(
            risk_posture="LOW", compliance_score=0.9,
            top_gaps=["g1", "g2", "g3", "g4", "g5"],
            immediate_actions=["a1", "a2", "a3", "a4", "a5"],
        )
        assert len(r.top_gaps) == 5

    def test_action_plan(self):
        r = ActionPlan(
            action_id="a1", action_type="remediate", target="A.5",
            priority="HIGH", regulation="GDPR", risk_level="Critical",
            cost_estimate=5000.0, timeline="2 weeks",
            graph_reference="node:123",
        )
        assert r.cost_estimate == 5000.0

    def test_compliance_artifacts(self):
        ap = ActionPlan(
            action_id="a1", action_type="remediate", target="A.5",
            priority="HIGH", regulation="GDPR", risk_level="High",
            cost_estimate=1000.0, timeline="1w", graph_reference="n:1",
        )
        r = ComplianceArtifacts(
            compliance_posture={"score": 0.7},
            action_plan=[ap], risk_assessment={"level": "medium"},
        )
        assert len(r.action_plan) == 1

    def test_compliance_evidence(self):
        r = ComplianceEvidence(
            controls_executed=5, evidence_stored=10, metrics_updated=3,
        )
        assert r.evidence_stored == 10

    def test_next_action(self):
        r = NextAction(
            action="Review policies", priority="HIGH",
            owner="CISO", graph_reference="node:456",
        )
        assert r.owner == "CISO"

    def test_iq_agent_response(self):
        summary = ComplianceSummary(
            risk_posture="MEDIUM", compliance_score=0.7,
            top_gaps=[], immediate_actions=[],
        )
        artifacts = ComplianceArtifacts(
            compliance_posture={}, action_plan=[], risk_assessment={},
        )
        graph = GraphContext(
            nodes_traversed=5, patterns_detected=[],
            memories_accessed=[], learnings_applied=0,
        )
        evidence = ComplianceEvidence(
            controls_executed=0, evidence_stored=0, metrics_updated=0,
        )
        r = IQAgentResponse(
            status="success", timestamp="2024-01-01",
            summary=summary, artifacts=artifacts,
            graph_context=graph, evidence=evidence,
            next_actions=[], llm_response="Analysis complete",
        )
        assert r.status == "success"

    def test_memory_store_request(self):
        r = MemoryStoreRequest(
            memory_type="compliance_insight",
            content={"key": "value"},
        )
        assert r.importance_score == 0.5
        assert r.tags is None

    def test_memory_store_score_range(self):
        with pytest.raises(Exception):
            MemoryStoreRequest(
                memory_type="x", content={}, importance_score=1.5,
            )

    def test_memory_retrieval_request(self):
        r = MemoryRetrievalRequest(query="GDPR compliance")
        assert r.max_memories == 10
        assert r.relevance_threshold == 0.5

    def test_memory_retrieval_max_range(self):
        with pytest.raises(Exception):
            MemoryRetrievalRequest(query="x", max_memories=0)
        with pytest.raises(Exception):
            MemoryRetrievalRequest(query="x", max_memories=51)

    def test_memory_node(self):
        r = MemoryNode(
            id="m1", memory_type="insight",
            content={"data": "test"}, timestamp=datetime.now(),
            importance_score=0.8, access_count=5,
            tags=["gdpr"], confidence_score=0.9,
        )
        assert r.access_count == 5

    def test_memory_retrieval_response(self):
        r = MemoryRetrievalResponse(
            query_id="q1", retrieved_memories=[],
            relevance_scores=[], total_memories_searched=100,
            retrieval_strategy="semantic", confidence_score=0.85,
        )
        assert r.retrieval_strategy == "semantic"

    def test_graph_initialization_request(self):
        r = GraphInitializationRequest()
        assert r.clear_existing is False
        assert r.load_sample_data is True

    def test_graph_initialization_response(self):
        r = GraphInitializationResponse(
            status="success", timestamp="2024-01-01",
            nodes_created={"Framework": 5, "Control": 20},
            relationships_created=50, message="Initialized",
        )
        assert r.relationships_created == 50

    def test_health_check_response(self):
        r = HealthCheckResponse(
            status="healthy", neo4j_connected=True,
            graph_statistics={"nodes": 100},
            memory_statistics={"total": 50},
        )
        assert r.last_query_time is None
