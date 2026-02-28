# `scripts/` — Operational Scripts

Setup and maintenance scripts for the BlueStar platform.

## Scripts

### `seed_dynamodb.py` — DynamoDB Table Setup

Creates all 8 DynamoDB tables and seeds them with sample data.

```bash
# Against LocalStack (development)
python scripts/seed_dynamodb.py --endpoint-url http://localhost:4566

# Against real AWS (with custom suffix)
python scripts/seed_dynamodb.py --table-suffix "-prod" --region us-east-1

# Options
python scripts/seed_dynamodb.py --help
  --endpoint-url    LocalStack or DynamoDB endpoint
  --table-suffix    Appended to all table names (e.g., "-dev", "-inttest")
  --region          AWS region (default: us-east-1)
```

**What it creates:**

| Table | Seed Data |
|-------|-----------|
| `bluestar-processing-pipeline` | 27 pipeline steps from `config/pipeline_seed.json` |
| `bluestar-validation-rules` | 4 sample rules (SSN, NAME, COMP) |
| `bluestar-calculation-rules` | 3 GLOBAL rules (match, er_contrib, catch_up) |
| `bluestar-irs-limits` | 2024 and 2025 IRS contribution limits |
| `bluestar-agent-config` | (empty) |
| `bluestar-vendor-schema-mapping` | (empty) |
| `bluestar-batch-state` | (empty) |
| `bluestar-processing-metadata` | (empty) |

Tables are created idempotently — re-running skips existing tables.

### `download_models.py` — GGUF Model Download (Stage 2)

Downloads quantized models for in-process SLM inference:

| Model | Size | Agent |
|-------|------|-------|
| SmolLM3 3B (Q4_K_M) | ~2.2 GB | IDP |
| Arcee AFM 4.5B (Q4_K_M) | ~3 GB | Validator |
| Phi-4 Mini 3.8B (Q4_K_M) | ~2.5 GB | Transform |
