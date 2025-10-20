from datetime import datetime, timedelta
from fastapi import APIRouter, Cookie, Depends, HTTPException, status, Response
from jose import JWTError, jwt
from src.database.get_db import get_db
from src.database.models import User
from sqlalchemy.orm import Session
from src.auth.auth_utils import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    ALGORITHM,
    REFRESH_TOKEN_EXPIRE_DAYS,
    SECRET_KEY,
    Auth,
)
from src.schemas.auth import LoginForm
from src.schemas.basic_response import BasicResponse


router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login")
def login_for_access_token(
    response: Response, form_data: LoginForm, db: Session = Depends(get_db)
) -> BasicResponse[None]:
    with db as session:
        user = session.query(User).filter(User.email == form_data.email).first()
        if user is None or not Auth.verify_password(form_data.password, user.password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuário ou senha incorretos",
            )

        user.last_access = datetime.now()
        session.commit()

        token_data = {"sub": str(user.id)}
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = Auth.create_access_token(
            data=token_data,
            access_token_expires=access_token_expires,
        )
        refresh_token_expires = timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
        refresh_token = Auth.create_refresh_token(
            data=token_data,
            refresh_token_expires=refresh_token_expires,
        )
        Auth.set_cookies_to_response(
            response,
            access_token,
            refresh_token,
            access_token_expires=access_token_expires,
            refresh_token_expires=refresh_token_expires,
        )

        return BasicResponse(message="OK")


@router.post("/logout")
def logout(response: Response) -> BasicResponse[None]:
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")

    return BasicResponse(message="Logout realizado com sucesso")


@router.post("/refresh")
def refresh_token(
    response: Response,
    refresh_token: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
) -> BasicResponse[None]:
    if refresh_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token cookie is missing",
        )

    try:
        payload = jwt.decode(refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: int = int(payload.get("sub", 0))
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token inválido",
            )

        with db as session:
            user = session.query(User).filter(User.id == user_id).first()
            if user is None or not user.is_active:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Usuário inválido",
                )

        new_access_token = Auth.create_access_token({"sub": str(user.id)})
        new_refresh_token = Auth.create_refresh_token({"sub": str(user.id)})
        Auth.set_cookies_to_response(response, new_access_token, new_refresh_token)

        return BasicResponse(message="OK")
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token inválido ou expirado",
        )
