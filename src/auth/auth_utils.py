from fastapi import Cookie, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session
from jose import ExpiredSignatureError, JWTError, jwt
from datetime import datetime, timedelta, timezone
from typing import Any
from passlib.context import CryptContext
from src.database.models import User
from src.database.get_db import get_db
from src.schemas.auth import CurrentUser
from src.settings import settings


SECRET_KEY = settings.SECRET_KEY
ALGORITHM = settings.ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRATION_TIME_MINUTES
REFRESH_TOKEN_EXPIRE_DAYS = settings.REFRESH_TOKEN_EXPIRATION_TIME_DAYS
NO_AUTH = settings.NO_AUTH

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class Auth:
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        return pwd_context.verify(plain_password, hashed_password)

    @staticmethod
    def get_password_hash(password: str) -> str:
        return pwd_context.hash(password)

    @staticmethod
    def create_access_token(
        data: dict[str, Any],
        access_token_expires: timedelta = timedelta(
            minutes=ACCESS_TOKEN_EXPIRE_MINUTES
        ),
    ) -> str:
        to_encode = data.copy()

        expire = datetime.now(timezone.utc) + access_token_expires
        to_encode.update({"exp": expire, "type": "access"})
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt

    @staticmethod
    def create_refresh_token(
        data: dict[str, Any],
        refresh_token_expires: timedelta = timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
    ) -> str:
        to_encode = data.copy()
        expire = datetime.now(timezone.utc) + refresh_token_expires
        to_encode.update({"exp": expire, "type": "refresh"})
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt

    @staticmethod
    def get_access_token_from_cookie(
        access_token: str | None = Cookie(default=None),
    ) -> str | None:
        if NO_AUTH:
            return None
        if access_token is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Access token cookie is missing",
            )
        return access_token

    @staticmethod
    def get_current_user(
        token: str = Depends(get_access_token_from_cookie),
        db: Session = Depends(get_db),
    ) -> CurrentUser | None:
        if NO_AUTH:
            print("NO_AUTH is True, skipping authentication")
            return None
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciais inválidas"
        )
        expired_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expirado"
        )
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            if payload.get("type") != "access":
                raise HTTPException(status_code=401, detail="Token inválido")
            user_id: int = int(payload.get("sub", 0))
            if user_id is None:
                raise credentials_exception
            with db as session:
                user = session.query(User).filter(User.id == user_id).first()
                print(user)
                if user is None or not user.is_active:
                    raise credentials_exception
        except ExpiredSignatureError:
            raise expired_exception
        except JWTError:
            raise credentials_exception
        return CurrentUser.model_validate(user)

    @staticmethod
    def set_cookies_to_response(
        response: Response,
        access_token: str,
        refresh_token: str,
        access_token_expires: timedelta = timedelta(
            minutes=ACCESS_TOKEN_EXPIRE_MINUTES
        ),
        refresh_token_expires: timedelta = timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
    ) -> None:
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            secure=False,  # mudar pra True se tiver com HTTPS
            samesite="strict",
            max_age=int(access_token_expires.total_seconds()),
        )
        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            secure=False,
            samesite="strict",
            max_age=int(refresh_token_expires.total_seconds()),
        )


class PermissionValidator:
    def __init__(
        self,
        user: CurrentUser,
    ):
        self._user = user

    def execute(self) -> None:
        if NO_AUTH:
            return None
        if not self._user.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Você não possui acesso a esse recurso",
            )
