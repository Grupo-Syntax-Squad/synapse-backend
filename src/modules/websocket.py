from enum import Enum
from typing import Any, Dict
from fastapi import WebSocket
from abc import ABC

from src.database.models import Notification
from src.nlp.extract_data_nl import (
    RuleIntentClassifier,
    SQLQueryBuilder,
    ResponseGenerator,
)
from sqlalchemy.engine import create_engine
from src.settings import settings
from src.logger_instance import logger


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
        self._builder = SQLQueryBuilder(self._engine)
        super().__init__()

    async def send_personal_message(self, message: str, user_id: int) -> None:
        websocket = self.active_connections.get(user_id)
        if websocket:
            await websocket.send_text(self._response_builder(message))

    def _response_builder(self, text: str) -> str:
        classifier = RuleIntentClassifier()
        try:
            intent, params = classifier.classify(text)
        except Exception as e:
            self._logger.error(f"Erro ao classificar intenção:{e}")
            return "Desculpe — não fui projetado para responder esse tipo de pergunta."

        self._logger.debug(f"Intent: {intent}")
        self._logger.debug(f"Params: {params}")
        try:
            out = self._builder.execute(intent, params)
        except Exception as e:
            self._logger.error(f"Erro ao executar consulta: {e}")
            return "Desculpe — ocorreu um erro ao buscar os dados."

        rg = ResponseGenerator()
        reply = rg.generate(intent, params, out)
        self._logger.info("Resposta:")
        self._logger.info(reply)
        return reply


class NotificationWebSocketManager(WebSocketManager):
    async def send_global_message(self, message: str) -> None:
        for connection in self.active_connections.values():
            await connection.send_text(message)

    def notification_to_dict(self, notification: Notification) -> dict[str, Any]:
        return {
            "id": notification.id,
            "type": notification.type.name
            if isinstance(notification.type, Enum)
            else notification.type,
            "message": notification.message,
            "details": notification.details,
            "created_at": notification.created_at.isoformat()
            if notification.created_at
            else None,
            "visualized": notification.visualized,
            "visualizedAt": notification.visualizedAt.isoformat()
            if notification.visualizedAt
            else None,
            "visualizedBy": notification.visualizedBy,
        }

    async def send_notification(self, notification: Notification) -> None:
        for connection in self.active_connections.values():
            await connection.send_json(self.notification_to_dict(notification))
