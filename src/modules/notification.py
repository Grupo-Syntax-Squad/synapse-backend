from datetime import datetime
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from src.database.models import Notification
from src.schemas.auth import CurrentUser
from src.logger_instance import logger
from src.schemas.basic_response import BasicResponse


class VisualizeNotification:
    def __init__(self, session: Session, notification_id: int, current_user: CurrentUser):
        self._session = session
        self._notification_id = notification_id
        self._current_user = current_user
        self._log = logger

    def execute(self) -> BasicResponse[None]:
        self._log.info(f"Fetching notification ID {self._notification_id} to mark as viewed")

        notification = self._session.query(Notification).filter(
            Notification.id == self._notification_id
        ).first()

        if not notification:
            self._log.warning(f"Notification ID {self._notification_id} not found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Notificação com id {self._notification_id} não encontrada",
            )

        notification.visualized = True
        notification.visualizedAt = datetime.utcnow()
        notification.visualizedBy = self._current_user.id

        self._session.commit()
        self._log.info(f"Notification ID {self._notification_id} marked as viewed by user {self._current_user.id}")

        return BasicResponse(message="Notificação marcada como visualizada")