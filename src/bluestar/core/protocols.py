"""Protocol interfaces for all BlueStar abstractions.

All inter-layer communication uses these Protocols — structural typing,
no inheritance required, easy to test with isinstance().
"""

from __future__ import annotations

from typing import Any, Protocol, TypeVar, runtime_checkable

T = TypeVar("T")


# ---------------------------------------------------------------------------
# Model Provider
# ---------------------------------------------------------------------------

@runtime_checkable
class IModelProvider(Protocol):
    """Abstraction over LLM providers (mock, in-process SLM, Bedrock)."""

    def chat(self, messages: list[dict[str, str]], **kwargs: Any) -> str: ...

    def structured_output(
        self, messages: list[dict[str, str]], response_model: type[T], **kwargs: Any
    ) -> T: ...


# ---------------------------------------------------------------------------
# Persistence: Rules Store
# ---------------------------------------------------------------------------

@runtime_checkable
class IRulesStore(Protocol):
    """DynamoDB business rules engine with Redis caching."""

    def get_client_config(self, plan_id: str, pay_freq: str) -> dict[str, Any]: ...

    def get_validation_rules(self, category: str) -> list[dict[str, Any]]: ...

    def get_calculation_rule(self, plan_id: str, calc_type: str) -> dict[str, Any]: ...

    def get_pipeline_steps(self, plan_id: str, pay_freq: str) -> list[dict[str, Any]]: ...

    def get_plan_holds(self, plan_id: str) -> list[dict[str, Any]]: ...

    def get_irs_limits(self, year: int) -> dict[str, Any]: ...

    def get_ach_config(self, plan_id: str, pay_freq: str) -> dict[str, Any]: ...

    def get_vendor_schema(self, vendor_id: str, plan_id: str, pay_freq: str) -> dict[str, Any]: ...


# ---------------------------------------------------------------------------
# Persistence: Cache Backend
# ---------------------------------------------------------------------------

@runtime_checkable
class ICacheBackend(Protocol):
    """Redis-compatible cache interface."""

    def get(self, key: str) -> str | None: ...

    def setex(self, key: str, ttl: int, value: str) -> None: ...

    def delete(self, key: str) -> None: ...


# ---------------------------------------------------------------------------
# Persistence: File Store
# ---------------------------------------------------------------------------

@runtime_checkable
class IFileStore(Protocol):
    """S3-compatible file storage interface."""

    def read(self, path: str) -> bytes: ...

    def write(self, path: str, data: bytes, content_type: str = "application/octet-stream") -> str: ...

    def move(self, src: str, dst: str) -> None: ...

    def list_files(self, prefix: str) -> list[str]: ...


# ---------------------------------------------------------------------------
# SQL Server Client
# ---------------------------------------------------------------------------

@runtime_checkable
class ISQLClient(Protocol):
    """On-premises SQL Server (Relius/PlanConnect) query interface."""

    def query(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]: ...

    def execute_sp(self, sp_name: str, params: dict[str, Any]) -> dict[str, Any]: ...


# ---------------------------------------------------------------------------
# Token Service (NACHA)
# ---------------------------------------------------------------------------

@runtime_checkable
class ITokenService(Protocol):
    """On-premises Token Service for NACHA bank data resolution."""

    def resolve(self, sefa_id1: str, sefa_id2: str, sefa_id3: str) -> dict[str, Any]: ...


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

@runtime_checkable
class IOrchestrator(Protocol):
    """Pipeline orchestration abstraction (SQS or Strands Graph)."""

    async def dispatch_step(
        self, batch_id: str, step_order: int, agent: str, parameters: dict[str, Any]
    ) -> dict[str, Any]: ...

    async def run_pipeline(
        self, batch_id: str, plan_id: str, pay_freq: str, s3_path: str
    ) -> dict[str, Any]: ...


# ---------------------------------------------------------------------------
# Workflow State
# ---------------------------------------------------------------------------

@runtime_checkable
class IWorkflowState(Protocol):
    """Batch and step state tracking."""

    async def get_batch_state(self, batch_id: str) -> dict[str, Any]: ...

    async def update_step_state(
        self, batch_id: str, step_order: int, status: str, **metadata: Any
    ) -> None: ...

    async def update_batch_state(self, batch_id: str, status: str, **metadata: Any) -> None: ...
