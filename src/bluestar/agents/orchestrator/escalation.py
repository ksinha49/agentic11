"""EscalationRouter — routes exceptions to human review."""

from __future__ import annotations

# TODO: Implement EscalationRouter
# Triggers: required step fails (3 retries), schema confidence < 0.80,
#   STOP issues > 50% records, multiple clientids on hold,
#   deadline at risk (< 30 min), financial anomaly (> 200% variance)
# Action: Send to human-review SQS queue with EscalationPayload
