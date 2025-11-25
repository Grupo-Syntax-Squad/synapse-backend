from pydantic import BaseModel, ConfigDict
from pydantic import EmailStr


class LoginForm(BaseModel):
    email: str
    password: str


class CurrentUser(BaseModel):
    id: int
    email: str
    username: str
    is_active: bool
    is_admin: bool
    receive_email: bool

    model_config = ConfigDict(from_attributes=True)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    email: EmailStr
    code: str
    new_password: str

    model_config = ConfigDict(from_attributes=True)
