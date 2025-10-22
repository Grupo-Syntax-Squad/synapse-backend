import asyncio
from fastapi import APIRouter, Cookie, Depends, WebSocket, WebSocketDisconnect

from src.auth.auth_utils import Auth
from src.managers.websocket import chat_manager, notifications_manager
from src.schemas.auth import CurrentUser

router = APIRouter(prefix="/ws", tags=["Websocket"])

@router.websocket("/chat")
async def websocket_chat(websocket: WebSocket, current_user: CurrentUser = Depends(Auth.get_current_user)):
    await chat_manager.connect(current_user.id, websocket)
    try:
        while True:
            user_msg = await websocket.receive_text()
            # process_message(user_msg)
            pln_response = "Resposta de exemplo do PLN"
            await chat_manager.send_personal_message("Reply: " + user_msg, current_user.id)
    except WebSocketDisconnect:
        chat_manager.disconnect(current_user.id)
        print(f"User {current_user.username} disconnected")

@router.websocket("/notification")
async def websocket_notification(websocket: WebSocket, current_user: CurrentUser = Depends(Auth.get_current_user)):
    if not current_user.is_admin:
        await websocket.close(code=1008, reason="Access denied")
        return

    await notifications_manager.connect(current_user.id, websocket)
    try:
        while True:
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        notifications_manager.disconnect(current_user.id)
        print(f"Admin {current_user.username} disconnected")