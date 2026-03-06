"""

# Constants

Unit tests for integration service
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
import uuid
from database.services.integration_service import IntegrationService, EvidenceCollectionService
from database.models.integrations import Integration, EvidenceCollection, IntegrationEvidenceItem
from api.clients.base_api_client import APICredentials, AuthType

from tests.test_constants import MAX_RETRIES


class TestIntegrationService:
    """Test cases for IntegrationService"""

    @pytest.fixture
    def mock_db(self):
        """Mock database session"""
        db = AsyncMock()
        async_context_manager = AsyncMock()
        async_context_manager.__aenter__ = AsyncMock(return_value=async_context_manager)
        async_context_manager.__aexit__ = AsyncMock(return_value=None)
        db.begin = MagicMock(return_value=async_context_manager)
        return db

    @pytest.fixture
    def mock_encryption(self):
        """Mock credential encryption"""
        encryption = MagicMock()
        encryption.encrypt_credentials.return_value = "encrypted_credentials"
        encryption.decrypt_credentials.return_value = {
            "access_key_id": "test_key",
            "secret_access_key": "test_secret",
            "region": "us-east-1",
        }
        return encryption

    @pytest.fixture
    def integration_service(self, mock_db, mock_encryption):
        """Create IntegrationService instance with mocked dependencies"""
        with patch(
            "database.services.integration_service.get_credential_encryption",
            return_value=mock_encryption,
        ):
            return IntegrationService(mock_db)

    @pytest.fixture
    def sample_credentials(self):
        """Sample API credentials"""
        return APICredentials(
            provider="aws",
            auth_type=AuthType.API_KEY,
            credentials={
                "access_key_id": "MOCK_AWS_ACCESS_KEY",
                "secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
            },
            region="us-east-1",
        )

    @pytest.fixture
    def sample_health_info(self):
        """Sample health check info"""
        return {
            "status": "healthy",
            "response_time": 0.5,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    @pytest.mark.asyncio
    async def test_store_integration_config_new(
        self, integration_service, sample_credentials, sample_health_info
    ):
        """Test storing new integration configuration"""
        user_id = str(uuid.uuid4())
        provider = "aws"
        integration_service.db.execute = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        integration_service.db.execute.return_value = result_mock
        integration_service.db.commit = AsyncMock()
        integration_service.db.refresh = AsyncMock()
        integration_service.db.add = MagicMock()
        result = await integration_service.store_integration_config(
            user_id=user_id,
            provider=provider,
            credentials=sample_credentials,
            health_info=sample_health_info,
        )
        assert integration_service.db.add.call_count == MAX_RETRIES
        integration_service.db.refresh.assert_called_once()
        assert result is not None

    @pytest.mark.asyncio
    async def test_store_integration_config_update_existing(
        self, integration_service, sample_credentials, sample_health_info
    ):
        """Test updating existing integration configuration"""
        user_id = str(uuid.uuid4())
        provider = "aws"
        existing_integration = Integration(
            id=uuid.uuid4(),
            user_id=user_id,
            provider=provider,
            encrypted_credentials="old_encrypted_data",
            health_status={"status": "unknown"},
        )
        integration_service.db.execute = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = existing_integration
        integration_service.db.execute.return_value = result_mock
        integration_service.db.commit = AsyncMock()
        integration_service.db.refresh = AsyncMock()
        result = await integration_service.store_integration_config(
            user_id=user_id,
            provider=provider,
            credentials=sample_credentials,
            health_info=sample_health_info,
        )
        assert existing_integration.health_status == sample_health_info
        assert existing_integration.is_active
        assert existing_integration.encrypted_credentials == "encrypted_credentials"
        integration_service.db.refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_user_integrations(self, integration_service):
        """Test retrieving user integrations"""
        user_id = str(uuid.uuid4())
        integration_service.db.execute = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = [
            Integration(
                id=uuid.uuid4(),
                user_id=user_id,
                provider="aws",
                encrypted_credentials="encrypted",
                health_status={},
            ),
            Integration(
                id=uuid.uuid4(),
                user_id=user_id,
                provider="okta",
                encrypted_credentials="encrypted",
                health_status={},
            ),
        ]
        integration_service.db.execute.return_value = result_mock
        integrations = await integration_service.get_user_integrations(user_id)
        assert len(integrations) == 2
        assert integrations[0].provider == "aws"
        assert integrations[1].provider == "okta"

    @pytest.mark.asyncio
    async def test_get_integration_by_id(self, integration_service):
        """Test retrieving integration by ID"""
        integration_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())
        integration_service.db.execute = AsyncMock()
        result_mock = MagicMock()
        expected_integration = Integration(
            id=integration_id,
            user_id=user_id,
            provider="aws",
            encrypted_credentials="encrypted",
            health_status={},
        )
        result_mock.scalar_one_or_none.return_value = expected_integration
        integration_service.db.execute.return_value = result_mock
        integration = await integration_service.get_integration_by_id(integration_id, user_id)
        assert integration == expected_integration

    @pytest.mark.asyncio
    async def test_decrypt_integration_credentials(self, integration_service):
        """Test decrypting integration credentials"""
        integration = Integration(
            id=uuid.uuid4(),
            user_id=str(uuid.uuid4()),
            provider="aws",
            encrypted_credentials="encrypted_data",
            health_status={},
        )
        credentials = await integration_service.decrypt_integration_credentials(integration)
        assert credentials.provider == "aws"
        assert credentials.auth_type == AuthType.API_KEY
        assert credentials.credentials["access_key_id"] == "test_key"
        assert credentials.credentials["secret_access_key"] == "test_secret"
        assert credentials.region == "us-east-1"

    @pytest.mark.asyncio
    async def test_update_integration_health(self, integration_service):
        """Test updating integration health"""
        integration_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())
        existing_integration = Integration(
            id=integration_id,
            user_id=user_id,
            provider="aws",
            encrypted_credentials="encrypted",
            health_status={"status": "unknown"},
        )
        integration_service.db.execute = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = existing_integration
        integration_service.db.execute.return_value = result_mock
        integration_service.db.commit = AsyncMock()
        health_data = {"status": "healthy", "response_time": 0.3}
        result = await integration_service.update_integration_health(
            integration_id, health_data, user_id
        )
        assert result
        assert existing_integration.health_status == health_data
        assert existing_integration.last_health_check is not None

    @pytest.mark.asyncio
    async def test_delete_integration(self, integration_service):
        """Test deleting (deactivating) integration"""
        integration_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())
        existing_integration = Integration(
            id=integration_id,
            user_id=user_id,
            provider="aws",
            encrypted_credentials="encrypted",
            health_status={},
            is_active=True,
        )
        integration_service.db.execute = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = existing_integration
        integration_service.db.execute.return_value = result_mock
        integration_service.db.commit = AsyncMock()
        result = await integration_service.delete_integration(integration_id, user_id)
        assert result
        assert not existing_integration.is_active


class TestEvidenceCollectionService:
    """Test cases for EvidenceCollectionService"""

    @pytest.fixture
    def mock_db(self):
        """Mock database session"""
        db = AsyncMock()
        async_context_manager = AsyncMock()
        async_context_manager.__aenter__ = AsyncMock(return_value=async_context_manager)
        async_context_manager.__aexit__ = AsyncMock(return_value=None)
        db.begin = MagicMock(return_value=async_context_manager)
        return db

    @pytest.fixture
    def evidence_service(self, mock_db):
        """Create EvidenceCollectionService instance"""
        return EvidenceCollectionService(mock_db)

    @pytest.mark.asyncio
    async def test_create_evidence_collection(self, evidence_service):
        """Test creating evidence collection"""
        integration_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())
        framework_id = "soc2_type2"
        evidence_types = ["iam_policies", "iam_users"]
        business_profile = {"company_size": "medium"}
        evidence_service.db.add = MagicMock()
        evidence_service.db.commit = AsyncMock()
        evidence_service.db.refresh = AsyncMock()
        collection = await evidence_service.create_evidence_collection(
            integration_id=integration_id,
            user_id=user_id,
            framework_id=framework_id,
            evidence_types_requested=evidence_types,
            business_profile=business_profile,
        )
        evidence_service.db.add.assert_called_once()
        evidence_service.db.commit.assert_called_once()
        evidence_service.db.refresh.assert_called_once()
        assert collection.integration_id == integration_id
        assert collection.user_id == user_id
        assert collection.framework_id == framework_id
        assert collection.evidence_types_requested == evidence_types
        assert collection.business_profile == business_profile
        assert collection.status == "pending"

    @pytest.mark.asyncio
    async def test_update_collection_status(self, evidence_service):
        """Test updating collection status"""
        collection_id = str(uuid.uuid4())
        existing_collection = EvidenceCollection(
            id=collection_id,
            integration_id=str(uuid.uuid4()),
            user_id=str(uuid.uuid4()),
            framework_id="soc2_type2",
            status="pending",
        )
        evidence_service.db.execute = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = existing_collection
        evidence_service.db.execute.return_value = result_mock
        evidence_service.db.commit = AsyncMock()
        result = await evidence_service.update_collection_status(
            collection_id=str(collection_id),
            status="running",
            progress_percentage=50,
            current_activity="Collecting IAM policies",
        )
        assert result
        assert existing_collection.status == "running"
        assert existing_collection.progress_percentage == 50
        assert existing_collection.current_activity == "Collecting IAM policies"

    @pytest.mark.asyncio
    async def test_store_evidence_item(self, evidence_service):
        """Test storing evidence item"""
        collection_id = str(uuid.uuid4())
        evidence_type = "iam_policies"
        source_system = "aws"
        resource_id = "policy-123"
        resource_name = "TestPolicy"
        evidence_data = {"policy_document": {"Version": "2012-10-17"}}
        compliance_controls = ["CC6.1", "CC6.2"]
        quality_score = {"overall": 0.9}
        collected_at = datetime.now(timezone.utc)
        evidence_service.db.add = MagicMock()
        evidence_service.db.commit = AsyncMock()
        evidence_service.db.refresh = AsyncMock()
        evidence_item = await evidence_service.store_evidence_item(
            collection_id=str(collection_id),
            evidence_type=evidence_type,
            source_system=source_system,
            resource_id=resource_id,
            resource_name=resource_name,
            evidence_data=evidence_data,
            compliance_controls=compliance_controls,
            quality_score=quality_score,
            collected_at=collected_at,
        )
        evidence_service.db.add.assert_called_once()
        evidence_service.db.commit.assert_called_once()
        evidence_service.db.refresh.assert_called_once()
        assert evidence_item.collection_id == collection_id
        assert evidence_item.evidence_type == evidence_type
        assert evidence_item.source_system == source_system
        assert evidence_item.resource_id == resource_id
        assert evidence_item.resource_name == resource_name
        assert evidence_item.evidence_data == evidence_data
        assert evidence_item.compliance_controls == compliance_controls
        assert evidence_item.quality_score == quality_score
        assert evidence_item.collected_at == collected_at
        assert evidence_item.checksum is not None

    @pytest.mark.asyncio
    async def test_get_collection_status(self, evidence_service):
        """Test getting collection status"""
        collection_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())
        evidence_service.db.execute = AsyncMock()
        result_mock = MagicMock()
        expected_collection = EvidenceCollection(
            id=collection_id,
            integration_id=str(uuid.uuid4()),
            user_id=user_id,
            framework_id="soc2_type2",
            status="running",
            progress_percentage=75,
        )
        result_mock.scalar_one_or_none.return_value = expected_collection
        evidence_service.db.execute.return_value = result_mock
        collection = await evidence_service.get_collection_status(str(collection_id), user_id)
        assert collection == expected_collection

    @pytest.mark.asyncio
    async def test_get_collection_evidence(self, evidence_service):
        """Test getting collection evidence with pagination"""
        collection_id = str(uuid.uuid4())
        evidence_items = [
            IntegrationEvidenceItem(
                id=uuid.uuid4(),
                collection_id=collection_id,
                evidence_type="iam_policies",
                source_system="aws",
                resource_id="policy-1",
                resource_name="Policy 1",
                evidence_data={},
                compliance_controls=["CC6.1"],
                quality_score={"overall": 0.9},
                collected_at=datetime.now(timezone.utc),
            ),
            IntegrationEvidenceItem(
                id=uuid.uuid4(),
                collection_id=collection_id,
                evidence_type="iam_users",
                source_system="aws",
                resource_id="user-1",
                resource_name="User 1",
                evidence_data={},
                compliance_controls=["CC6.2"],
                quality_score={"overall": 0.8},
                collected_at=datetime.now(timezone.utc),
            ),
        ]
        evidence_service.db.execute = AsyncMock()
        count_result = MagicMock()
        count_result.scalar.return_value = 2
        items_result = MagicMock()
        items_result.scalars.return_value.all.return_value = evidence_items
        evidence_service.db.execute.side_effect = [count_result, items_result]
        items, total_count = await evidence_service.get_collection_evidence(
            collection_id=str(collection_id), page=1, page_size=10
        )
        assert total_count == 2
        assert len(items) == 2
        assert items[0].evidence_type == "iam_policies"
        assert items[1].evidence_type == "iam_users"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
