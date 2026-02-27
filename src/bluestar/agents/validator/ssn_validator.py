"""SSNValidatorService — step 0900 BAD_SSN (subroutine-BadSSNs.do)."""

from __future__ import annotations

# TODO: Implement SSNValidatorService
# 7 checks: length < 7, length > 9, missing, numeric < 999999,
#   zero group, zero serial, known invalid patterns
# Clean: strip chars, format as %09d, set badssn="Y" on failure
