from fastapi import APIRouter, BackgroundTasks
from fastapi.params import Depends

from src.auth.auth_utils import Auth, PermissionValidator
from src.modules.report import SendReportToSubscribers
from src.schemas.auth import CurrentUser
from src.schemas.basic_response import BasicResponse
from src.database.get_db import get_db
from sqlalchemy.orm import Session

from src.schemas.report import SendReport


router = APIRouter(prefix="/reports", tags=["Reports"])


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