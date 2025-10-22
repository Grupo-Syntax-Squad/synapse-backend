from fastapi.testclient import TestClient
from fastapi import status


class TestLogin:    
    def test_login(self, client: TestClient) -> None:
        payload = {
            "username": "TestUser1",
            "email": "testemail@gmail.com",
            "password": "password123",
        }
        createResponse = client.post("/users/register", json=payload)
        assert createResponse.status_code == status.HTTP_200_OK
        loginResponse = client.post("/auth/login", json={
            "email": payload["email"],
            "password": payload["password"]
        })
        assert loginResponse.status_code == status.HTTP_200_OK