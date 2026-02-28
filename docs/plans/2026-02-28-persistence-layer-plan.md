# Persistence Layer Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement the three core persistence backends (DynamoDB, Redis, S3) that all five agents depend on, plus a seed script and full test coverage.

**Architecture:** Protocol-based design — each backend implements a protocol from `src/bluestar/core/protocols.py`. In-memory fakes in `memory_backend.py` define the expected behavior. DynamoDB integrates with Redis for read-through caching via the `ICacheBackend` protocol.

**Tech Stack:** Python 3.12, boto3, redis-py, moto (AWS mocking), fakeredis, pytest

---

## Task 1: Add `fakeredis` to dev dependencies

**Files:**
- Modify: `pyproject.toml:49` (dev dependencies list)

**Step 1: Add fakeredis to pyproject.toml**

In `pyproject.toml`, add `fakeredis` to the `dev` optional-dependencies list:

```toml
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
    "pytest-cov>=5.0",
    "ruff>=0.5",
    "mypy>=1.10",
    "boto3-stubs[dynamodb,s3,sqs,events]>=1.35",
    "respx>=0.21",
    "moto[dynamodb,s3,sqs]>=5.0",
    "fakeredis>=2.26",
]
```

**Step 2: Install updated dependencies**

Run: `pip install -e ".[dev]"`
Expected: Success, fakeredis installed

**Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "chore: add fakeredis to dev dependencies"
```

---

## Task 2: Implement `RedisCacheBackend`

**Files:**
- Modify: `src/bluestar/persistence/redis_backend.py`
- Create: `tests/unit/persistence/__init__.py`
- Create: `tests/unit/persistence/test_redis_backend.py`

**Step 1: Write the failing tests**

Create `tests/unit/persistence/__init__.py` (empty file).

Create `tests/unit/persistence/test_redis_backend.py`:

```python
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
    with patch("redis.Redis", return_value=fakeredis.FakeRedis(server=fake_server)):
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
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/persistence/test_redis_backend.py -v`
Expected: FAIL — `NotImplementedError` from all methods

**Step 3: Implement RedisCacheBackend**

Replace contents of `src/bluestar/persistence/redis_backend.py`:

```python
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
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/persistence/test_redis_backend.py -v`
Expected: All 7 tests PASS

**Step 5: Verify protocol conformance**

Run: `python -c "from bluestar.persistence.redis_backend import RedisCacheBackend; from bluestar.core.protocols import ICacheBackend; assert isinstance(RedisCacheBackend('localhost'), ICacheBackend)"`
Expected: No error (assertion passes)

**Step 6: Commit**

```bash
git add src/bluestar/persistence/redis_backend.py tests/unit/persistence/
git commit -m "feat: implement RedisCacheBackend with error wrapping"
```

---

## Task 3: Implement `S3FileStore`

**Files:**
- Modify: `src/bluestar/persistence/s3_backend.py`
- Create: `tests/unit/persistence/test_s3_backend.py`

**Step 1: Write the failing tests**

Create `tests/unit/persistence/test_s3_backend.py`:

```python
"""Unit tests for S3FileStore using moto."""

from __future__ import annotations

import boto3
import pytest
from moto import mock_aws

from bluestar.persistence.s3_backend import S3FileStore

BUCKET = "test-payroll-files"


@pytest.fixture
def s3_backend():
    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket=BUCKET)
        yield S3FileStore(bucket=BUCKET, region="us-east-1")


class TestWrite:
    def test_write_returns_path(self, s3_backend):
        result = s3_backend.write("dropzone/file.csv", b"a,b,c")
        assert result == "dropzone/file.csv"

    def test_write_stores_bytes(self, s3_backend):
        s3_backend.write("test/data.bin", b"\x00\x01\x02")
        assert s3_backend.read("test/data.bin") == b"\x00\x01\x02"


class TestRead:
    def test_read_returns_bytes(self, s3_backend):
        s3_backend.write("docs/hello.txt", b"Hello")
        assert s3_backend.read("docs/hello.txt") == b"Hello"

    def test_read_missing_key_raises(self, s3_backend):
        with pytest.raises(Exception):
            s3_backend.read("does/not/exist.txt")


class TestMove:
    def test_move_copies_and_deletes_source(self, s3_backend):
        s3_backend.write("src/file.csv", b"data")
        s3_backend.move("src/file.csv", "dst/file.csv")
        assert s3_backend.read("dst/file.csv") == b"data"
        with pytest.raises(Exception):
            s3_backend.read("src/file.csv")


