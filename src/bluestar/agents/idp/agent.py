"""IDP Agent definition — dual-model: in-process SLM + Bedrock escalation."""

from __future__ import annotations

# TODO: Define IDPAgent
# Primary model: In-process SmolLM3 3B (stage 2, mock for now)
# Escalation model: Bedrock Claude Haiku (for unknown schema inference)
# Tools: match_schema, parse_file, destring_fields, learn_new_schema, read_s3_file
