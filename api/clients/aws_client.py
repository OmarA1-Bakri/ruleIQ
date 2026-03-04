"""
import logging


logger = logging.getLogger(__name__)
AWS API client for collecting infrastructure and security evidence
"""
import boto3
from botocore.exceptions import ClientError, NoCredentialsError, BotoCoreError
from typing import Dict, List, Any, Optional
import json
from datetime import datetime, timedelta, timezone
from .base_api_client import (
    BaseAPIClient, APICredentials, EvidenceItem,
    BaseEvidenceCollector, APIException, AuthType
)
from config.logging_config import get_logger

# Network Ports
SSH_PORT = 22
RDP_PORT = 3389

# Time Constants
KEY_AGE_THRESHOLD_DAYS = 90
DEFAULT_SESSION_DURATION = 3600
MAX_POLICY_RESULTS = 100
MAX_USERS_PER_PAGE = 500

# Quality Score Penalties
MFA_PENALTY = 0.3
OLD_KEY_PENALTY = 0.2
WILDCARD_ACTION_PENALTY = 0.3
WILDCARD_RESOURCE_PENALTY = 0.4

# Pagination and Result Limits
MAX_POLICY_RESULTS = 100
MAX_USERS_PER_PAGE = 500

# Quality Score Thresholds
MFA_PENALTY = 0.3
OLD_KEY_PENALTY = 0.2
WILDCARD_ACTION_PENALTY = 0.3
WILDCARD_RESOURCE_PENALTY = 0.4

logger = get_logger(__name__)


class AWSAPIException(APIException):
    """AWS-specific API exception"""
    pass


class AWSAPIClient(BaseAPIClient):
    """AWS API client for collecting infrastructure and security evidence"""

    def __init__(self, credentials: APICredentials) ->None:
        super().__init__(credentials)
        self.aws_session: Optional[boto3.Session] = None
        self.region = credentials.region or 'us-east-1'

    @property
    def provider_name(self) ->str:
        return 'aws'

    def get_base_url(self) ->str:
        return ''

    async def authenticate(self) ->bool:
        """Authenticate using AWS credentials (Access Key, Role Assumption, etc.)"""
        try:
            if self.credentials.auth_type == AuthType.API_KEY:
                self.aws_session = boto3.Session(aws_access_key_id=self.
                    credentials.credentials['access_key_id'],
                    aws_secret_access_key=self.credentials.credentials[
                    'secret_access_key'], region_name=self.region)
            elif self.credentials.auth_type == AuthType.ROLE_ASSUMPTION:
                sts_client = boto3.client('sts')
                assume_role_params = {'RoleArn': self.credentials.
                    credentials['role_arn'], 'RoleSessionName':
                    'ruleiq-evidence-collection'}
                if 'external_id' in self.credentials.credentials:
                    assume_role_params['ExternalId'
                        ] = self.credentials.credentials['external_id']
                response = sts_client.assume_role(**assume_role_params)
                credentials = response['Credentials']
                self.aws_session = boto3.Session(aws_access_key_id=
                    credentials['AccessKeyId'], aws_secret_access_key=
                    credentials['SecretAccessKey'], aws_session_token=
                    credentials['SessionToken'], region_name=self.region)
                self.credentials.expires_at = credentials['Expiration']
            else:
                raise AWSAPIException(
                    f'Unsupported AWS auth type: {self.credentials.auth_type}')
            sts = self.aws_session.client('sts')
            caller_identity = sts.get_caller_identity()
            logger.info('AWS authentication successful for account: %s' %
                caller_identity.get('Account'))
            return True
        except (ClientError, NoCredentialsError, BotoCoreError) as e:
            logger.error('AWS authentication failed: %s' % e)
            return False
        except Exception as e:
            logger.error('Unexpected error during AWS authentication: %s' % e)
            return False

    async def refresh_credentials(self) ->bool:
        """Refresh AWS credentials if using role assumption"""
        if self.credentials.auth_type == AuthType.ROLE_ASSUMPTION:
            return await self.authenticate()
        return True

    def get_evidence_collector(self, evidence_type: str) -> Optional[BaseEvidenceCollector]:
        """Get AWS evidence collector for specific evidence type"""
        if not self.aws_session:
            return None
        collectors = {'iam_policies': AWSIAMEvidenceCollector(self),
            'iam_users': AWSIAMEvidenceCollector(self), 'iam_roles':
            AWSIAMEvidenceCollector(self), 'security_groups':
            AWSSecurityGroupCollector(self), 'vpc_configuration':
            AWSVPCCollector(self), 'cloudtrail_logs':
            AWSCloudTrailCollector(self), 'config_rules':
            AWSConfigCollector(self), 'guardduty_findings':
            AWSGuardDutyCollector(self), 'inspector_findings':
            AWSInspectorCollector(self), 'compliance_reports':
            AWSComplianceCollector(self), 's3_buckets': AWSS3Collector(self
            ), 'ec2_instances': AWSEC2Collector(self)}
        return collectors.get(evidence_type)

    def get_supported_evidence_types(self) ->List[str]:
        """Get list of supported evidence types for AWS"""
        return ['iam_policies', 'iam_users', 'iam_roles', 'security_groups',
            'vpc_configuration', 'cloudtrail_logs', 'config_rules',
            'guardduty_findings', 'inspector_findings',
            'compliance_reports', 's3_buckets', 'ec2_instances']

    def get_health_endpoint(self) ->str:
        return '/health'

    async def health_check(self) ->Dict[str, Any]:
        """AWS-specific health check using STS get_caller_identity"""
        try:
            if not await self.ensure_authenticated():
                raise AWSAPIException('Authentication failed')
            start_time = datetime.now(timezone.utc)
            sts = self.aws_session.client('sts')
            caller_identity = sts.get_caller_identity()
            response_time = (datetime.now(timezone.utc) - start_time
                ).total_seconds()
            return {'status': 'healthy', 'response_time': response_time,
                'provider': self.provider_name, 'timestamp': datetime.now(
                timezone.utc), 'account_id': caller_identity.get('Account'),
                'user_id': caller_identity.get('UserId'), 'arn':
                caller_identity.get('Arn'), 'region': self.region}
        except Exception as e:
            return {'status': 'unhealthy', 'error': str(e), 'provider':
                self.provider_name, 'timestamp': datetime.now(timezone.utc),
                'region': self.region}


