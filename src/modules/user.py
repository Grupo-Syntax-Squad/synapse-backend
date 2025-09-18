from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from src.auth.auth_utils import Auth
from src.database.models import User
from src.schemas.basic_response import BasicResponse
from src.schemas.user import PostUser


class CreateUser:
    def __init__(self, session: Session, request: PostUser):
        self.session = session
        self.request = request

    def execute(self) -> BasicResponse[None]:
        try:
            with self.session as session:
                self._create_user(session)
                session.commit()
                return BasicResponse(message="OK")
        except Exception as e:
            raise HTTPException(
                detail=f"Erro ao criar o usuário: {e}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def _create_user(self, session: Session) -> User | None:
        hashed_password = Auth.get_password_hash(self.request.password)
        user = User(
            username=self.request.username,
            email=self.request.email,
            password=hashed_password,
        )
        session.add(user)
        session.flush()
        session.refresh(user)
        return user