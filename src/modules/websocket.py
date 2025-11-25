from abc import ABC
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict
from fastapi import WebSocket, WebSocketDisconnect
from fastapi.websockets import WebSocketState
from pydantic import BaseModel
from sqlalchemy.engine import create_engine

from src.database.models import Notification
from src.modules.chat import ChatHistoryCreator
from src.nlp.sql_query_builder import SQLQueryBuilder
from src.database.get_db import get_db
from src.logger_instance import logger
from src.nlp.response_generator import ResponseGenerator
from src.nlp.intent_classifier import RuleIntentClassifier
from src.schemas.chat import ChatRequest
from src.settings import settings
from src.enums.notification_type import NotificationType


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
    def __init__(self) -> None:
        self._logger = logger
        self._engine = create_engine(settings.DATABASE_URL)
        self._sql_query_builder = SQLQueryBuilder(self._engine)
        super().__init__()

    async def send_personal_message(
        self, chat_request: ChatRequest, user_id: int
    ) -> None:
        websocket = self.active_connections.get(user_id)
        if websocket:
            await websocket.send_text(
                self._build_response(chat_request.data.message, user_id)
            )

    def _build_response(self, user_message: str, user_id: int) -> str:
        intent_classifier = RuleIntentClassifier()
        try:
            intent, params = intent_classifier.execute(user_message)
        except Exception as e:
            self._logger.error(f"Erro ao classificar intenção:{e}")
            return "Desculpe — não fui projetado para responder esse tipo de pergunta."
        self._logger.debug(f"Intent: {intent}")
        self._logger.debug(f"Params: {params}")
        try:
            out = self._sql_query_builder.execute(intent, params)
        except Exception as e:
            self._logger.error(f"Erro ao executar consulta: {e}")
            return "Desculpe — ocorreu um erro ao buscar os dados."
        response_generator = ResponseGenerator()
        reply = response_generator.execute(intent, params, out)
        self._logger.debug("Resposta:")
        self._logger.info(reply)
        with get_db() as session:
            chat_history_creator = ChatHistoryCreator(session)
            chat_history_creator.execute(user_id, True, user_message)
            chat_history_creator.execute(user_id, False, reply)
        return reply


class NotificationSchema(BaseModel):
    notification_id: int | None
    type_name: str
    message: str
    details: dict[str, Any]
    created_at: datetime
    visualized: bool
    visualizedAt: datetime | None
    visualizedBy: int | None


class NotificationWebSocketManager(WebSocketManager):
    def is_connected(self) -> bool:
        return len(self.active_connections) > 0

    async def send_global_message(self, message: str) -> None:
        payload = self._generic_to_schema(message).model_dump_json()

        dead_connections = []

        for key, connection in self.active_connections.items():
            try:
                if connection.application_state != WebSocketState.CONNECTED:
                    dead_connections.append(key)
                    continue
                await connection.send_json(payload)
            except (WebSocketDisconnect, RuntimeError) as e:
                if isinstance(e, RuntimeError) and 'Cannot call "send"' not in str(e):
                    raise
                dead_connections.append(key)

        for key in dead_connections:
            self.active_connections.pop(key, None)

    def _generic_to_schema(self, message: str) -> NotificationSchema:
        now = datetime.now(timezone.utc)
        return NotificationSchema(
            notification_id=None,
            type_name=NotificationType.GENERIC,
            message=message,
            details={},
            created_at=now,
            visualized=True,
            visualizedAt=None,
            visualizedBy=None,
        )

    def notification_to_schema(self, notification: Notification) -> NotificationSchema:
        return NotificationSchema(
            notification_id=notification.id,
            type_name=notification.type.name
            if isinstance(notification.type, Enum)
            else notification.type,
            message=notification.message,
            details=notification.details,
            created_at=notification.created_at,
            visualized=notification.visualized,
            visualizedAt=notification.visualizedAt
            if notification.visualizedAt
            else None,
            visualizedBy=notification.visualizedBy,
        )

    async def send_notification(self, notification: NotificationSchema) -> None:
        for connection in self.active_connections.values():
            await connection.send_json(notification.model_dump_json())
