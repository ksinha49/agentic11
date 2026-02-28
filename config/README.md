# `config/` — Runtime Configuration

Static configuration files loaded at application startup.

## Files

### `pipeline_seed.json`

The default 27-step processing pipeline loaded into DynamoDB:

```json
{
  "PK": "CLIENT#DEFAULT_BiWeeklyFri",
  "SK": "STEP#0100",
  "stepOrder": 100,
  "subroutineName": "FILE_INGEST",
  "agent": "IDP",
  "enabled": true,
  "required": true
}
```

Each step defines:
- **PK/SK** — DynamoDB composite key
- **stepOrder** — Execution order (0100–2600)
- **subroutineName** — Human-readable step name
- **agent** — Which agent handles this step (IDP, VALIDATOR, TRANSFORM, COMPLIANCE)
- **enabled** — Can be toggled per-client
- **required** — Whether failure stops the pipeline

Used by `scripts/seed_dynamodb.py` to populate the `bluestar-processing-pipeline` table.

### `litellm_config.yaml`

LiteLLM proxy configuration for routing Bedrock API calls:

- **Model routes** — Maps agent names to Bedrock models (Claude Sonnet, Claude Haiku)
- **Router settings** — Retry count (3), timeout (60s), fallback chains
- **Guardrails** — PII filter on Compliance agent calls
- **Budget** — $300/month spend limit with tracking

## Modifying the Pipeline

To add/remove/reorder steps:

1. Edit `pipeline_seed.json`
2. Re-run: `python scripts/seed_dynamodb.py --endpoint-url http://localhost:4566`
3. Update tests in `tests/unit/test_seed_dynamodb.py` if step count changes
