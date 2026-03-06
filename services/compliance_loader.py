"""
UK Compliance Frameworks Loader Service

Implements loading and management of UK-specific compliance frameworks
following the Agent Operating Protocol and test specifications.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime, timezone
import logging

from database.compliance_framework import ComplianceFramework
from database.db_setup import get_db
from sqlalchemy.orm import Session


logger = logging.getLogger(__name__)


@dataclass
class LoadResult:
    """Result of framework loading operation"""

    success: bool
    loaded_frameworks: List[ComplianceFramework]
    skipped_frameworks: List[str]
    errors: List[str]
    total_processed: int


class UKComplianceLoader:
    """
    Service for loading UK-specific compliance frameworks.

    Handles validation, deduplication, and database persistence
    of UK regulatory frameworks.
    """

    def __init__(self, db_session: Optional[Session] = None) -> None:
        """
        Initialize the loader.

        Args:
            db_session: Database session. If None, will create new session.
        """
        self.db_session = db_session or next(get_db())
        self.loaded_frameworks: List[ComplianceFramework] = []
        self.skipped_frameworks: List[str] = []
        self.errors: List[str] = []

    def load_frameworks(self, frameworks_data: List[Dict[str, Any]]) -> LoadResult:
        """
        Load multiple UK compliance frameworks from data.

        Args:
            frameworks_data: List of framework dictionaries

        Returns:
            LoadResult with success status and details
        """
        self.loaded_frameworks.clear()
        self.skipped_frameworks.clear()
        self.errors.clear()

        for framework_data in frameworks_data:
            try:
                # Check if framework already exists
                existing = (
                    self.db_session.query(ComplianceFramework)
                    .filter(ComplianceFramework.name == framework_data.get("name"))
                    .first(),
                )

                if existing:
                    self.skipped_frameworks.append(framework_data["name"])
                    logger.info(f"Skipped existing framework: {framework_data['name']}")
                    continue

                # Create and validate new framework
                framework = self.create_framework(framework_data)

                # Add to database
                self.db_session.add(framework)
                self.loaded_frameworks.append(framework)

                logger.info(f"Loaded framework: {framework.name}")

            except Exception as e:
                error_msg = (
                    f"Failed to load framework {framework_data.get('name', 'unknown')}: {str(e)}"
                )
                self.errors.append(error_msg)
                logger.error(error_msg)

        # Commit all changes
        try:
            self.db_session.commit()
            success = len(self.errors) == 0
        except Exception as e:
            self.db_session.rollback()
            self.errors.append(f"Database commit failed: {str(e)}")
            success = False

        return LoadResult(
            success=success,
            loaded_frameworks=self.loaded_frameworks.copy(),
            skipped_frameworks=self.skipped_frameworks.copy(),
            errors=self.errors.copy(),
            total_processed=len(frameworks_data),
        )

    def create_framework(self, data: Dict[str, Any]) -> ComplianceFramework:
        """
        Create a ComplianceFramework instance from data dictionary.

        Args:
            data: Framework data dictionary

        Returns:
            ComplianceFramework instance

        Raises:
            ValueError: If required fields are missing or invalid
        """
        # Validate required fields
        if not data.get("name"):
            raise ValueError("Framework name cannot be empty")

        if not data.get("display_name"):
            raise ValueError("Framework display_name is required")

        if not data.get("category"):
            raise ValueError("Framework category is required")

        # Create framework with proper field mappings
        framework = ComplianceFramework(
            name=data["name"],
            display_name=data["display_name"],
            description=data.get("description", ""),
            category=data["category"],
            # Truncated column mappings
            applicable_indu=data.get("applicable_indu", []),
            employee_thresh=data.get("employee_thresh"),
            revenue_thresho=data.get("revenue_thresho"),
            geographic_scop=data.get("geographic_scop", ["UK"]),
            key_requirement=data.get("key_requirement", []),
            control_domains=data.get("control_domains", []),
            evidence_types=data.get("evidence_types", []),
            # Assessment criteria
            relevance_facto=data.get("relevance_facto", {}),
            complexity_scor=data.get("complexity_scor", 1),
            implementation_=data.get("implementation_", 12),
            estimated_cost_=data.get("estimated_cost_", "£5,000-£25,000"),
            # Templates
            policy_template=data.get("policy_template", ""),
            control_templat=data.get("control_templat", {}),
            evidence_templa=data.get("evidence_templa", {}),
            # Metadata
            is_active=data.get("is_active", True),
            version=data.get("version", "1.0"),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        return framework

    def get_uk_frameworks(self) -> List[ComplianceFramework]:
        """
        Retrieve all active UK frameworks from database.

        Returns:
            List of UK compliance frameworks
        """
        return (
            self.db_session.query(ComplianceFramework)
            .filter(
                ComplianceFramework.is_active,
                ComplianceFramework.geographic_scop.contains(["UK"]),
            )
            .all(),
        )

    def update_framework_version(
        self, framework_name: str, new_version: str, description_update: str = ""
    ) -> ComplianceFramework:
        """
        Update framework version and description.

        Args:
            framework_name: Name of framework to update
            new_version: New version string
            description_update: Additional description text

        Returns:
            Updated framework

        Raises:
            ValueError: If framework not found
        """
        framework = (
            self.db_session.query(ComplianceFramework)
            .filter(ComplianceFramework.name == framework_name)
            .first(),
        )

        if not framework:
            raise ValueError(f"Framework not found: {framework_name}")

        framework.version = new_version
        if description_update:
            framework.description = f"{framework.description} {description_update}"
        framework.updated_at = datetime.now(timezone.utc)

        self.db_session.commit()
        return framework


class GeographicValidator:
    """Validator for geographic scope of frameworks"""

    #     UK_REGIONS = {"UK", "England", "Scotland", "Wales", "Northern Ireland"}  # Unused variable

    def validate_uk_scope(self, geographic_scope: List[str]) -> bool:
        """
        Validate that geographic scope is appropriate for UK frameworks.

        Args:
            geographic_scope: List of geographic regions

        Returns:
            True if valid UK scope, False otherwise
        """
        if not geographic_scope:
            return False

        # Must contain at least one UK region
        return bool(set(geographic_scope) & self.UK_REGIONS)


class ISO27001UKMapper:
    """Mapper for ISO 27001 controls to UK regulatory requirements"""

    ISO_TO_UK_GDPR_MAPPING = {
        "A.5.1.1": {
            "uk_requirement": "Data Protection by Design and Default",
            "ico_guidance": "Implement appropriate technical and organisational measures",
        },
        "A.8.2.1": {
            "uk_requirement": "Data Classification and Handling",
            "ico_guidance": "Classify personal data based on sensitivity and risk",
        },
        "A.12.6.1": {
            "uk_requirement": "Secure Data Disposal",
            "ico_guidance": "Securely delete personal data when no longer needed",
        },
    }

    def map_iso_to_uk_gdpr(self, iso_controls: List[str]) -> List[Dict[str, str]]:
        """
        Map ISO 27001 controls to UK GDPR requirements.

        Args:
            iso_controls: List of ISO control identifiers

        Returns:
            List of UK GDPR requirement mappings
        """
        mappings = []
        for control in iso_controls:
            if control in self.ISO_TO_UK_GDPR_MAPPING:
                mappings.append(self.ISO_TO_UK_GDPR_MAPPING[control])
            else:
                # Default mapping for unmapped controls
                mappings.append(
                    {
                        "uk_requirement": f"General Data Protection Requirement for {control}",
                        "ico_guidance": "Refer to ICO guidance for specific implementation",
                    },
                )

        return mappings
