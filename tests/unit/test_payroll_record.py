"""Tests for CanonicalPayrollRecord model."""

from __future__ import annotations

from decimal import Decimal

from bluestar.models.payroll_record import CanonicalPayrollRecord


def test_default_record_has_zero_contributions():
    record = CanonicalPayrollRecord()
    assert record.total_contributions == Decimal("0")


def test_er_total_excludes_prevailing_wage():
    record = CanonicalPayrollRecord(
        match=Decimal("100"),
        shmatch=Decimal("50"),
        pshare=Decimal("75"),
        prevwageer=Decimal("200"),  # Should NOT be in er_total
    )
    assert record.er_total == Decimal("225")  # 100 + 50 + 0 + 0 + 0 + 75


def test_total_contributions_sums_all_12_fields():
    record = CanonicalPayrollRecord(
        deferral=Decimal("100"),
        rothdeferral=Decimal("50"),
        match=Decimal("75"),
        loan=Decimal("25"),
    )
    assert record.total_contributions == Decimal("250")
