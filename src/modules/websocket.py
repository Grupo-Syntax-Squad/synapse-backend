from enum import Enum
from typing import Any, Dict
from fastapi import WebSocket
from abc import ABC

from src.database.models import Notification


class WebSocketManager(ABC):
    def __init__(self) -> None:
        self.active_connections: Dict[int, WebSocket] = {}

    async def connect(self, user_id: int, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections[user_id] = websocket

    def disconnect(self, user_id: int) -> None:
        if user_id in self.active_connections:
            del self.active_connections[user_id]


class ChatWebSocketManager(WebSocketManager):
    async def send_personal_message(self, message: str, user_id: int) -> None:
        websocket = self.active_connections.get(user_id)
        if websocket:
            await websocket.send_text(message)


class NotificationWebSocketManager(WebSocketManager):
    async def send_global_message(self, message: str) -> None:
        for connection in self.active_connections.values():
            await connection.send_text(message)

    def notification_to_dict(self, notification: Notification) -> dict[str, Any]:
        return {
            "id": notification.id,
            "type": notification.type.name if isinstance(notification.type, Enum) else notification.type,
            "message": notification.message,
            "details": notification.details,
            "created_at": notification.created_at.isoformat() if notification.created_at else None,
            "visualized": notification.visualized,
            "visualizedAt": notification.visualizedAt.isoformat() if notification.visualizedAt else None,
            "visualizedBy": notification.visualizedBy,
        }

    async def send_notification(self, notification: Notification) -> None:
        for connection in self.active_connections.values():
            await connection.send_json(self.notification_to_dict(notification))