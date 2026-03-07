"""Validators for Golden Dataset system with enhanced security and compliance controls."""

import requests
import re
import time
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from functools import wraps
from collections import defaultdict
from enum import Enum
from services.ai.evaluation.schemas.compliance_scenario import ComplianceScenario
from services.ai.evaluation.schemas.evidence_case import EvidenceCase
from services.ai.evaluation.schemas.regulatory_qa import RegulatoryQAPair
from services.ai.evaluation.schemas.common import SourceMeta

# Constants
HTTP_OK = 200

DEFAULT_TIMEOUT = 30

DEFAULT_RETRIES = 5
HALF_RATIO = 0.5
MAX_RETRIES = 3

logger = logging.getLogger(__name__)
MAX_INPUT_LENGTH = 100000
MAX_ENTRIES_COUNT = 1000
MAX_STRING_LENGTH = 10000
MAX_REGEX_COMPLEXITY = 100
RATE_LIMIT_WINDOW = 60
RATE_LIMIT_MAX_CALLS = 100


class DataClassification(Enum):
    """Data classification levels for compliance."""

    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


@dataclass
class ValidationResult:
    """Result of a validation check."""

    valid: bool
    errors: List[str]
    warnings: List[str]
    layer: str
    confidence_score: float = 1.0
    data_classification: DataClassification = DataClassification.INTERNAL

    @property
    def is_valid(self) -> bool:
        """Check if validation passed."""
        return self.valid

    def add_error(self, error: str) -> None:
        """Add an error message (sanitized for security)."""
        sanitized_error = self._sanitize_message(error)
        self.errors.append(sanitized_error)
        self.valid = False
        logger.debug("Validation error in layer %s: %s" % (self.layer, error))

    def add_warning(self, warning: str) -> None:
        """Add a warning message (sanitized for security)."""
        sanitized_warning = self._sanitize_message(warning)
        self.warnings.append(sanitized_warning)
        logger.debug("Validation warning in layer %s: %s" % (self.layer, warning))

    def _sanitize_message(self, message: str) -> str:
        """Sanitize message to prevent information disclosure."""
        sanitized = re.sub("'[^']*'", "'[REDACTED]'", message)
        sanitized = re.sub('"[^"]*"', '"[REDACTED]"', sanitized)
        if len(sanitized) > HTTP_OK:
            sanitized = sanitized[:197] + "..."
        return sanitized


def rate_limit(max_calls: int = RATE_LIMIT_MAX_CALLS, window: int = RATE_LIMIT_WINDOW) -> Any:
    """Rate limiting decorator to prevent abuse."""
    call_times = defaultdict(list)

    def decorator(func) -> Any:

        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            now = time.time()
            key = f"{func.__name__}"
            call_times[key] = [t for t in call_times[key] if now - t < window]
            if len(call_times[key]) >= max_calls:
                logger.warning("Rate limit exceeded for %s" % func.__name__)
                raise ValueError("Rate limit exceeded. Please try again later.")
            call_times[key].append(now)
            return func(*args, **kwargs)

        return wrapper

    return decorator


@dataclass
class ExternalValidationResult:
    """Result of external data validation."""

    is_valid: bool
    trust_score: float
    errors: List[str]
    warnings: List[str]
    metadata: Dict[str, Any]


def validate_input_bounds(data: Any, max_length: int = MAX_INPUT_LENGTH) -> None:
    """Validate input size to prevent resource exhaustion attacks.

    Args:
        data: Input data to validate
        max_length: Maximum allowed size in characters

    Raises:
        ValueError: If input exceeds bounds
    """
    data_str = str(data)
    if len(data_str) > max_length:
        logger.error("Input exceeds maximum allowed size: %s > %s" % (len(data_str), max_length))
        raise ValueError("Input exceeds maximum allowed size")
    if isinstance(data, (dict, list)):

        def check_depth(obj, depth=0, max_depth=10) -> None:
            if depth > max_depth:
                raise ValueError("Input structure too deeply nested")
            if isinstance(obj, dict):
                for value in obj.values():
                    check_depth(value, depth + 1, max_depth)
            elif isinstance(obj, list):
                for item in obj:
                    check_depth(item, depth + 1, max_depth)

        check_depth(data)


