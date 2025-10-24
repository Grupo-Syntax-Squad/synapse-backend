from fastapi import APIRouter
from fastapi.params import Depends

from src.auth.auth_utils import Auth
from src.database.get_db import get_db
from src.modules.user import CreateUser, ListUsers, UpdateUser
from src.schemas.auth import CurrentUser
from sqlalchemy.orm import Session

from src.schemas.basic_response import BasicResponse
from src.schemas.user import PostUser, UserResponse, UpdateUserRequest


router = APIRouter(prefix="/users", tags=["User"])


@router.post("/register")
async def register_user(
    request: PostUser,
    session: Session = Depends(get_db),  # type: ignore
) -> BasicResponse[None]:
    return await CreateUser(session, request).execute()


@router.get("/me")
def me(
    current_user: CurrentUser = Depends(Auth.get_current_user)  # type: ignore
) -> BasicResponse[CurrentUser]:
    return BasicResponse(data=current_user, message="OK")


@router.get("")
def get_users(
    session: Session = Depends(get_db),  # type: ignore
) -> BasicResponse[list[UserResponse]]:
    return ListUsers(session).execute()


@router.patch("")
def update_user(
    request: UpdateUserRequest,
    current_user: CurrentUser = Depends(Auth.get_current_user),  # type: ignore
    session: Session = Depends(get_db),  # type: ignore
) -> BasicResponse[None]:
    return UpdateUser(session, request).execute()