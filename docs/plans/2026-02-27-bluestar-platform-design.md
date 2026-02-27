# BlueStar AI Payroll Processing Platform — Design Document

**Date:** 2026-02-27
**Status:** Approved
**Classification:** CONFIDENTIAL

---

## 1. Overview

Multi-agent AI platform replacing legacy Stata/Blue Prism payroll processing for BlueStar Retirement Services. 5 agents, 26 pipeline steps, 26 services, 8 DynamoDB tables.

### Key Decisions

| Decision | Choice |
|---|---|
| Structure | Monorepo, single `bluestar` Python package |
| Orchestration | Protocol-abstracted: SQS (local/test) + Strands Graph (prod) |
| SLM models | Mock provider (stage 1); llama-cpp-python in-process (stage 2) |
| Agentcore | Stage 2 |
| Data layer | Hybrid: Protocol + in-memory fakes (unit), LocalStack (integration) |
| Agent framework | Strands Agents SDK 1.x |
| Bedrock access | LiteLLM proxy (Orchestrator + Compliance agents only) |
| MCP servers | FastMCP (rules, SQL, S3) |
| Code style | Protocol-based, pydantic-settings, `from __future__ import annotations`, Python 3.12+ |

---

## 2. Directory Layout

```
bluestar/
├── pyproject.toml
├── src/bluestar/
│   ├── __init__.py
│   ├── core/
│   │   ├── config.py                    # AppSettings + per-group sub-configs
│   │   ├── types.py                     # Type aliases (BatchId, PlanId, JsonDict)
│   │   ├── exceptions.py                # Exception hierarchy
│   │   └── protocols.py                 # All Protocol interfaces
│   │
│   ├── models/
│   │   ├── payroll_record.py            # CanonicalPayrollRecord (60+ fields)
│   │   ├── pipeline.py                  # PipelineStep, BatchState, WorkflowState
│   │   ├── rules.py                     # ValidationRule, CalcRule, HoldRule
│   │   ├── schema_mapping.py            # VendorSchemaMapping, ColumnMapping
│   │   └── outputs.py                   # ACHRecord, XMLPayload, ExportFile
│   │
│   ├── persistence/
│   │   ├── protocols.py                 # IRulesStore, ICacheBackend, IFileStore
│   │   ├── dynamodb_backend.py          # Real DynamoDB (8 tables)
│   │   ├── redis_backend.py             # Real Redis with TTL patterns
│   │   ├── s3_backend.py               # S3 file operations
│   │   ├── memory_backend.py            # Dict-backed fakes for unit tests
│   │   └── sql_server.py               # ODBC connection pool to CapitalSG-64
│   │
│   ├── agents/
│   │   ├── base.py                      # BaseAgent with common wiring
│   │   ├── orchestrator/
│   │   │   ├── agent.py
│   │   │   ├── pipeline_executor.py
│   │   │   ├── workflow_state.py
│   │   │   ├── escalation.py
│   │   │   └── main.py
│   │   ├── idp/
│   │   │   ├── agent.py
│   │   │   ├── schema_matcher.py
│   │   │   ├── file_parser.py
│   │   │   ├── destring.py
│   │   │   └── main.py
│   │   ├── validator/
│   │   │   ├── agent.py
│   │   │   ├── ssn_validator.py
│   │   │   ├── date_cleaner.py
│   │   │   ├── employment_status.py
│   │   │   ├── issue_detector.py
│   │   │   ├── contrib_rate_check.py
│   │   │   └── main.py
│   │   ├── transform/
│   │   │   ├── agent.py
│   │   │   ├── compensation_calc.py
│   │   │   ├── match_calc.py
│   │   │   ├── er_contrib_calc.py
│   │   │   ├── duplicate_employee.py
│   │   │   ├── hours_estimation.py
│   │   │   ├── negative_payroll.py
│   │   │   ├── totals_by_plan.py
│   │   │   ├── xml_generator.py
│   │   │   ├── file_export.py
│   │   │   └── main.py
│   │   └── compliance/
│   │       ├── agent.py
│   │       ├── plan_hold.py
│   │       ├── forfeiture.py
│   │       ├── ach_prep.py
│   │       ├── ach_calc.py
│   │       ├── depwd_detail.py
│   │       ├── deadline_monitor.py
│   │       └── main.py
│   │
│   ├── skills/                          # Strands @tool functions
│   │   ├── rules_tools.py
│   │   ├── sql_tools.py
│   │   ├── s3_tools.py
│   │   └── pipeline_tools.py
│   │
│   ├── mcp_servers/
│   │   ├── rules_server.py             # FastMCP: DynamoDB rules engine
│   │   ├── sql_server.py               # FastMCP: SQL Server queries
│   │   └── file_server.py              # FastMCP: S3 file operations
│   │
│   ├── model_providers/
│   │   ├── protocols.py                # IModelProvider Protocol
│   │   ├── mock_provider.py            # MockSLM for local dev/tests
│   │   ├── in_process_slm.py           # llama-cpp-python (stage 2)
│   │   └── bedrock_provider.py         # LiteLLM → Bedrock wrapper
│   │
│   ├── orchestration/
│   │   ├── protocols.py                # IOrchestrator Protocol
│   │   ├── sqs_orchestrator.py         # SQS dispatch (local/test)
│   │   └── strands_orchestrator.py     # Strands GraphBuilder (prod)
│   │
│   └── api/
│       ├── app.py                      # FastAPI lifespan + router mounting
│       └── routes/
│           ├── health.py
│           └── admin.py
│
├── tests/
│   ├── unit/
│   │   ├── test_payroll_record.py
│   │   ├── test_ssn_validator.py
│   │   ├── test_date_cleaner.py
│   │   ├── test_match_calc.py
│   │   ├── test_hours_estimation.py
│   │   ├── test_negative_payroll.py
│   │   └── test_config.py
│   ├── integration/
│   │   ├── test_dynamodb_backend.py
│   │   ├── test_pipeline_execution.py
│   │   └── conftest.py                 # LocalStack fixtures
│   └── fakes/
│       ├── fake_dynamodb.py
│       ├── fake_redis.py
│       ├── fake_sql.py
│       └── fake_model.py
│
├── docker/
│   ├── Dockerfile
│   ├── Dockerfile.dev
│   ├── docker-compose.yml
│   └── docker-compose.dev.yml
│
├── config/
│   ├── litellm_config.yaml
│   └── pipeline_seed.json
│
├── scripts/
│   ├── seed_dynamodb.py
│   └── download_models.py
│
└── deploy/
    ├── ecs/
    └── cdk/
```

