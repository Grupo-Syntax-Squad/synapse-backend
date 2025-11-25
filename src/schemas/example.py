from pydantic import BaseModel


class GetExampleResponse(BaseModel):
    id: int
    name: str
    enabled: bool
    created_at: str
    updated_at: str


class PostExampleRequest(BaseModel):
    name: str


class DeleteExampleRequest(BaseModel):
    id: int
