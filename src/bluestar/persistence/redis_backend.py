"""Redis cache backend implementing ICacheBackend."""

from __future__ import annotations

# TODO: Implement real Redis client with TTL-aware caching


class RedisCacheBackend:
    """Production ICacheBackend backed by Redis."""

    def __init__(self, host: str = "localhost", port: int = 6379, db: int = 0) -> None:
        self._host = host
        self._port = port
        self._db = db

    def get(self, key: str) -> str | None:
        raise NotImplementedError

    def setex(self, key: str, ttl: int, value: str) -> None:
        raise NotImplementedError

    def delete(self, key: str) -> None:
        raise NotImplementedError
