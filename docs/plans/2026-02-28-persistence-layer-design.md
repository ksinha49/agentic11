# Phase 1: Persistence Layer Design

**Date:** 2026-02-28
**Status:** Approved
**Scope:** DynamoDB + Redis + S3 backends, seed script, tests

---

## Goal

Implement the three core persistence backends (`DynamoDBRulesStore`, `RedisCacheBackend`, `S3FileStore`) that all five agents depend on, plus a seed script to bootstrap DynamoDB tables with pipeline and rule data. This unblocks all downstream agent development.

## Architecture Decisions

### Protocol-Based Design (Already Established)

All backends implement protocols defined in `src/bluestar/core/protocols.py`:
- `IRulesStore` — 8 methods for DynamoDB rule/pipeline access
- `ICacheBackend` — get/setex/delete for Redis caching
- `IFileStore` — read/write/move/list_files for S3 storage

In-memory fakes in `memory_backend.py` serve as the behavioral reference.

### CLIENT→GLOBAL Fallback Pattern

`DynamoDBRulesStore.get_calculation_rule()` must implement the fallback:
1. Query with `CLIENT#{client_id}` partition key
2. If no result, query with `CLIENT#GLOBAL` partition key
3. Raise `RuleNotFoundError` if neither exists

This pattern is already demonstrated in `MemoryRulesStore`.

### 3-Tier Caching (Read-Through)

DynamoDB methods that accept an optional `ICacheBackend`:
1. Check Redis first (`cache.get(key)`)
2. On miss, query DynamoDB
3. Write result to Redis (`cache.setex(key, ttl, value)`)
4. Return result

### Table Naming Convention

All 8 DynamoDB tables use the pattern: `bluestar-{name}{suffix}`

Tables:
| Table | PK | SK | Purpose |
|-------|----|----|---------|
| bluestar-processing-pipeline | PK (e.g. `CLIENT#DEFAULT_BiWeeklyFri`) | SK (e.g. `STEP#0100`) | 26-step pipeline definitions |
| bluestar-validation-rules | PK | SK | Field-level validation rules |
| bluestar-calculation-rules | PK | SK | Pay calculation rules |
| bluestar-irs-limits | PK | SK | IRS tax limits by year |
| bluestar-batch-state | PK | SK | Batch processing state |
| bluestar-processing-results | PK | SK | Step-level processing results |
| bluestar-audit-log | PK | SK | Compliance audit trail |
| bluestar-agent-config | PK | SK | Agent runtime configuration |

## Components

### 1. `DynamoDBRulesStore` (`persistence/dynamodb_backend.py`)

**Constructor:** `table_suffix`, `region`, `endpoint_url`, `cache` (optional `ICacheBackend`)

**Methods to implement:**

| Method | Behavior |
|--------|----------|
| `get_pipeline(plan_id)` | Query pipeline table, return sorted steps |
| `get_validation_rules(client_id, field)` | CLIENT→GLOBAL fallback |
| `get_calculation_rule(client_id, rule_id)` | CLIENT→GLOBAL fallback with caching |
| `get_irs_limits(year)` | Direct lookup by year |
| `save_batch_state(batch_id, state)` | Put item to batch-state table |
| `get_batch_state(batch_id)` | Get item from batch-state table |
| `save_processing_result(batch_id, step, result)` | Put item to results table |
| `append_audit_entry(entry)` | Put item to audit-log table |

**Key implementation details:**
- Use `boto3.resource("dynamodb")` for cleaner API
- JSON serialize/deserialize Decimal types (DynamoDB returns Decimal)
- Wrap boto3 errors in `BlueStarError` subclasses
- Thread-safe: boto3 resources are thread-safe

### 2. `RedisCacheBackend` (`persistence/redis_backend.py`)

**Constructor:** `host`, `port`, `db`, `decode_responses`

**Methods:**

| Method | Behavior |
|--------|----------|
| `get(key)` | `redis.get(key)` → JSON deserialize, return `None` on miss |
| `setex(key, ttl, value)` | JSON serialize → `redis.setex(key, ttl, serialized)` |
| `delete(key)` | `redis.delete(key)` |

**Key implementation details:**
- Use `redis.Redis` client (sync)
- JSON serialize all values (DynamoDB items are dicts)
- Wrap `redis.RedisError` in `CacheError`
- Connection pooling via default Redis client behavior

### 3. `S3FileStore` (`persistence/s3_backend.py`)

**Constructor:** `bucket`, `region`, `endpoint_url`

**Methods:**

| Method | Behavior |
|--------|----------|
| `read(path)` | `s3.get_object()` → return bytes |
| `write(path, data)` | `s3.put_object()` with bytes or str |
| `move(src, dst)` | `s3.copy_object()` then `s3.delete_object()` |
| `list_files(prefix)` | `s3.list_objects_v2()` → return list of keys |

**Key implementation details:**
- Use `boto3.client("s3")` for lower-level control
- Wrap `ClientError` in `FileStoreError`
- Handle pagination in `list_files` with `ContinuationToken`

### 4. Seed Script (`scripts/seed_dynamodb.py`)

**Purpose:** Create 8 DynamoDB tables and seed initial data.

**Behavior:**
1. Parse CLI args: `--endpoint-url` (for LocalStack), `--table-suffix`
2. Create all 8 tables with correct key schemas and GSIs
3. Load `config/pipeline_seed.json` → batch-write to pipeline table
4. Seed sample validation rules, IRS limits, GLOBAL calculation rules
5. Idempotent: skip table creation if table already exists

### 5. `persistence/__init__.py`

Export a `create_persistence()` factory function that reads config and returns wired-up instances of all three backends.

## Testing Strategy

### Unit Tests (moto, no Docker)

- `tests/unit/persistence/test_dynamodb_backend.py`
  - Mock DynamoDB with `@moto.mock_aws`
  - Test all 8 methods including CLIENT→GLOBAL fallback
  - Test cache integration (mock ICacheBackend)
  - Test error handling (missing items, malformed data)

- `tests/unit/persistence/test_redis_backend.py`
  - Use `fakeredis` library for in-process Redis mock
  - Test get/setex/delete with JSON serialization
  - Test TTL expiry behavior
  - Test error wrapping

- `tests/unit/persistence/test_s3_backend.py`
  - Mock S3 with `@moto.mock_aws`
  - Test read/write/move/list_files
  - Test pagination in list_files
  - Test error handling (missing keys)

### Integration Tests (LocalStack, Docker)

- `tests/integration/persistence/test_dynamodb_backend.py`
  - Real DynamoDB operations against LocalStack
  - Seed script creates tables, tests verify data

- `tests/integration/conftest.py`
  - Pytest fixtures for LocalStack endpoints
  - Table creation/cleanup fixtures
  - Skip if Docker not available

## Dependencies

**New packages needed:**
- `moto[dynamodb,s3]` — AWS service mocking for unit tests
- `fakeredis` — Redis mocking for unit tests
- `redis` — Redis client (may already be in requirements)

## Success Criteria

1. All three backends pass their unit tests
2. `DynamoDBRulesStore` correctly implements CLIENT→GLOBAL fallback
3. Cache integration works (cache hit avoids DynamoDB query)
4. Seed script creates all 8 tables and loads pipeline data
5. Integration tests pass against LocalStack
6. All backends satisfy their Protocol contracts (type-check passes)
