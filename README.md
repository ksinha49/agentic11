# BlueStar AI Payroll Processing Platform

A multi-agent AI platform that replaces legacy Stata/Blue Prism payroll processing with five specialized agents, a 26-step pipeline, and rules-driven business logic stored in DynamoDB.

Built for **BlueStar Retirement Services** to process ~6,000 employee records per payroll cycle across multiple vendors and file formats.

---

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [The 5 Agents](#the-5-agents)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [Configuration](#configuration)
- [The 26-Step Pipeline](#the-26-step-pipeline)
- [Data Model](#data-model)
- [DynamoDB Tables](#dynamodb-tables)
- [Caching Strategy](#caching-strategy)
- [Model Serving Strategy](#model-serving-strategy)
- [API Endpoints](#api-endpoints)
- [Agent Skills (MCP Tools)](#agent-skills-mcp-tools)
- [Testing](#testing)
- [Deployment](#deployment)
- [Key Design Decisions](#key-design-decisions)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        FastAPI Gateway                          │
│                    (Health, Ready, Admin)                        │
└──────────────────────────┬──────────────────────────────────────┘
                           │
              ┌────────────▼────────────┐
              │     Orchestrator Agent   │
              │  (Claude Sonnet/Bedrock) │
              │  Pipeline Coordinator    │
              └──┬─────┬─────┬──────┬───┘
                 │     │     │      │
        ┌────────▼──┐ ┌▼─────▼──┐ ┌─▼──────────┐
        │ IDP Agent │ │Validator │ │ Transform   │
        │ SmolLM3 3B│ │Arcee 4.5B│ │ Phi-4 3.8B │
        │ File Parse│ │ SSN/Date │ │ Calcs/XML  │
        └───────────┘ └─────────┘ └────────────┘
                                        │
                              ┌─────────▼──────────┐
                              │ Compliance Agent    │
                              │ (Claude Sonnet)     │
                              │ ACH/Holds/Forfeit   │
                              └─────────────────────┘
                                        │
              ┌─────────────────────────┼─────────────────────┐
              │                         │                     │
        ┌─────▼─────┐          ┌───────▼────────┐    ┌──────▼───────┐
        │ DynamoDB   │          │   Redis Cache  │    │ S3 File Store│
        │ (8 tables) │          │  (L2 Cache)    │    │ (Payroll I/O)│
        └────────────┘          └────────────────┘    └──────────────┘
```

**Orchestration modes:**
- **Dev/Test:** SQS-based dispatch with per-agent queues
- **Production:** AWS Strands Graph with parallel step execution

---

## The 5 Agents

| Agent | Responsibility | Pipeline Steps | Model (Stage 2) |
|-------|---------------|----------------|-----------------|
| **Orchestrator** | Central coordinator, pipeline execution, state tracking, escalation routing | All (meta) | Claude Sonnet (Bedrock) |
| **IDP** | File parsing, schema detection, vendor mapping, destringing | 0100–0500 | SmolLM3 3B + Bedrock fallback |
| **Validator** | SSN checks, date cleaning, employment status, issue detection | 0900, 1000, 1200, 1600 | Arcee AFM 4.5B |
| **Transformation** | Compensation calcs, match calcs, ER contributions, XML generation, file export | 0550–2300 (non-validation) | Phi-4 Mini 3.8B (no AI for calcs) |
| **Compliance** | Plan holds, forfeitures, ACH generation, DepWDDetail, deadline monitoring | 2000–2600 | Claude Sonnet (Bedrock) |

---

## Tech Stack

| Category | Technology |
|----------|-----------|
| **Language** | Python 3.12+ |
| **Web Framework** | FastAPI 0.115 + Uvicorn 0.30 |
| **Agent Framework** | Strands Agents SDK 1.x (AWS native) |
| **LLM Proxy** | LiteLLM 1.50 (Bedrock) |
| **Configuration** | Pydantic 2.7 + Pydantic-Settings 2.3 |
| **Structured Output** | Instructor 1.14 |
| **AWS SDK** | boto3 1.35 (DynamoDB, S3, SQS, EventBridge) |
| **Cache** | Redis 5.2 |
| **SLM Inference** | llama-cpp-python 0.3.8 (in-process) |
| **MCP Servers** | FastMCP 3.0 |
| **Database** | SQL Server via pyodbc 5.2 (on-prem CapitalSG-64) |
| **Logging** | structlog 24.1 |
| **Testing** | pytest 8.0, pytest-asyncio 0.24, moto 5.0 |
| **Linting** | ruff 0.5, mypy 1.10 (strict) |

---

## Project Structure

```
bluestar/
├── src/bluestar/
│   ├── core/
│   │   ├── config.py              # Pydantic-Settings configuration
│   │   ├── protocols.py           # Protocol interfaces (structural typing)
│   │   └── types.py               # Type aliases (BatchId, PlanId, etc.)
│   ├── models/
│   │   └── payroll_record.py      # CanonicalPayrollRecord (60+ fields)
│   ├── agents/
│   │   ├── base.py                # BaseAgent with shared wiring
│   │   ├── orchestrator/          # Pipeline coordinator
│   │   ├── idp/                   # File parsing & schema detection
│   │   ├── validator/             # Data validation & SSN checks
│   │   ├── transform/             # Calculations & XML generation
│   │   └── compliance/            # ACH, holds, forfeitures
│   ├── persistence/
│   │   ├── dynamodb_backend.py    # IRulesStore implementation
│   │   ├── redis_backend.py       # ICacheBackend implementation
│   │   ├── s3_backend.py          # IFileStore implementation
│   │   ├── sql_server.py          # ISQLClient implementation
│   │   └── memory_backend.py      # In-memory fakes for tests
│   ├── skills/
│   │   ├── rules_tools.py         # DynamoDB rule queries
│   │   ├── sql_tools.py           # SQL Server queries
│   │   ├── s3_tools.py            # File operations
│   │   └── pipeline_tools.py      # Pipeline dispatch
│   └── api/
│       └── app.py                 # FastAPI application
├── tests/
│   ├── unit/                      # Unit tests (no AWS needed)
│   ├── integration/               # Integration tests (LocalStack)
│   └── fakes/                     # Test doubles
├── config/
│   └── litellm_config.yaml        # LiteLLM model routing
├── docker/
│   └── docker-compose.dev.yml     # LocalStack + Redis + API
├── deploy/
│   └── cdk/                       # AWS CDK infrastructure
├── scripts/
│   ├── seed_dynamodb.py           # Seed DynamoDB tables
│   └── download_models.py         # Download SLM model files
├── docs/
│   └── plans/                     # Design documents
└── General/Agent Artifacts/       # Skill definitions & references
```

---

## Getting Started

### Prerequisites

- Python 3.12+
- Docker & Docker Compose (for local development)

### Installation

```bash
# Clone the repository
git clone <repo-url>
cd agentic11

# Install with all optional dependencies
pip install -e ".[agents,mcp,slm,sql,dev]"
```

### Local Development

```bash
# 1. Start LocalStack (DynamoDB, S3, SQS) and Redis
docker-compose -f docker/docker-compose.dev.yml up -d

# 2. Seed DynamoDB tables with initial data
python scripts/seed_dynamodb.py --endpoint-url http://localhost:4566

# 3. (Optional, Stage 2) Download SLM model files
python scripts/download_models.py

# 4. Run the test suite
pytest tests/unit/ -v
pytest tests/integration/ -v --localstack

# 5. Start the FastAPI server
uvicorn bluestar.api.app:create_app --reload --port 8080
```

### Docker Compose Services

| Service | Port | Purpose |
|---------|------|---------|
| LocalStack | 4566 | DynamoDB, S3, SQS, EventBridge |
| Redis | 6379 | L2 Cache |
| bluestar-api | 8080 | FastAPI application |

---

## Configuration

Configuration uses Pydantic-Settings with grouped environment variable prefixes:

| Group | Env Prefix | Key Settings |
|-------|-----------|--------------|
| **App** | `BLUESTAR_` | `environment` (dev/uat/prod), `log_level` |
| **LLM** | `BLUESTAR_LLM_` | `provider` (mock/bedrock/in_process), model IDs, `slm_model_path`, `temperature` |
| **DynamoDB** | `BLUESTAR_DYNAMO_` | `table_suffix` (-dev/-uat/""), `region`, `endpoint_url` |
| **Redis** | `BLUESTAR_REDIS_` | `host`, `port`, `db` |
| **S3** | `BLUESTAR_S3_` | `bucket`, `region`, `endpoint_url` |
| **SQS** | `BLUESTAR_SQS_` | Per-agent queue URLs, `endpoint_url` |
| **SQL Server** | `BLUESTAR_SQL_` | `connection_string`, `pool_size`, `timeout` |
| **Token Service** | `BLUESTAR_TOKEN_` | `base_url` (on-prem), `timeout` |

### Example `.env` (Development)

```env
BLUESTAR_ENVIRONMENT=dev
BLUESTAR_LLM_PROVIDER=mock
BLUESTAR_DYNAMO_ENDPOINT_URL=http://localstack:4566
BLUESTAR_DYNAMO_TABLE_SUFFIX=-dev
BLUESTAR_REDIS_HOST=redis
BLUESTAR_REDIS_PORT=6379
BLUESTAR_S3_ENDPOINT_URL=http://localstack:4566
BLUESTAR_SQS_ENDPOINT_URL=http://localstack:4566
```

---

## The 26-Step Pipeline

Each step is defined in DynamoDB (`bluestar-processing-pipeline`) and executed by the Orchestrator:

| Step | Subroutine | Agent | Required | Description |
|------|-----------|-------|----------|-------------|
| 0100 | FILE_INGEST | IDP | Yes | Parse file into records |
| 0200 | FILE_VALIDATION | Validator | Yes | Validate file structure |
| 0300 | MERGE_PAYROLL_FIELDS | IDP | Yes | Add canonical fields |
| 0400 | DROP_V_VARIABLES | IDP | Yes | Remove excess columns |
| 0500 | DESTRING_NUMBERS | IDP | Yes | Convert strings to decimals |
| 0550 | SPLIT_MONTH_PEO | Transform | Yes | Handle multi-identifier PEO files |
| 0600 | CALC_COMPENSATION | Transform | Yes | Compute plancomp, matchcomp, ercomp |
| 0700 | CALC_MATCH | Transform | No | Two-tier employer match |
| 0800 | CALC_ER_CONTRIB | Transform | No | Flat-rate ER contributions |
| 0900 | BAD_SSN | Validator | Yes | SSN validation (7 checks) |
| 1000 | FORMAT_DATES_STRINGS | Validator | Yes | Date cleaning & formatting |
| 1100 | EETYPE_CODING | Transform | No | Employee type coding |
| 1200 | EMPLOYMENT_STATUS | Validator | Yes | DOH/DOT/DOR validation |
| 1300 | DUPLICATE_EMPLOYEES | Transform | Yes | Consolidate duplicate SSNs |
| 1400 | DROP_OLD_TERMS | Transform | Yes | Remove fully-terminated employees |
| 1500 | FIX_HOURS | Transform | Yes | Estimate/cap hours |
| 1600 | ISSUE_DETECTION | Validator | Yes | STOP + WARNING detection |
| 1700 | TOTALS_INCLNEG | Transform | Yes | Totals (including negatives) |
| 1800 | NEGATIVE_PAYROLL | Transform | Yes | Zero-floor negative contributions |
| 1900 | TOTALS_EXCLNEG | Transform | Yes | Totals (excluding negatives) |
| 2000 | PLAN_HOLD_CHECK | Compliance | Yes | Plan hold evaluation |
| 2100 | EXPORT_FILES | Transform | Yes | Export payroll files |
| 2200 | FORFEITURES | Compliance | Yes | Apply forfeiture offsets |
| 2300 | GENERATE_XML | Transform | Yes | Relius IMPORT_PAYROLL XML |
| 2400 | DEPWD_DETAIL_UPDATE | Compliance | Yes | Update DepWDDetail in PlanConnect |
| 2500 | ACH_PREP | Compliance | Yes | ACH request date calculation |
| 2600 | ACH_CALC | Compliance | Yes | NACHA-compliant ACH generation |

---

## Data Model

All agents operate on a single normalized **`CanonicalPayrollRecord`** schema with 60+ fields:

### Field Categories

| Category | Fields |
|----------|--------|
| **Identity** | `planid`, `clientid`, `ssn`, `planidfreq` |
| **Demographic** | `fname`, `lname`, `mname`, `dob`, `email`, `phone`, `gender`, `maritalstatus`, address fields |
| **Employment** | `doh` (hire), `dot` (termination), `dor` (rehire), `payfreq` (W/B/S/M/Q/A) |
| **Compensation** | `hours`, `salary`, `bonus`, `commissions`, `overtime`, `plancomp`, `matchcomp`, `ercomp` |
| **Contributions** (12 types) | `deferral`, `rothdeferral`, `match`, `shmatch`, `shmatchqaca`, `pshare`, `shne`, `shneqaca`, `loan`, `prevwageer`, `prevwageqnec`, `aftertax` |
| **Validation** | `badssn`, `issue`, `warning`, `eetype`, `eesubtype`, `planhold`, `planholdnote` |
| **Processing** | `identifier`, `batchid`, `grosscomp`, `annualcomp` |

---

## DynamoDB Tables

| Table | PK Pattern | SK Pattern | Purpose |
|-------|-----------|-----------|---------|
| `bluestar-client-processing-config` | `CLIENT#{planId}` | `CONFIG#{payFreq}#v{ver}` | Compensation formulas, match rules, PEO flags |
| `bluestar-vendor-schema-mapping` | `VENDOR#{vendorId}` | `SCHEMA#{planId}_{payFreq}#v{ver}` | Column mappings, fingerprints, destring config |
| `bluestar-validation-rules` | `CATEGORY#{category}` | `RULE#{ruleId}` | SSN validation, date cleaning, issue detection |
| `bluestar-business-calculation-rules` | `CLIENT#{planId}` / `GLOBAL` | `CALC#{calcType}#v{ver}` | Match formulas, ER rates, duplicate handling |
| `bluestar-compliance-limits` | `YEAR#{year}` | `LIMITS` | IRS contribution limits (401(a)(17), 415(c)) |
| `bluestar-plan-hold-rules` | `PLAN#{planId}` | `HOLD#{clientId}` | Plan holds (new client, amendment, frozen) |
| `bluestar-processing-pipeline` | `CLIENT#{planId}_{payFreq}` | `STEP#{stepOrder}` | 26-step pipeline definition |
| `bluestar-ach-configuration` | `PLAN#{planId}` | `ACH#{payFreq}#v{ver}` | ACH request dates, SEFA setup |

**Table suffix by environment:** `-dev` | `-uat` | (none for prod)

---

## Caching Strategy

Three-tier hierarchy: **In-memory -> Redis (L2) -> DynamoDB (L3)**

| Cache Key Pattern | TTL | Reason |
|-------------------|-----|--------|
| `schema:{vendorId}:{fingerprint}` | 24 hrs | Schemas rarely change |
| `rules:validation:{category}` | 1 hr | Rule updates infrequent |
| `rules:calc:{planId}:{calcType}` | 1 hr | Same |
| `config:{planId}:{payFreq}` | 1 hr | Same |
| `limits:{year}` | 24 hrs | Annual IRS limits |
| `hold:{planId}` | 15 min | Holds change intraday |
| `pipeline:{planId}:{payFreq}` | 1 hr | Pipeline config stable |
| `session:{batchId}:state` | 4 hrs | Active batch window |
| `session:{batchId}:records` | 4 hrs | Active batch window |

---

## Model Serving Strategy

### Stage 1 (Current)
- **MockModelProvider** — Returns canned responses for development and testing

### Stage 2 (Production)

| Provider | Models | Used By |
|----------|--------|---------|
| **Amazon Bedrock** (via LiteLLM) | Claude Sonnet, Claude Haiku | Orchestrator, Compliance, IDP escalation |
| **In-Process SLM** (llama-cpp-python) | SmolLM3 3B | IDP Agent |
| | Arcee AFM 4.5B | Validator Agent |
| | Phi-4 Mini 3.8B | Transform Agent (non-calc tasks only) |

> **Important:** The Transformation Agent uses **NO AI inference** for financial calculations. Every match and ER contribution amount is computed from explicit deterministic formulas. This is a regulatory requirement for auditability.

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check |
| `GET` | `/ready` | Readiness check (validates DynamoDB, Redis, SQS) |
| `POST` | `/admin/*` | Admin operations |

---

## Agent Skills (MCP Tools)

### Rules Tools (`rules_tools.py`)
- `get_client_config(plan_id, pay_freq)` — Client processing configuration
- `get_validation_rules(category)` — Validation rule sets
- `get_calculation_rule(plan_id, calc_type)` — Calc rules with CLIENT->GLOBAL fallback
- `get_irs_limits(year)` — IRS contribution limits
- `get_plan_holds(plan_id)` — Active plan holds
- `get_pipeline_steps(plan_id, pay_freq)` — Pipeline step definitions

### SQL Tools (`sql_tools.py`)
- Query SQL Server (CapitalSG-64 on-prem)
- Execute stored procedures (ERContribYTD, jobstatuscurrent, etc.)
- Load YTD contribution totals and eligibility data

### S3 Tools (`s3_tools.py`)
- Read/write files
- Move files between folders (dropzone -> inprogress -> validated/failed)
- List files by prefix

### Pipeline Tools (`pipeline_tools.py`)
- Dispatch steps to agent queues
- Track batch state
- Escalate to human review

---

## Testing

### Unit Tests (no AWS dependencies)

```bash
pytest tests/unit/ -v
```

Tests cover: payroll record validation, SSN checks, date cleaning, match calculations, hours estimation, negative payroll handling, configuration loading.

### Integration Tests (requires LocalStack)

```bash
pytest tests/integration/ -v --localstack
```

Tests cover: DynamoDB backend access, full 26-step pipeline execution.

### Test Fakes

All persistence layers have in-memory implementations (`tests/fakes/`) for fully reproducible testing without AWS:

- `fake_dynamodb.py` — Dict-backed rules store
- `fake_redis.py` — Dict-backed cache
- `fake_sql.py` — Dict-backed SQL client
- `fake_model.py` — Canned response model provider

---

## Deployment

### Local (Docker Compose)

```bash
docker-compose -f docker/docker-compose.dev.yml up
```

### Production (AWS CDK)

Infrastructure defined in `deploy/cdk/`:

| Service | Purpose |
|---------|---------|
| **ECS Fargate** | Per-agent task definitions |
| **DynamoDB** | 8 tables (rules, config, pipeline) |
| **ElastiCache Redis** | L2 cache cluster |
| **S3** | Payroll file storage |
| **SQS** | Agent step dispatch queues |
| **EventBridge** | Workflow triggers (file.received -> file.completed) |

---

## Key Design Decisions

### Rules as Data, Not Code
All business logic (validation rules, match formulas, plan holds) lives in DynamoDB. Changing a rule requires updating a DynamoDB item, not redeploying agent code.

### Client-Specific with GLOBAL Fallback
Calculation rules use two-level lookup: check `CLIENT#{planId}` first, fall back to `GLOBAL`. This enables per-client overrides without duplicating the entire rule set.

### Financial Calculations Are 100% Deterministic
No AI inference is used for contribution calculations. Every amount is computed from explicit formulas stored in DynamoDB. This is a regulatory requirement for auditability.

### NACHA Compliance — Bank Data Never in Cloud
The Compliance Agent's ACH services call an on-premises Token Service to resolve tokenized bank account references. Bank data is held in memory only during file generation, then immediately discarded. Never persisted to Redis, DynamoDB, S3, or logs.

### Hybrid Model Serving
High-volume agents (IDP, Validator, Transform) use in-process SLMs via `llama-cpp-python` for ~2x lower latency vs HTTP. Complex reasoning agents (Orchestrator, Compliance) use Amazon Bedrock via LiteLLM.

### Protocol-Based Architecture
All layers use Python `Protocol` (structural typing) interfaces for loose coupling. Implementations can be swapped at runtime — real AWS backends in production, in-memory fakes in tests — with zero code changes.

---

## License

Proprietary — BlueStar Retirement Services
