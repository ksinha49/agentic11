"""FastMCP server: DynamoDB business rules engine.

Exposes all 8 DynamoDB tables as MCP tools consumed by agents
via Strands' native MCP client.
"""

from __future__ import annotations

# TODO: Implement FastMCP server with tools:
# - get_client_config, get_validation_rules, get_calculation_rule,
#   get_pipeline_steps, get_plan_holds, get_irs_limits, get_ach_config,
#   get_vendor_schema
# All with Redis caching at configured TTLs
