"""ERContribCalcService — step 0800 CALC_ER_CONTRIB (subroutine-calcERamt.do)."""

from __future__ import annotations

# TODO: Implement flat-rate ER contribution
# ercalc = ROUND(level1upto * ercomp, 0.01)
# Eligibility check: planentry > payroll → ercalc = 0
# Annual limit check against 415c and 402g limits
# Target: pshare, shne, or shneqaca