class AWSIAMEvidenceCollector(BaseEvidenceCollector):
    """Collect IAM-related evidence from AWS"""

    async def collect(self, **kwargs: Any) -> List[EvidenceItem]:
        """Collect IAM policies, users, roles, and access patterns"""
        evidence = []
        try:
            iam = self.api_client.aws_session.client('iam')
            evidence.extend(await self._collect_iam_policies(iam))
            evidence.extend(await self._collect_iam_users(iam))
            evidence.extend(await self._collect_iam_roles(iam))
        except ClientError as e:
            self.logger.error('Error collecting IAM evidence: %s' % e)
            raise AWSAPIException(f'Failed to collect IAM evidence: {e}')
        return evidence

    async def _collect_iam_policies(self, iam_client) ->List[EvidenceItem]:
        """Collect IAM policies"""
        evidence = []
        try:
            policies_paginator = iam_client.get_paginator('list_policies')
            for page in policies_paginator.paginate(Scope='Local'):
                for policy in page['Policies']:
                    try:
                        policy_version = iam_client.get_policy_version(
                            PolicyArn=policy['Arn'], VersionId=policy[
                            'DefaultVersionId'])
                        entities = iam_client.list_entities_for_policy(
                            PolicyArn=policy['Arn'])
                        evidence_item = self.create_evidence_item(
                            evidence_type='iam_policy',
                            resource_id=policy['Arn'],
                            resource_name=policy['PolicyName'],
                            data={
                                'policy_name': policy['PolicyName'],
                                'policy_id': policy['PolicyId'],
                                'arn': policy['Arn'],
                                'path': policy['Path'],
                                'policy_document': policy_version['PolicyVersion']['Document'],
                                'default_version_id': policy['DefaultVersionId'],
                                'attachment_count': policy['AttachmentCount'],
                                'permissions_boundary_usage_count': policy.get(
                                    'PermissionsBoundaryUsageCount', 0
                                ),
                                'is_attachable': policy['IsAttachable'],
                                'description': policy.get('Description', ''),
                            'create_date': policy['CreateDate'].isoformat(),
                            'update_date': policy['UpdateDate'].isoformat(),
                            'attached_users': [user['UserName'] for user in
                            entities.get('PolicyUsers', [])],
                            'attached_groups': [group['GroupName'] for
                            group in entities.get('PolicyGroups', [])],
                            'attached_roles': [role['RoleName'] for role in
                            entities.get('PolicyRoles', [])]},
                            compliance_controls=['CC6.1', 'CC6.2', 'CC6.3'],
                            quality_score=self.
                            _calculate_policy_quality_score(policy,
                            policy_version['PolicyVersion']['Document']))
                        evidence.append(evidence_item)
                    except ClientError as e:
                        self.logger.warning(
                            'Failed to get details for policy %s: %s' % (
                            policy['PolicyName'], e))
                        continue
        except ClientError as e:
            self.logger.error('Error collecting IAM policies: %s' % e)
        return evidence

    async def _collect_iam_users(self, iam_client) ->List[EvidenceItem]:
        """Collect IAM users"""
        evidence = []
        try:
            users_paginator = iam_client.get_paginator('list_users')
            for page in users_paginator.paginate():
                for user in page['Users']:
                    try:
                        user_policies = iam_client.list_attached_user_policies(
                            UserName=user['UserName'])
                        user_groups = iam_client.get_groups_for_user(UserName
                            =user['UserName'])
                        access_keys = iam_client.list_access_keys(UserName=
                            user['UserName'])
                        mfa_devices = iam_client.list_mfa_devices(UserName=
                            user['UserName'])
                        has_console_access = False
                        try:
                            iam_client.get_login_profile(UserName=user[
                                'UserName'])
                            has_console_access = True
                        except ClientError:
                            pass
                        evidence_item = self.create_evidence_item(evidence_type
                            ='iam_user', resource_id=user['Arn'],
                            resource_name=user['UserName'], data={
                            'user_name': user['UserName'], 'user_id': user[
                            'UserId'], 'arn': user['Arn'], 'path': user[
                            'Path'], 'create_date': user['CreateDate'].
                            isoformat(), 'password_last_used': user.get(
                            'PasswordLastUsed', '').isoformat() if user.get
                            ('PasswordLastUsed') else None,
                            'has_console_access': has_console_access,
                            'attached_policies': [policy['PolicyName'] for
                            policy in user_policies['AttachedPolicies']],
                            'groups': [group['GroupName'] for group in
                            user_groups['Groups']], 'access_keys': [{
                            'access_key_id': key['AccessKeyId'], 'status':
                            key['Status'], 'create_date': key['CreateDate']
                            .isoformat()} for key in access_keys[
                            'AccessKeyMetadata']], 'mfa_devices': [{
                            'serial_number': device['SerialNumber'],
                            'enable_date': device['EnableDate'].isoformat()
                            } for device in mfa_devices['MFADevices']],
                            'tags': user.get('Tags', [])},
                            compliance_controls=['CC6.1', 'CC6.2', 'CC6.7'],
                            quality_score=self.
                            _calculate_user_quality_score(user, mfa_devices
                            ['MFADevices'], access_keys['AccessKeyMetadata']))
                        evidence.append(evidence_item)
                    except ClientError as e:
                        self.logger.warning(
                            'Failed to get details for user %s: %s' % (user
                            ['UserName'], e))
                        continue
        except ClientError as e:
            self.logger.error('Error collecting IAM users: %s' % e)
        return evidence

    async def _collect_iam_roles(self, iam_client) ->List[EvidenceItem]:
        """Collect IAM roles"""
        evidence = []
        try:
            roles_paginator = iam_client.get_paginator('list_roles')
            for page in roles_paginator.paginate():
                for role in page['Roles']:
                    try:
                        role_policies = iam_client.list_attached_role_policies(
                            RoleName=role['RoleName'])
                        inline_policies = iam_client.list_role_policies(
                            RoleName=role['RoleName'])
                        evidence_item = self.create_evidence_item(evidence_type
                            ='iam_role', resource_id=role['Arn'],
                            resource_name=role['RoleName'], data={
                            'role_name': role['RoleName'], 'role_id': role[
                            'RoleId'], 'arn': role['Arn'], 'path': role[
                            'Path'], 'assume_role_policy_document': role[
                            'AssumeRolePolicyDocument'], 'description':
                            role.get('Description', ''),
                            'max_session_duration': role.get(
                            'MaxSessionDuration', DEFAULT_SESSION_DURATION), 'create_date':
                            role['CreateDate'].isoformat(), 'last_used':
                            role.get('RoleLastUsed', {}).get('LastUsedDate',
                            '').isoformat() if role.get('RoleLastUsed', {})
                            .get('LastUsedDate') else None,
                            'last_used_region': role.get('RoleLastUsed', {}
                            ).get('Region'), 'attached_policies': [policy[
                            'PolicyName'] for policy in role_policies[
                            'AttachedPolicies']], 'inline_policies':
                            inline_policies['PolicyNames'], 'tags': role.
                            get('Tags', [])}, compliance_controls=['CC6.1',
                            'CC6.3'], quality_score=self.
                            _calculate_role_quality_score(role))
                        evidence.append(evidence_item)
                    except ClientError as e:
                        self.logger.warning(
                            'Failed to get details for role %s: %s' % (role
                            ['RoleName'], e))
                        continue
        except ClientError as e:
            self.logger.error('Error collecting IAM roles: %s' % e)
        return evidence

    def _calculate_policy_quality_score(self, policy: Dict[str, Any], policy_document: Any) -> float:
        """Calculate quality score for IAM policy"""
        score = 1.0
        if not policy.get('Description'):
            score -= 0.1
        if isinstance(policy_document, dict):
            statements = policy_document.get('Statement', [])
            if isinstance(statements, dict):
                statements = [statements]
            for statement in statements:
                if statement.get('Effect') == 'Allow':
                    actions = statement.get('Action', [])
                    if isinstance(actions, str):
                        actions = [actions]
                    if '*' in actions:
                        score -= WILDCARD_ACTION_PENALTY
                    resources = statement.get('Resource', [])
                    if isinstance(resources, str):
                        resources = [resources]
                    if '*' in resources and '*' in actions:
                        score -= WILDCARD_RESOURCE_PENALTY
        return max(0.0, score)

    def _calculate_user_quality_score(self, user: Dict[str, Any], mfa_devices: List[Dict[str, Any]], access_keys: List[Dict[str, Any]]) -> float:
        """Calculate quality score for IAM user"""
        score = 1.0
        if not mfa_devices:
            score -= MFA_PENALTY
        for key in access_keys:
            key_age = (datetime.now(timezone.utc) - key['CreateDate'].
                replace(tzinfo=None)).days
            if key_age > KEY_AGE_THRESHOLD_DAYS:
                score -= OLD_KEY_PENALTY
        if user.get('PasswordLastUsed'):
            last_used = user['PasswordLastUsed'].replace(tzinfo=None)
            days_since_login = (datetime.now(timezone.utc) - last_used).days
            if days_since_login > KEY_AGE_THRESHOLD_DAYS:
                score -= OLD_KEY_PENALTY
        return max(0.0, score)

    def _calculate_role_quality_score(self, role: Dict[str, Any]) -> float:
        """Calculate quality score for IAM role"""
        score = 1.0
        if not role.get('Description'):
            score -= 0.1
        assume_policy = role.get('AssumeRolePolicyDocument', {})
        if isinstance(assume_policy, dict):
            statements = assume_policy.get('Statement', [])
            if isinstance(statements, dict):
                statements = [statements]
            for statement in statements:
                principal = statement.get('Principal', {})
                if principal == '*' or isinstance(principal, dict
                    ) and principal.get('AWS') == '*':
                    score -= 0.5
        return max(0.0, score)


