#!/usr/bin/env python3
"""
Cache Hashing Migration Script

Migrates cache keys from MD5 to SHA-256 hashing for improved security.
Supports dual-read mode for gradual migration without cache invalidation.

Usage:
    python scripts/migrate_cache_hashing.py [--dry-run] [--migrate-all]
"""

import asyncio
import argparse
import hashlib
import json
import logging
from typing import Dict, List, Optional
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.redis_client import get_redis_client
from services.caching.cache_keys import CacheKeyBuilder

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Migration constants
MD5_KEY_PATTERNS = ["api:*", "compute:*", "external:*", "db:*"]
BATCH_SIZE = 100
MIGRATION_TTL = 3600  # 1 hour TTL for migrated keys


class CacheHashMigrator:
    """Handles migration of cache keys from MD5 to SHA-256"""

    def __init__(self, dry_run: bool = False) -> None:
        self.dry_run = dry_run
        self.redis_client = None
        self.stats = {
            "scanned": 0,
            "migrated": 0,
            "skipped": 0,
            "errors": 0,
            "md5_keys": [],
            "sha256_keys": [],
        }

    async def initialize(self):
        """Initialize Redis connection"""
        try:
            self.redis_client = await get_redis_client()
            logger.info("Redis client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Redis client: {e}")
            raise

    async def close(self):
        """Close Redis connection"""
        if self.redis_client and hasattr(self.redis_client, "close"):
            await self.redis_client.close()

    def is_md5_key(self, key: str) -> bool:
        """Check if a key appears to use MD5 hashing"""
        # MD5 produces 32 character hex strings
        # SHA-256 produces 64 character hex strings (but we truncate)

        parts = key.split(":")
        if len(parts) < 2:
            return False

        # Check if the hash part looks like MD5 (32 chars)
        hash_part = parts[-1]
        return bool(
            len(hash_part) == 32 and all(c in "0123456789abcdef" for c in hash_part.lower())
        )

    def generate_sha256_key(self, md5_key: str, key_data: Optional[Dict] = None) -> Optional[str]:
        """Generate corresponding SHA-256 key for an MD5 key"""
        parts = md5_key.split(":")
        if len(parts) < 2:
            return None

        prefix = parts[0]

        # For migration, we need to reconstruct the key data
        # This is simplified - in production you'd need the original data
        if key_data:
            # Use provided key data
            if prefix == "api":
                cache_key = CacheKeyBuilder.build_api_key(
                    key_data.get("method", "GET"),
                    key_data.get("endpoint", ""),
                    key_data.get("params", {}),
                )
            elif prefix == "compute":
                cache_key = CacheKeyBuilder.build_computation_key(
                    key_data.get("operation", ""), key_data.get("params", {})
                )
            else:
                # Generic SHA-256 conversion
                data_str = json.dumps(key_data, sort_keys=True)
                hash_part = hashlib.sha256(data_str.encode()).hexdigest()[:32]
                cache_key = f"{prefix}:{hash_part}"
        else:
            # Without original data, we can't regenerate the exact key
            # This would need to be handled by dual-read in the application
            return None

        return cache_key

    async def scan_keys(self, pattern: str) -> List[str]:
        """Scan Redis for keys matching pattern"""
        keys = []
        try:
            cursor = 0
            while True:
                cursor, batch_keys = await self.redis_client.scan(
                    cursor, match=pattern, count=BATCH_SIZE
                )
                keys.extend([k.decode() if isinstance(k, bytes) else k for k in batch_keys])

                if cursor == 0:
                    break
        except Exception as e:
            logger.error(f"Error scanning keys with pattern {pattern}: {e}")
            self.stats["errors"] += 1

        return keys

    async def migrate_key(self, old_key: str, new_key: str) -> bool:
        """Migrate a single key from old to new format"""
        try:
            # Get value and TTL from old key
            value = await self.redis_client.get(old_key)
            if value is None:
                logger.debug(f"Key {old_key} has no value, skipping")
                return False

            ttl = await self.redis_client.ttl(old_key)
            if ttl == -2:  # Key doesn't exist
                return False
            elif ttl == -1:  # No expiration
                ttl = MIGRATION_TTL

            if not self.dry_run:
                # Set new key with same value and TTL
                await self.redis_client.set(new_key, value, ex=ttl)
                logger.debug(f"Migrated {old_key} -> {new_key}")
            else:
                logger.info(f"[DRY RUN] Would migrate {old_key} -> {new_key}")

            return True

        except Exception as e:
            logger.error(f"Error migrating key {old_key}: {e}")
            self.stats["errors"] += 1
            return False

    async def analyze_keys(self) -> Dict[str, List[str]]:
        """Analyze cache keys to identify MD5 vs SHA-256"""
        md5_keys = []
        sha256_keys = []

        for pattern in MD5_KEY_PATTERNS:
            keys = await self.scan_keys(pattern)
            self.stats["scanned"] += len(keys)

            for key in keys:
                if self.is_md5_key(key):
                    md5_keys.append(key)
                else:
                    sha256_keys.append(key)

        self.stats["md5_keys"] = md5_keys
        self.stats["sha256_keys"] = sha256_keys

        return {"md5": md5_keys, "sha256": sha256_keys}

    async def migrate_all(self) -> None:
        """Migrate all MD5 keys to SHA-256"""
        logger.info("Starting cache key migration...")

        # Analyze existing keys
        key_analysis = await self.analyze_keys()

        logger.info(
            f"Found {len(key_analysis['md5'])} MD5 keys and {len(key_analysis['sha256'])} SHA-256 keys"
        )

        if not key_analysis["md5"]:
            logger.info("No MD5 keys found, migration complete!")
            return

        # Note: Full migration would require original key data
        # This is a simplified version showing the pattern
        logger.warning(
            "Full automatic migration requires original key data. "
            "Keys will be handled by dual-read in the application."
        )

        for md5_key in key_analysis["md5"]:
            # In production, you'd reconstruct the original data
            # For now, we just mark them for manual review
            logger.info(f"MD5 key found: {md5_key} - will be handled by dual-read")
            self.stats["skipped"] += 1

    def print_stats(self) -> None:
        """Print migration statistics"""
        print("\n" + "=" * 50)
        print("Cache Key Migration Statistics")
        print("=" * 50)
        print(f"Keys scanned:  {self.stats['scanned']}")
        print(f"Keys migrated: {self.stats['migrated']}")
        print(f"Keys skipped:  {self.stats['skipped']}")
        print(f"Errors:        {self.stats['errors']}")
        print(f"MD5 keys:      {len(self.stats['md5_keys'])}")
        print(f"SHA-256 keys:  {len(self.stats['sha256_keys'])}")

        if self.stats["md5_keys"] and len(self.stats["md5_keys"]) <= 10:
            print("\nMD5 keys found:")
            for key in self.stats["md5_keys"]:
                print(f"  - {key}")
        elif self.stats["md5_keys"]:
            print(f"\nFound {len(self.stats['md5_keys'])} MD5 keys (showing first 10):")
            for key in self.stats["md5_keys"][:10]:
                print(f"  - {key}")

        print("=" * 50)


async def main():
    """Main migration entry point"""
    parser = argparse.ArgumentParser(description="Migrate cache keys from MD5 to SHA-256")
    parser.add_argument(
        "--dry-run", action="store_true", help="Run in dry-run mode (no changes made)"
    )
    parser.add_argument(
        "--migrate-all", action="store_true", help="Migrate all MD5 keys to SHA-256"
    )
    parser.add_argument(
        "--analyze-only", action="store_true", help="Only analyze keys without migration"
    )

    args = parser.parse_args()

    if args.dry_run:
        logger.info("Running in DRY RUN mode - no changes will be made")

    migrator = CacheHashMigrator(dry_run=args.dry_run)

    try:
        await migrator.initialize()

        if args.analyze_only:
            logger.info("Analyzing cache keys...")
            await migrator.analyze_keys()
        elif args.migrate_all:
            await migrator.migrate_all()
        else:
            # Default: analyze keys
            logger.info("Analyzing cache keys (use --migrate-all to migrate)")
            await migrator.analyze_keys()

        migrator.print_stats()

    except Exception as e:
        logger.error(f"Migration failed: {e}")
        return 1
    finally:
        await migrator.close()

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