class DeepValidator:
    """Multi-layer validation for Golden Dataset entries with security controls."""

    def __init__(self) -> None:
        """Initialize validator with security features."""
        self.known_frameworks = {
            "GDPR",
            "HIPAA",
            "CCPA",
            "PCI-DSS",
            "SOX",
            "ISO27001",
            "NIST",
            "FERPA",
            "GLBA",
        }
        self.known_jurisdictions = {"US", "EU", "UK", "CA", "AU", "JP", "CN", "IN", "BR"}
        self._id_pattern = re.compile("^[A-Z]{2,3}\\d{3,}$", re.IGNORECASE)
        self._safe_patterns = {
            "gdpr_article": re.compile("^Article\\s+\\d+(\\.\\d+)?$", re.IGNORECASE),
            "iso_control": re.compile("^A\\.\\d+\\.\\d+\\.\\d+$", re.IGNORECASE),
            "nist_control": re.compile("^[A-Z]{2}-\\d+(\\.\\d+)?$", re.IGNORECASE),
            "semantic_version": re.compile("^\\d+\\.\\d+\\.\\d+$"),
        }
        self._audit_log = []

    @rate_limit(max_calls=100, window=60)
    def validate(self, entry: Any) -> List[ValidationResult]:
        """Validate an entry through all layers with security controls.

        Args:
            entry: ComplianceScenario, EvidenceCase, or RegulatoryQAPair

        Returns:
            List of ValidationResult objects for each validation layer
        """
        try:
            validate_input_bounds(entry)
        except ValueError as e:
            logger.error("Input validation failed: %s" % e)
            result = ValidationResult(
                valid=False,
                errors=["Input validation failed"],
                warnings=[],
                layer="input_validation",
            )
            self._log_validation_decision("input_validation", result)
            return [result]
        results = []
        semantic_result = self._validate_semantic_layer(entry)
        self._log_validation_decision("semantic", semantic_result)
        results.append(semantic_result)
        cross_ref_result = self._validate_cross_reference_layer({"entries": [entry]})
        self._log_validation_decision("cross_reference", cross_ref_result)
        results.append(cross_ref_result)
        regulatory_result = self._validate_regulatory_accuracy(entry)
        self._log_validation_decision("regulatory_accuracy", regulatory_result)
        results.append(regulatory_result)
        temporal_result = self._validate_temporal_consistency({"entries": [entry]})
        self._log_validation_decision("temporal_consistency", temporal_result)
        results.append(temporal_result)
        return results

    @rate_limit(max_calls=50, window=60)
    def validate_dataset(self, dataset: Dict[str, List[Any]]) -> List[ValidationResult]:
        """Validate an entire dataset with security controls.

        Args:
            dataset: Dictionary with keys like 'compliance_scenarios', 'evidence_cases', etc.

        Returns:
            List of ValidationResult objects for each validation layer
        """
        try:
            validate_input_bounds(dataset)
        except ValueError as e:
            logger.error("Dataset validation failed: %s" % e)
            result = ValidationResult(
                valid=False,
                errors=["Dataset exceeds size limits"],
                warnings=[],
                layer="input_validation",
            )
            self._log_validation_decision("dataset_input_validation", result)
            return [result]
        results = []
        all_entries = []
        for key in dataset:
            if isinstance(dataset.get(key), list):
                entries = dataset[key]
                if len(entries) > MAX_ENTRIES_COUNT:
                    logger.warning(
                        "Dataset key '%s' has too many entries: %s" % (key, len(entries))
                    )
                    entries = entries[:MAX_ENTRIES_COUNT]
                all_entries.extend(entries)
        if len(all_entries) > MAX_ENTRIES_COUNT:
            logger.warning("Total entries exceed limit: %s" % len(all_entries))
            all_entries = all_entries[:MAX_ENTRIES_COUNT]
        if all_entries:
            semantic_result = self._validate_semantic_layer(all_entries[0] if all_entries else None)
            self._log_validation_decision("dataset_semantic", semantic_result)
            results.append(semantic_result)
            cross_ref_result = self._validate_cross_reference_layer(dataset)
            self._log_validation_decision("dataset_cross_reference", cross_ref_result)
            results.append(cross_ref_result)
            regulatory_result = self._validate_regulatory_accuracy(
                all_entries[0] if all_entries else None
            )
            self._log_validation_decision("dataset_regulatory", regulatory_result)
            results.append(regulatory_result)
            temporal_result = self._validate_temporal_consistency(dataset)
            self._log_validation_decision("dataset_temporal", temporal_result)
            results.append(temporal_result)
        return results

    def _log_validation_decision(self, layer: str, result: ValidationResult):
        """Log validation decision for audit trail (GDPR Article 30 compliance).

        Args:
            layer: Name of validation layer
            result: ValidationResult object
        """
        timestamp = datetime.now(timezone.utc)
        log_entry = {
            "timestamp": timestamp.isoformat(),
            "layer": layer,
            "valid": result.valid,
            "confidence_score": result.confidence_score,
            "error_count": len(result.errors),
            "warning_count": len(result.warnings),
            "data_classification": result.data_classification.value,
        }
        self._audit_log.append(log_entry)
        logger.info(
            "Validation decision - Layer: %s, Valid: %s, Confidence: %s, Classification: %s"
            % (layer, result.valid, result.confidence_score, result.data_classification.value)
        )

    def validate_compliance_scenario(self, scenario: ComplianceScenario) -> List[ValidationResult]:
        """Validate a compliance scenario.

        Args:
            scenario: ComplianceScenario to validate

        Returns:
            List of ValidationResult objects for each validation layer
        """
        return self.validate(scenario)

    def _validate_semantic_layer(self, entry: Any) -> ValidationResult:
        """Validate semantic coherence.

        Checks:
        - Required fields are present and non-empty
        - Text fields meet minimum length requirements
        - IDs follow expected patterns
        """
        result = ValidationResult(
            valid=True, errors=[], warnings=[], layer="semantic", confidence_score=1.0
        )
        confidence_deductions = 0.0
        if hasattr(entry, "id"):
            if len(str(entry.id)) > 20:
                result.add_error("ID exceeds maximum allowed length")
                confidence_deductions += 0.3
            elif not self._id_pattern.match(str(entry.id)):
                result.add_warning("ID doesn't follow standard pattern (e.g., CS001)")
                confidence_deductions += 0.1
        if hasattr(entry, "title"):
            if len(entry.title) < DEFAULT_RETRIES:
                result.add_error("Title too short (minimum 5 characters)")
                confidence_deductions += 0.3
            elif len(entry.title) > HTTP_OK:
                result.add_warning("Title unusually long (over 200 characters)")
                confidence_deductions += 0.05
        if hasattr(entry, "description"):
            if not entry.description or len(entry.description) < 10:
                result.add_error("Description too short (minimum 10 characters)")
                confidence_deductions += 0.2
        if isinstance(entry, RegulatoryQAPair):
            if not entry.question.endswith("?"):
                result.add_warning("Question doesn't end with question mark")
                confidence_deductions += 0.05
            if len(entry.authoritative_answer) < 20:
                result.add_error("Answer too short to be authoritative (minimum 20 characters)")
                confidence_deductions += 0.3
        if isinstance(entry, ComplianceScenario):
            if len(entry.triggers) == 0:
                result.add_error("No triggers specified")
                confidence_deductions += 0.4
            for trigger in entry.triggers:
                if len(trigger) < MAX_RETRIES:
                    result.add_error(f"Trigger '{trigger}' too short")
                    confidence_deductions += 0.1
        if isinstance(entry, EvidenceCase):
            if len(entry.required_evidence) == 0:
                result.add_error("No evidence items specified")
                confidence_deductions += 0.4
            for item in entry.required_evidence:
                if len(item.acceptance_criteria) == 0:
                    result.add_error(f"No acceptance criteria for evidence '{item.name}'")
                    confidence_deductions += 0.2
        result.confidence_score = max(0.0, 1.0 - confidence_deductions)
        return result

    def _validate_cross_reference_layer(self, dataset: Dict[str, Any]) -> ValidationResult:
        """Validate cross-references and relationships.

        Checks:
        - Obligation IDs are consistent
        - Framework references are valid
        - Control mappings are properly formatted
        """
        result = ValidationResult(
            valid=True, errors=[], warnings=[], layer="cross_reference", confidence_score=1.0
        )
        confidence_deductions = 0.0
        all_entries = []
        for key in dataset:
            if isinstance(dataset.get(key), list):
                all_entries.extend(dataset[key])
        valid_obligation_ids = set()
        if "compliance_scenarios" in dataset and dataset["compliance_scenarios"]:
            for scenario in dataset["compliance_scenarios"]:
                if hasattr(scenario, "obligation_id"):
                    valid_obligation_ids.add(scenario.obligation_id)
        for entry in all_entries:
            if hasattr(entry, "obligation_id"):
                if not re.match("^OBL\\d{3,}$", entry.obligation_id):
                    result.add_error(f"Invalid obligation ID format: {entry.obligation_id}")
                    confidence_deductions += 0.2
                if isinstance(entry, EvidenceCase):
                    if entry.obligation_id not in valid_obligation_ids:
                        result.add_error(
                            f"Orphaned evidence case: obligation ID '{entry.obligation_id}' not found in compliance scenarios"
                        )
                        confidence_deductions += 0.3
            if hasattr(entry, "regulation_refs"):
                for ref in entry.regulation_refs:
                    if ref.framework not in self.known_frameworks:
                        result.add_warning(f"Unknown framework: {ref.framework}")
                        confidence_deductions += 0.05
                    if ref.jurisdiction and ref.jurisdiction not in self.known_jurisdictions:
                        result.add_warning(f"Unknown jurisdiction: {ref.jurisdiction}")
                        confidence_deductions += 0.05
            if isinstance(entry, EvidenceCase) and entry.control_mappings:
                for mapping in entry.control_mappings:
                    if mapping.framework == "NIST":
                        if not re.match("^[A-Z]{2}-\\d+", mapping.control_id):
                            result.add_warning(
                                f"NIST control ID '{mapping.control_id}' doesn't match pattern"
                            )
                            confidence_deductions += 0.1
                    elif mapping.framework == "ISO27001":
                        if not re.match("^A\\.\\d+\\.\\d+\\.\\d+", mapping.control_id):
                            result.add_warning(
                                f"ISO27001 control ID '{mapping.control_id}' doesn't match pattern"
                            )
                            confidence_deductions += 0.1
        result.confidence_score = max(0.0, 1.0 - confidence_deductions)
        return result

    def _validate_regulatory_accuracy(self, entry: Any) -> ValidationResult:
        """Validate regulatory accuracy and completeness.

        Checks:
        - Citations follow expected formats
        - URLs are properly formatted
        - Regulatory references are complete
        """
        result = ValidationResult(
            valid=True, errors=[], warnings=[], layer="regulatory_accuracy", confidence_score=1.0
        )
        confidence_deductions = 0.0
        if hasattr(entry, "regulation_refs"):
            if len(entry.regulation_refs) == 0:
                result.add_warning("No regulatory references provided")
                confidence_deductions += 0.2
            for ref in entry.regulation_refs:
                if ref.framework == "GDPR":
                    if not self._safe_patterns["gdpr_article"].match(str(ref.citation)[:100]):
                        result.add_error("Invalid GDPR citation format")
                        confidence_deductions += 0.3
                elif ref.framework == "HIPAA":
                    if not re.match("^\\d{1,3}\\.\\d{1,3}$", str(ref.citation)[:10]):
                        result.add_error("Invalid HIPAA citation format")
                        confidence_deductions += 0.3
                elif ref.framework == "ISO27001":
                    if not self._safe_patterns["iso_control"].match(str(ref.citation)[:20]):
                        result.add_error("Invalid ISO27001 control format")
                        confidence_deductions += 0.3
                elif ref.framework == "NIST":
                    if not self._safe_patterns["nist_control"].match(str(ref.citation)[:20]):
                        result.add_error("Invalid NIST control format")
                        confidence_deductions += 0.3
                if ref.url:
                    url_str = str(ref.url)[:1000]
                    if not url_str.startswith(("http://", "https://")):
                        result.add_error("Invalid URL format")
                        confidence_deductions += 0.3
        if isinstance(entry, ComplianceScenario):
            if entry.sector == "healthcare" and entry.jurisdiction == "US":
                has_hipaa = any(ref.framework == "HIPAA" for ref in entry.regulation_refs)
                if not has_hipaa:
                    result.add_warning("US healthcare scenario should reference HIPAA")
                    confidence_deductions += 0.15
        result.confidence_score = max(0.0, 1.0 - confidence_deductions)
        return result

    def _validate_temporal_consistency(self, dataset: Dict[str, Any]) -> ValidationResult:
        """Validate temporal consistency.

        Checks:
        - Dates are logically consistent
        - Version formats are valid
        - Temporal validity makes sense
        """
        result = ValidationResult(
            valid=True, errors=[], warnings=[], layer="temporal", confidence_score=1.0
        )
        confidence_deductions = 0.0
        all_entries = []
        for key in dataset:
            if isinstance(dataset.get(key), list):
                all_entries.extend(dataset[key])
        id_temporal_map = {}
        for entry in all_entries:
            if hasattr(entry, "id") and hasattr(entry, "temporal"):
                entry_id = entry.id
                if entry_id in id_temporal_map:
                    existing = id_temporal_map[entry_id]
                    if self._check_temporal_overlap(existing.temporal, entry.temporal):
                        result.add_warning(f"Temporal overlap detected for ID '{entry_id}'")
                        confidence_deductions += 0.15
                else:
                    id_temporal_map[entry_id] = entry
        for entry in all_entries:
            if hasattr(entry, "temporal"):
                now = datetime.now(timezone.utc).replace(tzinfo=None)
                if entry.temporal.effective_from and entry.temporal.effective_from > now:
                    result.add_warning("Effective date is in the future")
                    confidence_deductions += 0.1
                if entry.temporal.effective_to and entry.temporal.effective_from:
                    duration = entry.temporal.effective_to - entry.temporal.effective_from
                    if duration.days < DEFAULT_TIMEOUT:
                        result.add_warning("Validity period less than 30 days")
                        confidence_deductions += 0.1
                    elif duration.days > 3650:
                        result.add_warning("Validity period exceeds 10 years")
                        confidence_deductions += 0.05
            if hasattr(entry, "version"):
                if not re.match("^\\d+\\.\\d+\\.\\d+$", entry.version):
                    result.add_error(f"Invalid version format: {entry.version}")
                    confidence_deductions += 0.3
            if hasattr(entry, "created_at") and entry.created_at > datetime.now():
                result.add_error("Creation timestamp is in the future")
                confidence_deductions += 0.2
            if hasattr(entry, "source") and entry.source.created_at > datetime.now():
                result.add_error("Source creation timestamp is in the future")
                confidence_deductions += 0.2
        result.confidence_score = max(0.0, 1.0 - confidence_deductions)
        return result

    def _check_temporal_overlap(self, temporal1: Any, temporal2: Any) -> bool:
        """Check if two temporal validity periods overlap.

        Args:
            temporal1: First temporal validity period
            temporal2: Second temporal validity period

        Returns:
            True if periods overlap, False otherwise
        """
        if not temporal1.effective_from or not temporal2.effective_from:
            return False
        if not temporal1.effective_to and not temporal2.effective_to:
            return temporal1.effective_from == temporal2.effective_from
        if not temporal1.effective_to:
            return (
                temporal2.effective_from <= temporal1.effective_from <= temporal2.effective_to
                if temporal2.effective_to
                else False
            )
        if not temporal2.effective_to:
            return (
                temporal1.effective_from <= temporal2.effective_from <= temporal1.effective_to
                if temporal1.effective_to
                else False
            )
        return not (
            temporal1.effective_to < temporal2.effective_from
            or temporal2.effective_to < temporal1.effective_from
        )


