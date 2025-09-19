from pydantic import BaseModel, ConfigDict


class LoginForm(BaseModel):
    email: str
    password: str


class CurrentUser(BaseModel):
    id: int
    email: str
    username: str
    is_active: bool
    is_admin: bool

    model_config = ConfigDict(from_attributes=True)
