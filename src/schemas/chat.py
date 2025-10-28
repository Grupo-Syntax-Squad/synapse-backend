from datetime import datetime
from pydantic import BaseModel, Field


class ChatHistoryRequest(BaseModel):
    user_id: int


class ChatHistoryResponse(BaseModel):
    message: str
    user_id: int
    user_message: bool
    created_at: datetime


class ChatRequestData(BaseModel):
    message: str
    user_id: int
    user_message: bool
    created_at: datetime


class ChatRequest(BaseModel):
    message_type: str = Field(..., alias="type")
    data: ChatRequestData
    timestamp: datetime
