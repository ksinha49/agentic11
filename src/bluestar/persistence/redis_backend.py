"""Redis cache backend implementing ICacheBackend."""

from __future__ import annotations

import redis

from bluestar.core.exceptions import CacheError


class RedisCacheBackend:
    """Production ICacheBackend backed by Redis."""

    def __init__(self, host: str = "localhost", port: int = 6379, db: int = 0) -> None:
        self._host = host
        self._port = port
        self._db = db
        self._client = redis.Redis(
            host=host, port=port, db=db, decode_responses=True,
        )

    def get(self, key: str) -> str | None:
        try:
            return self._client.get(key)
        except Exception as exc:
            raise CacheError(f"Redis GET failed for key={key!r}: {exc}") from exc

    def setex(self, key: str, ttl: int, value: str) -> None:
        try:
            self._client.setex(key, ttl, value)
        except Exception as exc:
            raise CacheError(f"Redis SETEX failed for key={key!r}: {exc}") from exc

    def delete(self, key: str) -> None:
        try:
            self._client.delete(key)
        except Exception as exc:
            raise CacheError(f"Redis DELETE failed for key={key!r}: {exc}") from exc
