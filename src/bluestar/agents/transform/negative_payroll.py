"""NegativePayrollService — step 1800 (subroutine-negativepayroll.do)."""

from __future__ import annotations

# TODO: Implement negative zeroing
# Zero all 12 contribution fields where value < 0
# CRITICAL ordering: totals_inclneg (1700) → this (1800) → totals_exclneg (1900)
