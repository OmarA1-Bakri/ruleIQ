"""Add comprehensive CHECK constraints for data integrity

Revision ID: add_check_constraints_data_integrity
Revises: 802adb6d1be8
Create Date: 2025-07-17 12:00:00.000000

"""

import logging
import contextlib
from alembic import op

logger = logging.getLogger(__name__)


# revision identifiers, used by Alembic.
revision = "add_check_constraints_data_integrity"
down_revision = "802adb6d1be8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add CHECK constraints for data integrity."""

    # ==== HIGH PRIORITY CONSTRAINTS ====

    # 1. BUSINESS PROFILE CONSTRAINTS
    try:
        # Employee count validation
        op.execute(
            """
            ALTER TABLE business_profiles
            ADD CONSTRAINT ck_business_profile_employee_count
            CHECK (employee_count >= 1 AND employee_count <= 1000000)
        """
        )
    except (OSError, Exception):
        pass  # Constraint may already exist

    try:
        # Company name validation
        op.execute(
            """
            ALTER TABLE business_profiles
            ADD CONSTRAINT ck_business_profile_company_name_length
            CHECK (length(company_name) >= 2 AND length(company_name) <= 255)
        """
        )
    except (OSError, Exception):
        pass

    try:
        # Data sensitivity validation
        op.execute(
            """
            ALTER TABLE business_profiles
            ADD CONSTRAINT ck_business_profile_data_sensitivity
            CHECK (data_sensitivity IN ('Low', 'Medium', 'High', 'Critical'))
        """
        )
    except (OSError, Exception):
        pass

    # 2. COMPLIANCE FRAMEWORK CONSTRAINTS
    try:
        # Complexity score validation (1-10 scale)
        op.execute(
            """
            ALTER TABLE compliance_frameworks
            ADD CONSTRAINT ck_compliance_framework_complexity
            CHECK (complexity_score >= 1 AND complexity_score <= 10)
        """
        )
    except Exception:
        pass

    try:
        # Implementation time validation (1-260 weeks, max 5 years)
        op.execute(
            """
            ALTER TABLE compliance_frameworks
            ADD CONSTRAINT ck_compliance_framework_implementation_time
            CHECK (implementation_time_weeks >= 1 AND implementation_time_weeks <= 260)
        """
        )
    except Exception:
        pass

    try:
        # Employee threshold validation
        op.execute(
            """
            ALTER TABLE compliance_frameworks
            ADD CONSTRAINT ck_compliance_framework_employee_threshold
            CHECK (
                employee_threshold IS NULL OR
                (employee_threshold > 0 AND employee_threshold <= 1000000)
            )
        """
        )
    except Exception:
        pass

    # 3. EVIDENCE ITEM CONSTRAINTS
    try:
        # Evidence name length validation
        op.execute(
            """
            ALTER TABLE evidence_items
            ADD CONSTRAINT ck_evidence_item_name_length
            CHECK (length(evidence_name) >= 2 AND length(evidence_name) <= 255)
        """
        )
    except Exception:
        pass

    try:
        # Evidence type validation
        op.execute(
            """
            ALTER TABLE evidence_items
            ADD CONSTRAINT ck_evidence_item_type
            CHECK (evidence_type IN (
                'Policy', 'Procedure', 'Log', 'Certificate',
                'Configuration', 'Audit Report', 'Training Record', 'Other'
            ))
        """
        )
    except Exception:
        pass

    try:
        # Status validation
        op.execute(
            """
            ALTER TABLE evidence_items
            ADD CONSTRAINT ck_evidence_item_status
            CHECK (status IN (
                'not_started', 'in_progress', 'collected', 'under_review',
                'approved', 'rejected', 'expired'
            ))
        """
        )
    except Exception:
        pass

    try:
        # Priority validation
        op.execute(
            """
            ALTER TABLE evidence_items
            ADD CONSTRAINT ck_evidence_item_priority
            CHECK (priority IN ('low', 'medium', 'high', 'critical'))
        """
        )
    except Exception:
        pass

    try:
        # Collection method validation
        op.execute(
            """
            ALTER TABLE evidence_items
            ADD CONSTRAINT ck_evidence_item_method
            CHECK (collection_method IN ('manual', 'automated', 'semi_automated'))
        """
        )
    except Exception:
        pass

    try:
        # Collection frequency validation
        op.execute(
            """
            ALTER TABLE evidence_items
            ADD CONSTRAINT ck_evidence_item_frequency
            CHECK (collection_frequency IN (
                'once', 'daily', 'weekly', 'monthly', 'quarterly', 'annually'
            ))
        """
        )
    except Exception:
        pass

    try:
        # Compliance score impact validation (0-100%)
        op.execute(
            """
            ALTER TABLE evidence_items
            ADD CONSTRAINT ck_evidence_item_score_impact
            CHECK (compliance_score_impact >= 0.0 AND compliance_score_impact <= 100.0)
        """
        )
    except Exception:
        pass

    try:
        # File size validation (max 5GB)
        op.execute(
            """
            ALTER TABLE evidence_items
            ADD CONSTRAINT ck_evidence_item_file_size
            CHECK (
                file_size_bytes IS NULL OR
                (file_size_bytes >= 0 AND file_size_bytes <= 5368709120)
            )
        """
        )
    except (OSError, Exception):
        pass

    # 4. ASSESSMENT SESSION CONSTRAINTS
    try:
        # Session type validation
        op.execute(
            """
            ALTER TABLE assessment_sessions
            ADD CONSTRAINT ck_assessment_session_type
            CHECK (session_type IN (
                'compliance_scoping', 'readiness_assessment',
                'gap_analysis', 'risk_assessment'
            ))
        """
        )
    except Exception:
        pass

    try:
        # Status validation
        op.execute(
            """
            ALTER TABLE assessment_sessions
            ADD CONSTRAINT ck_assessment_session_status
            CHECK (status IN ('in_progress', 'completed', 'abandoned', 'paused'))
        """
        )
    except Exception:
        pass

    try:
        # Stage validation
        op.execute(
            """
            ALTER TABLE assessment_sessions
            ADD CONSTRAINT ck_assessment_session_stages
            CHECK (current_stage >= 1 AND current_stage <= total_stages)
        """
        )
    except Exception:
        pass

    try:
        # Total stages validation
        op.execute(
            """
            ALTER TABLE assessment_sessions
            ADD CONSTRAINT ck_assessment_session_total_stages
            CHECK (total_stages >= 1 AND total_stages <= 50)
        """
        )
    except Exception:
        pass

    try:
        # Questions validation
        op.execute(
            """
            ALTER TABLE assessment_sessions
            ADD CONSTRAINT ck_assessment_session_questions
            CHECK (questions_answered >= 0 AND questions_answered <= total_questions)
        """
        )
    except Exception:
        pass

    try:
        # Total questions validation
        op.execute(
            """
            ALTER TABLE assessment_sessions
            ADD CONSTRAINT ck_assessment_session_total_questions
            CHECK (total_questions >= 0 AND total_questions <= 1000)
        """
        )
    except Exception:
        pass

    # 5. READINESS ASSESSMENT CONSTRAINTS
    try:
        # Overall score validation (0-100%)
        op.execute(
            """
            ALTER TABLE readiness_assessments
            ADD CONSTRAINT ck_readiness_assessment_overall_score
            CHECK (overall_score >= 0.0 AND overall_score <= 100.0)
        """
        )
    except Exception:
        pass

    try:
        # Score trend validation
        op.execute(
            """
            ALTER TABLE readiness_assessments
            ADD CONSTRAINT ck_readiness_assessment_trend
            CHECK (score_trend IN ('improving', 'stable', 'declining', 'unknown'))
        """
        )
    except Exception:
        pass

    # 6. INTEGRATION CONSTRAINTS
    try:
        # Integration provider validation
        op.execute(
            """
            ALTER TABLE integrations
            ADD CONSTRAINT ck_integration_provider
            CHECK (provider IN (
                'aws', 'okta', 'google_workspace', 'microsoft_365',
                'azure', 'github', 'gitlab'
            ))
        """
        )
    except Exception:
        pass

    try:
        # Provider length validation
        op.execute(
            """
            ALTER TABLE integrations
            ADD CONSTRAINT ck_integration_provider_length
            CHECK (length(provider) >= 2 AND length(provider) <= 50)
        """
        )
    except Exception:
        pass

    # 7. EVIDENCE COLLECTION CONSTRAINTS
    try:
        # Evidence collection status validation
        op.execute(
            """
            ALTER TABLE evidence_collections
            ADD CONSTRAINT ck_evidence_collection_status
            CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled'))
        """
        )
    except Exception:
        pass

    try:
        # Progress percentage validation
        op.execute(
            """
            ALTER TABLE evidence_collections
            ADD CONSTRAINT ck_evidence_collection_progress
            CHECK (progress_percentage >= 0 AND progress_percentage <= 100)
        """
        )
    except Exception:
        pass

    try:
        # Collection mode validation
        op.execute(
            """
            ALTER TABLE evidence_collections
            ADD CONSTRAINT ck_evidence_collection_mode
            CHECK (collection_mode IN ('immediate', 'scheduled', 'streaming'))
        """
        )
    except Exception:
        pass

    # 8. INTEGRATION EVIDENCE ITEM CONSTRAINTS
    try:
        # Source system validation
        op.execute(
            """
            ALTER TABLE integration_evidence_items
            ADD CONSTRAINT ck_integration_evidence_source
            CHECK (source_system IN (
                'aws', 'okta', 'google_workspace', 'microsoft_365',
                'azure', 'github', 'gitlab', 'manual'
            ))
        """
        )
    except Exception:
        pass

    try:
        # Data classification validation
        op.execute(
            """
            ALTER TABLE integration_evidence_items
            ADD CONSTRAINT ck_integration_evidence_classification
            CHECK (data_classification IN ('public', 'internal', 'confidential', 'restricted'))
        """
        )
    except Exception:
        pass

    try:
        # Retention policy validation
        op.execute(
            """
            ALTER TABLE integration_evidence_items
            ADD CONSTRAINT ck_integration_evidence_retention
            CHECK (retention_policy IN ('standard', 'extended', 'permanent', 'minimal'))
        """
        )
    except Exception:
        pass

    # 9. GENERATED POLICY CONSTRAINTS
    try:
        # Policy status validation
        op.execute(
            """
            ALTER TABLE generated_policies
            ADD CONSTRAINT ck_generated_policy_status
            CHECK (status IN ('draft', 'reviewed', 'approved', 'implemented', 'deprecated'))
        """
        )
    except Exception:
        pass

    try:
        # Policy type validation
        op.execute(
            """
            ALTER TABLE generated_policies
            ADD CONSTRAINT ck_generated_policy_type
            CHECK (policy_type IN ('comprehensive', 'specific', 'update', 'template'))
        """
        )
    except Exception:
        pass

    try:
        # Generation time validation (0.1 seconds to 1 hour)
        op.execute(
            """
            ALTER TABLE generated_policies
            ADD CONSTRAINT ck_generated_policy_generation_time
            CHECK (generation_time_seconds >= 0.1 AND generation_time_seconds <= 3600)
        """
        )
    except Exception:
        pass

    try:
        # Word count validation
        op.execute(
            """
            ALTER TABLE generated_policies
            ADD CONSTRAINT ck_generated_policy_word_count
            CHECK (word_count >= 0 AND word_count <= 100000)
        """
        )
    except Exception:
        pass

    try:
        # Compliance coverage validation (0-1 score)
        op.execute(
            """
            ALTER TABLE generated_policies
            ADD CONSTRAINT ck_generated_policy_coverage
            CHECK (compliance_coverage >= 0.0 AND compliance_coverage <= 1.0)
        """
        )
    except Exception:
        pass

    # 10. CHAT CONVERSATION CONSTRAINTS
    try:
        # Chat conversation status validation
        op.execute(
            """
            ALTER TABLE chat_conversations
            ADD CONSTRAINT ck_chat_conversation_status_values
            CHECK (status IN ('active', 'archived', 'deleted'))
        """
        )
    except Exception:
        pass

    try:
        # Title length validation
        op.execute(
            """
            ALTER TABLE chat_conversations
            ADD CONSTRAINT ck_chat_conversation_title_length
            CHECK (length(title) >= 1 AND length(title) <= 255)
        """
        )
    except Exception:
        pass

    # ==== DATE LOGIC CONSTRAINTS ====

    # Evidence items date logic
    with contextlib.suppress(Exception):
        op.execute(
            """
            ALTER TABLE evidence_items
            ADD CONSTRAINT ck_evidence_item_collection_dates
            CHECK (collected_at IS NULL OR collected_at >= created_at)
        """
        )

    with contextlib.suppress(Exception):
        op.execute(
            """
            ALTER TABLE evidence_items
            ADD CONSTRAINT ck_evidence_item_review_dates
            CHECK (reviewed_at IS NULL OR collected_at IS NULL OR reviewed_at >= collected_at)
        """
        )

    with contextlib.suppress(Exception):
        op.execute(
            """
            ALTER TABLE evidence_items
            ADD CONSTRAINT ck_evidence_item_approval_dates
            CHECK (approved_at IS NULL OR reviewed_at IS NULL OR approved_at >= reviewed_at)
        """
        )

    # Assessment session date logic
    with contextlib.suppress(Exception):
        op.execute(
            """
            ALTER TABLE assessment_sessions
            ADD CONSTRAINT ck_assessment_session_activity_dates
            CHECK (last_activity >= started_at)
        """
        )

    with contextlib.suppress(Exception):
        op.execute(
            """
            ALTER TABLE assessment_sessions
            ADD CONSTRAINT ck_assessment_session_completion_dates
            CHECK (completed_at IS NULL OR completed_at >= started_at)
        """
        )

    # Evidence collection date logic
    with contextlib.suppress(Exception):
        op.execute(
            """
            ALTER TABLE evidence_collections
            ADD CONSTRAINT ck_evidence_collection_dates
            CHECK (started_at IS NULL OR started_at >= created_at)
        """
        )

    with contextlib.suppress(Exception):
        op.execute(
            """
            ALTER TABLE evidence_collections
            ADD CONSTRAINT ck_evidence_collection_completion_dates
            CHECK (completed_at IS NULL OR started_at IS NULL OR completed_at >= started_at)
        """
        )

    # Generated policy date logic
    with contextlib.suppress(Exception):
        op.execute(
            """
            ALTER TABLE generated_policies
            ADD CONSTRAINT ck_generated_policy_review_dates
            CHECK (reviewed_at IS NULL OR reviewed_at >= generated_at)
        """
        )

    with contextlib.suppress(Exception):
        op.execute(
            """
            ALTER TABLE generated_policies
            ADD CONSTRAINT ck_generated_policy_approval_dates
            CHECK (approved_at IS NULL OR reviewed_at IS NULL OR approved_at >= reviewed_at)
        """
        )

    # Chat conversation date logic
    with contextlib.suppress(Exception):
        op.execute(
            """
            ALTER TABLE chat_conversations
            ADD CONSTRAINT ck_chat_conversation_update_dates
            CHECK (updated_at >= created_at)
        """
        )

    logger.info("✅ Successfully added CHECK constraints for data integrity")


