"""Health check endpoints."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy"}


@router.get("/ready")
async def ready() -> dict[str, str]:
    # TODO: Check DynamoDB, Redis, SQS connectivity
    return {"status": "ready"}
