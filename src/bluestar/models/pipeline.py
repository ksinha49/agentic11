"""Pipeline, batch, and workflow state models."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Optional

from pydantic import BaseModel, Field


class BatchStatus(StrEnum):
    RECEIVED = "RECEIVED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    ESCALATED = "ESCALATED"


class StepStatus(StrEnum):
    PENDING = "PENDING"
    DISPATCHED = "DISPATCHED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class PipelineStep(BaseModel):
    """A single step in the processing pipeline (from DynamoDB)."""

    step_order: int
    subroutine_name: str
    agent: str  # IDP, VALIDATOR, TRANSFORMATION, COMPLIANCE
    enabled: bool = True
    required: bool = True
    depends_on: list[str] = Field(default_factory=list)
    parameters: dict[str, Any] = Field(default_factory=dict)


class StepState(BaseModel):
    """Execution state for a single pipeline step."""

    step_order: int
    status: StepStatus = StepStatus.PENDING
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_ms: Optional[int] = None
    record_count: int = 0
    error_count: int = 0
    warning_count: int = 0
    agent_name: str = ""
    retry_count: int = 0
    error_details: str = ""


class BatchState(BaseModel):
    """Execution state for an entire batch."""

    batch_id: str
    plan_id: str
    pay_freq: str
    s3_path: str
    status: BatchStatus = BatchStatus.RECEIVED
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    steps: list[StepState] = Field(default_factory=list)
    record_count: int = 0
    escalation_reason: str = ""


class EscalationPayload(BaseModel):
    """Context payload for human review escalation."""

    batch_id: str
    plan_id: str
    escalation_reason: str
    failed_step: str = ""
    error_details: str = ""
    record_count: int = 0
    affected_record_count: int = 0
    custodian_deadline: str = ""
    time_remaining: str = ""
