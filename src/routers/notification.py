from fastapi import APIRouter
from fastapi.params import Depends
from pytest import Session

from src.database.get_db import get_db
from src.modules.notification import VisualizeNotification
from src.schemas.auth import CurrentUser
from src.schemas.basic_response import BasicResponse
from src.auth.auth_utils import Auth


router = APIRouter(prefix="/notifications", tags=["Notification"])


@router.patch("/{notification_id}/visualize")
def visualize_notification(
    notification_id: int,
    current_user: CurrentUser = Depends(Auth.get_current_user),
    session: Session = Depends(get_db),
) -> BasicResponse[None]:
    return VisualizeNotification(
        session=session,
        notification_id=notification_id,
        current_user=current_user
    ).execute()