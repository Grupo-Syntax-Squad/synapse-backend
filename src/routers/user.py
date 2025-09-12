from fastapi import APIRouter
from fastapi.params import Depends

from src.auth.auth_utils import Auth
from src.database.get_db import get_db
from src.modules.user import CreateUser
from src.schemas.auth import CurrentUser
from sqlalchemy.orm import Session

from src.schemas.basic_response import BasicResponse
from src.schemas.user import PostUser


router = APIRouter(prefix="/users", tags=["User"])


@router.post("/register")
def register_user(
    request: PostUser,
    session: Session = Depends(get_db),  # type: ignore
) -> BasicResponse[None]:
    return CreateUser(session, request).execute()


@router.get("/me")
def me(
    current_user: CurrentUser = Depends(Auth.get_current_user)  # type: ignore
) -> BasicResponse[CurrentUser]:
    return BasicResponse(data=current_user, message="OK")