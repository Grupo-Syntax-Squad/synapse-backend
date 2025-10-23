from datetime import datetime, timezone
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.database.models import ChatHistory, User
from src.logger_instance import logger
from src.schemas.basic_response import BasicResponse
from src.schemas.chat import ChatHistoryRequest, ChatHistoryResponse


class ChatHistoryGetter:
    def __init__(self, session: Session, params: ChatHistoryRequest) -> None:
        self._log = logger
        self._session = session
        self._params = params

    def execute(self) -> BasicResponse[list[ChatHistoryResponse]]:
        try:
            self._log.info(
                f"Trying to get user with ID: {self._params.user_id} chat history"
            )
            user = self._get_user_by_id(self._params.user_id)
            chat_history = self._get_chat_history_by_user_id(user)
            self._log.info("Successfully get user chat history")
            return BasicResponse(
                data=sorted(chat_history, key=lambda chat: chat.created_at)
            )
        except HTTPException:
            raise
        except Exception as e:
            self._log.error(str(e))
            raise HTTPException(
                detail="Internal error",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def _get_user_by_id(self, user_id: int) -> User:
        user = (
            self._session.execute(
                select(User).where(User.id == user_id, User.is_active)
            )
        ).scalar_one_or_none()
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
        return user

    def _get_chat_history_by_user_id(self, user: User) -> list[ChatHistoryResponse]:
        chat_history = (
            self._session.execute(
                select(
                    ChatHistory.message,
                    ChatHistory.user_id,
                    ChatHistory.user_message,
                    ChatHistory.created_at,
                ).where(ChatHistory.user_id == user.id)
            )
        ).fetchall()
        self._log.debug(f"{chat_history}")
        return [ChatHistoryResponse(**chat._asdict()) for chat in chat_history]


class ChatHistoryCreator:
    def __init__(self, session: Session):
        self._log = logger
        self._session = session

    def execute(self, user_id: int, user_message: bool, message: str) -> None:
        try:
            self._log.info(f"Creating chat history for user with ID: {user_id}")
            self._log.debug(
                f"User ID: {user_id} | User message: {user_message} | Message: {message}"
            )
            now = datetime.now(timezone.utc)
            user = self._get_user_by_id(user_id)
            new_chat_history = ChatHistory(
                {
                    "message": message,
                    "user_id": user.id,
                    "user_message": user_message,
                    "created_at": now,
                }
            )
            self._session.add(new_chat_history)
            self._session.commit()
            self._log.info("Chat history created")
        except Exception as e:
            self._log.error(str(e))
            raise e

    def _get_user_by_id(self, user_id: int) -> User:
        user = (
            self._session.execute(
                select(User).where(User.id == user_id, User.is_active)
            )
        ).scalar_one_or_none()
        if user is None:
            raise ValueError("User not found")
        return user