class ExternalDataValidator:
    """Validator for external data sources with trust scoring."""

    def __init__(self) -> None:
        """Initialize external data validator."""
        self.trusted_sources = {
            "official_regulation": 1.0,
            "regulatory_document": 0.9,
            "official_guidance": 0.85,
            "industry_standard": 0.7,
            "expert_review": 0.6,
            "manual": 0.5,
            "automated": 0.3,
        }

    def validate_external_data(self, entry: Any) -> "ExternalValidationResult":
        """Validate external data entry with trust scoring.

        Args:
            entry: Data entry to validate

        Returns:
            ExternalValidationResult with validation status and trust score
        """
        result = ExternalValidationResult(
            is_valid=True, trust_score=0.0, errors=[], warnings=[], metadata={"subscores": {}}
        )
        if not hasattr(entry, "source"):
            result.is_valid = False
            result.errors.append("Missing source metadata")
            return result
        if not entry.source.source_kind:
            result.is_valid = False
            result.errors.append("Missing source_kind in metadata")
            return result
        result.trust_score = self.calculate_trust_score(entry.source)
        if result.trust_score < HALF_RATIO and entry.source.created_at:
            age_days = (datetime.now() - entry.source.created_at).days
            if age_days > 365:
                result.warnings.append(f"Data source is {age_days} days old")
        result.metadata["subscores"] = {
            "reputation": self._get_source_reputation(entry.source.source_kind),
            "extraction": self._get_extraction_confidence(entry.source.method),
            "temporal": self._get_temporal_relevance(entry.source.created_at),
            "version": self._get_version_stability(
                entry.source.version if hasattr(entry.source, "version") else None
            ),
        }
        return result

    def calculate_trust_score(self, source: SourceMeta) -> float:
        """Calculate trust score for a data source with validation.

        Args:
            source: SourceMeta containing source information

        Returns:
            Trust score between 0.0 and 1.0
        """
        subscores = {}
        if not source:
            logger.warning("No source provided for trust scoring")
            return 0.0
        subscores["reputation"] = self._get_source_reputation(source.source_kind)
        subscores["extraction"] = self._get_extraction_confidence(source.method)
        subscores["temporal"] = self._get_temporal_relevance(source.created_at)
        subscores["version"] = self._get_version_stability(
            source.version if hasattr(source, "version") else None
        )
        for key, score in subscores.items():
            if not isinstance(score, (int, float)) or not 0.0 <= score <= 1.0:
                logger.error("Invalid trust score component %s: %s" % (key, score))
                subscores[key] = 0.0
        weights = {"reputation": 0.4, "extraction": 0.3, "temporal": 0.2, "version": 0.1}
        weight_sum = sum(weights.values())
        if abs(weight_sum - 1.0) > 0.01:
            logger.error("Invalid weight configuration: sum=%s" % weight_sum)
            return 0.0
        try:
            trust_score = sum(subscores.get(key, 0.0) * weights[key] for key in weights)
            trust_score = min(1.0, max(0.0, trust_score))
            logger.debug("Trust score calculated: %s, components: %s" % (trust_score, subscores))
            return trust_score
        except (requests.RequestException, KeyError, IndexError) as e:
            logger.error("Error calculating trust score: %s" % e)
            return 0.0

    def _get_source_reputation(self, source_kind: str) -> float:
        """Get reputation score for source kind."""
        reputation_scores = {
            "regulatory_document": 1.0,
            "official_guidance": 0.9,
            "official_regulation": 0.95,
            "industry_standard": 0.8,
            "expert_review": 0.7,
            "manual": 0.6,
            "automated": 0.5,
            "unknown": 0.3,
        }
        return reputation_scores.get(source_kind, 0.3)

    def _get_extraction_confidence(self, method: str) -> float:
        """Get confidence score for extraction method."""
        method_scores = {
            "automated_extraction": 0.9,
            "expert_review": 0.95,
            "manual_extraction": 0.8,
            "manual": 0.7,
            "automated": 0.6,
            "unknown": 0.3,
        }
        return method_scores.get(method, 0.5)

    def _get_temporal_relevance(self, created_at: datetime) -> float:
        """Get temporal relevance score based on age."""
        if not created_at:
            return 0.5
        age_days = (datetime.now() - created_at).days
        if age_days <= DEFAULT_TIMEOUT:
            return 1.0
        elif age_days <= 90:
            return 0.9
        elif age_days <= 180:
            return 0.8
        elif age_days <= 365:
            return 0.6
        else:
            return 0.3

    def _get_version_stability(self, version: Optional[str]) -> float:
        """Get stability score based on version."""
        if not version:
            return 0.5
        try:
            parts = version.split(".")
            if len(parts) == MAX_RETRIES:
                major, minor, patch = map(int, parts)
                if major >= 1:
                    return 0.9 if minor >= 0 else 0.8
                else:
                    return 0.7 if minor > DEFAULT_RETRIES else 0.6
        except (ValueError, TypeError):
            pass
        return 0.5

    def validate_external_source(
        self, data: Dict[str, Any], source_url: Optional[str] = None
    ) -> Tuple[bool, float, List[str]]:
        """Validate external data source.

        Args:
            data: Data from external source
            source_url: Optional URL of the source

        Returns:
            Tuple of (is_valid, trust_score, issues)
        """
        issues = []
        subscores = {}
        source_score = self._calculate_source_score(data, source_url)
        subscores["source_credibility"] = source_score
        completeness_score = self._calculate_completeness_score(data)
        subscores["data_completeness"] = completeness_score
        consistency_score = self._calculate_consistency_score(data)
        subscores["consistency"] = consistency_score
        timeliness_score = self._calculate_timeliness_score(data)
        subscores["timeliness"] = timeliness_score
        weights = {
            "source_credibility": 0.4,
            "data_completeness": 0.3,
            "consistency": 0.2,
            "timeliness": 0.1,
        }
        trust_score = sum(subscores[key] * weights[key] for key in weights)
        is_valid = trust_score >= HALF_RATIO
        if source_score < HALF_RATIO:
            issues.append("Low source credibility")
        if completeness_score < 0.6:
            issues.append("Incomplete data")
        if consistency_score < 0.7:
            issues.append("Inconsistent data")
        if timeliness_score < HALF_RATIO:
            issues.append("Outdated data")
        return is_valid, trust_score, issues

    def _calculate_source_score(self, data: Dict[str, Any], source_url: Optional[str]) -> float:
        """Calculate source credibility score."""
        score = 0.0
        if "source" in data:
            source = data["source"]
            if isinstance(source, dict):
                source_kind = source.get("source_kind", "")
                score = self.trusted_sources.get(source_kind, 0.3)
        if source_url:
            if ".gov" in source_url or ".eu" in source_url:
                score = min(1.0, score + 0.2)
            elif ".org" in source_url:
                score = min(1.0, score + 0.1)
        return score

    def _calculate_completeness_score(self, data: Dict[str, Any]) -> float:
        """Calculate data completeness score."""
        inner_data = data.get("data", data)
        required_fields = {"id", "title"}
        optional_fields = {"description", "version", "created_at"}
        present_required = sum(1 for f in required_fields if f in inner_data)
        present_optional = sum(1 for f in optional_fields if f in inner_data)
        required_score = present_required / len(required_fields) if required_fields else 1.0
        optional_score = present_optional / len(optional_fields) if optional_fields else 0.0
        return 0.7 * required_score + 0.3 * optional_score

    def _calculate_consistency_score(self, data: Dict[str, Any]) -> float:
        """Calculate data consistency score."""
        score = 1.0
        if "data" in data:
            inner_data = data["data"]
            if "id" in inner_data:
                id_val = inner_data["id"]
                if not re.match("^[A-Z]{2,3}\\d{3,}$", id_val):
                    score -= 0.2
            if "created_at" in inner_data and "source" in data:
                if "created_at" in data["source"]:
                    score -= 0.1
        return max(0.0, score)

    def _calculate_timeliness_score(self, data: Dict[str, Any]) -> float:
        """Calculate data timeliness score."""
        score = 1.0
        now = datetime.now()
        if "created_at" in data:
            try:
                if isinstance(data["created_at"], str):
                    created = datetime.fromisoformat(data["created_at"].replace("Z", "+00:00"))
                else:
                    created = data["created_at"]
                age_days = (now - created).days
                if age_days > 365:
                    score = 0.5
                elif age_days > 180:
                    score = 0.7
                elif age_days > 90:
                    score = 0.9
            except (KeyError, IndexError):
                score = 0.5
        return score
