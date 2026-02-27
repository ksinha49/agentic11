"""Strands tools for pipeline dispatch and event emission."""

from __future__ import annotations

# TODO: Implement @tool decorated functions:
# - dispatch_step(batch_id, step_order, agent, parameters)
# - emit_event(event_type, detail) → EventBridge
# - check_workflow_state(batch_id) → BatchState
# - escalate_to_human(batch_id, reason, context) → SQS
