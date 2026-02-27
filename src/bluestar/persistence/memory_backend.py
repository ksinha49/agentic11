"""In-memory backends for unit tests — dict-backed fakes."""

from __future__ import annotations

from typing import Any


class MemoryRulesStore:
    """Dict-backed IRulesStore for unit tests."""

    def __init__(self) -> None:
        self._configs: dict[str, dict[str, Any]] = {}
        self._validation_rules: dict[str, list[dict[str, Any]]] = {}
        self._calc_rules: dict[str, dict[str, Any]] = {}
        self._pipeline_steps: dict[str, list[dict[str, Any]]] = {}
        self._plan_holds: dict[str, list[dict[str, Any]]] = {}
        self._irs_limits: dict[int, dict[str, Any]] = {}
        self._ach_configs: dict[str, dict[str, Any]] = {}
        self._vendor_schemas: dict[str, dict[str, Any]] = {}

    def get_client_config(self, plan_id: str, pay_freq: str) -> dict[str, Any]:
        return self._configs.get(f"{plan_id}:{pay_freq}", {})

    def get_validation_rules(self, category: str) -> list[dict[str, Any]]:
        return self._validation_rules.get(category, [])

    def get_calculation_rule(self, plan_id: str, calc_type: str) -> dict[str, Any]:
        key = f"{plan_id}:{calc_type}"
        if key in self._calc_rules:
            return self._calc_rules[key]
        return self._calc_rules.get(f"GLOBAL:{calc_type}", {})

    def get_pipeline_steps(self, plan_id: str, pay_freq: str) -> list[dict[str, Any]]:
        return self._pipeline_steps.get(f"{plan_id}:{pay_freq}", [])

    def get_plan_holds(self, plan_id: str) -> list[dict[str, Any]]:
        return self._plan_holds.get(plan_id, [])

    def get_irs_limits(self, year: int) -> dict[str, Any]:
        return self._irs_limits.get(year, {})

    def get_ach_config(self, plan_id: str, pay_freq: str) -> dict[str, Any]:
        return self._ach_configs.get(f"{plan_id}:{pay_freq}", {})

    def get_vendor_schema(self, vendor_id: str, plan_id: str, pay_freq: str) -> dict[str, Any]:
        return self._vendor_schemas.get(f"{vendor_id}:{plan_id}:{pay_freq}", {})


class MemoryCacheBackend:
    """Dict-backed ICacheBackend for unit tests."""

    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    def get(self, key: str) -> str | None:
        return self._store.get(key)

    def setex(self, key: str, ttl: int, value: str) -> None:
        self._store[key] = value

    def delete(self, key: str) -> None:
        self._store.pop(key, None)


class MemoryFileStore:
    """Dict-backed IFileStore for unit tests."""

    def __init__(self) -> None:
        self._files: dict[str, bytes] = {}

    def read(self, path: str) -> bytes:
        return self._files[path]

    def write(self, path: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        self._files[path] = data
        return path

    def move(self, src: str, dst: str) -> None:
        self._files[dst] = self._files.pop(src)

    def list_files(self, prefix: str) -> list[str]:
        return [k for k in self._files if k.startswith(prefix)]


class MemorySQLClient:
    """Canned-response ISQLClient for unit tests."""

    def __init__(self) -> None:
        self._responses: dict[str, list[dict[str, Any]]] = {}

    def query(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        return self._responses.get(sql, [])

    def execute_sp(self, sp_name: str, params: dict[str, Any]) -> dict[str, Any]:
        return self._responses.get(sp_name, {})  # type: ignore[return-value]
