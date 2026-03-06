"""Mock Redis implementation for testing."""

from typing import Any, Dict, Optional, List
from datetime import datetime, timedelta
import json
from decimal import Decimal


class MockRedis:
    """Mock Redis client for testing without requiring actual Redis server."""

    def __init__(self):
        self.data: Dict[str, Any] = {}
        self.expires: Dict[str, datetime] = {}

    async def hset(self, key: str, mapping: Dict[str, Any] = None, **kwargs) -> int:
        """Mock hset operation."""
        if key not in self.data:
            self.data[key] = {}

        if mapping:
            for field, value in mapping.items():
                if isinstance(value, (dict, list)):
                    value = json.dumps(value)
                elif isinstance(value, Decimal):
                    value = str(value)
                self.data[key][field] = value

        for field, value in kwargs.items():
            if isinstance(value, (dict, list)):
                value = json.dumps(value)
            elif isinstance(value, Decimal):
                value = str(value)
            self.data[key][field] = value

        return len(self.data[key])

    async def hget(self, key: str, field: str) -> Optional[str]:
        """Mock hget operation."""
        if key in self.data and isinstance(self.data[key], dict):
            return self.data[key].get(field)
        return None

    async def hgetall(self, key: str) -> Dict[str, str]:
        """Mock hgetall operation."""
        if key in self.data and isinstance(self.data[key], dict):
            return self.data[key].copy()
        return {}

    async def zadd(self, key: str, mapping: Dict[str, float]) -> int:
        """Mock zadd operation."""
        if key not in self.data:
            self.data[key] = []

        for member, score in mapping.items():
            # Remove existing member if present
            self.data[key] = [item for item in self.data[key] if item[0] != member]
            # Add with new score
            self.data[key].append((member, score))
            # Sort by score
            self.data[key].sort(key=lambda x: x[1])

        return len(mapping)

    async def zrangebyscore(
        self, key: str, min_score: float, max_score: float, withscores: bool = False
    ) -> List:
        """Mock zrangebyscore operation."""
        if key not in self.data:
            return []

        results = []
        for member, score in self.data[key]:
            if min_score <= score <= max_score:
                if withscores:
                    results.append((member, score))
                else:
                    results.append(member)

        return results

    async def set(self, key: str, value: Any, ex: Optional[int] = None) -> bool:
        """Mock set operation."""
        if isinstance(value, (dict, list)):
            value = json.dumps(value)
        elif isinstance(value, Decimal):
            value = str(value)

        self.data[key] = value

        if ex:
            self.expires[key] = datetime.now() + timedelta(seconds=ex)

        return True

    async def get(self, key: str) -> Optional[str]:
        """Mock get operation."""
        # Check expiration
        if key in self.expires and datetime.now() > self.expires[key]:
            del self.data[key]
            del self.expires[key]
            return None

        return self.data.get(key)

    async def incr(self, key: str) -> int:
        """Mock incr operation."""
        if key not in self.data:
            self.data[key] = 0

        try:
            self.data[key] = int(self.data[key]) + 1
        except (ValueError, TypeError):
            self.data[key] = 1

        return self.data[key]

    async def incrby(self, key: str, amount: int) -> int:
        """Mock incrby operation."""
        if key not in self.data:
            self.data[key] = 0

        try:
            self.data[key] = int(self.data[key]) + amount
        except (ValueError, TypeError):
            self.data[key] = amount

        return self.data[key]

    async def keys(self, pattern: str = "*") -> List[str]:
        """Mock keys operation."""
        if pattern == "*":
            return list(self.data.keys())

        # Simple pattern matching (just prefix for now)
        if pattern.endswith("*"):
            prefix = pattern[:-1]
            return [k for k in self.data if k.startswith(prefix)]

        return [k for k in self.data if k == pattern]

    async def delete(self, *keys: str) -> int:
        """Mock delete operation."""
        deleted = 0
        for key in keys:
            if key in self.data:
                del self.data[key]
                deleted += 1
            if key in self.expires:
                del self.expires[key]
        return deleted

    async def exists(self, key: str) -> bool:
        """Mock exists operation."""
        return key in self.data

    async def expire(self, key: str, seconds: int) -> bool:
        """Mock expire operation."""
        if key in self.data:
            self.expires[key] = datetime.now() + timedelta(seconds=seconds)
            return True
        return False

    async def hincrbyfloat(self, key: str, field: str, increment: float) -> float:
        """Mock hincrbyfloat operation."""
        if key not in self.data:
            self.data[key] = {}

        if field not in self.data[key]:
            self.data[key][field] = 0.0

        try:
            current = float(self.data[key][field])
        except (ValueError, TypeError):
            current = 0.0

        new_value = current + increment
        self.data[key][field] = str(new_value)
        return new_value

    def pipeline(self):
        """Mock pipeline for batch operations."""
        return MockPipeline(self)

    async def execute(self):
        """Mock execute for pipeline."""
        return []


class MockPipeline:
    """Mock Redis pipeline for batch operations."""

    def __init__(self, redis_client):
        self.redis_client = redis_client
        self.operations = []

    def hincrbyfloat(self, key: str, field: str, increment: float):
        """Queue hincrbyfloat operation."""
        self.operations.append(("hincrbyfloat", key, field, increment))
        return self

    def hincrby(self, key: str, field: str, increment: int):
        """Queue hincrby operation."""
        self.operations.append(("hincrby", key, field, increment))
        return self

    def hset(self, key: str, field: str, value: Any):
        """Queue hset operation."""
        self.operations.append(("hset", key, field, value))
        return self

    def zadd(self, key: str, mapping: Dict[str, float]):
        """Queue zadd operation."""
        self.operations.append(("zadd", key, mapping))
        return self

    def expire(self, key: str, seconds: int):
        """Queue expire operation."""
        self.operations.append(("expire", key, seconds))
        return self

    async def execute(self):
        """Execute all queued operations."""
        results = []
        for op in self.operations:
            if op[0] == "hincrbyfloat":
                _, key, field, increment = op
                result = await self.redis_client.hincrbyfloat(key, field, increment)
                results.append(result)
            elif op[0] == "hincrby":
                _, key, field, increment = op
                if key not in self.redis_client.data:
                    self.redis_client.data[key] = {}
                current = int(self.redis_client.data[key].get(field, 0))
                new_value = current + increment
                self.redis_client.data[key][field] = str(new_value)
                results.append(new_value)
            elif op[0] == "hset":
                _, key, field, value = op
                if key not in self.redis_client.data:
                    self.redis_client.data[key] = {}
                if isinstance(value, (dict, list)):
                    value = json.dumps(value)
                elif isinstance(value, Decimal):
                    value = str(value)
                self.redis_client.data[key][field] = value
                results.append(1)
            elif op[0] == "zadd":
                _, key, mapping = op
                await self.redis_client.zadd(key, mapping)
                results.append(len(mapping))
            elif op[0] == "expire":
                _, key, seconds = op
                await self.redis_client.expire(key, seconds)
                results.append(True)
        return results

    def reset(self):
        """Reset all data (for testing)."""
        self.operations = []
