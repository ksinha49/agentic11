"""PipelineExecutor service — loads and executes the ordered pipeline for a client."""

from __future__ import annotations

# TODO: Implement PipelineExecutor
# - Query bluestar-processing-pipeline table (PK=CLIENT#{planId}_{payFreq})
# - Cache in Redis: pipeline:{planId}:{payFreq} / 1 hr TTL
# - Execute steps in order, respecting dependsOn and enabled flags
# - Dispatch to agent SQS queues, wait for completion callbacks
