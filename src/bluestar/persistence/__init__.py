"""Pluggable persistence backends behind Protocol interfaces."""

from __future__ import annotations

from bluestar.core.config import AppSettings
from bluestar.persistence.dynamodb_backend import DynamoDBRulesStore
from bluestar.persistence.redis_backend import RedisCacheBackend
from bluestar.persistence.s3_backend import S3FileStore


def create_persistence(settings: AppSettings | None = None):
    """Create wired-up persistence backends from application settings.

    Returns:
        Tuple of (rules_store, cache, file_store).
    """
    if settings is None:
        settings = AppSettings()

    cache = RedisCacheBackend(
        host=settings.redis.host,
        port=settings.redis.port,
        db=settings.redis.db,
    )

    rules_store = DynamoDBRulesStore(
        table_suffix=settings.dynamodb.table_suffix,
        region=settings.dynamodb.region,
        endpoint_url=settings.dynamodb.endpoint_url,
        cache=cache,
    )

    file_store = S3FileStore(
        bucket=settings.s3.bucket,
        region=settings.s3.region,
        endpoint_url=settings.s3.endpoint_url,
    )

    return rules_store, cache, file_store
