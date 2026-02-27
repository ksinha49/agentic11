"""Bedrock model provider via LiteLLM proxy.

Used by Orchestrator and Compliance agents for frontier reasoning.
"""

from __future__ import annotations

# TODO (Stage 2): Implement BedrockModelProvider
# - Route through LiteLLM proxy at configured base_url
# - Support Claude Sonnet (orchestrator/compliance) and Claude Haiku (IDP escalation)
# - Integrate Bedrock Guardrails for PII filtering on Compliance agent calls
