"""Tests for DynamoDB seed script."""

from __future__ import annotations

import sys
from pathlib import Path

import boto3
import pytest
from moto import mock_aws

# Make scripts/ importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "scripts"))

from seed_dynamodb import create_tables, seed_pipeline_data  # noqa: E402


@pytest.fixture
def ddb():
    with mock_aws():
        yield boto3.resource("dynamodb", region_name="us-east-1")


class TestCreateTables:
    def test_creates_all_eight_tables(self, ddb):
        create_tables(ddb, suffix="-test")
        client = boto3.client("dynamodb", region_name="us-east-1")
        tables = client.list_tables()["TableNames"]
        assert len(tables) == 8
        assert "bluestar-processing-pipeline-test" in tables

    def test_idempotent_skips_existing(self, ddb):
        create_tables(ddb, suffix="-test")
        create_tables(ddb, suffix="-test")  # should not raise
        client = boto3.client("dynamodb", region_name="us-east-1")
        assert len(client.list_tables()["TableNames"]) == 8


class TestSeedPipelineData:
    def test_seeds_26_pipeline_steps(self, ddb):
        create_tables(ddb, suffix="-test")
        seed_pipeline_data(ddb, suffix="-test")
        tbl = ddb.Table("bluestar-processing-pipeline-test")
        resp = tbl.scan()
        assert resp["Count"] == 27

    def test_seeds_sample_validation_rules(self, ddb):
        create_tables(ddb, suffix="-test")
        seed_pipeline_data(ddb, suffix="-test")
        tbl = ddb.Table("bluestar-validation-rules-test")
        resp = tbl.scan()
        assert resp["Count"] > 0

    def test_seeds_global_calc_rules(self, ddb):
        create_tables(ddb, suffix="-test")
        seed_pipeline_data(ddb, suffix="-test")
        tbl = ddb.Table("bluestar-calculation-rules-test")
        resp = tbl.scan()
        items = resp["Items"]
        global_items = [i for i in items if i["PK"].startswith("CLIENT#GLOBAL")]
        assert len(global_items) > 0

    def test_seeds_irs_limits(self, ddb):
        create_tables(ddb, suffix="-test")
        seed_pipeline_data(ddb, suffix="-test")
        tbl = ddb.Table("bluestar-irs-limits-test")
        resp = tbl.scan()
        assert resp["Count"] > 0
