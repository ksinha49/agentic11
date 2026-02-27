"""Admin endpoints for pipeline and rules management."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["admin"])


@router.get("/pipeline/{plan_id}/{pay_freq}")
async def get_pipeline(plan_id: str, pay_freq: str) -> dict:
    """Return pipeline configuration for a client."""
    # TODO: Load from DynamoDB rules store
    return {"plan_id": plan_id, "pay_freq": pay_freq, "steps": []}


@router.get("/rules/{category}")
async def get_rules(category: str) -> dict:
    """Return validation rules for a category."""
    # TODO: Load from DynamoDB rules store
    return {"category": category, "rules": []}