class TestListFiles:
    def test_list_returns_matching_keys(self, s3_backend):
        s3_backend.write("prefix/a.csv", b"1")
        s3_backend.write("prefix/b.csv", b"2")
        s3_backend.write("other/c.csv", b"3")
        result = s3_backend.list_files("prefix/")
        assert sorted(result) == ["prefix/a.csv", "prefix/b.csv"]

    def test_list_empty_prefix_returns_nothing(self, s3_backend):
        result = s3_backend.list_files("nonexistent/")
        assert result == []

    def test_list_handles_pagination(self, s3_backend):
        for i in range(1050):
            s3_backend.write(f"bulk/{i:04d}.txt", b"x")
        result = s3_backend.list_files("bulk/")
        assert len(result) == 1050
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/persistence/test_s3_backend.py -v`
Expected: FAIL — `NotImplementedError`

**Step 3: Implement S3FileStore**

Replace contents of `src/bluestar/persistence/s3_backend.py`:

```python
"""S3 file storage backend implementing IFileStore."""

from __future__ import annotations

import boto3
from botocore.exceptions import ClientError

from bluestar.core.exceptions import BlueStarError


class S3FileStore:
    """Production IFileStore backed by S3."""

    def __init__(self, bucket: str, region: str = "us-east-1",
                 endpoint_url: str | None = None) -> None:
        self._bucket = bucket
        self._region = region
        self._endpoint_url = endpoint_url
        kwargs: dict = {"region_name": region}
        if endpoint_url:
            kwargs["endpoint_url"] = endpoint_url
        self._client = boto3.client("s3", **kwargs)

    def read(self, path: str) -> bytes:
        try:
            resp = self._client.get_object(Bucket=self._bucket, Key=path)
            return resp["Body"].read()
        except ClientError as exc:
            raise BlueStarError(f"S3 read failed for {path!r}: {exc}") from exc

    def write(self, path: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        try:
            self._client.put_object(
                Bucket=self._bucket, Key=path, Body=data, ContentType=content_type,
            )
            return path
        except ClientError as exc:
            raise BlueStarError(f"S3 write failed for {path!r}: {exc}") from exc

    def move(self, src: str, dst: str) -> None:
        try:
            self._client.copy_object(
                Bucket=self._bucket,
                CopySource={"Bucket": self._bucket, "Key": src},
                Key=dst,
            )
            self._client.delete_object(Bucket=self._bucket, Key=src)
        except ClientError as exc:
            raise BlueStarError(f"S3 move {src!r} -> {dst!r} failed: {exc}") from exc

    def list_files(self, prefix: str) -> list[str]:
        try:
            keys: list[str] = []
            paginator = self._client.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=self._bucket, Prefix=prefix):
                for obj in page.get("Contents", []):
                    keys.append(obj["Key"])
            return keys
        except ClientError as exc:
            raise BlueStarError(f"S3 list failed for prefix={prefix!r}: {exc}") from exc
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/persistence/test_s3_backend.py -v`
Expected: All 7 tests PASS

**Step 5: Verify protocol conformance**

Run: `python -c "from bluestar.persistence.s3_backend import S3FileStore; from bluestar.core.protocols import IFileStore; print(isinstance(S3FileStore('bucket'), IFileStore))"`
Expected: `True`

**Step 6: Commit**

```bash
git add src/bluestar/persistence/s3_backend.py tests/unit/persistence/test_s3_backend.py
git commit -m "feat: implement S3FileStore with pagination and error wrapping"
```

---

## Task 4: Implement `DynamoDBRulesStore`

This is the largest task. The store has 8 methods, each querying a different DynamoDB table. The `get_calculation_rule` method implements CLIENT→GLOBAL fallback with optional Redis caching.

**Files:**
- Modify: `src/bluestar/persistence/dynamodb_backend.py`
- Create: `tests/unit/persistence/test_dynamodb_backend.py`

**Step 1: Write the failing tests**

Create `tests/unit/persistence/test_dynamodb_backend.py`:

```python
"""Unit tests for DynamoDBRulesStore using moto."""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

import boto3
import pytest
from moto import mock_aws

from bluestar.core.exceptions import RuleNotFoundError
from bluestar.persistence.dynamodb_backend import DynamoDBRulesStore
from bluestar.persistence.memory_backend import MemoryCacheBackend

TABLE_SUFFIX = "-test"
REGION = "us-east-1"

# ---------- helpers ----------

