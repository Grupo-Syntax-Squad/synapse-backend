from typing import Any, Callable, Generator
from unittest.mock import patch
from starlette.websockets import WebSocketDisconnect
import pytest
from fastapi.testclient import TestClient
from src.main import app
from src.auth.auth_utils import Auth
from pytest import MonkeyPatch


class DummyUser:
    def __init__(self, id: int, username:str, is_admin: bool = False) -> None:
        self.id = id
        self.username = username
        self.is_admin = is_admin


@pytest.fixture
def mock_user(monkeypatch: MonkeyPatch) -> Callable[[Any], Any]:
    def _mock(user: DummyUser) -> Any:
        async def fake_get_current_user(*args: Any, **kwargs: Any) -> Any:
            return user
        monkeypatch.setattr(Auth, "get_current_user", fake_get_current_user)
        return user
    return _mock


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(autouse=True)
def override_auth() ->  Generator[None, None, None]:
    def fake_user() -> DummyUser:
        return DummyUser(1, "user1")
    app.dependency_overrides[Auth.get_current_user] = fake_user
    yield
    app.dependency_overrides = {}


class TestWebSockets:
    def test_chat_send_receive(self, client: TestClient) -> None:
        client.cookies.set("access_token", "fake_token")

        with patch.object(Auth, "get_current_user", return_value=DummyUser(1, "user1")):
            with client.websocket_connect("/ws/chat") as ws:
                ws.send_text("oi")
                response = ws.receive_text()

                assert response == "Reply: oi"

    def test_notification_admin_connect(self, client: TestClient) -> None:
        client.cookies.set("access_token", "fake_token")

        async def fake_get_current_user() -> DummyUser:
            return DummyUser(99, "admin", True)

        app.dependency_overrides[Auth.get_current_user] = fake_get_current_user
        with client.websocket_connect("/ws/notification") as ws:
            assert ws is not None
        app.dependency_overrides = {}

    def test_notification_non_admin_denied(self, client: TestClient, mock_user: Callable[[DummyUser], DummyUser]) -> None:
        client.cookies.set("access_token", "fake_token")

        async def fake_get_current_user() -> DummyUser:
            return DummyUser(99, "admin", False)

        app.dependency_overrides[Auth.get_current_user] = fake_get_current_user
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect("/ws/notification"):
                pass
        assert exc_info.value.code == 1008
        assert exc_info.value.reason == "Access denied"
        app.dependency_overrides = {}

    def test_multiple_chat_clients(self, client: TestClient, mock_user: Callable[[DummyUser], DummyUser]) -> None:
        client.cookies.set("access_token", "fake_token")

        users = [mock_user(DummyUser(i, f"user{i}")) for i in range(3)]

        for i, user in enumerate(users):
            with client.websocket_connect("/ws/chat") as ws:
                ws.send_text(f"Message {i}")
                response = ws.receive_text()
                assert response == f"Reply: Message {i}"

    def test_disconnect_handling(self, client: TestClient, mock_user: Callable[[DummyUser], DummyUser]) -> None:
        client.cookies.set("access_token", "fake_token")
        mock_user(DummyUser(10, "disconnect_user"))

        with client.websocket_connect("/ws/chat") as ws:
            assert ws is not None
