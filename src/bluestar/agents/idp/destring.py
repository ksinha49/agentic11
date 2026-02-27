"""DestringService — converts string-encoded numeric fields to actual numbers."""

from __future__ import annotations

# TODO: Implement DestringService (step 0500)
# - Strip ignore chars from numeric fields
# - Handle trailing negatives (123.45- → -123.45) BEFORE numeric conversion
# - Convert to Decimal, set 0 on failure
# - Sum multi-instance fields (salary1-salary10 → salary)
# - Null replacement: empty numeric → 0
