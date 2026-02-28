"""Seed DynamoDB tables with default pipeline and rule configurations.

Usage:
    python scripts/seed_dynamodb.py --endpoint-url http://localhost:4566
"""

from __future__ import annotations

import argparse
import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import boto3

TABLE_DEFINITIONS: list[dict[str, Any]] = [
    {"name": "bluestar-processing-pipeline"},
    {"name": "bluestar-validation-rules"},
    {"name": "bluestar-calculation-rules"},
    {"name": "bluestar-irs-limits"},
    {"name": "bluestar-batch-state"},
    {"name": "bluestar-processing-results"},
    {"name": "bluestar-audit-log"},
    {"name": "bluestar-agent-config"},
]


def create_tables(ddb: Any, suffix: str = "") -> None:
    """Create all 8 DynamoDB tables. Skips if table already exists."""
    client = ddb.meta.client
    existing = client.list_tables().get("TableNames", [])

    for defn in TABLE_DEFINITIONS:
        table_name = f"{defn['name']}{suffix}"
        if table_name in existing:
            print(f"  Table {table_name} already exists, skipping")
            continue
        client.create_table(
            TableName=table_name,
            KeySchema=[
                {"AttributeName": "PK", "KeyType": "HASH"},
                {"AttributeName": "SK", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "PK", "AttributeType": "S"},
                {"AttributeName": "SK", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        print(f"  Created table {table_name}")


def _json_to_dynamodb(obj: Any) -> Any:
    """Convert JSON-parsed floats/ints to Decimal for DynamoDB."""
    if isinstance(obj, float):
        return Decimal(str(obj))
    if isinstance(obj, dict):
        return {k: _json_to_dynamodb(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_json_to_dynamodb(i) for i in obj]
    return obj


def seed_pipeline_data(ddb: Any, suffix: str = "") -> None:
    """Load pipeline_seed.json and seed sample rules/limits."""
    seed_path = Path(__file__).resolve().parent.parent / "config" / "pipeline_seed.json"
    data = json.loads(seed_path.read_text())

    # -- Pipeline steps --
    tbl = ddb.Table(f"bluestar-processing-pipeline{suffix}")
    with tbl.batch_writer() as batch:
        for step in data["steps"]:
            batch.put_item(Item=_json_to_dynamodb(step))
    print(f"  Seeded {len(data['steps'])} pipeline steps")

    # -- Sample validation rules --
    tbl = ddb.Table(f"bluestar-validation-rules{suffix}")
    sample_rules = [
        {
            "PK": "CATEGORY#SSN", "SK": "RULE#001",
            "field": "ssn", "pattern": r"^\d{9}$",
            "message": "SSN must be 9 digits",
        },
        {
            "PK": "CATEGORY#SSN", "SK": "RULE#002",
            "field": "ssn", "check": "not_blank",
            "message": "SSN is required",
        },
        {
            "PK": "CATEGORY#NAME", "SK": "RULE#001",
            "field": "last_name", "check": "not_blank",
            "message": "Last name is required",
        },
        {
            "PK": "CATEGORY#COMP", "SK": "RULE#001",
            "field": "compensation", "check": "positive_number",
            "message": "Compensation must be positive",
        },
    ]
    with tbl.batch_writer() as batch:
        for rule in sample_rules:
            batch.put_item(Item=rule)
    print(f"  Seeded {len(sample_rules)} validation rules")

    # -- GLOBAL calculation rules --
    tbl = ddb.Table(f"bluestar-calculation-rules{suffix}")
    global_rules = [
        {
            "PK": "CLIENT#GLOBAL", "SK": "CALC#match",
            "formula": "ee_deferral_pct * compensation",
            "max_pct": Decimal("6"),
            "description": "Default employer match",
        },
        {
            "PK": "CLIENT#GLOBAL", "SK": "CALC#er_contrib",
            "formula": "compensation * er_pct",
            "max_pct": Decimal("3"),
            "description": "Default ER contribution",
        },
        {
            "PK": "CLIENT#GLOBAL", "SK": "CALC#catch_up",
            "formula": "min(excess, irs_catch_up_limit)",
            "age_threshold": 50,
            "description": "Catch-up contribution calc",
        },
    ]
    with tbl.batch_writer() as batch:
        for rule in global_rules:
            batch.put_item(Item=rule)
    print(f"  Seeded {len(global_rules)} GLOBAL calculation rules")

    # -- IRS limits --
    tbl = ddb.Table(f"bluestar-irs-limits{suffix}")
    irs_data = [
        {
            "PK": "YEAR#2024", "SK": "LIMITS",
            "max_401k": Decimal("23000"), "catch_up": Decimal("7500"),
            "comp_limit": Decimal("345000"), "annual_addition": Decimal("69000"),
        },
        {
            "PK": "YEAR#2025", "SK": "LIMITS",
            "max_401k": Decimal("23500"), "catch_up": Decimal("7500"),
            "comp_limit": Decimal("350000"), "annual_addition": Decimal("70000"),
        },
    ]
    with tbl.batch_writer() as batch:
        for item in irs_data:
            batch.put_item(Item=item)
    print(f"  Seeded IRS limits for {len(irs_data)} years")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed DynamoDB tables for BlueStar")
    parser.add_argument("--endpoint-url", default=None, help="DynamoDB endpoint (e.g. http://localhost:4566)")
    parser.add_argument("--table-suffix", default="", help="Table name suffix (e.g. -dev)")
    parser.add_argument("--region", default="us-east-1", help="AWS region")
    args = parser.parse_args()

    kwargs: dict[str, Any] = {"region_name": args.region}
    if args.endpoint_url:
        kwargs["endpoint_url"] = args.endpoint_url

    ddb = boto3.resource("dynamodb", **kwargs)

    print("Creating tables...")
    create_tables(ddb, suffix=args.table_suffix)

    print("Seeding data...")
    seed_pipeline_data(ddb, suffix=args.table_suffix)

    print("Done!")


if __name__ == "__main__":
    main()
