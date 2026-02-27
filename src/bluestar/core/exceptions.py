"""BlueStar exception hierarchy."""

from __future__ import annotations


class BlueStarError(Exception):
    """Base exception for all BlueStar errors."""


class PipelineError(BlueStarError):
    """Error during pipeline execution."""


class StepFailedError(PipelineError):
    """A pipeline step failed."""

    def __init__(self, step_order: int, subroutine: str, message: str) -> None:
        self.step_order = step_order
        self.subroutine = subroutine
        super().__init__(f"Step {step_order} ({subroutine}) failed: {message}")


class EscalationRequired(PipelineError):
    """Condition requires human review escalation."""

    def __init__(self, reason: str, batch_id: str, context: dict | None = None) -> None:
        self.reason = reason
        self.batch_id = batch_id
        self.context = context or {}
        super().__init__(f"Escalation required for batch {batch_id}: {reason}")


class SchemaNotFoundError(BlueStarError):
    """No schema mapping found for vendor file."""


class RuleNotFoundError(BlueStarError):
    """Business rule not found in DynamoDB."""


class CacheError(BlueStarError):
    """Redis cache operation failed."""


class SQLServerError(BlueStarError):
    """On-premises SQL Server query failed."""


class TokenServiceError(BlueStarError):
    """On-premises Token Service (NACHA) call failed."""


class DeadlineAtRiskError(BlueStarError):
    """Custodian deadline at risk."""

    def __init__(self, custodian: str, time_remaining_minutes: int) -> None:
        self.custodian = custodian
        self.time_remaining_minutes = time_remaining_minutes
        super().__init__(f"{custodian} deadline at risk: {time_remaining_minutes} min remaining")
