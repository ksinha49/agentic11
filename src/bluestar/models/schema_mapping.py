"""Vendor schema mapping models for IDP Agent."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ColumnMapping(BaseModel):
    """Mapping from a vendor file column to a canonical payroll field."""

    position: int
    source_field: str
    target_field: str
    data_type: str = "string"  # string, numeric, date
    confidence: float = 1.0


class DestringConfig(BaseModel):
    """Configuration for numeric destringing."""

    ignore_chars: list[str] = Field(
        default_factory=lambda: ["-", ".", " ", "*", "x", "X", "$", ",", "(", ")"]
    )
    trailing_negative_handling: bool = False
    numeric_fields: list[str] = Field(
        default_factory=lambda: [
            "hours", "salary", "bonus", "commissions", "overtime",
            "deferral", "rothdeferral", "match", "shmatch", "shne", "pshare",
            "loan", "shmatchqaca", "shneqaca", "prevwageer", "prevwageqnec",
            "aftertax", "grosscomp", "plancomp", "matchcomp", "annualcomp",
        ]
    )


class VendorSchemaMapping(BaseModel):
    """Complete schema mapping for a vendor file format."""

    vendor_id: str
    plan_id: str
    pay_freq: str
    version: int = 1
    fingerprint: str = ""
    confidence_score: float = 0.0
    file_format: str = "CSV"  # CSV, TSV, XLSX, FIXED
    delimiter: str = ","
    has_header: bool = True
    data_start_row: int = 0
    column_mappings: list[ColumnMapping] = Field(default_factory=list)
    destring_config: DestringConfig = DestringConfig()
    post_import_drop_rules: list[dict[str, Any]] = Field(default_factory=list)
    file_validation_pattern: str = ""
    file_validation_field: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
