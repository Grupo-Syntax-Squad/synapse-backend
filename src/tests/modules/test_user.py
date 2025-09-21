import pytest
from typing import Any
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.database.models import User


class TestUser:
    @pytest.mark.parametrize(
        "payload",
        [
            {
                "username": "TestUser1",
                "email": "testuser1@gmail.com",
                "password": "password123",
            },
            {
                "username": "TestUser2",
                "email": "testuser2@gmail.com",
                "password": "password123",
            },
        ],
    )
    def test_create_user(
        self, session: Session, client: TestClient, payload: dict[str, Any]
    ) -> None:
        response = client.post("/users/register", json=payload)
        assert response.status_code == status.HTTP_200_OK
        result: User | None = session.execute(
            select(User).where(User.username == payload["username"])
        ).scalar_one_or_none()
        assert result is not None
        assert result.email == payload["email"]
        assert result.is_active is True
        assert result.receive_email is True
        assert result.is_admin is False

    def test_create_two_users_with_same_email(self, client: TestClient) -> None:
        payload1 = {
            "username": "TestUser1",
            "email": "sameemail@gmail.com",
            "password": "password123",
        }
        payload2 = {
            "username": "TestUser2",
            "email": "sameemail@gmail.com",
            "password": "password123",
        }
        response = client.post("/users/register", json=payload1)
        assert response.status_code == status.HTTP_200_OK
        response = client.post("/users/register", json=payload2)
        assert response.status_code == status.HTTP_409_CONFLICT
        assert response.json()["detail"] == "Email already registered"

    def test_create_two_users_with_same_username(self, client: TestClient) -> None:
        payload1 = {
            "username": "SameUser",
            "email": "user1@gmail.com",
            "password": "password123",
        }
        payload2 = {
            "username": "SameUser",
            "email": "user2@gmail.com",
            "password": "password123",
        }
        response = client.post("/users/register", json=payload1)
        assert response.status_code == status.HTTP_200_OK
        response = client.post("/users/register", json=payload2)
        assert response.status_code == status.HTTP_409_CONFLICT
        assert response.json()["detail"] == "Username already taken"

    def test_create_user_without_username(self, client: TestClient) -> None:
        payload = {"email": "testuser@gmail.com", "password": "password123"}
        response = client.post("/users/register", json=payload)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_create_user_without_password(self, client: TestClient) -> None:
        payload = {"username": "UserNoPassword", "email": "nopassword@gmail.com"}
        response = client.post("/users/register", json=payload)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_create_user_with_short_password(self, client: TestClient) -> None:
        payload = {
            "username": "UserShortPass",
            "email": "shortpass@gmail.com",
            "password": "123",  # too short
        }
        response = client.post("/users/register", json=payload)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert (
            response.json()["detail"] == "Password must be at least 8 characters long"
        )

    def test_create_user_with_invalid_email(self, client: TestClient) -> None:
        payload = {
            "username": "InvalidEmailUser",
            "email": "notanemail",
            "password": "password123",
        }
        response = client.post("/users/register", json=payload)
        # handled by Pydantic EmailStr
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
