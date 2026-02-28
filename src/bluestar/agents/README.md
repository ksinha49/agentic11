# `bluestar/agents` — AI Agent Implementations

Five specialized agents that collectively execute the 26-step payroll processing pipeline. Each agent owns a subset of steps and uses either an in-process SLM or Bedrock API for inference.

## Agent Overview

| Agent | Directory | Model | Steps | Role |
|-------|-----------|-------|-------|------|
| **Orchestrator** | `orchestrator/` | Claude Sonnet (Bedrock) | Dispatch all | Pipeline coordination, state tracking |
| **IDP** | `idp/` | SmolLM3 3B (in-process) | 0100–0500 | File parsing, schema matching |
| **Validator** | `validator/` | Arcee AFM 4.5B (in-process) | 0900–1600 | SSN/date validation, issue detection |
| **Transform** | `transform/` | Phi-4 Mini 3.8B (in-process) | 0550–2300 | Financial calcs, exports, dedup |
| **Compliance** | `compliance/` | Claude Sonnet (Bedrock) | 2000–2600 | Plan holds, forfeitures, ACH |

## Base Agent (`base.py`)

All agents extend `BaseAgent` with dependency injection:

```python
from bluestar.agents.base import BaseAgent

class MyAgent(BaseAgent):
    def __init__(self, settings, model, rules_store, cache):
        super().__init__(settings, model, rules_store, cache)

    def health_check(self) -> dict:
        return {"agent": "my-agent", "status": "healthy"}
```

## Directory Structure (per agent)

```
agents/{name}/
├── agent.py          # Agent class definition and configuration
├── main.py           # Entry point (ECS container command override)
└── {services}.py     # Domain-specific service modules
```

## Pipeline Steps by Agent

### Orchestrator
Coordinates all steps — loads pipeline from DynamoDB, dispatches to agent SQS queues, tracks state.

### IDP (Intelligent Document Processing)
| Step | Subroutine | Description |
|------|-----------|-------------|
| 0100 | FILE_INGEST | Parse vendor file using schema mapping |
| 0200 | FILE_VALIDATION | Validate file structure and format |
| 0300 | MERGE_PAYROLL_FIELDS | Apply payroll fields template |
| 0400 | DROP_V_VARIABLES | Remove vendor-specific columns |
| 0500 | SPLIT_PAY_FREQ | Split by pay frequency |

### Validator
| Step | Subroutine | Description |
|------|-----------|-------------|
| 0900 | SSN_VALIDATION | Validate SSN format and existence |
| 1000 | DATE_CLEANING | Normalize date formats |
| 1200 | EMPLOYMENT_STATUS | Cross-reference Relius for status |
| 1600 | ISSUE_DETECTION | Flag STOP/WARNING issues |

### Transform
| Step | Subroutine | Description |
|------|-----------|-------------|
| 0550 | SPLIT_MONTH_PEO | Split monthly PEO records |
| 0600 | COMPENSATION_CALC | Calculate compensation components |
| 0700 | HOURS_ESTIMATION | Estimate hours for monthly records |
| 0800 | MATCH_CALC | Apply employer match formula |
| 1100 | CONTRIB_RATE_CHECK | Validate contribution rates |
| 1300 | NEGATIVE_PAYROLL | Handle negative payroll adjustments |
| 1400 | DUPLICATE_EMPLOYEE | Detect and merge duplicates |
| 1500 | ER_CONTRIB_CALC | Employer contribution calculation |
| 1700 | TOTALS_BY_PLAN | Aggregate totals per plan |
| 1800 | FILE_EXPORT_CSV | Export to CSV |
| 1900 | FILE_EXPORT_XLS | Export to XLS |
| 2100 | FILE_EXPORT_TXT | Export to TXT |
| 2300 | XML_GENERATION | Generate Relius IMPORT_PAYROLL XML |

### Compliance
| Step | Subroutine | Description |
|------|-----------|-------------|
| 2000 | PLAN_HOLD_CHECK | Check for plan holds |
| 2200 | FORFEITURE_CALC | Apply forfeitures |
| 2400 | ACH_PREP | Prepare ACH file |
| 2500 | DEPWD_DETAIL | Update DepWDDetail |
| 2600 | ACH_CALC | Final ACH calculations |

## Current Status

- **Base agent:** Implemented with DI pattern
- **Agent services:** Placeholder modules with documented interfaces
- **Stage 2:** Full agent implementation with Strands SDK integration

## Key Design Rules

- **Transform agent:** No AI inference for financial calculations — all math is deterministic
- **IDP agent:** Uses SLM for schema inference only; falls back to Bedrock for low-confidence matches
- **Compliance agent:** Uses frontier model (Claude Sonnet) for regulatory reasoning
