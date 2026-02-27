# Architecture: AI-Powered Payroll Processing Platform

**BlueStar Retirement Services**
**Version 2.1 | February 2026**

---

## Table of Contents

- [1. Executive Summary](#1-executive-summary)
- [2. System Architecture Overview](#2-system-architecture-overview)
- [3. Hybrid In-Process SLM Architecture](#3-hybrid-in-process-slm-architecture)
- [4. Agent Layer](#4-agent-layer)
  - [4.1 Orchestrator Agent](#41-orchestrator-agent)
  - [4.2 IDP Agent](#42-idp-agent)
  - [4.3 Validator Agent](#43-validator-agent)
  - [4.4 Transformation Agent](#44-transformation-agent)
  - [4.5 Compliance Agent](#45-compliance-agent)
- [5. Processing Pipeline (26 Steps)](#5-processing-pipeline-26-steps)
- [6. Data Layer](#6-data-layer)
  - [6.1 Canonical Payroll Record](#61-canonical-payroll-record)
  - [6.2 DynamoDB Tables](#62-dynamodb-tables)
  - [6.3 Redis Caching Strategy](#63-redis-caching-strategy)
  - [6.4 S3 File Lifecycle](#64-s3-file-lifecycle)
  - [6.5 SQL Server (On-Premises)](#65-sql-server-on-premises)
- [7. Protocol-Based Interface Layer](#7-protocol-based-interface-layer)
- [8. Model Serving Strategy](#8-model-serving-strategy)
  - [8.1 LiteLLM Configuration](#81-litellm-configuration)
  - [8.2 In-Process SLM Integration](#82-in-process-slm-integration)
  - [8.3 Instructor Structured Outputs](#83-instructor-structured-outputs)
- [9. MCP Tool Servers](#9-mcp-tool-servers)
- [10. Strands Graph Orchestration](#10-strands-graph-orchestration)
- [11. NACHA Compliance Architecture](#11-nacha-compliance-architecture)
- [12. Bedrock Guardrails](#12-bedrock-guardrails)
- [13. Infrastructure & Deployment](#13-infrastructure--deployment)
  - [13.1 VPC Layout](#131-vpc-layout)
  - [13.2 ECS Fargate Container Inventory](#132-ecs-fargate-container-inventory)
  - [13.3 Container Image Pipeline](#133-container-image-pipeline)
  - [13.4 Cost Estimates](#134-cost-estimates)
- [14. Observability](#14-observability)
- [15. Error Handling](#15-error-handling)

---

## 1. Executive Summary

This document defines the technical architecture for BlueStar's AI-powered payroll processing platform. The system replaces the legacy Stata/Blue Prism workflow with a multi-agent architecture built on **Strands Agents SDK**, **Amazon Bedrock**, and **in-process Small Language Models (SLMs) co-deployed inside agent containers on ECS Fargate**.

The hybrid model-serving strategy is the defining architectural choice: high-volume agent tasks (IDP, Validation, Transformation) embed **CPU-native SLMs directly in-process** via `llama-cpp-python` — zero HTTP overhead, zero network hops, zero serialization. Complex reasoning agents (Orchestrator, Compliance) call **Bedrock API** models (Claude Sonnet, Claude Haiku) via LiteLLM. There is **no separate SLM service tier, no internal ALB for model routing, and no Ollama**.

### Key Architectural Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Agent framework | Strands Agents SDK 1.x | AWS-native, Graph orchestration, MCP support, multi-model |
| SLM deployment | In-process via llama-cpp-python | Zero latency: model loaded in agent process memory. ~2x faster than HTTP server mode |
| SLM models | SmolLM3 3B, Phi-4 Mini 3.8B, Arcee AFM 4.5B | Purpose-built CPU-native sub-5B models. No GPU anywhere |
| Frontier model access | Amazon Bedrock API | Claude Sonnet/Haiku for Orchestrator + Compliance agents |
| Model gateway | LiteLLM (Bedrock-only) | Unified API for Bedrock calls with fallback, cost tracking. SLM agents bypass LiteLLM entirely |
| Structured outputs | Instructor + PydanticAI | Type-safe extraction with Pydantic validation and retry |
| Tool sharing | FastMCP | MCP servers for DynamoDB rules, SQL Server access, S3 ops |
| Document ingestion | MarkItDown | Convert XLSX/CSV/PDF to markdown for LLM consumption |
| Token management | tiktoken | Context window budgeting, chunking, cost estimation |
| Business rules | DynamoDB (8 tables) | Versioned rules engine consumed by all agents |
| Compliance | Bedrock Guardrails + On-prem Token Service | PII filtering, NACHA bank data isolation |
| Financial calculations | 100% deterministic | No AI inference for contribution amounts. Regulatory requirement |
| Orchestration | Protocol-abstracted | SQS (dev/test) + Strands Graph (prod) |
| Code structure | Monorepo, single `bluestar` Python package | Protocol-based, pydantic-settings, Python 3.12+ |

---

## 2. System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        PRESENTATION LAYER                           │
│   Operations Dashboard  │  Admin Console  │  Monitoring Dashboard    │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────────┐
│                     API GATEWAY (Amazon API Gateway)                 │
│              Routes: /files, /schemas, /reviews, /admin              │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────────┐
│                   ORCHESTRATION LAYER                                │
│                                                                      │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────────────────┐   │
│  │ EventBridge │→ │ Strands Graph │→ │  SQS Processing Queues    │   │
│  │ (Events)    │  │ (Orchestrator)│  │  (IDP/Val/Xform/Comply)  │   │
│  └─────────────┘  └──────┬───────┘  └───────────────────────────┘   │
│                          │                                           │
│                  ┌───────▼───────┐                                   │
│                  │  LiteLLM      │ ← Bedrock-only (Orchestrator +   │
│                  │  (Bedrock API)│   Compliance agents)              │
│                  └───────┬───────┘                                   │
│                          │                                           │
│                  ┌───────▼───────────────────────────────────┐       │
│                  │           BEDROCK API                      │       │
│                  │  Claude Sonnet 4  │  Claude Haiku 3.5     │       │
│                  │  Bedrock Guardrails (PII/Compliance)       │       │
│                  └───────────────────────────────────────────┘       │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────────┐
│              AGENT APPLICATION LAYER (ECS Fargate)                    │
│          SLM models embedded IN-PROCESS — zero network hops          │
│                                                                      │
│  ┌────────────────────┐  ┌────────────────────┐                     │
│  │ ORCHESTRATOR AGENT │  │  COMPLIANCE AGENT  │                     │
│  │ 3 services         │  │  6 services        │                     │
│  │ Model: Bedrock     │  │  Model: Bedrock    │                     │
│  │ (via LiteLLM)      │  │  (via LiteLLM)     │                     │
│  └────────────────────┘  └────────────────────┘                     │
│                                                                      │
│  ┌────────────────────┐  ┌────────────────────┐  ┌──────────────┐  │
│  │    IDP AGENT       │  │  VALIDATOR AGENT   │  │ TRANSFORM    │  │
│  │    3 services      │  │  5 services        │  │ AGENT        │  │
│  │ ┌────────────────┐ │  │ ┌────────────────┐ │  │ 9 services   │  │
│  │ │ SmolLM3 3B     │ │  │ │ Arcee AFM 4.5B │ │  │┌────────────┐│  │
│  │ │ (IN-PROCESS)   │ │  │ │ (IN-PROCESS)   │ │  ││Phi-4 Mini  ││  │
│  │ │ llama-cpp-py   │ │  │ │ llama-cpp-py   │ │  ││(IN-PROCESS)││  │
│  │ └────────────────┘ │  │ └────────────────┘ │  │└────────────┘│  │
│  │ + Bedrock escalate │  │                    │  │              │  │
│  └────────────────────┘  └────────────────────┘  └──────────────┘  │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────────┐
│                       DATA LAYER                                     │
│                                                                      │
│  ┌─────────────┐ ┌───────┐ ┌───────────────┐ ┌──────────────────┐  │
│  │  DynamoDB   │ │ Redis │ │  S3 (Files)   │ │ SQL Server       │  │
│  │  (8 Rules   │ │ (Hot  │ │  (Raw/Output/ │ │ (On-Prem: STP    │  │
│  │   Tables)   │ │ Cache)│ │   Archive)    │ │  tables, Relius, │  │
│  └─────────────┘ └───────┘ └───────────────┘ │  PlanConnect)    │  │
│                                               └──────────────────┘  │
│  ┌──────────────────┐  ┌────────────────────────────────────────┐   │
│  │ FastMCP Servers   │  │  On-Premises Integration               │   │
│  │ (Tool Exposure)   │  │  Token Service (NACHA bank data)       │   │
│  └──────────────────┘  │  CapitalSG-64 (SQL Server ODBC)        │   │
│                         └────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 3. Hybrid In-Process SLM Architecture

### 3.1 The Co-Deployment Pattern

Instead of running SLMs as separate services behind a load balancer, IDP, Validator, and Transformation agents **embed their SLM directly in-process** using `llama-cpp-python` as a Python library. The model weights are loaded into the agent's process memory at container startup. LLM inference is a local function call with zero HTTP serialization.

```
BEFORE (Separate SLM Service):                 AFTER (In-Process):
Agent → HTTP → ALB → SLM Container → response  Agent → llm.create_chat_completion() → result
       ~2-10ms network + serialization                  ~0ms (in-process function call)
       ~50% throughput penalty from HTTP                ~2x throughput vs HTTP mode
```

### 3.2 Agent-to-Model Assignment

| Agent | Model Strategy | Why |
|-------|---------------|-----|
| **IDP** | In-process: SmolLM3 3B + Bedrock escalation | High-volume parsing (6K records). Schema inference is rare (new vendors only) |
| **Validator** | In-process: Arcee AFM 4.5B | Highest call volume (6K records x 14 rules = 84K evaluations). Must be fast |
| **Transformation** | In-process: Phi-4 Mini 3.8B | Deterministic transforms with AI-assisted field normalization. Speed critical |
| **Orchestrator** | Bedrock: Claude Sonnet 4 (via LiteLLM) | Low call volume (~26 dispatch decisions per batch). Needs frontier reasoning |
| **Compliance** | Bedrock: Claude Sonnet 4 (via LiteLLM) | Complex compliance analysis, NACHA reasoning. Bedrock Guardrails for PII |

### 3.3 CPU-Native SLM Models

All models use **Q4_K_M GGUF** quantization (4.5 effective bits/weight). No GPU required.

| Model | Params | RAM (Q4) | CPU tok/s | Agent | License |
|-------|--------|----------|-----------|-------|---------|
| Arcee AFM 4.5B | 4.5B | ~3 GB | 30-50 | Validator | Apache 2.0 |
| SmolLM3 3B | 3B | ~2.2 GB | 20-35 | IDP | Apache 2.0 |
| Phi-4 Mini 3.8B | 3.8B | ~2.5 GB | 15-30 | Transformation | MIT |
| Qwen3 0.6B | 0.6B | ~400 MB | 50-80 | Routing (optional) | Apache 2.0 |

### 3.4 Agent Container Images

Each SLM agent is a **single Docker image** containing both agent code AND the GGUF model:

| Container | Model | Image Size | Fargate Spec | Cold Start |
|-----------|-------|-----------|-------------|-----------|
| bluestar-agent-idp | SmolLM3 3B (2.2 GB) | ~3.0 GB | 4 vCPU / 8 GB | ~15 sec |
| bluestar-agent-validator | Arcee AFM 4.5B (3 GB) | ~3.8 GB | 4 vCPU / 8 GB | ~20 sec |
| bluestar-agent-transform | Phi-4 Mini 3.8B (2.5 GB) | ~3.3 GB | 4 vCPU / 8 GB | ~18 sec |
| bluestar-agent-orchestrator | None (Bedrock) | ~500 MB | 2 vCPU / 4 GB | ~5 sec |
| bluestar-agent-compliance | None (Bedrock) | ~500 MB | 2 vCPU / 4 GB | ~5 sec |

---

## 4. Agent Layer

### 4.1 Orchestrator Agent

**Role:** Central coordinator for all payroll file processing. Receives EventBridge `file.received` events, loads the client's pipeline from DynamoDB, dispatches steps to agents, and tracks workflow state.

**Services:**

| Service | Responsibility |
|---------|---------------|
| **PipelineExecutor** | Loads 26-step pipeline from DynamoDB, dispatches steps to agent SQS queues in order, waits for completion callbacks, halts on required-step failures |
| **WorkflowStateManager** | Tracks batch/step state machines (`RECEIVED → PROCESSING → COMPLETED/FAILED/ESCALATED`), enables resume-from-failure, writes operational stats to SQL Server |
| **EscalationRouter** | Routes exceptions to human review: schema confidence < 0.80, >50% STOP issues, deadline at risk (<30 min), financial anomaly (>200% variance), multiple plan holds |

**State Machine:**
```
Batch: RECEIVED → PROCESSING → COMPLETED | FAILED | ESCALATED
Step:  PENDING → DISPATCHED → PROCESSING → COMPLETED | FAILED | SKIPPED
```

### 4.2 IDP Agent

**Role:** First agent to touch every payroll file. Parses raw vendor files (CSV, TSV, XLSX, fixed-width) into canonical payroll records. Handles pipeline steps 0100–0500.

**Services:**

| Service | Pipeline Step | Key Behavior |
|---------|-------------|-------------|
| **SchemaMatcherService** | 0100 | SHA-256 fingerprint → DynamoDB GSI lookup. If no match or confidence < 0.95, escalates to Bedrock Claude Haiku for AI schema inference. New schemas written back to DynamoDB |
| **FileParserService** | 0100-0400 | Applies column mapping per file type. Executes post-import drop rules (removes header rows, padding records). Merges with canonical payroll fields template. Drops V-variables |
| **DestringService** | 0500 | Strips non-numeric characters, handles trailing-negative (COBOL format: `123.45-` → `-123.45`), converts to decimals, sums multi-instance fields (salary1-10 → salary) |

**Multi-File Handling:** PEO clients submit multiple files per period (one per location). IDP parses each independently, adds an `identifier` field, and concatenates into a single record set.

**Dual-Model Pattern:** Primary model (SmolLM3 3B) runs in-process for routine parsing. The `infer_unknown_schema` tool creates a temporary Bedrock-backed agent for rare schema inference (1% of calls).

### 4.3 Validator Agent

**Role:** Validates every payroll record against business rules. Catches bad data before financial calculations. Handles steps 0900, 1000, 1200, 1600.

**Rule Loading:** At batch start, loads all rule sets from DynamoDB (cached 1 hour in Redis). A batch of 6,000 records executes against ~5 DynamoDB reads, not 6,000.

**Services:**

| Service | Pipeline Step | Key Behavior |
|---------|-------------|-------------|
| **SSNValidatorService** | 0900 | 7-point SSN validation: length checks (7-9 digits), numeric floor (<999999), zero group/serial checks, known-invalid patterns (123456789, all-same-digit). Assigns sequence numbers for missing SSNs |
| **DateCleanerService** | 1000 | Strips timestamps, nullifies known-invalid dates (01/01/1900, N/A, 00/00/0000), parses multiple date formats (MDY/YMD/DMY per client config) |
| **EmploymentStatusService** | 1200 | Cross-references Relius via ODBC (`jobstatuscurrent`, `originalDOH`). Clears invalid DOT/DOR, detects rehire-without-DOT, replaces DOH with Relius original when available |
| **IssueDetectorService** | 1600 | Cross-references Relius `PersonalInfoByPlan` for sort issues. 9 STOP-level issues (sort mismatch, bad SSN, no DOB, zero comp with contrib, etc.) + 5 WARNING-level issues (hours too large, missing last name, invalid email, negative hours/comp, rehire without DOT). Nickname exception for fname mismatches |
| **ContribRateCheckService** | Optional | Compares file deferrals against BlueStar election records. Detects 6 discrepancy types (dollar mismatch, percent mismatch, no-election contributions) |

### 4.4 Transformation Agent

**Role:** Executes all deterministic data transformations. **NO AI inference for financial calculations** — every contribution amount is computed from explicit formulas in DynamoDB. This is a regulatory requirement for auditability. Handles steps 0550–2300 (non-validation, non-compliance).

**Services:**

| Service | Pipeline Step | Key Behavior |
|---------|-------------|-------------|
| **CompensationCalcService** | 0600 | Computes `plancomp`, `matchcomp`, `ercomp` from client-specific formula. Default: `salary + bonus + commissions + overtime`. Some clients exclude components or apply adjustments |
| **MatchCalcService** | 0700 | Two-tier employer match: Level 1 (e.g., 100% up to 3% of comp) + Level 2 (e.g., 50% up to 5%). Includes IRS annual limit check via YTD query to SQL Server. Target field configurable (match/shmatch/shmatchqaca) |
| **ERContribCalcService** | 0800 | Flat-rate ER contributions with eligibility check (plan entry date) and IRS 415(c)/401(a)(17) limit enforcement. Target: pshare/shne/shneqaca |
| **DuplicateEmployeeService** | 1300 | Tags duplicate SSNs within planId. Aggregates: SUM financials, MIN dates (dob/doh), MAX dates (dot/dor). Keeps row with non-zero salary and highest total comp |
| **HoursEstimationService** | 1500 | Estimates hours as `(salary + commissions + overtime) / 10`, capped by pay frequency (W:45, B:90, S:95, M:190). Removes hours for bonus-only pay |
| **NegativePayrollService** | 1800 | Zeroes all 12 contribution fields where negative. **Ordering critical:** totals-with-negatives (1700) → zero negatives (1800) → totals-without-negatives (1900) |
| **TotalsByPlanService** | 1700, 1900 | Collapses records by planId, sums all contribution fields. Flags plans with zero total (census-only, no payroll). Computes by-identifier totals for PEO files |
| **XMLGeneratorService** | 2300 | Generates Relius `IMPORT_PAYROLL` XML. Determines plan year-end, allocation effective date (next business day), frequency code via ODBC query to `DetailsWithPaySchedXML` |
| **FileExportService** | 2100 | Splits records by plan hold status. Exports: PayrollALL, BadSSN, Loans, PlanHOLD files. Multi-planId batches export per-planId files into subdirectory |

**Critical Financial Calculation Constraints:**
1. All amounts use `ROUND(value, 0.01)` (nearest penny)
2. IRS annual limits always checked AFTER base calculation
3. YTD source totals always included in limit calculations
4. Off-calendar plan years use `limitationyear = year(payroll) - 1`
5. ER contributions require plan entry date eligibility check

### 4.5 Compliance Agent

**Role:** Enforces regulatory and business compliance at the end of the pipeline. Handles steps 2000–2600.

**Services:**

| Service | Pipeline Step | Key Behavior |
|---------|-------------|-------------|
| **PlanHoldService** | 2000 | Evaluates hold conditions from DynamoDB (15-min cache TTL — shortest in system). Hold types: New Client (auto-detected via date calc), Amendment, Revocation, Frozen, Blackout, Transfer. EligRun zero-total override releases holds when no contributions exist. Multiple holds trigger "Research-Multiple Clientids On Hold" escalation |
| **ForfeitureService** | 2200 | Applies forfeiture offsets to ER total. **Davis-Bacon exclusion:** `prevwageer` and `prevwageqnec` excluded (double-credit prohibition per ASPPA handbook). Multi-identifier allocation at plan level |
| **ACHPrepService** | 2500 | Calculates ACH request date with weekend/after-hours adjustments. Validates SEFA setup windows. Looks up plan name (truncated to 42 chars) |
| **ACHCalcService** | 2600 | Collapses records by SEFA IDs, calculates ACH amounts (TotalAmt, ERAmt, EEAmt, RothAmt, LoanPymtAmt, AfterTaxAmt). **Resolves bank data via on-prem Token Service — held in memory only, never persisted** |
| **DepWDDetailService** | 2400 | Aggregates contribution amounts with specific combination rules (Roth includes aftertax, PShare includes prevailing wage). Executes `Stata_Save_DepWDDetail` stored procedure in PlanConnect |
| **DeadlineMonitorService** | Continuous | Monitors custodian deadlines: Matrix Trust 3:30 PM CT, Schwab 12:00 PM CT. Escalates at 30-minute threshold |

---

## 5. Processing Pipeline (26 Steps)

Each step is defined in DynamoDB (`bluestar-processing-pipeline`) with ordering, agent routing, dependencies, and enabled/required flags.

| Step | Subroutine | Agent | Required | Description |
|------|-----------|-------|----------|-------------|
| 0100 | FILE_INGEST | IDP | Yes | Parse raw vendor file into canonical records |
| 0200 | FILE_VALIDATION | Validator | Yes | Validate file belongs to correct plan |
| 0300 | MERGE_PAYROLL_FIELDS | IDP | Yes | Ensure all canonical fields exist |
| 0400 | DROP_V_VARIABLES | IDP | Yes | Remove excess columns not in schema |
| 0500 | DESTRING_NUMBERS | IDP | Yes | Convert strings to decimals, handle trailing negatives |
| 0550 | SPLIT_MONTH_PEO | Transform | Yes | Handle multi-identifier PEO files |
| 0600 | CALC_COMPENSATION | Transform | Yes | Compute plancomp, matchcomp, ercomp |
| 0700 | CALC_MATCH | Transform | Conditional | Two-tier employer match with IRS limits |
| 0800 | CALC_ER_CONTRIB | Transform | Conditional | Flat-rate ER contributions with eligibility |
| 0900 | BAD_SSN | Validator | Yes | 7-point SSN validation |
| 1000 | FORMAT_DATES_STRINGS | Validator | Yes | Date cleaning, timestamp stripping, format parsing |
| 1100 | EETYPE_CODING | Transform | Conditional | Employee type classification |
| 1200 | EMPLOYMENT_STATUS | Validator | Yes | DOH/DOT/DOR validation via Relius cross-reference |
| 1300 | DUPLICATE_EMPLOYEES | Transform | Yes | Consolidate duplicate SSNs within planId |
| 1400 | DROP_OLD_TERMS | Transform | Yes | Remove fully-terminated employees (no comp, DOT >180 days) |
| 1500 | FIX_HOURS | Transform | Yes | Estimate missing hours, cap by pay frequency |
| 1600 | ISSUE_DETECTION | Validator | Yes | 9 STOP + 5 WARNING issues, Relius cross-reference |
| 1700 | TOTALS_INCLNEG | Transform | Yes | Plan totals including negative contributions |
| 1800 | NEGATIVE_PAYROLL | Transform | Yes | Zero-floor all negative contribution fields |
| 1900 | TOTALS_EXCLNEG | Transform | Yes | Plan totals excluding negatives (for ACH) |
| 2000 | PLAN_HOLD_CHECK | Compliance | Yes | Evaluate plan hold conditions |
| 2100 | EXPORT_FILES | Transform | Yes | Export payroll, bad SSN, loans, hold files |
| 2200 | FORFEITURES | Compliance | Yes | Apply forfeiture offsets (Davis-Bacon aware) |
| 2300 | GENERATE_XML | Transform | Yes | Relius IMPORT_PAYROLL XML generation |
| 2400 | DEPWD_DETAIL_UPDATE | Compliance | Yes | Populate DepWDDetail via stored procedure |
| 2500 | ACH_PREP | Compliance | Yes | Calculate ACH request date, validate SEFA |
| 2600 | ACH_CALC | Compliance | Yes | Generate NACHA-compliant ACH file |

---

## 6. Data Layer

### 6.1 Canonical Payroll Record

All agents operate on a single normalized `CanonicalPayrollRecord` schema (60+ fields). Every vendor file, regardless of source format, is parsed into this structure.

**Identity:** `planid`, `planidfreq`, `clientid`, `ssn`

**Demographic:** `fname`, `lname`, `mname`, `dob`, `email`, `phone`, `gender`, `maritalstatus`, address fields

**Employment:** `doh` (hire), `dot` (termination), `dor` (rehire), `payfreq` (W/B/S/M/Q/A)

**Compensation:** `hours`, `salary`, `bonus`, `commissions`, `overtime`, `plancomp` (computed), `matchcomp` (computed), `ercomp` (computed)

**Contributions (12 source types):** `deferral`, `rothdeferral`, `match`, `shmatch`, `shmatchqaca`, `pshare`, `shne`, `shneqaca`, `loan`, `prevwageer`, `prevwageqnec`, `aftertax`

**Validation & Classification:** `badssn`, `issue`, `warning`, `eetype`, `eesubtype`, `planhold`, `planholdnote`, `rehirewithoutdot`

**Processing Metadata:** `identifier` (multi-file location ID), `batchid`, `grosscomp`, `annualcomp`

### 6.2 DynamoDB Tables

Eight tables store all business rules and configuration. Table suffixes vary by environment: `-dev`, `-uat`, or none (prod).

| Table | PK Pattern | SK Pattern | Primary Consumer | Purpose |
|-------|-----------|-----------|-----------------|---------|
| `bluestar-client-processing-config` | `CLIENT#{planId}` | `CONFIG#{payFreq}#v{version}` | All agents | Compensation formulas, match rules, PEO flags, custodian |
| `bluestar-vendor-schema-mapping` | `VENDOR#{vendorId}` | `SCHEMA#{planId}_{payFreq}#v{ver}` | IDP | Column mappings, fingerprints, destring config, drop rules |
| `bluestar-validation-rules` | `CATEGORY#{category}` | `RULE#{ruleId}` | Validator | SSN validation, date cleaning, issue detection rules |
| `bluestar-business-calculation-rules` | `CLIENT#{planId}` or `GLOBAL` | `CALC#{calcType}#v{ver}` | Transform | Match formulas, ER rates, duplicate handling, hours estimation |
| `bluestar-compliance-limits` | `YEAR#{year}` | `LIMITS` | Transform | IRS 401(a)(17), 415(c), 402(g) contribution limits |
| `bluestar-plan-hold-rules` | `PLAN#{planId}` | `HOLD#{clientId}` | Compliance | Plan holds (new client, amendment, revocation, frozen, blackout) |
| `bluestar-processing-pipeline` | `CLIENT#{planId}_{payFreq}` | `STEP#{stepOrder}` | Orchestrator | 26-step pipeline: order, agent, dependencies, enabled/required |
| `bluestar-ach-configuration` | `PLAN#{planId}` | `ACH#{payFreq}#v{ver}` | Compliance | ACH request date config, SEFA setup, plan name |

**Access Pattern: Client-Specific with GLOBAL Fallback**
```
1. GetItem PK=CLIENT#{planId}, SK=CALC#{calcType}#v{latest}
   → If found: use client-specific rule
2. If not found: GetItem PK=GLOBAL, SK=CALC#{calcType}#v{latest}
   → Use global default
```

### 6.3 Redis Caching Strategy

Three-tier hierarchy: **In-memory → Redis (L2) → DynamoDB (L3)**

| Cache Key Pattern | TTL | Reason |
|-------------------|-----|--------|
| `schema:{vendorId}:{fingerprint}` | 24 hrs | Schemas change only when vendors update file formats |
| `rules:validation:{category}` | 1 hr | Rule updates infrequent |
| `rules:calc:{planId}:{calcType}` | 1 hr | Same |
| `config:{planId}:{payFreq}` | 1 hr | Same |
| `limits:{year}` | 24 hrs | Annual IRS limits |
| `hold:{planId}` | **15 min** | **Shortest TTL** — holds change intraday by ops team |
| `pipeline:{planId}:{payFreq}` | 1 hr | Pipeline config stable |
| `session:{batchId}:state` | 4 hrs | Active batch processing window |
| `session:{batchId}:records` | 4 hrs | Active batch record set |

### 6.4 S3 File Lifecycle

```
dropzone/{planId}/          ← Incoming vendor files
    │
    ▼ (IDP Agent starts processing)
inprogress/{batchId}/       ← Active processing
    │
    ├──▶ validated/{batchId}/    ← On success
    │       ├── PayrollALL.csv
    │       ├── BadSSN.csv
    │       ├── Loans.csv
    │       ├── Issues.csv
    │       ├── PayrollXML.xml
    │       └── ACHFile.txt
    │
    └──▶ failed/{batchId}/       ← On failure
            └── error_context.json
```

### 6.5 SQL Server (On-Premises)

CapitalSG-64 accessed via ODBC (`pyodbc`). Contains Relius/PlanConnect operational data.

**Key Queries:**
- `jobstatuscurrent` — Employment status by planId + SSN
- `originalDOH` — Original date of hire from Relius
- `PersonalInfoByPlan` — Name/DOB cross-reference for sort issue detection
- `CurrentContributionRates` — BlueStar deferral elections
- `ERContribYTD` — Year-to-date ER contribution totals by source
- `PlanEECodeHistExport` — Plan entry date for eligibility checks
- `DetailsWithPaySchedXML` — Frequency code and sequence number for XML
- `PayrollForfs` — Available forfeiture balance
- `DepWDDetail` — Deposit/withdrawal detail records
- `Stata_Save_DepWDDetail` — Stored procedure for DepWD population

---

## 7. Protocol-Based Interface Layer

All layers use Python `Protocol` (structural typing) for loose coupling. Implementations are swappable at runtime — real AWS backends in production, in-memory fakes in tests.

```python
@runtime_checkable
class IModelProvider(Protocol):
    def chat(self, messages: list[dict[str, str]], **kwargs) -> str: ...
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

**Implementations:**
| Protocol | Production | Test |
|----------|-----------|------|
| `IRulesStore` | `DynamoDBBackend` | `MemoryRulesStore` |
| `ICacheBackend` | `RedisBackend` | `MemoryCacheBackend` |
| `IFileStore` | `S3Backend` | `MemoryFileStore` |
| `ISQLClient` | `SQLServerClient` (ODBC) | `MemorySQLClient` |
| `IModelProvider` | `BedrockProvider` / `InProcessSLM` | `MockModelProvider` |
| `IOrchestrator` | `StrandsOrchestrator` | `SQSOrchestrator` |

---

## 8. Model Serving Strategy

### 8.1 LiteLLM Configuration

LiteLLM serves **only the Orchestrator and Compliance agents**. IDP, Validator, and Transformation agents bypass LiteLLM entirely because their SLMs are in-process.

```
Orchestrator Agent → LiteLLM → Bedrock Claude Sonnet (frontier reasoning)
Compliance Agent  → LiteLLM → Bedrock Claude Sonnet + Guardrails (PII filtered)
IDP Agent (rare)  → LiteLLM → Bedrock Claude Haiku (schema inference escalation)

IDP Agent (routine)       → IN-PROCESS SmolLM3 3B     (bypasses LiteLLM)
Validator Agent           → IN-PROCESS Arcee AFM 4.5B  (bypasses LiteLLM)
Transformation Agent      → IN-PROCESS Phi-4 Mini 3.8B (bypasses LiteLLM)
```

**Key LiteLLM settings:**
- Routing: `simple-shuffle` with 3 retries
- Fallback: Claude Sonnet → Claude Haiku
- Budget: $300/month cap with spend tracking
- Guardrails: `bluestar-pii-filter` on Compliance calls

### 8.2 In-Process SLM Integration

```python
from llama_cpp import Llama

class InProcessSLM:
    """Wraps llama-cpp-python for in-process inference inside a Strands agent."""

    def __init__(self, model_path: str, n_ctx: int = 4096, n_threads: int = 4):
        self.llm = Llama(
            model_path=model_path,
            n_ctx=n_ctx,
            n_threads=n_threads,      # Match Fargate vCPU count
            n_batch=512,
            verbose=False,
            chat_format="chatml",
        )
        self._warm_up()

    def chat(self, messages: list, max_tokens: int = 512,
             temperature: float = 0.1) -> str:
        """Direct in-process inference — zero HTTP, zero serialization."""
        response = self.llm.create_chat_completion(
            messages=messages, max_tokens=max_tokens, temperature=temperature,
        )
        return response["choices"][0]["message"]["content"]
```

### 8.3 Instructor Structured Outputs

Instructor wraps `llama-cpp-python` directly for Pydantic-validated extraction:

```python
import instructor
from llama_cpp import Llama
from pydantic import BaseModel

llm = Llama(model_path="/models/model.gguf", n_ctx=4096, chat_format="chatml")
client = instructor.patch(create=llm.create_chat_completion, mode=instructor.Mode.JSON)

class ValidationResult(BaseModel):
    ssn: str
    is_valid: bool
    issues: list[str]
    warnings: list[str]

result = client(
    response_model=ValidationResult,
    messages=[{"role": "user", "content": f"Validate: {record_json}"}],
    max_retries=2,
)
```

---

## 9. MCP Tool Servers

FastMCP exposes shared services as MCP tools consumed by all agents via Strands' native MCP client.

### Rules Server (DynamoDB)
- `get_client_config(plan_id, pay_freq)` — Client processing config
- `get_validation_rules(category)` — Rule sets by category
- `get_calculation_rule(plan_id, calc_type)` — Calc rules with CLIENT→GLOBAL fallback
- `get_irs_limits(year)` — IRS annual contribution limits
- `get_plan_holds(plan_id)` — Active plan holds (15-min cache)
- `get_pipeline_steps(plan_id, pay_freq)` — Ordered pipeline definition

### SQL Server
- Query `CapitalSG-64` via ODBC
- Execute stored procedures (DepWDDetail, YTD contrib totals)
- Load eligibility data, employment status, Relius cross-reference

### S3 File Server
- Read/write files to S3
- Move files between lifecycle folders (dropzone → inprogress → validated/failed)
- List files by prefix

### Pipeline Server
- Dispatch steps to agent SQS queues
- Track batch state
- Escalate to human review

---

## 10. Strands Graph Orchestration

Production uses Strands Graph for deterministic, conditional workflow control across agents:

```python
from strands import Agent
from strands.multiagent import GraphBuilder

builder = GraphBuilder()
builder.add_node(orchestrator, "orchestrator")
builder.add_node(idp_agent, "idp")
builder.add_node(validator_agent, "validator")
builder.add_node(transform_agent, "transform")
builder.add_node(compliance_agent, "compliance")

# Pipeline flow with conditional routing
builder.add_edge("orchestrator", "idp")
builder.add_edge("idp", "validator")
builder.add_edge("validator", "transform",
    condition=lambda state: state.get("validation_passed", False))
builder.add_edge("validator", "orchestrator",
    condition=lambda state: not state.get("validation_passed", False))
builder.add_edge("transform", "compliance")
builder.add_edge("compliance", "orchestrator")  # Completion callback

builder.set_entry_point("orchestrator")
pipeline = builder.build()
```

---

## 11. NACHA Compliance Architecture

Bank account data (routing numbers, account numbers) **NEVER enters AWS**.

```
Agent in AWS VPC                    On-Premises
┌────────────────┐                  ┌──────────────────┐
│ Compliance     │  SEFA tokens     │ Token Service    │
│ Agent          │ ───────────────→ │                  │
│                │                  │ Resolves tokens  │
│ ACHCalcService │ ←─────────────── │ to actual bank   │
│                │  Bank data       │ routing/account  │
│ IN MEMORY ONLY │  (encrypted TLS) │ numbers          │
│ NEVER CACHED   │                  └──────────────────┘
│ NEVER LOGGED   │
│ NEVER TO S3    │
│ DISCARDED AFTER│
│ FILE GENERATION│
└────────────────┘
```

| Requirement | Implementation |
|-------------|---------------|
| Bank data never in cloud | Token Service is on-premises only |
| Bank data not persisted | Held in memory during ACH generation, then discarded |
| Bank data not cached | Excluded from Redis and DynamoDB |
| Bank data not logged | Excluded from CloudWatch and audit trail |
| Tokenized references only in AWS | DynamoDB stores SEFA IDs (tokens), not bank accounts |

---

## 12. Bedrock Guardrails

Applied to Compliance Agent calls via LiteLLM guardrail config:

| Data Type | Action |
|-----------|--------|
| SSN | **BLOCK** — never output in agent responses |
| Bank Account | **BLOCK** |
| Date of Birth | ANONYMIZE — replace with `[DOB]` |
| Address | ANONYMIZE |
| Employee IDs | **BLOCK** — custom regex `\b\d{3}-\d{2}-\d{4}\b` |
| Plan Numbers | ALLOW — needed for processing |

---

## 13. Infrastructure & Deployment

### 13.1 VPC Layout

```
VPC: bluestar-ai-platform (10.0.0.0/16)
│
├── Public Subnets (10.0.1.0/24, 10.0.2.0/24)
│   └── ALB (external) → API Gateway
│
├── Private Subnets - Application (10.0.10.0/24, 10.0.11.0/24)
│   ├── ECS Fargate: Orchestrator Agent (2vCPU/4GB, Bedrock via LiteLLM)
│   ├── ECS Fargate: IDP Agent + SmolLM3 3B IN-PROCESS (4vCPU/8GB)
│   ├── ECS Fargate: Validator Agent + AFM 4.5B IN-PROCESS (4vCPU/8GB)
│   ├── ECS Fargate: Transform Agent + Phi-4 Mini IN-PROCESS (4vCPU/8GB)
│   ├── ECS Fargate: Compliance Agent (2vCPU/4GB, Bedrock via LiteLLM)
│   ├── ECS Fargate: LiteLLM Proxy (1vCPU/2GB, Bedrock-only)
│   ├── ECS Fargate: FastMCP servers
│   └── NAT Gateway → Bedrock API
│
├── Private Subnets - Data (10.0.30.0/24, 10.0.31.0/24)
│   ├── ElastiCache Redis Cluster
│   ├── RDS PostgreSQL (LiteLLM spend tracking)
│   └── VPC Endpoints: DynamoDB, S3, Bedrock
│
└── Direct Connect / VPN → On-Premises
    ├── SQL Server (CapitalSG-64)
    ├── Token Service (NACHA)
    └── BlueStar SFTP Server (Azure)
```

### 13.2 ECS Fargate Container Inventory

| Container | vCPU | Memory | Embedded SLM | Count | Monthly Cost |
|-----------|------|--------|-------------|-------|-------------|
| Orchestrator Agent | 2 | 4 GB | None (Bedrock) | 1 | ~$25 |
| IDP Agent + SmolLM3 3B | 4 | 8 GB | SmolLM3 3B (2.2 GB) | 2 | ~$81 |
| Validator Agent + AFM 4.5B | 4 | 8 GB | Arcee AFM 4.5B (3 GB) | 2 | ~$81 |
| Transform Agent + Phi-4 Mini | 4 | 8 GB | Phi-4 Mini 3.8B (2.5 GB) | 1 | ~$40 |
| Compliance Agent | 2 | 4 GB | None (Bedrock) | 1 | ~$25 |
| LiteLLM Proxy | 1 | 2 GB | N/A | 1 | ~$12 |
| FastMCP Rules Server | 1 | 2 GB | N/A | 2 | ~$25 |
| FastMCP SQL Server | 1 | 2 GB | N/A | 1 | ~$12 |
| **TOTAL** | | | | **11** | **~$301/mo** |

**Savings from in-process co-deployment:** Eliminated 6 SLM containers, internal ALB, and 2 extra LiteLLM proxy replicas — **~$280/month savings + zero SLM network latency**.

### 13.3 Container Image Pipeline

```
Developer pushes code
    │
    ▼
CodePipeline triggered
    │
    ├── Build agent+SLM images (GGUF model baked in)
    │   └── ECR: bluestar-agent-orchestrator:v{tag}    (~500 MB)
    │   └── ECR: bluestar-agent-idp:v{tag}             (~3.0 GB)
    │   └── ECR: bluestar-agent-validator:v{tag}        (~3.8 GB)
    │   └── ECR: bluestar-agent-transform:v{tag}        (~3.3 GB)
    │   └── ECR: bluestar-agent-compliance:v{tag}       (~500 MB)
    │
    ├── Build infrastructure images
    │   └── ECR: bluestar-litellm-proxy:v{tag}          (~200 MB)
    │   └── ECR: bluestar-mcp-rules:v{tag}
    │   └── ECR: bluestar-mcp-sql:v{tag}
    │
    ▼
Deploy to ECS (Blue/Green via CodeDeploy)
```

### 13.4 Cost Estimates

| Category | Monthly Cost |
|----------|-------------|
| ECS Fargate (11 containers, 3 with embedded SLMs) | ~$301 |
| Bedrock API (Orchestrator + Compliance + rare IDP escalation) | ~$241 |
| DynamoDB (PAY_PER_REQUEST) | ~$5 |
| Redis (ElastiCache r6g.medium) | ~$95 |
| S3 (storage + requests) | ~$15 |
| CloudWatch (logs + metrics) | ~$30 |
| **TOTAL** | **~$687/mo** |

---

## 14. Observability

**Structured Logging (structlog):**
```json
{
  "level": "INFO",
  "batchId": "batch-20260224-001",
  "planId": "ExtraSpecial",
  "step": "STEP#0900",
  "event": "STEP_COMPLETED",
  "durationMs": 1250,
  "recordCount": 150,
  "correlationId": "corr-abc-123"
}
```

**CloudWatch Metrics:**
- `BatchDuration` (by planId)
- `StepDuration` (by subroutineName)
- `EscalationCount` (by reason)
- `DeadlineMargin` (minutes remaining at completion, by custodian)

---

## 15. Error Handling

| Error Type | Action |
|-----------|--------|
| DynamoDB throttle | Exponential backoff with jitter, max 3 retries |
| SQS send failure | Retry 3x, then escalate batch |
| Agent timeout (>5 min per step) | Retry step once, then escalate |
| Redis connection failure | Bypass cache, read directly from DynamoDB |
| SQL Server ODBC failure | Escalate immediately (on-prem connectivity) |
| Token Service unreachable | Escalate immediately (NACHA compliance — cannot generate ACH) |
| Schema fingerprint no match | Escalate to Bedrock for inference, then human review if confidence < 0.80 |
| File empty or corrupt | Mark FAILED, escalate to human review |
| All records dropped by rules | Likely wrong file uploaded — escalate |
| DepWDDetail SP fails | Log error, output manual update file, continue batch |
| Forfeiture balance unavailable | Skip forfeiture, log warning, continue batch |
| Custodian deadline missed | Log DEADLINE_MISSED metric, escalate, still complete processing |
