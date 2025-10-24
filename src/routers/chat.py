from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, Query

from src.database.get_db import get_db
from src.modules.chat import ChatHistoryGetter
from src.schemas.chat import ChatHistoryRequest, ChatHistoryResponse
from src.schemas.basic_response import BasicResponse


router = APIRouter(prefix="/chat_history", tags=["Chat"])


@router.get("/")
def get_chat_history(
    params: ChatHistoryRequest = Query(), session: Session = Depends(get_db)
) -> BasicResponse[list[ChatHistoryResponse]]:
    return ChatHistoryGetter(session, params).execute()
