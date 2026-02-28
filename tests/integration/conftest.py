"""Integration test fixtures — LocalStack DynamoDB, Redis, S3."""

from __future__ import annotations

import os
import sys

import boto3
import pytest

# Default LocalStack endpoint
LOCALSTACK_URL = os.environ.get("LOCALSTACK_URL", "http://localhost:4566")
TABLE_SUFFIX = "-inttest"


def _localstack_available() -> bool:
    """Check if LocalStack is reachable."""
    try:
        client = boto3.client("dynamodb", region_name="us-east-1", endpoint_url=LOCALSTACK_URL)
        client.list_tables()
        return True
    except Exception:
        return False


skip_no_localstack = pytest.mark.skipif(
    not _localstack_available(),
    reason="LocalStack not available",
)


@pytest.fixture(scope="session")
def localstack_ddb():
    """DynamoDB resource pointing at LocalStack."""
    return boto3.resource("dynamodb", region_name="us-east-1", endpoint_url=LOCALSTACK_URL)


@pytest.fixture(scope="session")
def localstack_s3():
    """S3 client pointing at LocalStack."""
    return boto3.client("s3", region_name="us-east-1", endpoint_url=LOCALSTACK_URL)


@pytest.fixture(scope="session")
def seeded_tables(localstack_ddb):
    """Create and seed DynamoDB tables via the seed script."""
    sys.path.insert(0, str(os.path.join(os.path.dirname(__file__), "..", "..", "scripts")))
    from seed_dynamodb import create_tables, seed_pipeline_data

    create_tables(localstack_ddb, suffix=TABLE_SUFFIX)
    seed_pipeline_data(localstack_ddb, suffix=TABLE_SUFFIX)
    return TABLE_SUFFIX
