"""
import logging


logger = logging.getLogger(__name__)
# Constants
HTTP_BAD_REQUEST = 400
HTTP_INTERNAL_SERVER_ERROR = 500
HTTP_NOT_FOUND = 404


Foundation Evidence Collection API endpoints
AWS + Okta integration for automated compliance evidence gathering
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone
from pydantic import BaseModel
from api.dependencies.auth import get_current_active_user
from database.user import User
from database.db_setup import get_async_db
from database.services.integration_service import EvidenceCollectionService, store_integration_config, get_user_integrations, decrypt_integration_credentials
from api.background.evidence_collection import execute_foundation_evidence_collection
from api.clients.aws_client import AWSAPIClient
from api.clients.okta_client import OktaAPIClient
from api.clients.google_workspace_client import GoogleWorkspaceAPIClient
from api.clients.microsoft_client import MicrosoftGraphAPIClient
from api.clients.base_api_client import APICredentials, AuthType
from config.logging_config import get_logger
logger = get_logger(__name__)
router = APIRouter()


class AWSConfigurationRequest(BaseModel):
    auth_type: str
    access_key_id: Optional[str] = None
    secret_access_key: Optional[str] = None
    role_arn: Optional[str] = None
    external_id: Optional[str] = None
    region: str = 'us-east-1'


class OktaConfigurationRequest(BaseModel):
    domain: str
    api_token: str


class GoogleWorkspaceConfigurationRequest(BaseModel):
    domain: str
    client_id: str
    client_secret: str
    refresh_token: str


class MicrosoftConfigurationRequest(BaseModel):
    tenant_id: str
    client_id: str
    client_secret: str
    refresh_token: Optional[str] = None


class FoundationEvidenceRequest(BaseModel):
    framework_id: str
    business_profile: Dict[str, Any]
    evidence_types: Optional[List[str]] = None
    collection_mode: str = 'immediate'
    quality_requirements: Optional[Dict[str, Any]] = None


class EvidenceCollectionResponse(BaseModel):
    collection_id: str
    status: str
    message: str
    estimated_duration: str
    evidence_types: List[str]
    created_at: datetime


class EvidenceCollectionStatus(BaseModel):
    collection_id: str
    status: str
    progress_percentage: float
    evidence_collected: int
    total_expected: int
    quality_score: float
    started_at: datetime
    estimated_completion: Optional[datetime]
    current_activity: str
    errors: List[str]


class CollectedEvidence(BaseModel):
    evidence_id: str
    evidence_type: str
    source_system: str
    resource_id: str
    resource_name: str
    compliance_controls: List[str]
    quality_score: float
    collected_at: datetime
    data_summary: Dict[str, Any]


@router.post('/aws/configure')
async def configure_aws_integration(config: AWSConfigurationRequest,
    current_user: User=Depends(get_current_active_user), db: AsyncSession=
    Depends(get_async_db)) ->Dict[str, Any]:
    """Configure AWS integration for evidence collection"""
    try:
        if config.auth_type == 'access_key':
            if not config.access_key_id or not config.secret_access_key:
                raise HTTPException(status_code=HTTP_BAD_REQUEST, detail=
                    'Access key ID and secret access key are required for access_key auth type'
                    )
            credentials_dict = {'access_key_id': config.access_key_id,
                'secret_access_key': config.secret_access_key}
            auth_type = AuthType.API_KEY
        elif config.auth_type == 'role_assumption':
            if not config.role_arn:
                raise HTTPException(status_code=HTTP_BAD_REQUEST, detail=
                    'Role ARN is required for role_assumption auth type')
            credentials_dict = {'role_arn': config.role_arn, 'external_id':
                config.external_id}
            auth_type = AuthType.ROLE_ASSUMPTION
        else:
            raise HTTPException(status_code=HTTP_BAD_REQUEST, detail=
                "Invalid auth_type. Must be 'access_key' or 'role_assumption'")
        credentials = APICredentials(provider='aws', auth_type=auth_type,
            credentials=credentials_dict, region=config.region)
        aws_client = AWSAPIClient(credentials)
        if not await aws_client.authenticate():
            raise HTTPException(status_code=HTTP_BAD_REQUEST, detail=
                'AWS authentication failed')
        health_check = await aws_client.health_check()
        integration_config = await store_integration_config(user_id=str(
            current_user.id), provider='aws', credentials=credentials,
            health_info=health_check, db=db, configuration_metadata={
            'region': config.region, 'auth_type': config.auth_type})
        await aws_client.close()
        return {'integration_id': str(integration_config.id), 'provider':
            'aws', 'status': 'connected', 'account_id': health_check.get(
            'account_id'), 'region': config.region, 'capabilities':
            aws_client.get_supported_evidence_types(), 'message':
            'AWS integration configured successfully'}
    except HTTPException:
        raise
    except Exception as e:
        logger.error('Error configuring AWS integration for user %s: %s' %
            (str(current_user.id), e))
        raise HTTPException(status_code=HTTP_INTERNAL_SERVER_ERROR, detail=
            f'Configuration failed: {str(e)}')


@router.post('/okta/configure')
async def configure_okta_integration(config: OktaConfigurationRequest,
    current_user: User=Depends(get_current_active_user), db: AsyncSession=
    Depends(get_async_db)) ->Dict[str, Any]:
    """Configure Okta integration for evidence collection"""
    try:
        credentials = APICredentials(provider='okta', auth_type=AuthType.
            API_KEY, credentials={'domain': config.domain, 'api_token':
            config.api_token})
        okta_client = OktaAPIClient(credentials)
        if not await okta_client.authenticate():
            raise HTTPException(status_code=HTTP_BAD_REQUEST, detail=
                'Okta authentication failed')
        health_check = await okta_client.health_check()
        integration_config = await store_integration_config(user_id=str(
            current_user.id), provider='okta', credentials=credentials,
            health_info=health_check, db=db)
        await okta_client.close()
        return {'integration_id': str(integration_config.id), 'provider':
            'okta', 'status': 'connected', 'domain': config.domain,
            'capabilities': okta_client.get_supported_evidence_types(),
            'message': 'Okta integration configured successfully'}
    except HTTPException:
        raise
    except Exception as e:
        logger.error('Error configuring Okta integration for user %s: %s' %
            (str(current_user.id), e))
        raise HTTPException(status_code=HTTP_INTERNAL_SERVER_ERROR, detail=
            f'Configuration failed: {str(e)}')


@router.post('/google/configure')
async def configure_google_workspace_integration(config:
    GoogleWorkspaceConfigurationRequest, current_user: User=Depends(
    get_current_active_user), db: AsyncSession=Depends(get_async_db)) ->Dict[
    str, Any]:
    """Configure Google Workspace integration for evidence collection"""
    try:
        credentials = APICredentials(provider='google_workspace', auth_type
            =AuthType.OAUTH2, credentials={'domain': config.domain,
            'client_id': config.client_id, 'client_secret': config.
            client_secret, 'refresh_token': config.refresh_token})
        google_client = GoogleWorkspaceAPIClient(credentials)
        connection_test = await google_client.test_connection()
        if not connection_test[0]:
            raise HTTPException(status_code=HTTP_BAD_REQUEST, detail=
                f'Google Workspace connection failed: {connection_test[1]}')
        integration_config = await store_integration_config(user_id=str(
            current_user.id), provider='google_workspace', credentials=
            credentials, health_info={'domain': config.domain, 'status':
            'connected'}, db=db)
        await google_client.close()
        return {'integration_id': str(integration_config.id), 'provider':
            'google_workspace', 'status': 'connected', 'domain': config.
            domain, 'capabilities': google_client.
            get_supported_evidence_types(), 'message':
            'Google Workspace integration configured successfully'}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            'Error configuring Google Workspace integration for user %s: %s' %
            (str(current_user.id), e))
        raise HTTPException(status_code=HTTP_INTERNAL_SERVER_ERROR, detail=
            f'Configuration failed: {str(e)}')


@router.post('/microsoft/configure')
async def configure_microsoft_integration(config:
    MicrosoftConfigurationRequest, current_user: User=Depends(
    get_current_active_user), db: AsyncSession=Depends(get_async_db)) ->Dict[
    str, Any]:
    """Configure Microsoft 365/Azure AD integration for evidence collection"""
    try:
        credentials = APICredentials(provider='microsoft_365', auth_type=
            AuthType.OAUTH2, credentials={'tenant_id': config.tenant_id,
            'client_id': config.client_id, 'client_secret': config.
            client_secret, 'refresh_token': config.refresh_token})
        ms_client = MicrosoftGraphAPIClient(credentials)
        connection_test = await ms_client.test_connection()
        if not connection_test[0]:
            raise HTTPException(status_code=HTTP_BAD_REQUEST, detail=
                f'Microsoft Graph connection failed: {connection_test[1]}')
        integration_config = await store_integration_config(user_id=str(
            current_user.id), provider='microsoft_365', credentials=
            credentials, health_info={'tenant_id': config.tenant_id,
            'status': 'connected'}, db=db)
        await ms_client.close()
        return {'integration_id': str(integration_config.id), 'provider':
            'microsoft_365', 'status': 'connected', 'tenant_id': config.
            tenant_id, 'capabilities': ms_client.
            get_supported_evidence_types(), 'message':
            'Microsoft 365/Azure AD integration configured successfully'}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            'Error configuring Microsoft 365 integration for user %s: %s' %
            (str(current_user.id), e))
        raise HTTPException(status_code=HTTP_INTERNAL_SERVER_ERROR, detail=
            f'Configuration failed: {str(e)}')


@router.post('/collect', response_model=EvidenceCollectionResponse)
async def start_foundation_evidence_collection(request:
    FoundationEvidenceRequest, background_tasks: BackgroundTasks,
    current_user: User=Depends(get_current_active_user), db: AsyncSession=
    Depends(get_async_db)) ->Any:
    """Start foundation evidence collection from AWS and Okta"""
    try:
        user_integrations = await get_user_integrations(str(current_user.id
            ), db)
        integration_map = {i.provider: i for i in user_integrations}
        if not integration_map:
            raise HTTPException(status_code=HTTP_BAD_REQUEST, detail=
                'No integrations configured. Please configure at least one integration first.'
                )
        evidence_types = request.evidence_types or []
        if not evidence_types:
            for provider, _integration in integration_map.items():
                if provider == 'aws':
                    evidence_types.extend(['iam_policies', 'iam_users',
                        'iam_roles', 'security_groups', 'cloudtrail_logs'])
                elif provider == 'okta':
                    evidence_types.extend(['users', 'groups',
                        'applications', 'system_logs'])
                elif provider == 'google_workspace':
                    evidence_types.extend(['user_directory',
                        'access_groups', 'admin_activity_logs'])
                elif provider == 'microsoft_365':
                    evidence_types.extend(['user_directory',
                        'access_groups', 'applications'])
        evidence_service = EvidenceCollectionService(db)
        first_integration = next(iter(integration_map.values()))
        collection_record = await evidence_service.create_evidence_collection(
            integration_id=str(first_integration.id), user_id=str(
            current_user.id), framework_id=request.framework_id,
            evidence_types_requested=evidence_types, business_profile=
            request.business_profile, collection_mode=request.collection_mode)
        background_tasks.add_task(execute_foundation_evidence_collection,
            collection_id=str(collection_record.id), user_id=str(
            current_user.id), integration_map=integration_map,
            evidence_types=evidence_types)
        return EvidenceCollectionResponse(collection_id=str(
            collection_record.id), status='initiated', message=
            'Foundation evidence collection started', estimated_duration=
            '5-15 minutes', evidence_types=evidence_types, created_at=
            datetime.now(timezone.utc))
    except HTTPException:
        raise
    except Exception as e:
        logger.error('Error starting evidence collection for user %s: %s' %
            (str(current_user.id), e))
        raise HTTPException(status_code=HTTP_INTERNAL_SERVER_ERROR, detail=
            f'Failed to start collection: {str(e)}')


@router.get('/collect/{collection_id}/status', response_model=
    EvidenceCollectionStatus)
async def get_collection_status(collection_id: str, current_user: User=
    Depends(get_current_active_user), db: AsyncSession=Depends(get_async_db)
    ) ->Any:
    """Get status of evidence collection"""
    try:
        evidence_service = EvidenceCollectionService(db)
        collection = await evidence_service.get_collection_status(collection_id
            , str(current_user.id))
        if not collection:
            raise HTTPException(status_code=HTTP_NOT_FOUND, detail=
                'Collection not found')
        total_expected = len(collection.evidence_types_requested
            ) if collection.evidence_types_requested else 1
        evidence_collected = len(collection.evidence_types_completed
            ) if collection.evidence_types_completed else 0
        progress_percentage = min(100, int(evidence_collected /
            total_expected * 100)) if total_expected > 0 else 0
        return EvidenceCollectionStatus(collection_id=collection_id, status
            =collection.status, progress_percentage=progress_percentage,
            evidence_collected=evidence_collected, total_expected=
            total_expected, quality_score=sum(collection.quality_score.
            values()) / len(collection.quality_score) if collection.
            quality_score else 0.0, started_at=collection.started_at or
            collection.created_at, estimated_completion=collection.
            estimated_completion, current_activity=collection.
            current_activity or 'Processing...', errors=collection.errors or []
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error('Error getting collection status %s: %s' % (
            collection_id, e))
        raise HTTPException(status_code=HTTP_INTERNAL_SERVER_ERROR, detail=
            f'Failed to get status: {str(e)}')


@router.get('/collect/{collection_id}/results')
async def get_collection_results(collection_id: str, evidence_type:
    Optional[str]=Query(None, description='Filter by evidence type'), page:
    int=Query(1, ge=1, description='Page number'), page_size: int=Query(50,
    ge=1, le=200, description='Page size'), current_user: User=Depends(
    get_current_active_user), db: AsyncSession=Depends(get_async_db)) ->Dict[
    str, Any]:
    """Get collected evidence results"""
    try:
        evidence_service = EvidenceCollectionService(db)
        collection = await evidence_service.get_collection_status(collection_id
            , str(current_user.id))
        if not collection:
            raise HTTPException(status_code=HTTP_NOT_FOUND, detail=
                'Collection not found')
        evidence_items, total_count = (await evidence_service.
            get_collection_evidence(collection_id=collection_id,
            evidence_type=evidence_type, page=page, page_size=page_size))
        return {'collection_id': collection_id, 'status': collection.status,
            'total_evidence': total_count, 'page': page, 'page_size':
            page_size, 'evidence': [CollectedEvidence(evidence_id=str(item.
            id), evidence_type=item.evidence_type, source_system=item.
            source_system, resource_id=item.resource_id, resource_name=item
            .resource_name, compliance_controls=item.compliance_controls,
            quality_score=sum(item.quality_score.values()) / len(item.
            quality_score) if item.quality_score else 0.0, collected_at=
            item.collected_at, data_summary=item.evidence_data) for item in
            evidence_items]}
    except HTTPException:
        raise
    except Exception as e:
        logger.error('Error getting collection results %s: %s' % (
            collection_id, e))
        raise HTTPException(status_code=HTTP_INTERNAL_SERVER_ERROR, detail=
            f'Failed to get results: {str(e)}')


async def check_foundation_integrations_health(current_user: User=Depends(
    get_current_active_user), db: AsyncSession=Depends(get_async_db)) ->Dict[
    str, Any]:
    """Check health of foundation integrations (AWS + Okta)"""
    try:
        user_integrations = await get_user_integrations(str(current_user.id
            ), db)
        health_results = []
        for integration in user_integrations:
            try:
                credentials = await decrypt_integration_credentials(integration
                    )
                client = None
                if integration.provider == 'aws':
                    client = AWSAPIClient(credentials)
                elif integration.provider == 'okta':
                    client = OktaAPIClient(credentials)
                elif integration.provider == 'google_workspace':
                    client = GoogleWorkspaceAPIClient(credentials)
                elif integration.provider == 'microsoft_365':
                    client = MicrosoftGraphAPIClient(credentials)
                else:
                    continue
                health_result = await client.health_check()
                health_results.append({'integration_id': str(integration.id
                    ), 'provider': integration.provider, **health_result})
                await client.close()
            except Exception as e:
                health_results.append({'integration_id': str(integration.id
                    ), 'provider': integration.provider, 'status': 'error',
                    'error': str(e), 'timestamp': datetime.now(timezone.utc)})
        overall_status = 'healthy' if all(r['status'] == 'healthy' for r in
            health_results) else 'degraded'
        return {'overall_status': overall_status, 'integrations':
            health_results, 'total_integrations': len(health_results),
            'healthy_integrations': len([r for r in health_results if r[
            'status'] == 'healthy']), 'timestamp': datetime.now(timezone.utc)}
    except Exception as e:
        logger.error('Error checking foundation integrations health: %s' % e)
        raise HTTPException(status_code=HTTP_INTERNAL_SERVER_ERROR, detail=
            f'Health check failed: {str(e)}')
