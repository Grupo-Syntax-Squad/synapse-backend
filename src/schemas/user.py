from pydantic import BaseModel, ConfigDict, EmailStr


class PostUser(BaseModel):
    username: str
    email: EmailStr
    password: str

    model_config = ConfigDict(from_attributes=True)
