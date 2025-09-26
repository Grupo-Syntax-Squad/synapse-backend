from typing import Any
from sqlalchemy import text
from sqlalchemy.orm import Session
from src.schemas.report import GetReportResponse
from src.schemas.basic_response import BasicResponse


class GetReports:
    def __init__(self, session: Session, filters: dict[str, Any]):
        self._session = session
        self._filters = filters

    def execute(self) -> BasicResponse[list[GetReportResponse]]:
        self._get_reports()
        response = self._format_response()
        return BasicResponse(data=response)

    def _get_reports(self) -> None:
        base_query = "SELECT * FROM report WHERE 1=1"
        params: dict[str, Any] = {}

        if self._filters:
            if self._filters.get("start_date"):
                base_query += " AND created_at >= :start_date"
                params["start_date"] = self._filters.get("start_date")
            if self._filters.get("end_date"):
                base_query += " AND created_at <= :end_date"
                params["end_date"] = self._filters.get("end_date")

        with self._session as session:
            query = text(base_query).bindparams(**params)
            result = session.execute(query)
            reports = result.fetchall()
            self.result: list[dict[str, Any]] = [
                report._asdict() for report in reports
            ]

    def _format_response(self) -> list[GetReportResponse]:
        return [
            GetReportResponse(
                id=result["id"],
                name=result["name"],
                created_at=result["created_at"].isoformat(),
                content=result["content"],
            )
            for result in self.result
        ]


class GetReportById:
    def __init__(self, session: Session, report_id: int):
        self._session = session
        self._report_id = report_id

    def execute(self) -> BasicResponse[GetReportResponse | None]:
        self._get_report()
        if not self.result:
            return BasicResponse(data=None, message="Report not found")
        response = self._format_response()
        return BasicResponse(data=response)

    def _get_report(self) -> None:
        with self._session as session:
            query = text("""SELECT * FROM report WHERE id=:id""").bindparams(
                id=self._report_id
            )
            result = session.execute(query).fetchone()
            self.result: dict[str, Any] | None = (
                result._asdict() if result else None
            )

    def _format_response(self) -> GetReportResponse | None:
        response = GetReportResponse(
            id=self.result["id"],
            name=self.result["name"],
            created_at=self.result["created_at"].isoformat(),
            content=self.result["content"],
        ) if self.result else None
        return response
