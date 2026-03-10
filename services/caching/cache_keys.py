"""
Cache Key Management and Versioning

This module provides structured cache key generation, versioning, and compression
to ensure efficient and consistent cache key management across the application.

Security Note: This module uses SHA-256 hashing instead of MD5 for all cache key
generation to prevent potential security vulnerabilities from hash collisions.
"""

import hashlib
import json
from typing import Any, Dict, List, Optional, Union
from enum import Enum

# Security Constants - SHA-256 hash lengths for different use cases
COMPRESSED_KEY_HASH_LENGTH = 16  # For compressed cache keys
API_PARAM_HASH_LENGTH = 8  # For API parameter hashing
DB_PARAM_HASH_LENGTH = 8  # For database parameter hashing
COMPUTE_PARAM_HASH_LENGTH = 12  # For computation parameter hashing
EXTERNAL_PARAM_HASH_LENGTH = 8  # For external API parameter hashing

# Configuration Constants
MAX_CACHE_KEY_LENGTH = 250  # Maximum key length before compression
CACHE_KEY_PREFIX_MAX_LENGTH = 50  # Maximum prefix length for truncation


class CacheNamespace(str, Enum):
    """Standard cache namespaces for different data types"""

    USER = "user"
    SESSION = "session"
    BUSINESS = "business"
    EVIDENCE = "evidence"
    ASSESSMENT = "assessment"
    COMPLIANCE = "compliance"
    API = "api"
    COMPUTE = "compute"
    EXTERNAL = "external"
    DB = "db"


