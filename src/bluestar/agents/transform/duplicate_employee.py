"""DuplicateEmployeeService — step 1300 (subroutine-DuplicateEmployees.do)."""

from __future__ import annotations

# TODO: Implement duplicate consolidation
# Tag duplicates by planid+ssn, aggregate financial fields (SUM),
# MIN for dob/doh, MAX for dot/dor, keep row with non-zero salary + highest comp