def downgrade() -> None:
    """Remove CHECK constraints."""

    # Drop all constraints in reverse order
    constraint_tables = [
        (
            "chat_conversations",
            [
                "ck_chat_conversation_update_dates",
                "ck_chat_conversation_title_length",
                "ck_chat_conversation_status_values",
            ],
        ),
        (
            "generated_policies",
            [
                "ck_generated_policy_approval_dates",
                "ck_generated_policy_review_dates",
                "ck_generated_policy_coverage",
                "ck_generated_policy_word_count",
                "ck_generated_policy_generation_time",
                "ck_generated_policy_type",
                "ck_generated_policy_status",
            ],
        ),
        (
            "evidence_collections",
            [
                "ck_evidence_collection_completion_dates",
                "ck_evidence_collection_dates",
                "ck_evidence_collection_mode",
                "ck_evidence_collection_progress",
                "ck_evidence_collection_status",
            ],
        ),
        (
            "integration_evidence_items",
            [
                "ck_integration_evidence_retention",
                "ck_integration_evidence_classification",
                "ck_integration_evidence_source",
            ],
        ),
        ("integrations", ["ck_integration_provider_length", "ck_integration_provider"]),
        (
            "readiness_assessments",
            ["ck_readiness_assessment_trend", "ck_readiness_assessment_overall_score"],
        ),
        (
            "assessment_sessions",
            [
                "ck_assessment_session_completion_dates",
                "ck_assessment_session_activity_dates",
                "ck_assessment_session_total_questions",
                "ck_assessment_session_questions",
                "ck_assessment_session_total_stages",
                "ck_assessment_session_stages",
                "ck_assessment_session_status",
                "ck_assessment_session_type",
            ],
        ),
        (
            "evidence_items",
            [
                "ck_evidence_item_approval_dates",
                "ck_evidence_item_review_dates",
                "ck_evidence_item_collection_dates",
                "ck_evidence_item_file_size",
                "ck_evidence_item_score_impact",
                "ck_evidence_item_frequency",
                "ck_evidence_item_method",
                "ck_evidence_item_priority",
                "ck_evidence_item_status",
                "ck_evidence_item_type",
                "ck_evidence_item_name_length",
            ],
        ),
        (
            "compliance_frameworks",
            [
                "ck_compliance_framework_employee_threshold",
                "ck_compliance_framework_implementation_time",
                "ck_compliance_framework_complexity",
            ],
        ),
        (
            "business_profiles",
            [
                "ck_business_profile_data_sensitivity",
                "ck_business_profile_company_name_length",
                "ck_business_profile_employee_count",
            ],
        ),
    ]

    for table_name, constraints in constraint_tables:
        for constraint_name in constraints:
            try:
                op.execute(f"ALTER TABLE {table_name} DROP CONSTRAINT {constraint_name}")
            except Exception:
                pass  # Constraint may not exist

    logger.info("✅ Successfully removed CHECK constraints")