class CacheKeyBuilder:
    """
    Structured cache key builder with versioning and compression support.

    Provides consistent key generation patterns and handles versioning for
    cache invalidation during deployments.
    """

    # Current cache version - increment on breaking changes
    CACHE_VERSION = "v1"

    # Key prefixes for different operations
    PREFIX_CACHE = "cache"
    PREFIX_VERSION = "ver"
    PREFIX_COMPRESSED = "cmp"

    @classmethod
    def build_key(cls, *parts: Union[str, int]) -> str:
        """
        Build a structured cache key from parts.

        Args:
            *parts: Key components to join

        Returns:
            Structured cache key with prefix
        """
        if not parts:
            raise ValueError("At least one key part required")

        # Clean and validate parts
        clean_parts = []
        for part in parts:
            if part is None:
                continue
            clean_part = str(part).strip()
            if clean_part:  # Skip empty strings
                clean_parts.append(clean_part)

        if not clean_parts:
            raise ValueError("No valid key parts provided")

        return f"{cls.PREFIX_CACHE}:{':'.join(clean_parts)}"

    @classmethod
    def build_namespaced_key(
        cls, namespace: Union[str, CacheNamespace], *parts: Union[str, int]
    ) -> str:
        """
        Build a namespaced cache key.

        Args:
            namespace: Cache namespace
            *parts: Additional key components

        Returns:
            Namespaced cache key
        """
        ns = namespace.value if isinstance(namespace, CacheNamespace) else str(namespace)
        return cls.build_key(ns, *parts)

    @classmethod
    def build_versioned_key(cls, key: str, version: Optional[str] = None) -> str:
        """
        Add versioning to a cache key.

        Args:
            key: Base cache key
            version: Version string (defaults to current version)

        Returns:
            Versioned cache key
        """
        ver = version or cls.CACHE_VERSION
        return f"{key}:{cls.PREFIX_VERSION}:{ver}"

    @classmethod
    def compress_key(cls, key: str) -> str:
        """
        Compress a long cache key using hashing.

        Args:
            key: Original cache key

        Returns:
            Compressed cache key (maintains readability for short keys)
        """
        # Only compress if key is longer than MAX_CACHE_KEY_LENGTH characters
        if len(key) <= MAX_CACHE_KEY_LENGTH:
            return key

        # Create hash of the full key using SHA-256 for security
        # Truncate to maintain consistent key length
        key_hash = hashlib.sha256(key.encode("utf-8")).hexdigest()[:COMPRESSED_KEY_HASH_LENGTH]

        # Keep first part for readability
        parts = key.split(":")
        if len(parts) >= 2:
            prefix = f"{parts[0]}:{parts[1]}"
        else:
            prefix = parts[0][:CACHE_KEY_PREFIX_MAX_LENGTH] if parts else "cache"

        return f"{cls.PREFIX_COMPRESSED}:{prefix}:{key_hash}"

    @classmethod
    def build_user_key(cls, user_id: Union[str, int], *parts: Union[str, int]) -> str:
        """Build user-related cache key"""
        return cls.build_namespaced_key(CacheNamespace.USER, user_id, *parts)

    @classmethod
    def build_session_key(cls, session_id: Union[str, int], *parts: Union[str, int]) -> str:
        """Build session-related cache key"""
        return cls.build_namespaced_key(CacheNamespace.SESSION, session_id, *parts)

    @classmethod
    def build_business_key(cls, business_id: Union[str, int], *parts: Union[str, int]) -> str:
        """Build business-related cache key"""
        return cls.build_namespaced_key(CacheNamespace.BUSINESS, business_id, *parts)

    @classmethod
    def build_evidence_key(cls, evidence_id: Union[str, int], *parts: Union[str, int]) -> str:
        """Build evidence-related cache key"""
        return cls.build_namespaced_key(CacheNamespace.EVIDENCE, evidence_id, *parts)

    @classmethod
    def build_assessment_key(cls, assessment_id: Union[str, int], *parts: Union[str, int]) -> str:
        """Build assessment-related cache key"""
        return cls.build_namespaced_key(CacheNamespace.ASSESSMENT, assessment_id, *parts)

    @classmethod
    def build_compliance_key(cls, compliance_id: Union[str, int], *parts: Union[str, int]) -> str:
        """Build compliance-related cache key"""
        return cls.build_namespaced_key(CacheNamespace.COMPLIANCE, compliance_id, *parts)

    @classmethod
    def build_api_key(
        cls, method: str, endpoint: str, params: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Build API response cache key.

        Args:
            method: HTTP method
            endpoint: API endpoint
            params: Query parameters

        Returns:
            API cache key
        """
        key_parts = [method.upper(), endpoint]

        if params:
            # Sort params for consistent key generation
            param_str = json.dumps(params, sort_keys=True)
            # Use SHA-256 for secure parameter hashing
            param_hash = hashlib.sha256(param_str.encode()).hexdigest()[:API_PARAM_HASH_LENGTH]
            key_parts.append(param_hash)

        return cls.build_namespaced_key(CacheNamespace.API, *key_parts)

    @classmethod
    def build_db_query_key(
        cls, table: str, query_hash: str, params: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Build database query cache key.

        Args:
            table: Database table name
            query_hash: Hash of the query
            params: Query parameters

        Returns:
            Database query cache key
        """
        key_parts = [table, query_hash]

        if params:
            param_str = json.dumps(params, sort_keys=True)
            # Use SHA-256 for secure parameter hashing with DB-specific hash length
            param_hash = hashlib.sha256(param_str.encode()).hexdigest()[:DB_PARAM_HASH_LENGTH]
            key_parts.append(param_hash)

        return cls.build_namespaced_key(CacheNamespace.DB, *key_parts)

    @classmethod
    def build_computation_key(cls, operation: str, params: Dict[str, Any]) -> str:
        """
        Build computation cache key.

        Args:
            operation: Computation operation name
            params: Computation parameters

        Returns:
            Computation cache key
        """
        # Create deterministic hash of params
        param_str = json.dumps(params, sort_keys=True, default=str)
        # Use SHA-256 for secure parameter hashing
        param_hash = hashlib.sha256(param_str.encode()).hexdigest()[:COMPUTE_PARAM_HASH_LENGTH]

        return cls.build_namespaced_key(CacheNamespace.COMPUTE, operation, param_hash)

    @classmethod
    def build_external_api_key(
        cls, service: str, endpoint: str, params: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Build external API cache key.

        Args:
            service: External service name
            endpoint: API endpoint
            params: Request parameters

        Returns:
            External API cache key
        """
        key_parts = [service, endpoint]

        if params:
            param_str = json.dumps(params, sort_keys=True, default=str)
            # Use SHA-256 for secure parameter hashing with external API-specific hash length
            param_hash = hashlib.sha256(param_str.encode()).hexdigest()[:EXTERNAL_PARAM_HASH_LENGTH]
            key_parts.append(param_hash)

        return cls.build_namespaced_key(CacheNamespace.EXTERNAL, *key_parts)

    @classmethod
    def invalidate_pattern(cls, namespace: Union[str, CacheNamespace], *patterns: str) -> str:
        """
        Build invalidation pattern for namespace.

        Args:
            namespace: Cache namespace
            *patterns: Pattern components

        Returns:
            Invalidation pattern
        """
        ns = namespace.value if isinstance(namespace, CacheNamespace) else str(namespace)
        pattern_parts = [cls.PREFIX_CACHE, ns] + list(patterns)
        return ":".join(pattern_parts) + "*"

    @classmethod
    def get_related_keys(cls, entity_type: str, entity_id: Union[str, int]) -> List[str]:
        """
        Get related cache keys for an entity.

        Args:
            entity_type: Type of entity (user, business, etc.)
            entity_id: Entity ID

        Returns:
            List of related cache keys to potentially invalidate
        """
        entity_id_str = str(entity_id)
        related_keys = []

        if entity_type == "user":
            related_keys.extend(
                [
                    cls.build_user_key(entity_id_str),
                    cls.build_user_key(entity_id_str, "profile"),
                    cls.build_user_key(entity_id_str, "settings"),
                    cls.build_user_key(entity_id_str, "sessions"),
                    cls.build_user_key(entity_id_str, "permissions"),
                ]
            )
        elif entity_type == "business":
            related_keys.extend(
                [
                    cls.build_business_key(entity_id_str),
                    cls.build_business_key(entity_id_str, "profile"),
                    cls.build_business_key(entity_id_str, "assessments"),
                    cls.build_business_key(entity_id_str, "compliance"),
                ]
            )
        elif entity_type == "evidence":
            related_keys.extend(
                [
                    cls.build_evidence_key(entity_id_str),
                    cls.build_evidence_key(entity_id_str, "content"),
                    cls.build_evidence_key(entity_id_str, "metadata"),
                ]
            )
        elif entity_type == "assessment":
            related_keys.extend(
                [
                    cls.build_assessment_key(entity_id_str),
                    cls.build_assessment_key(entity_id_str, "results"),
                    cls.build_assessment_key(entity_id_str, "progress"),
                ]
            )

        return related_keys

    @classmethod
    def parse_key(cls, key: str) -> Dict[str, Any]:
        """
        Parse a cache key into components.

        Args:
            key: Cache key to parse

        Returns:
            Dictionary with parsed key components
        """
        if not key.startswith(cls.PREFIX_CACHE + ":"):
            raise ValueError(f"Invalid cache key format: {key}")

        parts = key.split(":")
        if len(parts) < 2:
            raise ValueError(f"Cache key too short: {key}")

        result = {
            "prefix": parts[0],
            "namespace": parts[1] if len(parts) > 1 else None,
            "parts": parts[2:] if len(parts) > 2 else [],
            "is_versioned": False,
            "version": None,
            "is_compressed": key.startswith(cls.PREFIX_COMPRESSED + ":"),
        }

        # Check for versioning
        for i, part in enumerate(parts):
            if part == cls.PREFIX_VERSION and i + 1 < len(parts):
                result["is_versioned"] = True
                result["version"] = parts[i + 1]
                result["parts"] = parts[2:i]  # Exclude version parts
                break

        return result

    @classmethod
    def is_expired_version(cls, key: str, current_version: Optional[str] = None) -> bool:
        """
        Check if a cache key has an expired version.

        Args:
            key: Cache key to check
            current_version: Current cache version (defaults to CACHE_VERSION)

        Returns:
            True if key version is expired
        """
        current = current_version or cls.CACHE_VERSION

        try:
            parsed = cls.parse_key(key)
            if not parsed["is_versioned"]:
                return False
            return parsed["version"] != current
        except ValueError:
            version_marker = f":{cls.PREFIX_VERSION}:"
            if version_marker in key:
                return key.rsplit(version_marker, 1)[1] != current

            # Invalid key format
            return True

    @classmethod
    def migrate_key_version(cls, key: str, new_version: Optional[str] = None) -> str:
        """
        Migrate a cache key to a new version.

        Args:
            key: Original cache key
            new_version: New version (defaults to CACHE_VERSION)

        Returns:
            Migrated cache key
        """
        try:
            parsed = cls.parse_key(key)
            if parsed["is_versioned"]:
                # Remove old version and add new one
                base_parts = [parsed["prefix"], parsed["namespace"], *parsed["parts"]]
                base_key = ":".join(part for part in base_parts if part)
                return cls.build_versioned_key(base_key, new_version)
            else:
                # Add version to unversioned key
                return cls.build_versioned_key(key, new_version)
        except ValueError:
            version_marker = f":{cls.PREFIX_VERSION}:"
            if version_marker in key:
                base_key = key.rsplit(version_marker, 1)[0]
                return cls.build_versioned_key(base_key, new_version)

            # Invalid key, return as-is
            return key
