"""Unit tests for the ComplianceRisk database model."""

import uuid
from datetime import datetime, timezone

import pytest


class TestComplianceRiskModel:
    """Tests for ComplianceRisk ORM model."""

    def _make_risk(self, **overrides):
        """Create a ComplianceRisk instance without touching the DB."""
        from database.compliance_risk import ComplianceRisk

        defaults = {
            "id": uuid.uuid4(),
            "user_id": uuid.uuid4(),
            "business_profile_id": uuid.uuid4(),
            "framework_id": uuid.uuid4(),
            "title": "Unpatched server exposure",
            "description": "Critical servers missing latest security patches",
            "severity": "high",
            "likelihood": "medium",
            "impact": "high",
            "risk_score": 7.5,
            "status": "open",
            "mitigation_plan": "Apply security patches within 72h",
            "mitigation_status": "in_progress",
            "category": "infrastructure",
            "control_reference": "A.12.6.1",
            "owner": "ciso@example.com",
            "due_date": datetime(2026, 4, 1, tzinfo=timezone.utc),
            "ai_metadata": {"source": "assessment", "confidence": 0.85},
        }
        defaults.update(overrides)
        return ComplianceRisk(**defaults)

    def test_tablename(self):
        from database.compliance_risk import ComplianceRisk

        assert ComplianceRisk.__tablename__ == "compliance_risks"

    def test_default_values(self):
        from database.compliance_risk import ComplianceRisk

        table = ComplianceRisk.__table__
        assert table.columns["severity"].default.arg == "medium"
        assert table.columns["likelihood"].default.arg == "medium"
        assert table.columns["impact"].default.arg == "medium"
        assert table.columns["risk_score"].default.arg == 5.0
        assert table.columns["status"].default.arg == "open"
        assert table.columns["mitigation_status"].default.arg == "not_started"

    def test_all_fields_set(self):
        risk = self._make_risk()
        assert risk.title == "Unpatched server exposure"
        assert risk.severity == "high"
        assert risk.risk_score == 7.5
        assert risk.mitigation_status == "in_progress"
        assert risk.ai_metadata["confidence"] == 0.85
        assert risk.control_reference == "A.12.6.1"

    def test_uuid_primary_key(self):
        risk = self._make_risk()
        assert isinstance(risk.id, uuid.UUID)

    def test_nullable_fields(self):
        risk = self._make_risk(
            mitigation_plan=None,
            category=None,
            control_reference=None,
            owner=None,
            due_date=None,
        )
        assert risk.mitigation_plan is None
        assert risk.category is None
        assert risk.control_reference is None
        assert risk.owner is None
        assert risk.due_date is None
