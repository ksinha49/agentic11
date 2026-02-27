"""EmploymentStatusService — step 1200 (subroutine-employmentstatus.do)."""

from __future__ import annotations

# TODO: Implement EmploymentStatusService
# ODBC queries: jobstatuscurrent, originalDOH
# Rules: clear invalid DOT/DOR, DOR before DOH, rehire detection,
#   DOT supersedes DOR, replace DOH with Relius original
