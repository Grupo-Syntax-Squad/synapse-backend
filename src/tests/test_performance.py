from fastapi.testclient import TestClient
from ..main import app
import pytest
from uuid import uuid4


client = TestClient(app)

@pytest.fixture
def perf_user_payload():
    return {"username": "perf_user", "email": f"perf_{uuid4().hex}@example.com", "password": "password123"}

@pytest.fixture
def perf_user(client: TestClient, perf_user_payload):
    r = client.post("/users/register", json=perf_user_payload)
    assert r.status_code == 200
    return perf_user_payload

def test_root_performance(benchmark, client: TestClient):
    response = benchmark(client.get, "/")
    assert response.status_code == 200

def test_create_user_performance(benchmark, client: TestClient):
    def register_unique():
        payload = {"username": "perf_user", "email": f"perf_{uuid4().hex}@example.com", "password": "password123"}
        r = client.post("/users/register", json=payload)
        assert r.status_code == 200
    benchmark(register_unique)

def test_login_performance(benchmark, client: TestClient, perf_user):
    login_data = {"email": perf_user["email"], "password": perf_user["password"]}
    response = benchmark(client.post, "/auth/login", json=login_data)
    assert response.status_code == 200