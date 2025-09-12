from pydantic import BaseModel


class LoginForm(BaseModel):
    email: str
    password: str


class CurrentUser(BaseModel):
    id: int
    email: str
    username: str
    is_active: bool
    is_admin: bool

    class Config:
        from_attributes = True