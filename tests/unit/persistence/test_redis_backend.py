"""Unit tests for RedisCacheBackend using fakeredis."""

from __future__ import annotations

import json
from unittest.mock import patch

import fakeredis
import pytest

from bluestar.core.exceptions import CacheError
from bluestar.persistence.redis_backend import RedisCacheBackend


@pytest.fixture
def fake_server():
    return fakeredis.FakeServer()


@pytest.fixture
def backend(fake_server):
    with patch("redis.Redis", return_value=fakeredis.FakeRedis(server=fake_server, decode_responses=True)):
        return RedisCacheBackend(host="localhost", port=6379, db=0)


class TestGet:
    def test_returns_none_on_miss(self, backend):
        assert backend.get("nonexistent") is None

    def test_returns_deserialized_value(self, backend):
        data = {"plan_id": "ACME", "calc_type": "match"}
        backend.setex("key1", 300, json.dumps(data))
        result = backend.get("key1")
        assert result == json.dumps(data)


class TestSetex:
    def test_stores_value_with_ttl(self, backend):
        backend.setex("mykey", 60, json.dumps({"a": 1}))
        result = backend.get("mykey")
        assert result == json.dumps({"a": 1})

    def test_overwrites_existing_value(self, backend):
        backend.setex("k", 60, "old")
        backend.setex("k", 60, "new")
        assert backend.get("k") == "new"


class TestDelete:
    def test_removes_existing_key(self, backend):
        backend.setex("del_me", 60, "val")
        backend.delete("del_me")
        assert backend.get("del_me") is None

    def test_noop_on_missing_key(self, backend):
        backend.delete("never_existed")  # should not raise


class TestErrorWrapping:
    def test_get_wraps_redis_error(self):
        b = RedisCacheBackend.__new__(RedisCacheBackend)
        b._client = None  # will cause AttributeError -> CacheError
        with pytest.raises(CacheError):
            b.get("k")