class AWSCloudTrailCollector(BaseEvidenceCollector):
    """Collect CloudTrail audit logs for compliance evidence"""

    async def collect(self, start_time: Optional[datetime] = None, event_types: Optional[List[str]] = None, **kwargs: Any) -> List[EvidenceItem]:
        """Collect CloudTrail events for audit evidence"""
        if not start_time:
            start_time = datetime.now(timezone.utc) - timedelta(days=7)
        evidence = []
        try:
            cloudtrail = self.api_client.aws_session.client('cloudtrail')
            lookup_attributes = []
            if event_types:
                for event_type in event_types:
                    lookup_attributes.append({'AttributeKey': 'EventName',
                        'AttributeValue': event_type})
            else:
                security_events = ['CreateUser', 'DeleteUser',
                    'AttachUserPolicy', 'DetachUserPolicy', 'CreateRole',
                    'DeleteRole', 'AttachRolePolicy', 'DetachRolePolicy',
                    'CreateAccessKey', 'DeleteAccessKey', 'UpdateAccessKey',
                    'ConsoleLogin', 'AssumeRole', 'CreateLoginProfile',
                    'DeleteLoginProfile']
                for event in security_events:
                    lookup_attributes.append({'AttributeKey': 'EventName',
                        'AttributeValue': event})
            for lookup_attr in lookup_attributes[:5]:
                try:
                    response = cloudtrail.lookup_events(LookupAttributes=[
                        lookup_attr], StartTime=start_time, EndTime=
                        datetime.now(timezone.utc), MaxItems=MAX_POLICY_RESULTS)
                    for event in response['Events']:
                        event_detail = json.loads(event.get(
                            'CloudTrailEvent', '{}'))
                        evidence_item = self.create_evidence_item(evidence_type
                            ='audit_log', resource_id=event['EventId'],
                            resource_name=event['EventName'], data={
                            'event_id': event['EventId'], 'event_name':
                            event['EventName'], 'event_time': event[
                            'EventTime'].isoformat(), 'username': event.get
                            ('Username'), 'user_identity': event_detail.get
                            ('userIdentity', {}), 'source_ip_address':
                            event_detail.get('sourceIPAddress'),
                            'user_agent': event_detail.get('userAgent'),
                            'aws_region': event_detail.get('awsRegion'),
                            'event_source': event_detail.get('eventSource'),
                            'event_type': event_detail.get('eventType'),
                            'api_version': event_detail.get('apiVersion'),
                            'request_parameters': event_detail.get(
                            'requestParameters', {}), 'response_elements':
                            event_detail.get('responseElements', {}),
                            'resources': event.get('Resources', []),
                            'error_code': event_detail.get('errorCode'),
                            'error_message': event_detail.get(
                            'errorMessage')}, compliance_controls=['CC6.1',
                            'CC7.2', 'CC7.3'], quality_score=self.
                            _calculate_log_quality_score(event_detail))
                        evidence.append(evidence_item)
                except ClientError as e:
                    self.logger.warning(
                        'Failed to collect events for %s: %s' % (
                        lookup_attr['AttributeValue'], e))
                    continue
        except ClientError as e:
            self.logger.error('Error collecting CloudTrail evidence: %s' % e)
            raise AWSAPIException(f'Failed to collect CloudTrail evidence: {e}',
                )
        return evidence

    def _calculate_log_quality_score(self, event_detail: Dict[str, Any]) -> float:
        """Calculate quality score for audit log entry"""
        score = 1.0
        required_fields = ['userIdentity', 'sourceIPAddress', 'eventTime',
            'eventSource']
        missing_fields = [field for field in required_fields if not
            event_detail.get(field)]
        if missing_fields:
            score -= 0.2 * len(missing_fields)
        if event_detail.get('errorCode'):
            score += 0.1
        return max(0.0, score)


