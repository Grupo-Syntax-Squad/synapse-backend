from pydantic import BaseModel, ConfigDict, EmailStr
from datetime import datetime
from typing import Any


class PostUser(BaseModel):
    username: str
    email: EmailStr
    password: str

    model_config = ConfigDict(from_attributes=True)


class UserResponse(BaseModel):
    id: int
    username: str
    email: EmailStr
    is_admin: bool
    is_active: bool
    receive_email: bool
    last_update: datetime | None
    last_access: datetime | None

    model_config = ConfigDict(from_attributes=True)


class UpdateUserRequest(BaseModel):
    id: int
    field: str
    value: Any

    model_config = ConfigDict(from_attributes=True)