from fastapi import APIRouter, Depends, Query
from typing import Optional
from sqlalchemy.orm import Session

from src.database.get_db import get_db
from src.modules.nlp import ReportGenerator
from src.modules.report import GetReports, GetReportById
from src.modules.report_scheduler import reset_scheduler
from src.schemas.basic_response import BasicResponse
from src.schemas.report import GetReportResponse

router = APIRouter(prefix="/reports", tags=["Report"])


@router.get("/")
def get_reports(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    session: Session = Depends(get_db),
) -> BasicResponse[list[GetReportResponse]]:
    filters = {"start_date": start_date, "end_date": end_date}
    return GetReports(session, filters).execute()


@router.get("/{report_id}")
def get_report_by_id(
    report_id: int,
    session: Session = Depends(get_db),
) -> BasicResponse[GetReportResponse | None]:
    return GetReportById(session, report_id).execute()


@router.post("/generate")
def generate_report_endpoint() -> BasicResponse[None]:
    ReportGenerator().execute()
    reset_scheduler()
    return BasicResponse(message="Report generated sucessfully")
