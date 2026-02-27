"""Canonical Payroll Record — the normalized structure all agents operate on.

Every vendor file, regardless of source format, is parsed into this schema.
Fields are sourced from the data-model-reference.md specification.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class CanonicalPayrollRecord(BaseModel):
    """Single employee payroll record in canonical format."""

    # --- Identity Fields ---
    planid: str = ""
    planidfreq: str = ""  # Computed: planid + "_" + payFreqDesc
    clientid: str = ""
    ssn: str = ""

    # --- Demographic Fields ---
    fname: str = ""
    lname: str = ""
    mname: str = ""
    dob: Optional[date] = None
    email: str = ""
    street1: str = ""
    street2: str = ""
    city: str = ""
    state: str = ""
    zip: str = ""
    phone: str = ""
    gender: str = ""
    maritalstatus: str = ""

    # --- Employment Fields ---
    doh: Optional[date] = None  # Date of hire
    dot: Optional[date] = None  # Date of termination
    dor: Optional[date] = None  # Date of rehire
    payfreq: str = ""  # W/B/S/M/Q/A

    # --- Compensation Fields ---
    hours: Decimal = Decimal("0")
    salary: Decimal = Decimal("0")
    bonus: Decimal = Decimal("0")
    commissions: Decimal = Decimal("0")
    overtime: Decimal = Decimal("0")
    plancomp: Decimal = Decimal("0")  # Computed by CompensationCalcService
    matchcomp: Decimal = Decimal("0")  # Computed by CompensationCalcService
    ercomp: Decimal = Decimal("0")  # Computed by CompensationCalcService

    # --- Contribution Fields (12 source types) ---
    deferral: Decimal = Decimal("0")
    rothdeferral: Decimal = Decimal("0")
    match: Decimal = Decimal("0")
    shmatch: Decimal = Decimal("0")
    shmatchqaca: Decimal = Decimal("0")
    pshare: Decimal = Decimal("0")
    shne: Decimal = Decimal("0")
    shneqaca: Decimal = Decimal("0")
    loan: Decimal = Decimal("0")
    prevwageer: Decimal = Decimal("0")
    prevwageqnec: Decimal = Decimal("0")
    aftertax: Decimal = Decimal("0")

    # --- Validation & Classification Fields ---
    badssn: str = ""  # "Y" if SSN fails validation
    issue: str = ""  # STOP-level issue messages (concatenated)
    warning: str = ""  # WARNING-level messages (concatenated)
    eetype: str = ""
    eesubtype: str = ""
    planhold: str = ""  # "False", "True", "TrueEligRun", "True-Revoked"
    planholdnote: str = ""
    rehirewithoutdot: int = 0

    # --- Processing Metadata ---
    identifier: str = ""  # Multi-file location identifier
    batchid: str = ""
    grosscomp: Decimal = Decimal("0")
    annualcomp: Decimal = Decimal("0")

    model_config = {"str_strip_whitespace": True}

    @property
    def total_contributions(self) -> Decimal:
        """Sum of all 12 contribution fields."""
        return (
            self.deferral + self.rothdeferral + self.match + self.shmatch
            + self.shmatchqaca + self.pshare + self.shne + self.shneqaca
            + self.loan + self.prevwageer + self.prevwageqnec + self.aftertax
        )

    @property
    def er_total(self) -> Decimal:
        """Employer contribution total (excludes prevailing wage per Davis-Bacon)."""
        return (
            self.match + self.shmatch + self.shmatchqaca
            + self.shne + self.shneqaca + self.pshare
        )
