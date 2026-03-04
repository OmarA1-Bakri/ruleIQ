"""
import logging


logger = logging.getLogger(__name__)
Base integration class for all third-party integrations.
This abstract class defines the contract that all specific
integration implementations (like Google, AWS, etc.) must follow.
"""
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID
from cryptography.fernet import InvalidToken
from config.app_config import get_cipher_suite
from config.logging_config import get_logger
logger = get_logger(__name__)


class IntegrationStatus(str, Enum):
    CONNECTED = 'connected'
    DISCONNECTED = 'disconnected'
    ERROR = 'error'
    NEEDS_REAUTH = 'needs_reauth'
    PENDING_VERIFICATION = 'pending_verification'


@dataclass
class IntegrationConfig:
    user_id: UUID
    provider: str
    credentials: Dict[str, Any]
    settings: Optional[Dict[str, Any]] = None
    status: IntegrationStatus = IntegrationStatus.DISCONNECTED
    last_sync: Optional[datetime] = None


class BaseIntegration(ABC):

    def __init__(self, config: IntegrationConfig) ->None:
        self.config = config
        self.cipher = get_cipher_suite()
        if not self.cipher:
            logger.error(
                'Fernet cipher not available for integration %s for user %s. Cannot proceed without encryption.'
                 % (self.config.provider, self.config.user_id))
            raise IntegrationError(
                'Encryption cipher not available. Cannot create integration without secure credential storage.',
                )

    @property
    @abstractmethod
    def provider_name(self) ->str:
        pass

    @abstractmethod
    async def test_connection(self) ->bool:
        pass

    @abstractmethod
    async def authenticate(self) ->bool:
        pass

    @abstractmethod
    async def collect_evidence(self, evidence_type: str, since: Optional[
        datetime]=None) ->List[Dict[str, Any]]:
        pass

    @abstractmethod
    async def get_available_evidence_types(self) ->List[Dict[str, Any]]:
        pass

    async def validate_credentials(self, credentials_to_test: Dict[str, Any]
        ) ->bool:
        original_creds = self.config.credentials
        self.config.credentials = credentials_to_test
        try:
            result = await self.test_connection()
            return result
        except Exception as e:
            logger.error('Error validating credentials for %s: %s' % (self.
                provider_name, e), exc_info=True)
            return False
        finally:
            self.config.credentials = original_creds

    def encrypt_credentials_to_str(self, credentials_dict: Dict[str, Any]
        ) ->str:
        if not self.cipher:
            logger.error(
                'Cannot encrypt credentials: Fernet cipher is not initialized.',
                )
            raise IntegrationError(
                'Encryption cipher not available. Cannot save credentials securely.',
                )
        try:
            credentials_json = json.dumps(credentials_dict)
            credentials_bytes = credentials_json.encode('utf-8')
            encrypted_bytes = self.cipher.encrypt(credentials_bytes)
            return encrypted_bytes.decode('utf-8')
        except Exception as e:
            logger.error('Failed to encrypt credentials: %s' % e, exc_info=True,
                )
            raise IntegrationError(f'Failed to encrypt credentials: {e}'
                ) from e

    def decrypt_credentials_from_str(self, encrypted_credentials_str: str
        ) ->Dict[str, Any]:
        if not self.cipher:
            logger.error(
                'Cannot decrypt credentials: Fernet cipher is not initialized.',
                )
            raise IntegrationError(
                'Decryption cipher not available. Cannot load credentials securely.',
                )
        try:
            encrypted_bytes = encrypted_credentials_str.encode('utf-8')
            decrypted_bytes = self.cipher.decrypt(encrypted_bytes)
            credentials_json = decrypted_bytes.decode('utf-8')
            return json.loads(credentials_json)
        except InvalidToken as e:
            logger.error(
                'Failed to decrypt credentials: Invalid Fernet token. Key might be wrong or data corrupted.',
                )
            raise IntegrationError('Invalid credentials token') from e
        except Exception as e:
            logger.error('Failed to decrypt credentials: %s' % e, exc_info=True,
                )
            raise IntegrationError(f'Failed to decrypt credentials: {e}'
                ) from e


class IntegrationError(Exception):
    pass


class AuthenticationError(IntegrationError):
    pass


class ConnectionError(IntegrationError):
    pass


class EvidenceCollectionError(IntegrationError):
    pass