---

## 3. Core Protocols

```python
from __future__ import annotations
from typing import Any, Protocol, runtime_checkable, TypeVar

T = TypeVar("T")

@runtime_checkable
class IModelProvider(Protocol):
    def chat(self, messages: list[dict[str, str]], **kwargs: Any) -> str: ...
    def structured_output(self, messages: list[dict[str, str]], response_model: type[T]) -> T: ...

@runtime_checkable
class IRulesStore(Protocol):
    def get_client_config(self, plan_id: str, pay_freq: str) -> dict[str, Any]: ...
    def get_validation_rules(self, category: str) -> list[dict[str, Any]]: ...
    def get_calculation_rule(self, plan_id: str, calc_type: str) -> dict[str, Any]: ...
    def get_pipeline_steps(self, plan_id: str, pay_freq: str) -> list[dict[str, Any]]: ...
    def get_plan_holds(self, plan_id: str) -> list[dict[str, Any]]: ...
    def get_irs_limits(self, year: int) -> dict[str, Any]: ...

@runtime_checkable
class ICacheBackend(Protocol):
    def get(self, key: str) -> str | None: ...
    def setex(self, key: str, ttl: int, value: str) -> None: ...
    def delete(self, key: str) -> None: ...

@runtime_checkable
class IFileStore(Protocol):
    def read(self, path: str) -> bytes: ...
    def write(self, path: str, data: bytes) -> str: ...
    def move(self, src: str, dst: str) -> None: ...

@runtime_checkable
class IOrchestrator(Protocol):
    async def dispatch_step(self, batch_id: str, step: Any) -> Any: ...
    async def run_pipeline(self, batch_id: str, plan_id: str, pay_freq: str) -> Any: ...

@runtime_checkable
class ISQLClient(Protocol):
    def query(self, sql: str, params: tuple[Any, ...]) -> list[dict[str, Any]]: ...
    def execute_sp(self, sp_name: str, params: dict[str, Any]) -> dict[str, Any]: ...
```

---

## 4. Configuration

Pydantic-settings with grouped env prefixes per subsystem:

| Group | Env Prefix | Key Settings |
|---|---|---|
| LLM | `BLUESTAR_LLM_` | provider (mock/bedrock/in_process), model paths, LiteLLM URL |
| DynamoDB | `BLUESTAR_DYNAMO_` | table_suffix, region, endpoint_url (LocalStack) |
| Redis | `BLUESTAR_REDIS_` | host, port |
| SQL Server | `BLUESTAR_SQL_` | connection_string |
| App | `BLUESTAR_` | environment (dev/uat/prod) |

---

## 5. Agent Service Pattern

Each of the 26 services follows a consistent pattern:

