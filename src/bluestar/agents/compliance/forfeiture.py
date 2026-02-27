"""ForfeitureService — step 2200 (subroutine-Forfeitures.do)."""

from __future__ import annotations

# TODO: Implement forfeiture application
# ERTotal = match + shmatch + shmatchqaca + shne + shneqaca + pshare
# EXCLUDED: prevwageer, prevwageqnec (Davis-Bacon Act)
# UseForfs = -MIN(ERTotal, ForfAvail from PayrollForfs ODBC)
# Multi-identifier proportional allocation
