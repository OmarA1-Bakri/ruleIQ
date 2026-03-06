"""
GDPR Compliance Module for RuleIQ.
Implements data privacy, consent management, and compliance tracking.
"""

import hashlib
import logging
from typing import Dict, Any, List, Optional, Set
from datetime import datetime, timedelta
from enum import Enum

from sqlalchemy.orm import Session

from database.session import SessionLocal

logger = logging.getLogger(__name__)


class LawfulBasis(Enum):
    """GDPR Article 6 - Lawful basis for processing"""

    CONSENT = "consent"
    CONTRACT = "contract"
    LEGAL_OBLIGATION = "legal_obligation"
    VITAL_INTERESTS = "vital_interests"
    PUBLIC_TASK = "public_task"
    LEGITIMATE_INTERESTS = "legitimate_interests"


class DataCategory(Enum):
    """Categories of personal data"""

    BASIC = "basic"  # Name, email, etc.
    CONTACT = "contact"  # Address, phone
    FINANCIAL = "financial"  # Payment info
    BEHAVIORAL = "behavioral"  # Usage patterns
    TECHNICAL = "technical"  # IP addresses, cookies
    SENSITIVE = "sensitive"  # Special category data


class GDPRComplianceManager:
    """Main GDPR compliance handler."""

    def __init__(self) -> None:
        self.retention_periods = {
            DataCategory.BASIC: 365 * 3,  # 3 years
            DataCategory.CONTACT: 365 * 3,
            DataCategory.FINANCIAL: 365 * 7,  # 7 years for tax
            DataCategory.BEHAVIORAL: 365,  # 1 year
            DataCategory.TECHNICAL: 90,  # 3 months
            DataCategory.SENSITIVE: 365 * 2,  # 2 years
        }

        self.anonymization_fields = {
            "email": self._anonymize_email,
            "phone": self._anonymize_phone,
            "ip_address": self._anonymize_ip,
            "name": self._anonymize_name,
            "address": self._anonymize_address,
        }

    async def process_consent(
        self,
        user_id: str,
        purpose: str,
        lawful_basis: LawfulBasis,
        data_categories: List[DataCategory],
        expires_in_days: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Process and record user consent."""

        consent = {
            "consent_id": self._generate_consent_id(),
            "user_id": user_id,
            "purpose": purpose,
            "lawful_basis": lawful_basis.value,
            "data_categories": [cat.value for cat in data_categories],
            "granted_at": datetime.utcnow().isoformat(),
            "expires_at": None,
            "status": "active",
        }

        if expires_in_days:
            expires_at = datetime.utcnow() + timedelta(days=expires_in_days)
            consent["expires_at"] = expires_at.isoformat()

        # Store consent record
        await self._store_consent(consent)

        # Log consent event
        logger.info(f"Consent granted: {consent['consent_id']} for user {user_id}")

        return consent

    async def withdraw_consent(self, user_id: str, consent_id: str) -> Dict[str, Any]:
        """Process consent withdrawal."""

        withdrawal = {
            "consent_id": consent_id,
            "user_id": user_id,
            "withdrawn_at": datetime.utcnow().isoformat(),
            "status": "withdrawn",
        }

        # Update consent record
        await self._update_consent_status(consent_id, "withdrawn")

        # Trigger data deletion if required
        await self._process_withdrawal_actions(user_id, consent_id)

        logger.info(f"Consent withdrawn: {consent_id} for user {user_id}")

        return withdrawal

    async def get_user_consents(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all consents for a user."""

        db = SessionLocal()
        try:
            # Query consent records
            consents = db.query(ConsentRecord).filter(ConsentRecord.user_id == user_id).all()

            return [self._serialize_consent(c) for c in consents]
        finally:
            db.close()

    async def export_user_data(self, user_id: str) -> Dict[str, Any]:
        """Export all user data (GDPR Article 20 - Data portability)."""

        export = {
            "export_id": self._generate_export_id(),
            "user_id": user_id,
            "exported_at": datetime.utcnow().isoformat(),
            "data": {},
        }

        db = SessionLocal()
        try:
            # Collect user data from all tables
            export["data"]["profile"] = await self._export_user_profile(db, user_id)
            export["data"]["assessments"] = await self._export_user_assessments(db, user_id)
            export["data"]["evidence"] = await self._export_user_evidence(db, user_id)
            export["data"]["consents"] = await self._export_user_consents(db, user_id)
            export["data"]["audit_logs"] = await self._export_user_audit_logs(db, user_id)

        finally:
            db.close()

        # Log export event
        logger.info(f"Data export created: {export['export_id']} for user {user_id}")

        return export

    async def delete_user_data(
        self,
        user_id: str,
        categories: Optional[List[DataCategory]] = None,
        retain_anonymized: bool = True,
    ) -> Dict[str, Any]:
        """Delete or anonymize user data (GDPR Article 17 - Right to erasure)."""

        deletion = {
            "deletion_id": self._generate_deletion_id(),
            "user_id": user_id,
            "categories": [cat.value for cat in categories] if categories else "all",
            "deleted_at": datetime.utcnow().isoformat(),
            "retain_anonymized": retain_anonymized,
            "affected_records": {},
        }

        db = SessionLocal()
        try:
            if retain_anonymized:
                # Anonymize data instead of deleting
                deletion["affected_records"] = await self._anonymize_user_data(
                    db, user_id, categories
                )
            else:
                # Permanently delete data
                deletion["affected_records"] = await self._delete_user_data_permanent(
                    db, user_id, categories
                )

            db.commit()

        except Exception as e:
            db.rollback()
            logger.error(f"Data deletion failed for user {user_id}: {e}")
            raise
        finally:
            db.close()

        # Log deletion event
        logger.info(f"Data deletion completed: {deletion['deletion_id']} for user {user_id}")

        return deletion

    async def check_retention_compliance(self) -> Dict[str, Any]:
        """Check and enforce data retention policies."""

        compliance_check = {
            "check_id": self._generate_check_id(),
            "checked_at": datetime.utcnow().isoformat(),
            "expired_data": [],
            "actions_taken": [],
        }

        db = SessionLocal()
        try:
            for category, retention_days in self.retention_periods.items():
                cutoff_date = datetime.utcnow() - timedelta(days=retention_days)

                # Find expired data
                expired = await self._find_expired_data(db, category, cutoff_date)
                compliance_check["expired_data"].extend(expired)

                # Process expired data
                for record in expired:
                    action = await self._process_expired_data(db, record, category)
                    compliance_check["actions_taken"].append(action)

            db.commit()

        finally:
            db.close()

        logger.info(f"Retention compliance check completed: {compliance_check['check_id']}")

        return compliance_check

    def _anonymize_email(self, email: str) -> str:
        """Anonymize email address."""
        parts = email.split("@")
        if len(parts) == 2:
            # Use SHA-256 instead of MD5 for security compliance in GDPR anonymization
            anonymized = f"user_{hashlib.sha256(email.encode()).hexdigest()[:8]}@{parts[1]}"
            return anonymized
        return "anonymous@example.com"

    def _anonymize_phone(self, phone: str) -> str:
        """Anonymize phone number."""
        return "***-***-" + phone[-4:] if len(phone) >= 4 else "***-***-****"

    def _anonymize_ip(self, ip: str) -> str:
        """Anonymize IP address."""
        parts = ip.split(".")
        if len(parts) == 4:
            return f"{parts[0]}.{parts[1]}.0.0"
        return "0.0.0.0"

    def _anonymize_name(self, name: str) -> str:
        """Anonymize name."""
        # Use SHA-256 instead of MD5 for security compliance in GDPR anonymization
        return f"User_{hashlib.sha256(name.encode()).hexdigest()[:8]}"

    def _anonymize_address(self, address: str) -> str:
        """Anonymize address."""
        return "Anonymized Address"

    def _generate_consent_id(self) -> str:
        """Generate unique consent ID."""
        timestamp = datetime.utcnow().timestamp()
        # Use SHA-256 instead of MD5 for security compliance in GDPR consent tracking
        return f"consent_{hashlib.sha256(str(timestamp).encode()).hexdigest()[:16]}"

    def _generate_export_id(self) -> str:
        """Generate unique export ID."""
        timestamp = datetime.utcnow().timestamp()
        # Use SHA-256 instead of MD5 for security compliance in GDPR export tracking
        return f"export_{hashlib.sha256(str(timestamp).encode()).hexdigest()[:16]}"

    def _generate_deletion_id(self) -> str:
        """Generate unique deletion ID."""
        timestamp = datetime.utcnow().timestamp()
        # Use SHA-256 instead of MD5 for security compliance in GDPR deletion tracking
        return f"deletion_{hashlib.sha256(str(timestamp).encode()).hexdigest()[:16]}"

    def _generate_check_id(self) -> str:
        """Generate unique check ID."""
        timestamp = datetime.utcnow().timestamp()
        # Use SHA-256 instead of MD5 for security compliance in GDPR compliance checking
        return f"check_{hashlib.sha256(str(timestamp).encode()).hexdigest()[:16]}"

    async def _store_consent(self, consent: Dict[str, Any]):
        """Store consent record in database."""
        # Implementation depends on your database schema
        pass

    async def _update_consent_status(self, consent_id: str, status: str):
        """Update consent status in database."""
        # Implementation depends on your database schema
        pass

    async def _process_withdrawal_actions(self, user_id: str, consent_id: str):
        """Process actions required after consent withdrawal."""
        # Implementation depends on your business logic
        pass

    async def _export_user_profile(self, db: Session, user_id: str) -> Dict:
        """Export user profile data."""
        # Implementation depends on your database schema
        return {}

    async def _export_user_assessments(self, db: Session, user_id: str) -> List[Dict]:
        """Export user assessment data."""
        # Implementation depends on your database schema
        return []

    async def _export_user_evidence(self, db: Session, user_id: str) -> List[Dict]:
        """Export user evidence data."""
        # Implementation depends on your database schema
        return []

    async def _export_user_consents(self, db: Session, user_id: str) -> List[Dict]:
        """Export user consent records."""
        # Implementation depends on your database schema
        return []

    async def _export_user_audit_logs(self, db: Session, user_id: str) -> List[Dict]:
        """Export user audit logs."""
        # Implementation depends on your database schema
        return []

    async def _anonymize_user_data(
        self, db: Session, user_id: str, categories: Optional[List[DataCategory]]
    ) -> Dict[str, int]:
        """Anonymize user data in database."""
        affected = {}

        # Anonymize user profile
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            for field, anonymizer in self.anonymization_fields.items():
                if hasattr(user, field):
                    setattr(user, field, anonymizer(getattr(user, field)))
            affected["user_profile"] = 1

        # Anonymize related records
        # Implementation depends on your database schema

        return affected

    async def _delete_user_data_permanent(
        self, db: Session, user_id: str, categories: Optional[List[DataCategory]]
    ) -> Dict[str, int]:
        """Permanently delete user data from database."""
        affected = {}

        # Delete user and cascade to related records
        # Implementation depends on your database schema

        return affected

    async def _find_expired_data(
        self, db: Session, category: DataCategory, cutoff_date: datetime
    ) -> List[Dict]:
        """Find data that has exceeded retention period."""
        # Implementation depends on your database schema
        return []

    async def _process_expired_data(
        self, db: Session, record: Dict, category: DataCategory
    ) -> Dict:
        """Process expired data according to retention policy."""
        # Implementation depends on your business logic
        return {
            "record_id": record.get("id"),
            "category": category.value,
            "action": "anonymized",
            "processed_at": datetime.utcnow().isoformat(),
        }

    def _serialize_consent(self, consent) -> Dict[str, Any]:
        """Serialize consent record."""
        return {
            "consent_id": consent.id,
            "purpose": consent.purpose,
            "lawful_basis": consent.lawful_basis,
            "status": consent.status,
            "granted_at": consent.granted_at.isoformat(),
            "expires_at": consent.expires_at.isoformat() if consent.expires_at else None,
        }


class ConsentValidator:
    """Validate consent for data processing operations."""

    def __init__(self, gdpr_manager: GDPRComplianceManager) -> None:
        self.gdpr_manager = gdpr_manager

    async def validate_processing(
        self, user_id: str, purpose: str, required_categories: List[DataCategory]
    ) -> bool:
        """Validate if processing is allowed under GDPR."""

        # Get user consents
        consents = await self.gdpr_manager.get_user_consents(user_id)

        # Check if there's valid consent for the purpose
        for consent in consents:
            if (
                consent["purpose"] == purpose
                and consent["status"] == "active"
                and self._categories_covered(consent["data_categories"], required_categories)
            ):
                # Check if consent is not expired
                if consent.get("expires_at"):
                    expires_at = datetime.fromisoformat(consent["expires_at"])
                    if expires_at < datetime.utcnow():
                        return False

                return True

        return False

    def _categories_covered(self, consented: List[str], required: List[DataCategory]) -> bool:
        """Check if consented categories cover required categories."""
        consented_set = set(consented)
        required_set = {cat.value for cat in required}
        return required_set.issubset(consented_set)


class PrivacyByDesign:
    """Implement privacy by design principles."""

    @staticmethod
    def minimize_data_collection(data: Dict[str, Any], required_fields: Set[str]) -> Dict[str, Any]:
        """Minimize data collection to only required fields."""
        return {k: v for k, v in data.items() if k in required_fields}

    @staticmethod
    def pseudonymize_identifier(identifier: str) -> str:
        """Create pseudonymous identifier."""
        return hashlib.sha256(identifier.encode()).hexdigest()

    @staticmethod
    def encrypt_sensitive_data(data: str, key: bytes) -> bytes:
        """Encrypt sensitive data."""
        from cryptography.fernet import Fernet

        f = Fernet(key)
        return f.encrypt(data.encode())

    @staticmethod
    def decrypt_sensitive_data(encrypted_data: bytes, key: bytes) -> str:
        """Decrypt sensitive data."""
        from cryptography.fernet import Fernet

        f = Fernet(key)
        return f.decrypt(encrypted_data).decode()


# Singleton instance
_gdpr_manager = None


def get_gdpr_manager() -> GDPRComplianceManager:
    """Get singleton GDPR compliance manager."""
    global _gdpr_manager
    if _gdpr_manager is None:
        _gdpr_manager = GDPRComplianceManager()
    return _gdpr_manager
