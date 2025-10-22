from datetime import datetime
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from src.enums.notification_type import NotificationType
from src.logger_instance import logger
from src.auth.auth_utils import Auth
from src.database.models import Notification, User
from src.schemas.basic_response import BasicResponse
from src.schemas.user import PostUser
from src.managers.websocket import notifications_manager


class CreateUser:
    def __init__(self, session: Session, request: PostUser):
        self._session = session
        self._request = request
        self._log = logger

    async def execute(self) -> BasicResponse[None]:
        try:
            self._log.info("Creating new user")
            with self._session as session:
                self._validate()
                user = self._create_user(session)
                session.commit()
                self._log.info("User created successfully")
                notification = await self._create_new_user_notification(user)
                if notification:
                    await notifications_manager.send_notification(notification)
                return BasicResponse(message="OK")
        except HTTPException:
            raise
        except Exception as e:
            self._log.error(f"Error creating user: {e}")
            raise HTTPException(
                detail="Internal error",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def _validate(self) -> None:
        if not self._request.username.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username cannot be empty",
            )
        if not self._request.email.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email cannot be empty",
            )
        if not self._request.password.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password cannot be empty",
            )

        existing_username = self._session.execute(
            select(User).where(User.username == self._request.username)
        ).scalar_one_or_none()
        if existing_username:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Username already taken",
            )

        self._log.info("Checking if user with email already exists")
        existing_email = self._session.execute(
            select(User).where(User.email == self._request.email)
        ).scalar_one_or_none()
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already registered",
            )

        if len(self._request.password) < 8:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password must be at least 8 characters long",
            )

    def _create_user(self, session: Session) -> User:
        hashed_password = Auth.get_password_hash(self._request.password)
        user = User(
            username=self._request.username.strip(),
            email=self._request.email.strip(),
            password=hashed_password,
        )
        session.add(user)
        session.flush()
        session.refresh(user)
        return user
    
    async def _create_new_user_notification(self, user: User) -> Notification | None:
        notification = Notification(
            type=NotificationType.NEW_USER,
            message=f"Novo usuário cadastrado: {user.username}",
            details={"user_id": user.id, "timestamp": datetime.utcnow().isoformat()},
        )

        self._session.add(notification)
        self._session.commit()
        self._session.refresh(notification)   
        return notification