def _create_table(client, name: str, pk: str = "PK", sk: str = "SK"):
    """Create a DynamoDB table with PK/SK key schema."""
    client.create_table(
        TableName=name,
        KeySchema=[
            {"AttributeName": pk, "KeyType": "HASH"},
            {"AttributeName": sk, "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": pk, "AttributeType": "S"},
            {"AttributeName": sk, "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )


def _put(table, item: dict[str, Any]):
    table.put_item(Item=item)


# ---------- fixtures ----------

@pytest.fixture
def aws():
    with mock_aws():
        ddb = boto3.resource("dynamodb", region_name=REGION)
        client = boto3.client("dynamodb", region_name=REGION)

        table_names = [
            "bluestar-processing-pipeline",
            "bluestar-validation-rules",
            "bluestar-calculation-rules",
            "bluestar-irs-limits",
            "bluestar-batch-state",
            "bluestar-agent-config",
        ]

        for name in table_names:
            _create_table(client, f"{name}{TABLE_SUFFIX}")

        yield ddb


@pytest.fixture
def store(aws):
    return DynamoDBRulesStore(table_suffix=TABLE_SUFFIX, region=REGION)


@pytest.fixture
def cached_store(aws):
    cache = MemoryCacheBackend()
    return DynamoDBRulesStore(table_suffix=TABLE_SUFFIX, region=REGION, cache=cache), cache


# ---------- get_pipeline_steps ----------

class TestGetPipelineSteps:
    def test_returns_sorted_steps(self, store, aws):
        tbl = aws.Table(f"bluestar-processing-pipeline{TABLE_SUFFIX}")
        _put(tbl, {"PK": "CLIENT#ACME_BiWeeklyFri", "SK": "STEP#0200", "stepOrder": 200, "subroutineName": "FILE_VALIDATION", "agent": "VALIDATOR", "enabled": True, "required": True})
        _put(tbl, {"PK": "CLIENT#ACME_BiWeeklyFri", "SK": "STEP#0100", "stepOrder": 100, "subroutineName": "FILE_INGEST", "agent": "IDP", "enabled": True, "required": True})

        steps = store.get_pipeline_steps("ACME", "BiWeeklyFri")
        assert len(steps) == 2
        assert steps[0]["stepOrder"] == 100
        assert steps[1]["stepOrder"] == 200

    def test_returns_empty_for_unknown_plan(self, store):
        assert store.get_pipeline_steps("NOBODY", "Weekly") == []


# ---------- get_validation_rules ----------

class TestGetValidationRules:
    def test_returns_rules_for_category(self, store, aws):
        tbl = aws.Table(f"bluestar-validation-rules{TABLE_SUFFIX}")
        _put(tbl, {"PK": "CATEGORY#SSN", "SK": "RULE#001", "field": "ssn", "pattern": r"^\d{9}$"})
        _put(tbl, {"PK": "CATEGORY#SSN", "SK": "RULE#002", "field": "ssn", "check": "not_blank"})

        rules = store.get_validation_rules("SSN")
        assert len(rules) == 2

    def test_returns_empty_for_unknown_category(self, store):
        assert store.get_validation_rules("UNKNOWN") == []


# ---------- get_calculation_rule ----------

class TestGetCalculationRule:
    def test_returns_client_specific_rule(self, store, aws):
        tbl = aws.Table(f"bluestar-calculation-rules{TABLE_SUFFIX}")
        _put(tbl, {"PK": "CLIENT#ACME", "SK": "CALC#match", "formula": "ee_pct * comp", "max_pct": Decimal("6")})

        rule = store.get_calculation_rule("ACME", "match")
        assert rule["formula"] == "ee_pct * comp"

    def test_falls_back_to_global(self, store, aws):
        tbl = aws.Table(f"bluestar-calculation-rules{TABLE_SUFFIX}")
        _put(tbl, {"PK": "CLIENT#GLOBAL", "SK": "CALC#match", "formula": "default_match"})

        rule = store.get_calculation_rule("NEWCLIENT", "match")
        assert rule["formula"] == "default_match"

    def test_raises_when_no_rule_exists(self, store):
        with pytest.raises(RuleNotFoundError):
            store.get_calculation_rule("GHOST", "nonexistent")

    def test_caches_result_on_hit(self, cached_store, aws):
        store, cache = cached_store
        tbl = aws.Table(f"bluestar-calculation-rules{TABLE_SUFFIX}")
        _put(tbl, {"PK": "CLIENT#ACME", "SK": "CALC#match", "formula": "cached_formula"})

        store.get_calculation_rule("ACME", "match")
        cached_val = cache.get("calc_rule:ACME:match")
        assert cached_val is not None
        assert "cached_formula" in cached_val


# ---------- get_irs_limits ----------

class TestGetIrsLimits:
    def test_returns_limits_for_year(self, store, aws):
        tbl = aws.Table(f"bluestar-irs-limits{TABLE_SUFFIX}")
        _put(tbl, {"PK": "YEAR#2024", "SK": "LIMITS", "max_401k": Decimal("23000"), "catch_up": Decimal("7500")})

        limits = store.get_irs_limits(2024)
        assert limits["max_401k"] == 23000

    def test_returns_empty_for_unknown_year(self, store):
        assert store.get_irs_limits(1999) == {}


# ---------- get_client_config ----------

class TestGetClientConfig:
    def test_returns_config(self, store, aws):
        tbl = aws.Table(f"bluestar-agent-config{TABLE_SUFFIX}")
        _put(tbl, {"PK": "CLIENT#ACME_BiWeeklyFri", "SK": "CONFIG", "custodian": "Fidelity", "deadline_hour": 16})

        config = store.get_client_config("ACME", "BiWeeklyFri")
        assert config["custodian"] == "Fidelity"

    def test_returns_empty_for_unknown_client(self, store):
        assert store.get_client_config("NOBODY", "Weekly") == {}


# ---------- get_ach_config ----------

class TestGetAchConfig:
    def test_returns_ach_config(self, store, aws):
        tbl = aws.Table(f"bluestar-agent-config{TABLE_SUFFIX}")
        _put(tbl, {"PK": "CLIENT#ACME_BiWeeklyFri", "SK": "ACH", "ach_method": "NACHA", "bank_id": "BK001"})

        config = store.get_ach_config("ACME", "BiWeeklyFri")
        assert config["ach_method"] == "NACHA"

    def test_returns_empty_for_missing(self, store):
        assert store.get_ach_config("NOBODY", "Weekly") == {}


# ---------- get_vendor_schema ----------

class TestGetVendorSchema:
    def test_returns_schema(self, store, aws):
        tbl = aws.Table(f"bluestar-validation-rules{TABLE_SUFFIX}")
        _put(tbl, {"PK": "VENDOR#ADP_ACME_BiWeeklyFri", "SK": "SCHEMA", "columns": ["ssn", "name", "comp"]})

        schema = store.get_vendor_schema("ADP", "ACME", "BiWeeklyFri")
        assert "ssn" in schema["columns"]

    def test_returns_empty_for_missing(self, store):
        assert store.get_vendor_schema("UNKNOWN", "X", "Y") == {}


# ---------- get_plan_holds ----------

class TestGetPlanHolds:
    def test_returns_holds(self, store, aws):
        tbl = aws.Table(f"bluestar-batch-state{TABLE_SUFFIX}")
        _put(tbl, {"PK": "PLAN#ACME", "SK": "HOLD#001", "reason": "Missing data", "created": "2024-01-15"})

        holds = store.get_plan_holds("ACME")
        assert len(holds) == 1
        assert holds[0]["reason"] == "Missing data"

    def test_returns_empty_for_no_holds(self, store):
        assert store.get_plan_holds("CLEAN_PLAN") == []
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/persistence/test_dynamodb_backend.py -v`
Expected: FAIL — `NotImplementedError`

**Step 3: Implement DynamoDBRulesStore**

Replace contents of `src/bluestar/persistence/dynamodb_backend.py`:

```python
"""DynamoDB backend implementing IRulesStore with Redis caching."""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

import boto3

from bluestar.core.exceptions import RuleNotFoundError


class _DecimalEncoder(json.JSONEncoder):
    """Encode Decimal values as int or float for JSON serialization."""

    def default(self, o: Any) -> Any:
        if isinstance(o, Decimal):
            return int(o) if o == int(o) else float(o)
        return super().default(o)


def _decode_decimals(item: dict[str, Any]) -> dict[str, Any]:
    """Convert Decimal values in a DynamoDB item to int/float."""
    out: dict[str, Any] = {}
    for k, v in item.items():
        if isinstance(v, Decimal):
            out[k] = int(v) if v == int(v) else float(v)
        elif isinstance(v, dict):
            out[k] = _decode_decimals(v)
        elif isinstance(v, list):
            out[k] = [
                _decode_decimals(i) if isinstance(i, dict)
                else (int(i) if isinstance(i, Decimal) and i == int(i) else float(i) if isinstance(i, Decimal) else i)
                for i in v
            ]
        else:
            out[k] = v
    return out


class DynamoDBRulesStore:
    """Production IRulesStore backed by DynamoDB + optional Redis cache."""

    CACHE_TTL = 300  # 5 minutes

    def __init__(self, table_suffix: str = "", region: str = "us-east-1",
                 endpoint_url: str | None = None, cache: Any = None) -> None:
        self._table_suffix = table_suffix
        self._region = region
        self._endpoint_url = endpoint_url
        self._cache = cache
        kwargs: dict = {"region_name": region}
        if endpoint_url:
            kwargs["endpoint_url"] = endpoint_url
        self._ddb = boto3.resource("dynamodb", **kwargs)

    def _table(self, base: str):
        return self._ddb.Table(f"{base}{self._table_suffix}")

    def _query_pk(self, table_base: str, pk: str) -> list[dict[str, Any]]:
        """Query all items with a given partition key."""
        tbl = self._table(table_base)
        resp = tbl.query(
            KeyConditionExpression="PK = :pk",
            ExpressionAttributeValues={":pk": pk},
        )
        return [_decode_decimals(item) for item in resp.get("Items", [])]

    def _get_item(self, table_base: str, pk: str, sk: str) -> dict[str, Any] | None:
        """Get a single item by PK + SK. Returns None if not found."""
        tbl = self._table(table_base)
        resp = tbl.get_item(Key={"PK": pk, "SK": sk})
        item = resp.get("Item")
        return _decode_decimals(item) if item else None

    # ---- IRulesStore methods ----

    def get_client_config(self, plan_id: str, pay_freq: str) -> dict[str, Any]:
        item = self._get_item("bluestar-agent-config", f"CLIENT#{plan_id}_{pay_freq}", "CONFIG")
        return item or {}

    def get_validation_rules(self, category: str) -> list[dict[str, Any]]:
        return self._query_pk("bluestar-validation-rules", f"CATEGORY#{category}")

    def get_calculation_rule(self, plan_id: str, calc_type: str) -> dict[str, Any]:
        cache_key = f"calc_rule:{plan_id}:{calc_type}"

        # Check cache first
        if self._cache is not None:
            cached = self._cache.get(cache_key)
            if cached is not None:
                return json.loads(cached)

        # Try client-specific rule
        item = self._get_item("bluestar-calculation-rules", f"CLIENT#{plan_id}", f"CALC#{calc_type}")

        # Fallback to GLOBAL
        if item is None:
            item = self._get_item("bluestar-calculation-rules", "CLIENT#GLOBAL", f"CALC#{calc_type}")

        if item is None:
            raise RuleNotFoundError(
                f"No calculation rule for plan_id={plan_id!r}, calc_type={calc_type!r}"
            )

        # Write to cache
        if self._cache is not None:
            self._cache.setex(cache_key, self.CACHE_TTL, json.dumps(item, cls=_DecimalEncoder))

        return item

    def get_pipeline_steps(self, plan_id: str, pay_freq: str) -> list[dict[str, Any]]:
        items = self._query_pk("bluestar-processing-pipeline", f"CLIENT#{plan_id}_{pay_freq}")
        return sorted(items, key=lambda x: x.get("stepOrder", 0))

    def get_plan_holds(self, plan_id: str) -> list[dict[str, Any]]:
        return self._query_pk("bluestar-batch-state", f"PLAN#{plan_id}")

    def get_irs_limits(self, year: int) -> dict[str, Any]:
        item = self._get_item("bluestar-irs-limits", f"YEAR#{year}", "LIMITS")
        return item or {}

    def get_ach_config(self, plan_id: str, pay_freq: str) -> dict[str, Any]:
        item = self._get_item("bluestar-agent-config", f"CLIENT#{plan_id}_{pay_freq}", "ACH")
        return item or {}

    def get_vendor_schema(self, vendor_id: str, plan_id: str, pay_freq: str) -> dict[str, Any]:
        item = self._get_item(
            "bluestar-validation-rules", f"VENDOR#{vendor_id}_{plan_id}_{pay_freq}", "SCHEMA"
        )
        return item or {}
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/persistence/test_dynamodb_backend.py -v`
Expected: All 16 tests PASS

**Step 5: Verify protocol conformance**

Run: `python -c "from bluestar.persistence.dynamodb_backend import DynamoDBRulesStore; from bluestar.core.protocols import IRulesStore; print(isinstance(DynamoDBRulesStore(), IRulesStore))"`
Expected: `True`

**Step 6: Commit**

```bash
git add src/bluestar/persistence/dynamodb_backend.py tests/unit/persistence/test_dynamodb_backend.py
git commit -m "feat: implement DynamoDBRulesStore with CLIENT->GLOBAL fallback and caching"
```

---

## Task 5: Implement seed script

**Files:**
- Modify: `scripts/seed_dynamodb.py`
- Create: `tests/unit/test_seed_dynamodb.py`

**Step 1: Write the failing test**

Create `tests/unit/test_seed_dynamodb.py`:

```python
"""Tests for DynamoDB seed script."""

from __future__ import annotations

import sys
from pathlib import Path

import boto3
import pytest
from moto import mock_aws

# Make scripts/ importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "scripts"))

from seed_dynamodb import create_tables, seed_pipeline_data, TABLE_DEFINITIONS  # noqa: E402


@pytest.fixture
def ddb():
    with mock_aws():
        yield boto3.resource("dynamodb", region_name="us-east-1")


class TestCreateTables:
    def test_creates_all_eight_tables(self, ddb):
        create_tables(ddb, suffix="-test")
        client = boto3.client("dynamodb", region_name="us-east-1")
        tables = client.list_tables()["TableNames"]
        assert len(tables) == 8
        assert "bluestar-processing-pipeline-test" in tables

    def test_idempotent_skips_existing(self, ddb):
        create_tables(ddb, suffix="-test")
        create_tables(ddb, suffix="-test")  # should not raise
        client = boto3.client("dynamodb", region_name="us-east-1")
        assert len(client.list_tables()["TableNames"]) == 8


class TestSeedPipelineData:
    def test_seeds_26_pipeline_steps(self, ddb):
        create_tables(ddb, suffix="-test")
        seed_pipeline_data(ddb, suffix="-test")
        tbl = ddb.Table("bluestar-processing-pipeline-test")
        resp = tbl.scan()
        assert resp["Count"] == 26

    def test_seeds_sample_validation_rules(self, ddb):
        create_tables(ddb, suffix="-test")
        seed_pipeline_data(ddb, suffix="-test")
        tbl = ddb.Table("bluestar-validation-rules-test")
        resp = tbl.scan()
        assert resp["Count"] > 0

    def test_seeds_global_calc_rules(self, ddb):
        create_tables(ddb, suffix="-test")
        seed_pipeline_data(ddb, suffix="-test")
        tbl = ddb.Table("bluestar-calculation-rules-test")
        resp = tbl.scan()
        items = resp["Items"]
        global_items = [i for i in items if i["PK"].startswith("CLIENT#GLOBAL")]
        assert len(global_items) > 0

    def test_seeds_irs_limits(self, ddb):
        create_tables(ddb, suffix="-test")
        seed_pipeline_data(ddb, suffix="-test")
        tbl = ddb.Table("bluestar-irs-limits-test")
        resp = tbl.scan()
        assert resp["Count"] > 0
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_seed_dynamodb.py -v`
Expected: FAIL — `ImportError` (functions not defined yet)

**Step 3: Implement the seed script**

Replace contents of `scripts/seed_dynamodb.py`:

```python
"""Seed DynamoDB tables with default pipeline and rule configurations.

Usage:
    python scripts/seed_dynamodb.py --endpoint-url http://localhost:4566
"""

from __future__ import annotations

import argparse
import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import boto3

TABLE_DEFINITIONS: list[dict[str, Any]] = [
    {"name": "bluestar-processing-pipeline"},
    {"name": "bluestar-validation-rules"},
    {"name": "bluestar-calculation-rules"},
    {"name": "bluestar-irs-limits"},
    {"name": "bluestar-batch-state"},
    {"name": "bluestar-processing-results"},
    {"name": "bluestar-audit-log"},
    {"name": "bluestar-agent-config"},
]


def create_tables(ddb: Any, suffix: str = "") -> None:
    """Create all 8 DynamoDB tables. Skips if table already exists."""
    client = ddb.meta.client
    existing = client.list_tables().get("TableNames", [])

    for defn in TABLE_DEFINITIONS:
        table_name = f"{defn['name']}{suffix}"
        if table_name in existing:
            print(f"  Table {table_name} already exists, skipping")
            continue
        client.create_table(
            TableName=table_name,
            KeySchema=[
                {"AttributeName": "PK", "KeyType": "HASH"},
                {"AttributeName": "SK", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "PK", "AttributeType": "S"},
                {"AttributeName": "SK", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        print(f"  Created table {table_name}")


def _json_to_dynamodb(obj: Any) -> Any:
    """Convert JSON-parsed floats/ints to Decimal for DynamoDB."""
    if isinstance(obj, float):
        return Decimal(str(obj))
    if isinstance(obj, dict):
        return {k: _json_to_dynamodb(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_json_to_dynamodb(i) for i in obj]
    return obj


def seed_pipeline_data(ddb: Any, suffix: str = "") -> None:
    """Load pipeline_seed.json and seed sample rules/limits."""
    seed_path = Path(__file__).resolve().parent.parent / "config" / "pipeline_seed.json"
    data = json.loads(seed_path.read_text())

    # -- Pipeline steps --
    tbl = ddb.Table(f"bluestar-processing-pipeline{suffix}")
    with tbl.batch_writer() as batch:
        for step in data["steps"]:
            batch.put_item(Item=_json_to_dynamodb(step))
    print(f"  Seeded {len(data['steps'])} pipeline steps")

    # -- Sample validation rules --
    tbl = ddb.Table(f"bluestar-validation-rules{suffix}")
    sample_rules = [
        {"PK": "CATEGORY#SSN", "SK": "RULE#001", "field": "ssn", "pattern": r"^\d{9}$", "message": "SSN must be 9 digits"},
        {"PK": "CATEGORY#SSN", "SK": "RULE#002", "field": "ssn", "check": "not_blank", "message": "SSN is required"},
        {"PK": "CATEGORY#NAME", "SK": "RULE#001", "field": "last_name", "check": "not_blank", "message": "Last name is required"},
        {"PK": "CATEGORY#COMP", "SK": "RULE#001", "field": "compensation", "check": "positive_number", "message": "Compensation must be positive"},
    ]
    with tbl.batch_writer() as batch:
        for rule in sample_rules:
            batch.put_item(Item=rule)
    print(f"  Seeded {len(sample_rules)} validation rules")

    # -- GLOBAL calculation rules --
    tbl = ddb.Table(f"bluestar-calculation-rules{suffix}")
    global_rules = [
        {"PK": "CLIENT#GLOBAL", "SK": "CALC#match", "formula": "ee_deferral_pct * compensation", "max_pct": Decimal("6"), "description": "Default employer match"},
        {"PK": "CLIENT#GLOBAL", "SK": "CALC#er_contrib", "formula": "compensation * er_pct", "max_pct": Decimal("3"), "description": "Default ER contribution"},
        {"PK": "CLIENT#GLOBAL", "SK": "CALC#catch_up", "formula": "min(excess, irs_catch_up_limit)", "age_threshold": 50, "description": "Catch-up contribution calc"},
    ]
    with tbl.batch_writer() as batch:
        for rule in global_rules:
            batch.put_item(Item=rule)
    print(f"  Seeded {len(global_rules)} GLOBAL calculation rules")

    # -- IRS limits --
    tbl = ddb.Table(f"bluestar-irs-limits{suffix}")
    irs_data = [
        {"PK": "YEAR#2024", "SK": "LIMITS", "max_401k": Decimal("23000"), "catch_up": Decimal("7500"), "comp_limit": Decimal("345000"), "annual_addition": Decimal("69000")},
        {"PK": "YEAR#2025", "SK": "LIMITS", "max_401k": Decimal("23500"), "catch_up": Decimal("7500"), "comp_limit": Decimal("350000"), "annual_addition": Decimal("70000")},
    ]
    with tbl.batch_writer() as batch:
        for item in irs_data:
            batch.put_item(Item=item)
    print(f"  Seeded IRS limits for {len(irs_data)} years")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed DynamoDB tables for BlueStar")
    parser.add_argument("--endpoint-url", default=None, help="DynamoDB endpoint (e.g. http://localhost:4566)")
    parser.add_argument("--table-suffix", default="", help="Table name suffix (e.g. -dev)")
    parser.add_argument("--region", default="us-east-1", help="AWS region")
    args = parser.parse_args()

    kwargs: dict[str, Any] = {"region_name": args.region}
    if args.endpoint_url:
        kwargs["endpoint_url"] = args.endpoint_url

    ddb = boto3.resource("dynamodb", **kwargs)

    print("Creating tables...")
    create_tables(ddb, suffix=args.table_suffix)

    print("Seeding data...")
    seed_pipeline_data(ddb, suffix=args.table_suffix)

    print("Done!")


if __name__ == "__main__":
    main()
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_seed_dynamodb.py -v`
Expected: All 6 tests PASS

**Step 5: Commit**

```bash
git add scripts/seed_dynamodb.py tests/unit/test_seed_dynamodb.py
git commit -m "feat: implement DynamoDB seed script with 8 tables and sample data"
```

---

## Task 6: Wire up `persistence/__init__.py` factory

**Files:**
- Modify: `src/bluestar/persistence/__init__.py`

**Step 1: Implement the factory function**

Replace contents of `src/bluestar/persistence/__init__.py`:

```python
"""Pluggable persistence backends behind Protocol interfaces."""

from __future__ import annotations

from bluestar.core.config import AppSettings
from bluestar.persistence.dynamodb_backend import DynamoDBRulesStore
from bluestar.persistence.redis_backend import RedisCacheBackend
from bluestar.persistence.s3_backend import S3FileStore


def create_persistence(settings: AppSettings | None = None):
    """Create wired-up persistence backends from application settings.

    Returns:
        Tuple of (rules_store, cache, file_store).
    """
    if settings is None:
        settings = AppSettings()

    cache = RedisCacheBackend(
        host=settings.redis.host,
        port=settings.redis.port,
        db=settings.redis.db,
    )

    rules_store = DynamoDBRulesStore(
        table_suffix=settings.dynamodb.table_suffix,
        region=settings.dynamodb.region,
        endpoint_url=settings.dynamodb.endpoint_url,
        cache=cache,
    )

    file_store = S3FileStore(
        bucket=settings.s3.bucket,
        region=settings.s3.region,
        endpoint_url=settings.s3.endpoint_url,
    )

    return rules_store, cache, file_store
```

**Step 2: Commit**

```bash
git add src/bluestar/persistence/__init__.py
git commit -m "feat: add create_persistence() factory wiring backends to config"
```

---

## Task 7: Integration test fixtures (LocalStack)

**Files:**
- Modify: `tests/integration/conftest.py`
- Create: `tests/integration/persistence/__init__.py`
- Create: `tests/integration/persistence/test_dynamodb_backend.py`

**Step 1: Implement integration conftest**

Replace contents of `tests/integration/conftest.py`:

```python
"""Integration test fixtures — LocalStack DynamoDB, Redis, S3."""

from __future__ import annotations

import os
import sys

import boto3
import pytest

# Default LocalStack endpoint
LOCALSTACK_URL = os.environ.get("LOCALSTACK_URL", "http://localhost:4566")
TABLE_SUFFIX = "-inttest"


def _localstack_available() -> bool:
    """Check if LocalStack is reachable."""
    try:
        client = boto3.client("dynamodb", region_name="us-east-1", endpoint_url=LOCALSTACK_URL)
        client.list_tables()
        return True
    except Exception:
        return False


skip_no_localstack = pytest.mark.skipif(
    not _localstack_available(),
    reason="LocalStack not available",
)


@pytest.fixture(scope="session")
def localstack_ddb():
    """DynamoDB resource pointing at LocalStack."""
    return boto3.resource("dynamodb", region_name="us-east-1", endpoint_url=LOCALSTACK_URL)


@pytest.fixture(scope="session")
def localstack_s3():
    """S3 client pointing at LocalStack."""
    return boto3.client("s3", region_name="us-east-1", endpoint_url=LOCALSTACK_URL)


@pytest.fixture(scope="session")
def seeded_tables(localstack_ddb):
    """Create and seed DynamoDB tables via the seed script."""
    sys.path.insert(0, str(os.path.join(os.path.dirname(__file__), "..", "..", "scripts")))
    from seed_dynamodb import create_tables, seed_pipeline_data

    create_tables(localstack_ddb, suffix=TABLE_SUFFIX)
    seed_pipeline_data(localstack_ddb, suffix=TABLE_SUFFIX)
    return TABLE_SUFFIX
```

**Step 2: Create integration test**

Create `tests/integration/persistence/__init__.py` (empty file).

Create `tests/integration/persistence/test_dynamodb_backend.py`:

```python
"""Integration tests for DynamoDBRulesStore against LocalStack."""

from __future__ import annotations

import pytest

from bluestar.persistence.dynamodb_backend import DynamoDBRulesStore
from tests.integration.conftest import LOCALSTACK_URL, TABLE_SUFFIX, skip_no_localstack


@skip_no_localstack
class TestDynamoDBIntegration:
    @pytest.fixture
    def store(self, seeded_tables):
        return DynamoDBRulesStore(
            table_suffix=seeded_tables,
            region="us-east-1",
            endpoint_url=LOCALSTACK_URL,
        )

    def test_pipeline_steps_from_seed(self, store):
        steps = store.get_pipeline_steps("DEFAULT", "BiWeeklyFri")
        assert len(steps) == 26
        assert steps[0]["subroutineName"] == "FILE_INGEST"

    def test_global_calc_rule_exists(self, store):
        rule = store.get_calculation_rule("GLOBAL", "match")
        assert "formula" in rule

    def test_irs_limits_2024(self, store):
        limits = store.get_irs_limits(2024)
        assert limits["max_401k"] == 23000

    def test_validation_rules_ssn(self, store):
        rules = store.get_validation_rules("SSN")
        assert len(rules) >= 2
```

**Step 3: Commit**

```bash
git add tests/integration/
git commit -m "feat: add integration test fixtures and DynamoDB integration tests"
```

---

## Task 8: Run full test suite and verify

**Step 1: Run all unit tests**

Run: `pytest tests/unit/ -v --tb=short`
Expected: All tests PASS (existing config/payroll tests + new persistence tests)

**Step 2: Run linter**

Run: `ruff check src/bluestar/persistence/ scripts/seed_dynamodb.py tests/`
Expected: No errors (fix any issues found)

**Step 3: Final commit if any fixes needed**

```bash
git add -A
git commit -m "fix: address lint issues from persistence implementation"
```

(Only if Step 2 found issues)
