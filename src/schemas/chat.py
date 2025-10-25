from datetime import datetime
from pydantic import BaseModel


class ChatHistoryRequest(BaseModel):
    user_id: int


class ChatHistoryResponse(BaseModel):
    message: str
    user_id: int
    user_message: bool
    created_at: datetime
