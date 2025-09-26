from fastapi import APIRouter, BackgroundTasks, Depends, Query
from fastapi.params import Depends
from sqlalchemy.orm import Session
from typing import Optional

from src.auth.auth_utils import Auth, PermissionValidator
from src.modules.report import SendReportToSubscribers, GetReports, GetReportById
from src.schemas.auth import CurrentUser
from src.schemas.basic_response import BasicResponse
from src.database.get_db import get_db
from src.schemas.report import SendReport, GetReportResponse


router = APIRouter(prefix="/reports", tags=["Report"])


@router.post("/send")
async def send_report(
    request: SendReport,
    background_tasks: BackgroundTasks,
    current_user: CurrentUser = Depends(Auth.get_current_user),  # type: ignore
    session: Session = Depends(get_db),  # type: ignore
) -> BasicResponse[None]:
    PermissionValidator(current_user).execute()
    service = SendReportToSubscribers(
        session=session,
        request=request
    )
    background_tasks.add_task(service.execute)
    return BasicResponse(message="O envio do relatório está sendo processado em background.")


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
