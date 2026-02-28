# `tests/` — Test Suite

Two-tier testing strategy: fast unit tests with mocked AWS, and integration tests against LocalStack.

## Running Tests

```bash
# All unit tests (no AWS required, ~3s)
pytest tests/unit/ -v

# Integration tests (requires LocalStack)
docker compose -f docker/docker-compose.yml up -d
pytest tests/integration/ -v

# Specific backend
pytest tests/unit/persistence/test_dynamodb_backend.py -v

# With coverage
pytest tests/unit/ --cov=bluestar --cov-report=term-missing
```

## Directory Structure

```
tests/
├── unit/                          # Fast, isolated tests (moto + fakeredis)
│   ├── persistence/
│   │   ├── test_dynamodb_backend.py   # 18 tests — all IRulesStore methods
│   │   ├── test_redis_backend.py      # 7 tests — get/setex/delete + errors
│   │   └── test_s3_backend.py         # 8 tests — read/write/move/list + pagination
│   ├── test_config.py                 # Config defaults
│   ├── test_payroll_record.py         # CanonicalPayrollRecord properties
│   └── test_seed_dynamodb.py          # 6 tests — table creation + seeding
├── integration/                   # Requires LocalStack
│   ├── conftest.py                    # LocalStack fixtures, table seeding
│   └── persistence/
│       └── test_dynamodb_backend.py   # 4 tests — real DynamoDB queries
└── fakes/                         # Shared test doubles
    └── __init__.py
```

## Test Counts

| Suite | Tests | Time |
|-------|-------|------|
| Unit — DynamoDB | 18 | ~1s |
| Unit — S3 | 8 | ~1s |
| Unit — Redis | 7 | <1s |
| Unit — Seed script | 6 | <1s |
| Unit — Config/Models | 5 | <1s |
| Integration — DynamoDB | 4 | skipped without LocalStack |
| **Total** | **48** | **~3s** |

## Mocking Strategy

| Service | Unit Test Mock | Integration |
|---------|---------------|-------------|
| DynamoDB | `moto` (`@mock_aws`) | LocalStack |
| Redis | `fakeredis` (with `decode_responses=True`) | Real Redis in Docker |
| S3 | `moto` (`@mock_aws`) | LocalStack |

## Key Fixtures

### Unit Tests

```python
# DynamoDB — creates tables in moto
@pytest.fixture
def aws():
    with mock_aws():
        ddb = boto3.resource("dynamodb", region_name="us-east-1")
        # ... create tables ...
        yield ddb

# Redis — patches redis.Redis with fakeredis
@pytest.fixture
def backend(fake_server):
    with patch("redis.Redis", return_value=fakeredis.FakeRedis(
        server=fake_server, decode_responses=True
    )):
        return RedisCacheBackend(host="localhost", port=6379, db=0)
```

### Integration Tests (`conftest.py`)

```python
LOCALSTACK_URL = os.environ.get("LOCALSTACK_URL", "http://localhost:4566")

@pytest.fixture(scope="session")
def seeded_tables(localstack_ddb):
    create_tables(localstack_ddb, suffix="-inttest")
    seed_pipeline_data(localstack_ddb, suffix="-inttest")
    return "-inttest"
```

Integration tests auto-skip when LocalStack is unreachable.

## Writing New Tests

1. **Unit tests** go in `tests/unit/` — use moto/fakeredis, no network calls
2. **Integration tests** go in `tests/integration/` — require LocalStack, use `@skip_no_localstack`
3. Follow existing patterns: fixtures for setup, one assertion concept per test
4. Run `ruff check tests/` before committing
