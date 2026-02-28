# `bluestar/models` — Data Models

Pydantic models representing every data structure in the system. All agents operate on these canonical types — no vendor-specific schemas leak past the IDP agent.

## Files

| File | Key Models | Purpose |
|------|-----------|---------|
| `payroll_record.py` | `CanonicalPayrollRecord` | The 60+ field record every agent reads/writes |
| `pipeline.py` | `BatchState`, `PipelineStep`, `StepState` | Workflow execution tracking |
| `rules.py` | `MatchFormula`, `IRSLimits`, `HoldRule` | Business rules from DynamoDB |
| `outputs.py` | `ACHRecord`, `XMLPayload`, `PlanTotals` | Output file structures |
| `schema_mapping.py` | `VendorSchemaMapping`, `ColumnMapping` | Vendor file parsing metadata |

## `CanonicalPayrollRecord`

The central data model — every vendor file is parsed into this format:

```python
from bluestar.models.payroll_record import CanonicalPayrollRecord

record = CanonicalPayrollRecord(planid="ACME", ssn="123456789", fname="Jane", ...)

# 12 contribution types
record.deferral     # Employee deferral
record.roth         # Roth contribution
record.match        # Employer match
record.shmatch      # Safe harbor match
record.pshare       # Profit sharing
record.shne         # Safe harbor non-elective
record.loan         # Loan repayment
record.rollover     # Rollover
record.prevwage     # Prevailing wage
record.qnec         # Qualified non-elective
record.qmatch       # Qualified match
record.eeroth       # Employee Roth (after-tax)

# Computed properties
record.total_contributions  # Sum of all 12 contribution fields
record.er_total             # Employer total (excludes prevailing wage)
```

## Pipeline Models (`pipeline.py`)

```
BatchStatus:  RECEIVED → PROCESSING → COMPLETED | FAILED | ESCALATED
StepStatus:   PENDING → DISPATCHED → PROCESSING → COMPLETED | FAILED | SKIPPED
```

`BatchState` tracks the full pipeline execution — each step has a `StepState` with timing, record counts, and error details.

## Business Rules (`rules.py`)

Loaded from DynamoDB via `IRulesStore`:

- **`MatchFormula`** — Two-tier employer match (e.g., 100% of first 3%, 50% of next 2%)
- **`ERContribFormula`** — Flat-rate employer contribution
- **`IRSLimits`** — Annual limits: 402g ($23,000), 415c ($69,000), catch-up ($7,500)
- **`HoldRule`** — Plan holds with effective dates and reasons

## Conventions

- All financial fields use `Decimal` for precision (no floats)
- Optional dates (`doh`, `dot`, `dor`) for employment tracking
- Validation flags (`badssn`, `issue`, `warning`, `planhold`) set by Validator agent
- All models are Pydantic `BaseModel` — use `.model_dump()` for serialization
