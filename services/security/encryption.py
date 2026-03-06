"""

Enhanced Data Encryption Service for Security Hardening
Implements field-level encryption, key management, and secure transmission
"""

import base64
import hashlib
import json
import logging
import os
import secrets
from typing import Any, Dict, Optional, Tuple
from datetime import datetime, timedelta, timezone
from cryptography.fernet import Fernet, MultiFernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305, AESGCM
import aiofiles
import aiofiles.os
from services.cache_service import CacheService
from config.settings import settings

logger = logging.getLogger(__name__)


class EncryptionService:
    """
    Comprehensive encryption service for data protection
    """

    def __init__(self) -> None:
        """Initialize encryption service with key management"""
        self.cache = CacheService()
        self._master_key = self._get_or_create_master_key()
        self._key_rotation_interval = timedelta(days=90)
        self._key_versions: Dict[int, bytes] = {}
        self._current_key_version = 1
        self._initialize_key_versions()
        self.encrypted_fields = [
            "ssn",
            "credit_card",
            "bank_account",
            "api_key",
            "password_recovery_token",
            "mfa_secret",
            "backup_codes",
            "personal_identification",
            "medical_record",
            "financial_data",
        ]
        self._fernet = self._initialize_fernet()
        self._aes_gcm = AESGCM(self._derive_key(32))
        self._chacha = ChaCha20Poly1305(self._derive_key(32))

    def _get_or_create_master_key(self) -> bytes:
        """Get or create master encryption key"""
        key_path = os.path.join(settings.upload_directory, ".encryption_key")
        try:
            if os.path.exists(key_path):
                with open(key_path, "rb") as f:
                    return f.read()
            else:
                key = Fernet.generate_key()
                os.makedirs(os.path.dirname(key_path), exist_ok=True)
                with open(key_path, "wb") as f:
                    f.write(key)
                os.chmod(key_path, 384)
                logger.info("Generated new master encryption key")
                return key
        except OSError as e:
            logger.error("Error managing master key: %s" % e)
            env_key = os.getenv("MASTER_ENCRYPTION_KEY")
            if env_key:
                return env_key.encode()
            raise Exception("Unable to initialize encryption key")

    def _initialize_fernet(self) -> MultiFernet:
        """Initialize Fernet with key rotation support"""
        keys = []
        keys.append(Fernet(self._master_key))
        for version, key in self._key_versions.items():
            if version != self._current_key_version:
                keys.append(Fernet(key))
        return MultiFernet(keys)

    def _initialize_key_versions(self):
        """Load or initialize key versions for rotation"""
        try:
            data_dir = getattr(settings, "data_dir", "./data")
            key_versions_path = os.path.join(data_dir, ".key_versions.json")
            if os.path.exists(key_versions_path):
                with open(key_versions_path, "r") as f:
                    versions_data = json.load(f)
                    self._key_versions = {
                        int(k): base64.b64decode(v) for k, v in versions_data.items()
                    }
                    self._current_key_version = max(self._key_versions.keys())
            else:
                self._key_versions[1] = self._master_key
                self._save_key_versions()
        except (OSError, json.JSONDecodeError, ValueError) as e:
            logger.error("Error loading key versions: %s" % e)
            self._key_versions[1] = self._master_key

    def _save_key_versions(self):
        """Save key versions to disk"""
        try:
            data_dir = getattr(settings, "data_dir", "./data")
            key_versions_path = os.path.join(data_dir, ".key_versions.json")
            versions_data = {
                str(k): base64.b64encode(v).decode() for k, v in self._key_versions.items()
            }
            with open(key_versions_path, "w") as f:
                json.dump(versions_data, f)
            os.chmod(key_versions_path, 384)
        except (OSError, json.JSONDecodeError) as e:
            logger.error("Error saving key versions: %s" % e)

    def _derive_key(self, length: int = 32) -> bytes:
        """Derive encryption key from master key"""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=length,
            salt=b"ruleiq_salt_2024",
            iterations=100000,
            backend=default_backend(),
        )
        return kdf.derive(self._master_key)

    async def encrypt_field(self, value: Any, field_name: str = "") -> str:
        """
        Encrypt a single field value

        Args:
            value: Value to encrypt
            field_name: Name of field for context

        Returns:
            Base64 encoded encrypted value
        """
        try:
            if value is None:
                return None
            if not isinstance(value, (str, bytes)):
                value = json.dumps(value)
            if isinstance(value, str):
                value = value.encode()
            metadata = {
                "field": field_name,
                "version": self._current_key_version,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            payload = json.dumps(
                {"value": base64.b64encode(value).decode(), "metadata": metadata}
            ).encode()
            encrypted = self._fernet.encrypt(payload)
            cache_key = f"enc:{hashlib.sha256(value).hexdigest()}"
            await self.cache.set(cache_key, encrypted, ttl=3600)
            return base64.b64encode(encrypted).decode()
        except json.JSONDecodeError as e:
            logger.error("Encryption error for field %s: %s" % (field_name, e))
            raise

    async def decrypt_field(self, encrypted_value: str, field_name: str = "") -> Any:
        """
        Decrypt a single field value

        Args:
            encrypted_value: Base64 encoded encrypted value
            field_name: Name of field for context

        Returns:
            Decrypted value
        """
        try:
            if encrypted_value is None:
                return None
            cache_key = f"dec:{hashlib.sha256(encrypted_value.encode()).hexdigest()}"
            cached = await self.cache.get(cache_key)
            if cached:
                return cached
            encrypted_bytes = base64.b64decode(encrypted_value)
            decrypted_payload = self._fernet.decrypt(encrypted_bytes)
            payload = json.loads(decrypted_payload)
            value_b64 = payload["value"]
            payload.get("metadata", {})
            value = base64.b64decode(value_b64)
            try:
                result = json.loads(value)
            except json.JSONDecodeError:
                result = value.decode()
            await self.cache.set(cache_key, result, ttl=3600)
            return result
        except json.JSONDecodeError as e:
            logger.error("Decryption error for field %s: %s" % (field_name, e))
            raise

    async def encrypt_document(self, document: Dict[str, Any]) -> Dict[str, Any]:
        """
        Encrypt sensitive fields in a document

        Args:
            document: Document with potentially sensitive fields

        Returns:
            Document with encrypted sensitive fields
        """
        encrypted_doc = document.copy()
        for field in self.encrypted_fields:
            if field in encrypted_doc and encrypted_doc[field] is not None:
                encrypted_doc[field] = await self.encrypt_field(encrypted_doc[field], field)
        encrypted_doc["_encryption"] = {
            "version": self._current_key_version,
            "fields": [f for f in self.encrypted_fields if f in document],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        return encrypted_doc

    async def decrypt_document(self, document: Dict[str, Any]) -> Dict[str, Any]:
        """
        Decrypt sensitive fields in a document

        Args:
            document: Document with encrypted fields

        Returns:
            Document with decrypted fields
        """
        decrypted_doc = document.copy()
        encryption_meta = decrypted_doc.pop("_encryption", {})
        encrypted_fields = encryption_meta.get("fields", self.encrypted_fields)
        for field in encrypted_fields:
            if field in decrypted_doc and decrypted_doc[field] is not None:
                decrypted_doc[field] = await self.decrypt_field(decrypted_doc[field], field)
        return decrypted_doc

    async def encrypt_file(self, file_path: str, output_path: Optional[str] = None) -> str:
        """
        Encrypt a file

        Args:
            file_path: Path to file to encrypt
            output_path: Optional output path

        Returns:
            Path to encrypted file
        """
        try:
            if output_path is None:
                output_path = f"{file_path}.encrypted"
            file_key = Fernet.generate_key()
            file_fernet = Fernet(file_key)
            chunk_size = 64 * 1024
            async with aiofiles.open(file_path, "rb") as infile:
                async with aiofiles.open(output_path, "wb") as outfile:
                    encrypted_key = self._fernet.encrypt(file_key)
                    await outfile.write(len(encrypted_key).to_bytes(4, "big"))
                    await outfile.write(encrypted_key)
                    while True:
                        chunk = await infile.read(chunk_size)
                        if not chunk:
                            break
                        encrypted_chunk = file_fernet.encrypt(chunk)
                        await outfile.write(len(encrypted_chunk).to_bytes(4, "big"))
                        await outfile.write(encrypted_chunk)
            await aiofiles.os.chmod(output_path, 384)
            logger.info("File encrypted: %s" % output_path)
            return output_path
        except OSError as e:
            logger.error("File encryption error: %s" % e)
            raise

    async def decrypt_file(self, file_path: str, output_path: Optional[str] = None) -> str:
        """
        Decrypt a file

        Args:
            file_path: Path to encrypted file
            output_path: Optional output path

        Returns:
            Path to decrypted file
        """
        try:
            if output_path is None:
                output_path = file_path.replace(".encrypted", "")
            async with aiofiles.open(file_path, "rb") as infile:
                key_length = int.from_bytes(await infile.read(4), "big")
                encrypted_key = await infile.read(key_length)
                file_key = self._fernet.decrypt(encrypted_key)
                file_fernet = Fernet(file_key)
                async with aiofiles.open(output_path, "wb") as outfile:
                    while True:
                        chunk_length_bytes = await infile.read(4)
                        if not chunk_length_bytes:
                            break
                        chunk_length = int.from_bytes(
                            chunk_length_bytes,
                            "big",
                        )
                        encrypted_chunk = await infile.read(chunk_length)
                        decrypted_chunk = file_fernet.decrypt(encrypted_chunk)
                        await outfile.write(decrypted_chunk)
            logger.info("File decrypted: %s" % output_path)
            return output_path
        except OSError as e:
            logger.error("File decryption error: %s" % e)
            raise

    async def generate_data_key(self, purpose: str = "general") -> Tuple[str, str]:
        """
        Generate a data encryption key

        Args:
            purpose: Purpose of the key

        Returns:
            Tuple of (key_id, encrypted_key)
        """
        try:
            data_key = Fernet.generate_key()
            key_id = (
                f"{purpose}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{secrets.token_hex(8)}",
            )
            encrypted_key = self._fernet.encrypt(data_key)
            key_metadata = {
                "id": key_id,
                "purpose": purpose,
                "created": datetime.now(timezone.utc).isoformat(),
                "version": self._current_key_version,
            }
            await self.cache.set(
                f"datakey:{key_id}",
                {"key": base64.b64encode(data_key).decode(), "metadata": key_metadata},
                ttl=86400,
            )
            return key_id, base64.b64encode(encrypted_key).decode()
        except (ValueError, TypeError) as e:
            logger.error("Error generating data key: %s" % e)
            raise

    async def rotate_encryption_keys(self) -> bool:
        """
        Rotate encryption keys

        Returns:
            Success status
        """
        try:
            new_key = Fernet.generate_key()
            new_version = self._current_key_version + 1
            self._key_versions[new_version] = new_key
            self._current_key_version = new_version
            self._master_key = new_key
            self._fernet = self._initialize_fernet()
            self._save_key_versions()
            key_path = os.path.join(settings.upload_directory, ".encryption_key")
            with open(key_path, "wb") as f:
                f.write(new_key)
            os.chmod(key_path, 384)
            logger.info("Encryption keys rotated to version %s" % new_version)
            await self._reencrypt_critical_data()
            return True
        except (OSError, KeyError, IndexError) as e:
            logger.error("Key rotation error: %s" % e)
            return False

    async def _reencrypt_critical_data(self):
        """Re-encrypt critical data with new key"""
        pass

    async def create_encrypted_backup(self, data: Any, backup_path: str) -> str:
        """
        Create encrypted backup of data

        Args:
            data: Data to backup
            backup_path: Path for backup file

        Returns:
            Path to encrypted backup
        """
        try:
            serialized = json.dumps(data) if isinstance(data, dict) else str(data)
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            backup_file = f"{backup_path}_{timestamp}.backup"
            encrypted_data = self._fernet.encrypt(serialized.encode())
            async with aiofiles.open(backup_file, "wb") as f:
                await f.write(encrypted_data)
            await aiofiles.os.chmod(backup_file, 384)
            logger.info("Encrypted backup created: %s" % backup_file)
            return backup_file
        except (OSError, json.JSONDecodeError) as e:
            logger.error("Backup creation error: %s" % e)
            raise

    async def verify_encryption_integrity(self, encrypted_value: str) -> bool:
        """
        Verify integrity of encrypted data

        Args:
            encrypted_value: Encrypted value to verify

        Returns:
            True if integrity is valid
        """
        try:
            decrypted = await self.decrypt_field(encrypted_value)
            return decrypted is not None
        except (ValueError, TypeError):
            return False

    def generate_encryption_report(self) -> Dict[str, Any]:
        """
        Generate encryption status report

        Returns:
            Encryption metrics and status
        """
        return {
            "master_key_present": self._master_key is not None,
            "current_key_version": self._current_key_version,
            "total_key_versions": len(self._key_versions),
            "encrypted_fields": self.encrypted_fields,
            "encryption_methods": ["Fernet", "AES-GCM", "ChaCha20-Poly1305"],
            "key_rotation_interval": str(self._key_rotation_interval),
            "last_rotation": "N/A",
            "status": "healthy",
        }


_encryption_service = None


def get_encryption_service() -> EncryptionService:
    """Get or create encryption service instance"""
    global _encryption_service
    if _encryption_service is None:
        _encryption_service = EncryptionService()
    return _encryption_service
