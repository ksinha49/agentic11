"""Integration tests for DynamoDBRulesStore against LocalStack."""

from __future__ import annotations

import pytest

from bluestar.persistence.dynamodb_backend import DynamoDBRulesStore
from tests.integration.conftest import LOCALSTACK_URL, TABLE_SUFFIX, skip_no_localstack


@skip_no_localstack
class TestDynamoDBIntegration:
    @pytest.fixture
    def store(self, seeded_tables):
        return DynamoDBRulesStore(
            table_suffix=seeded_tables,
            region="us-east-1",
            endpoint_url=LOCALSTACK_URL,
        )

    def test_pipeline_steps_from_seed(self, store):
        steps = store.get_pipeline_steps("DEFAULT", "BiWeeklyFri")
        assert len(steps) == 26
        assert steps[0]["subroutineName"] == "FILE_INGEST"

    def test_global_calc_rule_exists(self, store):
        rule = store.get_calculation_rule("GLOBAL", "match")
        assert "formula" in rule

    def test_irs_limits_2024(self, store):
        limits = store.get_irs_limits(2024)
        assert limits["max_401k"] == 23000

    def test_validation_rules_ssn(self, store):
        rules = store.get_validation_rules("SSN")
        assert len(rules) >= 2
