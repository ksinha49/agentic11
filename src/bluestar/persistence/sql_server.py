"""On-premises SQL Server (Relius/PlanConnect) ODBC client."""

from __future__ import annotations

from typing import Any

# TODO: Implement ODBC connection pool to CapitalSG-64
# Queries: PersonalInfoByPlan, jobstatuscurrent, originalDOH,
#          CurrentContributionRates, YTD, ERContribYTD, PlanEECodeHistExport,
#          DetailsWithPaySchedXML, DepWDDetail, PayrollForfs


class SQLServerClient:
    """Production ISQLClient backed by pyodbc."""

    def __init__(self, connection_string: str, pool_size: int = 5) -> None:
        self._connection_string = connection_string
        self._pool_size = pool_size

    def query(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        raise NotImplementedError

    def execute_sp(self, sp_name: str, params: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError
