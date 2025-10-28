from datetime import datetime
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select
from datetime import timezone

from src.enums.notification_type import NotificationType
from src.logger_instance import logger
from src.auth.auth_utils import Auth
from src.database.models import Notification, User
from src.schemas.basic_response import BasicResponse
from src.managers.websocket import notifications_manager
from src.schemas.user import PostUser, UserResponse, UpdateUserRequest


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
                    await notifications_manager.send_notification(
                        notifications_manager.notification_to_schema(notification)
                    )
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
            message=f"New user registered: {user.username}",
            details={"user_id": user.id, "timestamp": datetime.utcnow().isoformat()},
        )

        self._session.add(notification)
        self._session.commit()
        self._session.refresh(notification)
        return notification


class ListUsers:
    def __init__(self, session: Session):
        self._session = session
        self._log = logger

    def execute(self) -> BasicResponse[list[UserResponse]]:
        try:
            self._log.info("Listing active users")
            with self._session as session:
                results = (
                    session.execute(select(User).where(User.is_active.is_(True)))
                    .scalars()
                    .all()
                )

                users: list[UserResponse] = [
                    UserResponse(
                        id=u.id,
                        username=u.username,
                        email=u.email,
                        is_active=u.is_active,
                        is_admin=u.is_admin,
                        receive_email=u.receive_email,
                        last_update=u.last_update,
                        last_access=u.last_access,
                    )
                    for u in results
                ]

                return BasicResponse(data=users, message="OK")
        except Exception as e:
            self._log.error(f"Error listing users: {e}")
            raise HTTPException(
                detail="Internal error",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class UpdateUser:
    ALLOWED_FIELDS = {
        "username",
        "email",
        "password",
        "is_active",
        "is_admin",
        "receive_email",
        "last_update",
        "last_access",
    }

    def __init__(self, session: Session, request: UpdateUserRequest):
        self._session = session
        self._request = request
        self._log = logger

    def execute(self) -> BasicResponse[None]:
        try:
            self._log.info("Updating user")
            if self._request.field not in self.ALLOWED_FIELDS:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Field '{self._request.field}' cannot be updated",
                )

            with self._session as session:
                user = session.execute(
                    select(User).where(User.id == self._request.id)
                ).scalar_one_or_none()

                if user is None:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="User not found",
                    )

                if self._request.field == "email":
                    existing = session.execute(
                        select(User).where(
                            User.email == self._request.value, User.id != user.id
                        )
                    ).scalar_one_or_none()
                    if existing:
                        raise HTTPException(
                            status_code=status.HTTP_409_CONFLICT,
                            detail="Email already registered",
                        )

                if self._request.field == "username":
                    existing = session.execute(
                        select(User).where(
                            User.username == self._request.value, User.id != user.id
                        )
                    ).scalar_one_or_none()
                    if existing:
                        raise HTTPException(
                            status_code=status.HTTP_409_CONFLICT,
                            detail="Username already taken",
                        )

                if self._request.field == "password":
                    hashed = Auth.get_password_hash(str(self._request.value))
                    setattr(user, "password", hashed)
                else:
                    setattr(user, self._request.field, self._request.value)

                if self._request.field != "last_update":
                    user.last_update = datetime.now(timezone.utc)

                session.commit()
                return BasicResponse(message="OK")
        except HTTPException:
            raise
        except Exception as e:
            self._log.error(f"Error updating user: {e}")
            raise HTTPException(
                detail="Internal error",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
