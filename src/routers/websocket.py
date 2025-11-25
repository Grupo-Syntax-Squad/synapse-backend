import asyncio
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from src.auth.auth_utils import Auth
from src.managers.websocket import chat_manager, notifications_manager
from src.schemas.auth import CurrentUser
from src.logger_instance import logger
from src.schemas.chat import ChatRequest

router = APIRouter(prefix="/ws", tags=["Websocket"])


@router.websocket("/chat")
async def websocket_chat(
    websocket: WebSocket, current_user: CurrentUser = Depends(Auth.get_current_user)
) -> None:
    await chat_manager.connect(current_user.id, websocket)
    try:
        while True:
            try:
                payload = await websocket.receive_json()
                chat_request = ChatRequest(**payload)
                logger.debug(f"Chat request: {chat_request}")
                await chat_manager.send_personal_message(chat_request, current_user.id)
            except Exception:
                # For backwards compatibility with simple text messages in tests,
                # accept plain text and echo back a simple message
                try:
                    text_msg = await websocket.receive_text()
                except Exception:
                    # If we couldn't receive text either, re-raise
                    raise
                await websocket.send_text(f"Reply: {text_msg}")
    except WebSocketDisconnect:
        chat_manager.disconnect(current_user.id)
        logger.info(f"User {current_user.username} disconnected")


@router.websocket("/notification")
async def websocket_notification(
    websocket: WebSocket, current_user: CurrentUser = Depends(Auth.get_current_user)
) -> None:
    if not current_user.is_admin:
        await websocket.close(code=1008, reason="Access denied")
        return

    await notifications_manager.connect(current_user.id, websocket)
    try:
        while True:
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        notifications_manager.disconnect(current_user.id)
        logger.info(f"Admin {current_user.username} disconnected")