1. Constructor takes Protocol dependencies (IRulesStore, ICacheBackend, ISQLClient)
2. `execute(records) -> records` — pure transform on canonical records
3. Rules loaded once per batch from DynamoDB → Redis cache → in-memory
4. Financial calculations are deterministic (no AI inference)

---

## 6. Model Provider Strategy

| Agent | Stage 1 | Stage 2 |
|---|---|---|
| Orchestrator | MockSLM | Bedrock Claude Sonnet (via LiteLLM) |
| Compliance | MockSLM | Bedrock Claude Sonnet (via LiteLLM) |
| IDP | MockSLM | In-process SmolLM3 3B + Bedrock escalation |
| Validator | MockSLM | In-process Arcee AFM 4.5B |
| Transform | MockSLM | In-process Phi-4 Mini 3.8B |

---

## 7. Data Layer

### DynamoDB Tables (8)

| Table | PK Pattern | Primary Consumer |
|---|---|---|
| bluestar-client-processing-config | CLIENT#{planId} | All agents |
| bluestar-vendor-schema-mapping | VENDOR#{vendorId} | IDP |
| bluestar-validation-rules | CATEGORY#{category} | Validator |
| bluestar-business-calculation-rules | CLIENT#{planId} or GLOBAL | Transform |
| bluestar-compliance-limits | YEAR#{year} | Transform |
| bluestar-plan-hold-rules | PLAN#{planId} | Compliance |
| bluestar-processing-pipeline | CLIENT#{planId}_{payFreq} | Orchestrator |
| bluestar-ach-configuration | PLAN#{planId} | Compliance |

### Redis Cache TTLs

| Pattern | TTL | Reason |
|---|---|---|
| schema:{vendorId}:{fingerprint} | 24 hrs | Schemas rarely change |
| rules:validation:{category} | 1 hr | Rule updates infrequent |
| rules:calc:{planId}:{calcType} | 1 hr | Same |
| config:{planId}:{payFreq} | 1 hr | Same |
| limits:{year} | 24 hrs | Annual limits |
| hold:{planId} | 15 min | Holds change intraday |
| pipeline:{planId}:{payFreq} | 1 hr | Pipeline config stable |
| session:{batchId}:state | 4 hrs | Active batch window |
| session:{batchId}:records | 4 hrs | Active batch window |

---

## 8. Deployment

- Single Docker image, per-agent entrypoints via ECS task definition CMD
- docker-compose.dev.yml: LocalStack (DynamoDB, SQS, S3, EventBridge) + Redis
- Stage 2: AWS Agentcore, CDK infrastructure, GGUF model baking into images

---

## 9. Pipeline Steps (26)

| Step | Subroutine | Agent | Required |
|---|---|---|---|
| 0100 | FILE_INGEST | IDP | Yes |
| 0200 | FILE_VALIDATION | Validator | Yes |
| 0300 | MERGE_PAYROLL_FIELDS | IDP | Yes |
| 0400 | DROP_V_VARIABLES | IDP | Yes |
| 0500 | DESTRING_NUMBERS | IDP | Yes |
| 0550 | SPLIT_MONTH_PEO | Transform | Yes |
| 0600 | CALC_COMPENSATION | Transform | Yes |
| 0700 | CALC_MATCH | Transform | Conditional |
| 0800 | CALC_ER_CONTRIB | Transform | Conditional |
| 0900 | BAD_SSN | Validator | Yes |
| 1000 | FORMAT_DATES_STRINGS | Validator | Yes |
| 1100 | EETYPE_CODING | Transform | Conditional |
| 1200 | EMPLOYMENT_STATUS | Validator | Yes |
| 1300 | DUPLICATE_EMPLOYEES | Transform | Yes |
| 1400 | DROP_OLD_TERMS | Transform | Yes |
| 1500 | FIX_HOURS | Transform | Yes |
| 1600 | ISSUE_DETECTION | Validator | Yes |
| 1700 | TOTALS_INCLNEG | Transform | Yes |
| 1800 | NEGATIVE_PAYROLL | Transform | Yes |
| 1900 | TOTALS_EXCLNEG | Transform | Yes |
| 2000 | PLAN_HOLD_CHECK | Compliance | Yes |
| 2100 | EXPORT_FILES | Transform | Yes |
| 2200 | FORFEITURES | Compliance | Yes |
| 2300 | GENERATE_XML | Transform | Yes |
| 2400 | DEPWD_DETAIL_UPDATE | Compliance | Yes |
| 2500 | ACH_PREP | Compliance | Yes |
| 2600 | ACH_CALC | Compliance | Yes |

---

## 10. NACHA Compliance

Bank account data (routing numbers, account numbers) NEVER enters AWS. The Compliance Agent's ACH services call the on-premises Token Service. Bank data is held in memory only during file generation, then discarded. Never written to Redis, DynamoDB, S3, or logs.
