"""Business rule models loaded from DynamoDB."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Optional

from pydantic import BaseModel, Field


class ValidationRule(BaseModel):
    """A validation rule from bluestar-validation-rules table."""

    category: str
    rule_id: str
    checks: list[dict[str, Any]] = Field(default_factory=list)
    invalid_values: list[str] = Field(default_factory=list)
    thresholds: dict[str, Any] = Field(default_factory=dict)


class MatchFormula(BaseModel):
    """Two-tier employer match formula from bluestar-business-calculation-rules."""

    level1pct: Decimal = Decimal("0")
    level1upto: Decimal = Decimal("0")
    level2pct: Decimal = Decimal("0")
    level2upto: Decimal = Decimal("0")
    off_calendar_year: bool = False
    target_source: str = "match"  # match, shmatch, or shmatchqaca
    enabled: bool = False


class ERContribFormula(BaseModel):
    """Flat-rate ER contribution formula."""

    level1upto: Decimal = Decimal("0")
    target_field: str = "pshare"  # pshare, shne, or shneqaca
    enabled: bool = False


class CompensationFormula(BaseModel):
    """Compensation calculation formula per client."""

    plancomp_components: list[str] = Field(
        default_factory=lambda: ["salary", "bonus", "commissions", "overtime"]
    )
    matchcomp_components: list[str] = Field(
        default_factory=lambda: ["salary", "bonus", "commissions", "overtime"]
    )
    ercomp_components: list[str] = Field(
        default_factory=lambda: ["salary", "bonus", "commissions", "overtime"]
    )
    custom_adjustments: list[dict[str, Any]] = Field(default_factory=list)


class IRSLimits(BaseModel):
    """IRS annual limits from bluestar-compliance-limits."""

    year: int
    limit_402g_deferral: Decimal = Decimal("0")
    limit_401a17_comp: Decimal = Decimal("0")
    limit_415c_defined_contrib: Decimal = Decimal("0")
    catchup_limit: Decimal = Decimal("0")


class HoldRule(BaseModel):
    """Plan hold rule from bluestar-plan-hold-rules."""

    plan_id: str
    client_id: str
    hold_reason_cd: str = ""
    hold_reason: str = ""
    hold_as_of_date: Optional[str] = None
    max_start_date: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    addl_info: str = ""
