"""Unit tests for DynamoDBRulesStore using moto."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import boto3
import pytest
from moto import mock_aws

from bluestar.core.exceptions import RuleNotFoundError
from bluestar.persistence.dynamodb_backend import DynamoDBRulesStore
from bluestar.persistence.memory_backend import MemoryCacheBackend

TABLE_SUFFIX = "-test"
REGION = "us-east-1"

# ---------- helpers ----------

def _create_table(client, name: str, pk: str = "PK", sk: str = "SK"):
    """Create a DynamoDB table with PK/SK key schema."""
    client.create_table(
        TableName=name,
        KeySchema=[
            {"AttributeName": pk, "KeyType": "HASH"},
            {"AttributeName": sk, "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": pk, "AttributeType": "S"},
            {"AttributeName": sk, "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )


def _put(table, item: dict[str, Any]):
    table.put_item(Item=item)


# ---------- fixtures ----------

@pytest.fixture
def aws():
    with mock_aws():
        ddb = boto3.resource("dynamodb", region_name=REGION)
        client = boto3.client("dynamodb", region_name=REGION)

        table_names = [
            "bluestar-processing-pipeline",
            "bluestar-validation-rules",
            "bluestar-calculation-rules",
            "bluestar-irs-limits",
            "bluestar-batch-state",
            "bluestar-agent-config",
        ]

        for name in table_names:
            _create_table(client, f"{name}{TABLE_SUFFIX}")

        yield ddb


@pytest.fixture
def store(aws):
    return DynamoDBRulesStore(table_suffix=TABLE_SUFFIX, region=REGION)


@pytest.fixture
def cached_store(aws):
    cache = MemoryCacheBackend()
    return DynamoDBRulesStore(table_suffix=TABLE_SUFFIX, region=REGION, cache=cache), cache


# ---------- get_pipeline_steps ----------

class TestGetPipelineSteps:
    def test_returns_sorted_steps(self, store, aws):
        tbl = aws.Table(f"bluestar-processing-pipeline{TABLE_SUFFIX}")
        _put(tbl, {
            "PK": "CLIENT#ACME_BiWeeklyFri", "SK": "STEP#0200",
            "stepOrder": 200, "subroutineName": "FILE_VALIDATION",
            "agent": "VALIDATOR", "enabled": True, "required": True,
        })
        _put(tbl, {
            "PK": "CLIENT#ACME_BiWeeklyFri", "SK": "STEP#0100",
            "stepOrder": 100, "subroutineName": "FILE_INGEST",
            "agent": "IDP", "enabled": True, "required": True,
        })

        steps = store.get_pipeline_steps("ACME", "BiWeeklyFri")
        assert len(steps) == 2
        assert steps[0]["stepOrder"] == 100
        assert steps[1]["stepOrder"] == 200

    def test_returns_empty_for_unknown_plan(self, store):
        assert store.get_pipeline_steps("NOBODY", "Weekly") == []


# ---------- get_validation_rules ----------

class TestGetValidationRules:
    def test_returns_rules_for_category(self, store, aws):
        tbl = aws.Table(f"bluestar-validation-rules{TABLE_SUFFIX}")
        _put(tbl, {"PK": "CATEGORY#SSN", "SK": "RULE#001", "field": "ssn", "pattern": r"^\d{9}$"})
        _put(tbl, {"PK": "CATEGORY#SSN", "SK": "RULE#002", "field": "ssn", "check": "not_blank"})

        rules = store.get_validation_rules("SSN")
        assert len(rules) == 2

    def test_returns_empty_for_unknown_category(self, store):
        assert store.get_validation_rules("UNKNOWN") == []


# ---------- get_calculation_rule ----------

class TestGetCalculationRule:
    def test_returns_client_specific_rule(self, store, aws):
        tbl = aws.Table(f"bluestar-calculation-rules{TABLE_SUFFIX}")
        _put(tbl, {"PK": "CLIENT#ACME", "SK": "CALC#match", "formula": "ee_pct * comp", "max_pct": Decimal("6")})

        rule = store.get_calculation_rule("ACME", "match")
        assert rule["formula"] == "ee_pct * comp"

    def test_falls_back_to_global(self, store, aws):
        tbl = aws.Table(f"bluestar-calculation-rules{TABLE_SUFFIX}")
        _put(tbl, {"PK": "CLIENT#GLOBAL", "SK": "CALC#match", "formula": "default_match"})

        rule = store.get_calculation_rule("NEWCLIENT", "match")
        assert rule["formula"] == "default_match"

    def test_raises_when_no_rule_exists(self, store):
        with pytest.raises(RuleNotFoundError):
            store.get_calculation_rule("GHOST", "nonexistent")

    def test_caches_result_on_hit(self, cached_store, aws):
        store, cache = cached_store
        tbl = aws.Table(f"bluestar-calculation-rules{TABLE_SUFFIX}")
        _put(tbl, {"PK": "CLIENT#ACME", "SK": "CALC#match", "formula": "cached_formula"})

        store.get_calculation_rule("ACME", "match")
        cached_val = cache.get("calc_rule:ACME:match")
        assert cached_val is not None
        assert "cached_formula" in cached_val


# ---------- get_irs_limits ----------

class TestGetIrsLimits:
    def test_returns_limits_for_year(self, store, aws):
        tbl = aws.Table(f"bluestar-irs-limits{TABLE_SUFFIX}")
        _put(tbl, {"PK": "YEAR#2024", "SK": "LIMITS", "max_401k": Decimal("23000"), "catch_up": Decimal("7500")})

        limits = store.get_irs_limits(2024)
        assert limits["max_401k"] == 23000

    def test_returns_empty_for_unknown_year(self, store):
        assert store.get_irs_limits(1999) == {}


# ---------- get_client_config ----------

class TestGetClientConfig:
    def test_returns_config(self, store, aws):
        tbl = aws.Table(f"bluestar-agent-config{TABLE_SUFFIX}")
        _put(tbl, {"PK": "CLIENT#ACME_BiWeeklyFri", "SK": "CONFIG", "custodian": "Fidelity", "deadline_hour": 16})

        config = store.get_client_config("ACME", "BiWeeklyFri")
        assert config["custodian"] == "Fidelity"

    def test_returns_empty_for_unknown_client(self, store):
        assert store.get_client_config("NOBODY", "Weekly") == {}


# ---------- get_ach_config ----------

class TestGetAchConfig:
    def test_returns_ach_config(self, store, aws):
        tbl = aws.Table(f"bluestar-agent-config{TABLE_SUFFIX}")
        _put(tbl, {"PK": "CLIENT#ACME_BiWeeklyFri", "SK": "ACH", "ach_method": "NACHA", "bank_id": "BK001"})

        config = store.get_ach_config("ACME", "BiWeeklyFri")
        assert config["ach_method"] == "NACHA"

    def test_returns_empty_for_missing(self, store):
        assert store.get_ach_config("NOBODY", "Weekly") == {}


# ---------- get_vendor_schema ----------

class TestGetVendorSchema:
    def test_returns_schema(self, store, aws):
        tbl = aws.Table(f"bluestar-validation-rules{TABLE_SUFFIX}")
        _put(tbl, {"PK": "VENDOR#ADP_ACME_BiWeeklyFri", "SK": "SCHEMA", "columns": ["ssn", "name", "comp"]})

        schema = store.get_vendor_schema("ADP", "ACME", "BiWeeklyFri")
        assert "ssn" in schema["columns"]

    def test_returns_empty_for_missing(self, store):
        assert store.get_vendor_schema("UNKNOWN", "X", "Y") == {}


# ---------- get_plan_holds ----------

class TestGetPlanHolds:
    def test_returns_holds(self, store, aws):
        tbl = aws.Table(f"bluestar-batch-state{TABLE_SUFFIX}")
        _put(tbl, {"PK": "PLAN#ACME", "SK": "HOLD#001", "reason": "Missing data", "created": "2024-01-15"})

        holds = store.get_plan_holds("ACME")
        assert len(holds) == 1
        assert holds[0]["reason"] == "Missing data"

    def test_returns_empty_for_no_holds(self, store):
        assert store.get_plan_holds("CLEAN_PLAN") == []
