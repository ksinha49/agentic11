# `bluestar/skills` — Strands Agent Tools

`@tool`-decorated functions that agents invoke during pipeline execution. Each tool wraps a persistence or orchestration operation with type-safe parameters.

## Tool Files

| File | Tools | Used By |
|------|-------|---------|
| `pipeline_tools.py` | `dispatch_step`, `emit_event`, `check_workflow_state`, `escalate_to_human` | Orchestrator |
| `rules_tools.py` | `get_client_config`, `get_validation_rules`, `get_calculation_rule`, `get_irs_limits`, `get_plan_holds`, `get_pipeline_steps` | All agents |
| `sql_tools.py` | `query_relius`, `query_employment_status`, `query_original_doh`, `query_contrib_rates`, `query_ytd`, `query_forfeiture_balance` | Validator, Compliance |
| `s3_tools.py` | `read_s3_file`, `write_s3_file`, `move_s3_file`, `list_s3_files` | All agents |

## Skills vs MCP Servers

Both expose the same operations, but through different mechanisms:

- **Skills** — Python `@tool` functions for direct Strands agent invocation
- **MCP Servers** — FastMCP servers for network-based tool access

In production, MCP servers are preferred. Skills serve as a lightweight alternative for testing and single-process execution.

## Current Status

All tool modules are **Stage 2 placeholders** with documented function signatures.
