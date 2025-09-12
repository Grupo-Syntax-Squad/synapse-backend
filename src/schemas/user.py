from pydantic import BaseModel


class PostUser(BaseModel):
    username: str
    email: str
    password: str

    class Config:
        orm_mode = True
        from_attributes = True