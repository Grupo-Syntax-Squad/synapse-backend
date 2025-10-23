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
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_list_users_returns_only_active(self, session: Session, client: TestClient) -> None:
        payload1 = {
            "username": "ListUser1",
            "email": "listuser1@gmail.com",
            "password": "password123",
        }
        payload2 = {
            "username": "ListUser2",
            "email": "listuser2@gmail.com",
            "password": "password123",
        }
        payload_inactive = {
            "username": "ListUserInactive",
            "email": "listuser_inactive@gmail.com",
            "password": "password123",
        }

        resp = client.post("/users/register", json=payload1)
        assert resp.status_code == status.HTTP_200_OK
        resp = client.post("/users/register", json=payload2)
        assert resp.status_code == status.HTTP_200_OK
        resp = client.post("/users/register", json=payload_inactive)
        assert resp.status_code == status.HTTP_200_OK

        user = session.execute(
            select(User).where(User.username == payload_inactive["username"])
        ).scalar_one_or_none()
        assert user is not None
        user.is_active = False
        session.commit()

        response = client.get("/users")
        assert response.status_code == status.HTTP_200_OK

        data = response.json()["data"]
        usernames = [u["username"] for u in data]

        assert payload1["username"] in usernames
        assert payload2["username"] in usernames
        assert payload_inactive["username"] not in usernames

    def test_update_user_field_success(self, session: Session, client: TestClient) -> None:
        target = {"username": "TargetUser", "email": "target@example.com", "password": "password123"}
        admin = {"username": "AdminUser", "email": "admin@example.com", "password": "adminpass123"}

        r = client.post("/users/register", json=target)
        assert r.status_code == status.HTTP_200_OK
        r = client.post("/users/register", json=admin)
        assert r.status_code == status.HTTP_200_OK

        admin_obj = session.execute(select(User).where(User.email == admin["email"])).scalar_one()
        admin_obj.is_admin = True
        session.commit()

        login = client.post("/auth/login", json={"email": admin["email"], "password": admin["password"]})
        print(f"Login response: {login}")
        print(f"LOgin Cookies: {login.cookies}")
        assert login.status_code == status.HTTP_200_OK

        target_obj = session.execute(select(User).where(User.email == target["email"])).scalar_one()
        payload = {"id": target_obj.id, "field": "username", "value": "TargetUserUpdated"}

        resp = client.patch("/users", json=payload, cookies={"access_token": login.cookies['access_token']})
        assert resp.status_code == status.HTTP_200_OK

        updated = session.execute(select(User).where(User.id == target_obj.id)).scalar_one()
        assert updated.username == "TargetUserUpdated"

    def test_update_user_email_conflict(self, session: Session, client: TestClient) -> None:
        u1 = {"username": "U1", "email": "u1@example.com", "password": "password123"}
        u2 = {"username": "U2", "email": "u2@example.com", "password": "password123"}

        client.post("/users/register", json=u1)
        client.post("/users/register", json=u2)

        u1_obj = session.execute(select(User).where(User.email == u1["email"])).scalar_one()
        u1_obj.is_admin = True
        session.commit()

        login = client.post("/auth/login", json={"email": u1["email"], "password": u1["password"]})
        assert login.status_code == status.HTTP_200_OK

        u2_obj = session.execute(select(User).where(User.email == u2["email"])).scalar_one()
        payload = {"id": u2_obj.id, "field": "email", "value": u1["email"]}

        resp = client.patch("/users", json=payload, cookies={"access_token": login.cookies['access_token']})
        assert resp.status_code == status.HTTP_409_CONFLICT
        assert resp.json()["detail"] == "Email already registered"

    def test_update_user_not_found(self, session: Session, client: TestClient) -> None:
        admin = {"username": "Admin2", "email": "admin2@example.com", "password": "adminpass123"}
        client.post("/users/register", json=admin)
        admin_obj = session.execute(select(User).where(User.email == admin["email"])).scalar_one()
        admin_obj.is_admin = True
        session.commit()

        login = client.post("/auth/login", json={"email": admin["email"], "password": admin["password"]})
        assert login.status_code == status.HTTP_200_OK

        payload = {"id": 9999999, "field": "username", "value": "NoOne"}
        resp = client.patch("/users", json=payload, cookies={"access_token": login.cookies['access_token']})
        assert resp.status_code == status.HTTP_404_NOT_FOUND
