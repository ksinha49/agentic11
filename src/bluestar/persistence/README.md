# `bluestar/persistence` — Data Layer

Pluggable storage backends behind Protocol interfaces. Swap implementations between dev (in-memory), test (moto/fakeredis), and production (AWS services) without changing agent code.

## Backends

| File | Class | Protocol | Backing Service |
|------|-------|----------|-----------------|
| `dynamodb_backend.py` | `DynamoDBRulesStore` | `IRulesStore` | DynamoDB (8 tables) |
| `redis_backend.py` | `RedisCacheBackend` | `ICacheBackend` | Redis |
| `s3_backend.py` | `S3FileStore` | `IFileStore` | S3 |
| `memory_backend.py` | `Memory*` | All three | In-memory dicts (tests) |
| `sql_server.py` | — | `ISQLClient` | SQL Server (placeholder) |

## Quick Start

```python
from bluestar.persistence import create_persistence

rules_store, cache, file_store = create_persistence()  # reads AppSettings from env
```

Or construct individually:

```python
from bluestar.persistence.dynamodb_backend import DynamoDBRulesStore
from bluestar.persistence.redis_backend import RedisCacheBackend

cache = RedisCacheBackend(host="localhost", port=6379, db=0)
store = DynamoDBRulesStore(table_suffix="-dev", cache=cache)

steps = store.get_pipeline_steps("ACME", "BiWeeklyFri")
rule  = store.get_calculation_rule("ACME", "match")  # CLIENT→GLOBAL fallback
```

## DynamoDB Tables

All tables use `PK` (partition key) + `SK` (sort key):

| Table | PK Pattern | SK Pattern | Data |
|-------|-----------|------------|------|
| `bluestar-processing-pipeline` | `CLIENT#{planId}_{payFreq}` | `STEP#NNNN` | Pipeline step definitions |
| `bluestar-validation-rules` | `CATEGORY#{cat}` | `RULE#NNN` | Validation rules |
| `bluestar-calculation-rules` | `CLIENT#{planId\|GLOBAL}` | `CALC#{type}` | Match/ER formulas |
| `bluestar-irs-limits` | `YEAR#{yyyy}` | `LIMITS` | Annual IRS contribution limits |
| `bluestar-agent-config` | `CLIENT#{planId}_{payFreq}` | `CONFIG\|ACH` | Client/ACH configuration |
| `bluestar-vendor-schema-mapping` | `VENDOR#{id}` | `SCHEMA#{fingerprint}` | Vendor file schemas |
| `bluestar-batch-state` | `PLAN#{planId}` | `HOLD#*` | Plan holds |
| `bluestar-processing-metadata` | `BATCH#{batchId}` | `STATE` | Batch workflow state |

## Key Patterns

### CLIENT→GLOBAL Fallback (`get_calculation_rule`)

```
1. Query CLIENT#{plan_id} + CALC#{calc_type}
2. If not found → Query CLIENT#GLOBAL + CALC#{calc_type}
3. If still not found → raise RuleNotFoundError
```

### Read-Through Caching

```
1. Check Redis (key: calc_rule:{plan_id}:{calc_type})
2. Cache miss → Query DynamoDB
3. Write result to Redis (TTL: 300s)
```

### Decimal Handling

DynamoDB stores numbers as `Decimal`. The `_decode_decimals()` function recursively converts to `int`/`float`. The `_DecimalEncoder` handles the reverse for JSON serialization.

### Error Wrapping

- Redis errors → `CacheError`
- S3 errors → `BlueStarError`
- DynamoDB `ClientError` → `BlueStarError`

## Testing

```bash
# Unit tests (moto + fakeredis, no AWS needed)
pytest tests/unit/persistence/ -v

# Integration tests (requires LocalStack)
docker compose -f docker/docker-compose.yml up -d
pytest tests/integration/persistence/ -v
```

## Adding a New Backend

1. Create `new_backend.py` implementing the relevant Protocol
2. Add in-memory test double to `memory_backend.py`
3. Wire into `create_persistence()` in `__init__.py`
4. Add unit tests with moto/fakeredis/mocks
