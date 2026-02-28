"""DynamoDB backend implementing IRulesStore with Redis caching."""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

import boto3

from bluestar.core.exceptions import RuleNotFoundError


class _DecimalEncoder(json.JSONEncoder):
    """Encode Decimal values as int or float for JSON serialization."""

    def default(self, o: Any) -> Any:
        if isinstance(o, Decimal):
            return int(o) if o == int(o) else float(o)
        return super().default(o)


def _decode_decimals(item: dict[str, Any]) -> dict[str, Any]:
    """Convert Decimal values in a DynamoDB item to int/float."""
    out: dict[str, Any] = {}
    for k, v in item.items():
        if isinstance(v, Decimal):
            out[k] = int(v) if v == int(v) else float(v)
        elif isinstance(v, dict):
            out[k] = _decode_decimals(v)
        elif isinstance(v, list):
            out[k] = [
                _decode_decimals(i) if isinstance(i, dict)
                else (int(i) if isinstance(i, Decimal) and i == int(i) else float(i) if isinstance(i, Decimal) else i)
                for i in v
            ]
        else:
            out[k] = v
    return out


class DynamoDBRulesStore:
    """Production IRulesStore backed by DynamoDB + optional Redis cache."""

    CACHE_TTL = 300  # 5 minutes

    def __init__(self, table_suffix: str = "", region: str = "us-east-1",
                 endpoint_url: str | None = None, cache: Any = None) -> None:
        self._table_suffix = table_suffix
        self._region = region
        self._endpoint_url = endpoint_url
        self._cache = cache
        kwargs: dict = {"region_name": region}
        if endpoint_url:
            kwargs["endpoint_url"] = endpoint_url
        self._ddb = boto3.resource("dynamodb", **kwargs)

    def _table(self, base: str):
        return self._ddb.Table(f"{base}{self._table_suffix}")

    def _query_pk(self, table_base: str, pk: str) -> list[dict[str, Any]]:
        """Query all items with a given partition key."""
        tbl = self._table(table_base)
        resp = tbl.query(
            KeyConditionExpression="PK = :pk",
            ExpressionAttributeValues={":pk": pk},
        )
        return [_decode_decimals(item) for item in resp.get("Items", [])]

    def _get_item(self, table_base: str, pk: str, sk: str) -> dict[str, Any] | None:
        """Get a single item by PK + SK. Returns None if not found."""
        tbl = self._table(table_base)
        resp = tbl.get_item(Key={"PK": pk, "SK": sk})
        item = resp.get("Item")
        return _decode_decimals(item) if item else None

    # ---- IRulesStore methods ----

    def get_client_config(self, plan_id: str, pay_freq: str) -> dict[str, Any]:
        item = self._get_item("bluestar-agent-config", f"CLIENT#{plan_id}_{pay_freq}", "CONFIG")
        return item or {}

    def get_validation_rules(self, category: str) -> list[dict[str, Any]]:
        return self._query_pk("bluestar-validation-rules", f"CATEGORY#{category}")

    def get_calculation_rule(self, plan_id: str, calc_type: str) -> dict[str, Any]:
        cache_key = f"calc_rule:{plan_id}:{calc_type}"

        # Check cache first
        if self._cache is not None:
            cached = self._cache.get(cache_key)
            if cached is not None:
                return json.loads(cached)

        # Try client-specific rule
        item = self._get_item("bluestar-calculation-rules", f"CLIENT#{plan_id}", f"CALC#{calc_type}")

        # Fallback to GLOBAL
        if item is None:
            item = self._get_item("bluestar-calculation-rules", "CLIENT#GLOBAL", f"CALC#{calc_type}")

        if item is None:
            raise RuleNotFoundError(
                f"No calculation rule for plan_id={plan_id!r}, calc_type={calc_type!r}"
            )

        # Write to cache
        if self._cache is not None:
            self._cache.setex(cache_key, self.CACHE_TTL, json.dumps(item, cls=_DecimalEncoder))

        return item

    def get_pipeline_steps(self, plan_id: str, pay_freq: str) -> list[dict[str, Any]]:
        items = self._query_pk("bluestar-processing-pipeline", f"CLIENT#{plan_id}_{pay_freq}")
        return sorted(items, key=lambda x: x.get("stepOrder", 0))

    def get_plan_holds(self, plan_id: str) -> list[dict[str, Any]]:
        return self._query_pk("bluestar-batch-state", f"PLAN#{plan_id}")

    def get_irs_limits(self, year: int) -> dict[str, Any]:
        item = self._get_item("bluestar-irs-limits", f"YEAR#{year}", "LIMITS")
        return item or {}

    def get_ach_config(self, plan_id: str, pay_freq: str) -> dict[str, Any]:
        item = self._get_item("bluestar-agent-config", f"CLIENT#{plan_id}_{pay_freq}", "ACH")
        return item or {}

    def get_vendor_schema(self, vendor_id: str, plan_id: str, pay_freq: str) -> dict[str, Any]:
        item = self._get_item(
            "bluestar-validation-rules", f"VENDOR#{vendor_id}_{plan_id}_{pay_freq}", "SCHEMA"
        )
        return item or {}