class AWSSecurityGroupCollector(BaseEvidenceCollector):
    """Collect Security Group configurations for network security evidence"""

    async def collect(self, **kwargs: Any) -> List[EvidenceItem]:
        """Collect security group configurations"""
        evidence = []
        try:
            ec2 = self.api_client.aws_session.client('ec2')
            response = ec2.describe_security_groups()
            for sg in response['SecurityGroups']:
                evidence_item = self.create_evidence_item(evidence_type=
                    'security_group', resource_id=sg['GroupId'],
                    resource_name=sg['GroupName'], data={'group_id': sg[
                    'GroupId'], 'group_name': sg['GroupName'],
                    'description': sg['Description'], 'vpc_id': sg.get(
                    'VpcId'), 'owner_id': sg['OwnerId'], 'inbound_rules': [
                    {'ip_protocol': rule.get('IpProtocol'), 'from_port':
                    rule.get('FromPort'), 'to_port': rule.get('ToPort'),
                    'ip_ranges': rule.get('IpRanges', []), 'ipv6_ranges':
                    rule.get('Ipv6Ranges', []), 'user_id_group_pairs': rule
                    .get('UserIdGroupPairs', []), 'prefix_list_ids': rule.
                    get('PrefixListIds', [])} for rule in sg.get(
                    'IpPermissions', [])], 'outbound_rules': [{
                    'ip_protocol': rule.get('IpProtocol'), 'from_port':
                    rule.get('FromPort'), 'to_port': rule.get('ToPort'),
                    'ip_ranges': rule.get('IpRanges', []), 'ipv6_ranges':
                    rule.get('Ipv6Ranges', []), 'user_id_group_pairs': rule
                    .get('UserIdGroupPairs', []), 'prefix_list_ids': rule.
                    get('PrefixListIds', [])} for rule in sg.get(
                    'IpPermissionsEgress', [])], 'tags': sg.get('Tags', [])
                    }, compliance_controls=['CC6.1', 'CC6.6'],
                    quality_score=self.
                    _calculate_security_group_quality_score(sg))
                evidence.append(evidence_item)
        except ClientError as e:
            self.logger.error(
                'Error collecting security group evidence: %s' % e)
            raise AWSAPIException(
                f'Failed to collect security group evidence: {e}')
        return evidence

    def _calculate_security_group_quality_score(self, sg: Dict[str, Any]) -> float:
        """Calculate quality score for security group"""
        score = 1.0
        for rule in sg.get('IpPermissions', []):
            for ip_range in rule.get('IpRanges', []):
                if ip_range.get('CidrIp') == '0.0.0.0/0':
                    if rule.get('FromPort') == SSH_PORT or rule.get('FromPort'
                        ) == RDP_PORT:
                        score -= 0.5
                    else:
                        score -= OLD_KEY_PENALTY
        if not sg.get('Description') or sg['Description'] == sg['GroupName']:
            score -= 0.1
        return max(0.0, score)


class AWSVPCCollector(BaseEvidenceCollector):

    async def collect(self, **kwargs: Any) -> List[EvidenceItem]:
        return []


class AWSConfigCollector(BaseEvidenceCollector):

    async def collect(self, **kwargs: Any) -> List[EvidenceItem]:
        return []


class AWSGuardDutyCollector(BaseEvidenceCollector):

    async def collect(self, **kwargs: Any) -> List[EvidenceItem]:
        return []


class AWSInspectorCollector(BaseEvidenceCollector):

    async def collect(self, **kwargs: Any) -> List[EvidenceItem]:
        return []


class AWSComplianceCollector(BaseEvidenceCollector):

    async def collect(self, **kwargs: Any) -> List[EvidenceItem]:
        return []


class AWSS3Collector(BaseEvidenceCollector):

    async def collect(self, **kwargs: Any) -> List[EvidenceItem]:
        return []


class AWSEC2Collector(BaseEvidenceCollector):

    async def collect(self, **kwargs: Any) -> List[EvidenceItem]:
        return []
