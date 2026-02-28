# `bluestar/mcp_servers` — Model Context Protocol Servers

FastMCP servers that expose tools to agents via the Strands SDK's native MCP client. Each server wraps a persistence backend as callable tools.

## Servers

| File | Tools Exposed | Backing Service |
|------|--------------|-----------------|
| `file_server.py` | `read_s3_file`, `write_s3_file`, `move_s3_file`, `list_s3_files` | S3 |
| `rules_server.py` | `get_client_config`, `get_validation_rules`, `get_calculation_rule`, etc. | DynamoDB + Redis |
| `sql_server.py` | `query_relius`, `query_employment_status`, `query_contrib_rates`, etc. | SQL Server |

## S3 Path Organization

```
s3://bluestar-files-{env}/
├── dropzone/          # Incoming vendor files
├── inprogress/        # Files being processed
├── validated/         # Files that passed validation
├── failed/            # Files that failed processing
└── output/            # Generated exports (CSV, XLS, XML, ACH)
```

## How Agents Use MCP Tools

In the Strands Graph, agents invoke tools via MCP:

```python
# Agent calls tool → MCP server → S3/DynamoDB/SQL
result = agent.tool("read_s3_file", path="dropzone/acme-2024-01.csv")
rules  = agent.tool("get_validation_rules", category="SSN")
```

## Current Status

All three servers are **Stage 2 placeholders** with documented tool signatures and return types.
