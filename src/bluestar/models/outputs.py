"""Output file models: ACH, XML, exports."""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

from pydantic import BaseModel


class ACHRecord(BaseModel):
    """Single ACH file record for NACHA-compliant output."""

    plan_id: str
    sefa_id1: str = ""
    sefa_id2: str = ""
    sefa_id3: str = ""
    total_amt: Decimal = Decimal("0")
    er_amt: Decimal = Decimal("0")
    ee_amt: Decimal = Decimal("0")
    loan_pymt_amt: Decimal = Decimal("0")
    roth_amt: Decimal = Decimal("0")
    after_tax_amt: Decimal = Decimal("0")
    rollover_amt: Decimal = Decimal("0")
    transfer_amt: Decimal = Decimal("0")
    misc_amt: Decimal = Decimal("0")
    request_date: str = ""
    trust_description: str = ""
    dep_wd_category_cd: str = "P"
    create_source: str = "F"
    import_status: int = 0
    negative_source_ind: int = 0


class XMLPayload(BaseModel):
    """Relius IMPORT_PAYROLL XML generation parameters."""

    plan_id: str
    ein: str = ""
    year_end_date: str = ""
    freq_code: str = ""
    sequence_number: int = 0
    pay_period_end_date: str = ""
    der_name: str = ""
    der_file_path: str = ""
    allocation_date: str = ""


class ExportFile(BaseModel):
    """Metadata for an exported output file."""

    filename: str
    file_type: str  # csv, xls, xml, txt
    s3_path: str = ""
    record_count: int = 0
    plan_id: str = ""
    description: str = ""


class PlanTotals(BaseModel):
    """Aggregated totals for a plan."""

    plan_id: str
    deferral: Decimal = Decimal("0")
    rothdeferral: Decimal = Decimal("0")
    match: Decimal = Decimal("0")
    shmatch: Decimal = Decimal("0")
    pshare: Decimal = Decimal("0")
    shne: Decimal = Decimal("0")
    loan: Decimal = Decimal("0")
    shmatchqaca: Decimal = Decimal("0")
    shneqaca: Decimal = Decimal("0")
    prevwageer: Decimal = Decimal("0")
    prevwageqnec: Decimal = Decimal("0")
    aftertax: Decimal = Decimal("0")
    grand_total: Decimal = Decimal("0")
    no_payroll: bool = False  # True if grand total rounds to 0.00

    @property
    def computed_grand_total(self) -> Decimal:
        return (
            self.deferral + self.rothdeferral + self.match + self.shmatch
            + self.pshare + self.shne + self.loan + self.shmatchqaca
            + self.shneqaca + self.prevwageer + self.prevwageqnec + self.aftertax
        )


class ForfeitureResult(BaseModel):
    """Result of forfeiture application for a plan."""

    plan_id: str
    er_total: Decimal = Decimal("0")
    forfeiture_available: Decimal = Decimal("0")
    forfeiture_applied: Decimal = Decimal("0")
    identifier: Optional[str] = None
