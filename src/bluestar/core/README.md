# `bluestar/core` — Foundation Layer

The contract layer that every other module depends on. Contains **zero business logic** — only types, protocols, configuration, and exceptions.

## Files

| File | Purpose |
|------|---------|
| `config.py` | Pydantic-Settings config loaded from `BLUESTAR_*` env vars |
| `protocols.py` | `runtime_checkable` Protocol interfaces for all backends |
| `types.py` | Type aliases (`BatchId`, `PlanId`, `PayFreq`, `SSN`, etc.) |
| `exceptions.py` | Hierarchical exception classes with context metadata |

## Configuration (`config.py`)

All settings are loaded from environment variables with the `BLUESTAR_` prefix:

```python
from bluestar.core.config import AppSettings

settings = AppSettings()  # reads from env
settings.dynamodb.region      # BLUESTAR_DYNAMO_REGION (default: us-east-1)
settings.redis.host           # BLUESTAR_REDIS_HOST (default: localhost)
settings.s3.bucket            # BLUESTAR_S3_BUCKET (default: bluestar-files-dev)
settings.llm.provider         # BLUESTAR_LLM_PROVIDER (default: mock)
```

Sub-configs: `LLMConfig`, `DynamoDBConfig`, `RedisConfig`, `S3Config`, `SQSConfig`, `SQLServerConfig`, `TokenServiceConfig`.

## Protocols (`protocols.py`)

Every backend implements one of these — agents depend on protocols, never concrete classes:

```
IModelProvider    — LLM abstraction (chat, structured_output)
IRulesStore       — DynamoDB business rules (8 getter methods)
ICacheBackend     — Redis interface (get, setex, delete)
IFileStore        — S3 abstraction (read, write, move, list_files)
ISQLClient        — SQL Server queries and stored procedures
ITokenService     — NACHA bank data resolution
IOrchestrator     — Pipeline dispatch
IWorkflowState    — Batch/step state tracking
```

Usage — check conformance at runtime:

```python
from bluestar.core.protocols import IRulesStore

assert isinstance(my_store, IRulesStore)  # structural check, no inheritance needed
```

## Exceptions (`exceptions.py`)

```
BlueStarError (base)
├── PipelineError
│   ├── StepFailedError      — includes step_order, subroutine, batch_id
│   └── DeadlineAtRiskError
├── EscalationRequired       — triggers human review
├── SchemaNotFoundError
├── RuleNotFoundError
├── CacheError
├── SQLServerError
└── TokenServiceError
```

## Adding New Protocols

1. Define in `protocols.py` with `@runtime_checkable`
2. Add type alias in `types.py` if needed
3. Add exception subclass in `exceptions.py` if the backend can fail
4. Implement in `persistence/` or `model_providers/`
