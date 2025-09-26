from typing import Any
from fastapi.testclient import TestClient
from datetime import datetime, timedelta


def test_get_reports(client: TestClient) -> None:
    response = client.get("/reports/")
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) >= 2
    assert any(r["name"] == "Relatório 1" for r in data)


def test_get_reports_with_date_filter(client: TestClient) -> None:
    start = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    response = client.get(f"/reports/?start_date={start}")
    assert response.status_code == 200
    data = response.json()["data"]
    assert any(r["name"] == "Relatório 2" for r in data)


def test_get_report_by_id(client: TestClient, report_data: Any) -> None:
    report_id = report_data[0].id
    response = client.get(f"/reports/{report_id}")
    assert response.status_code == 200
    assert response.json()["data"]["name"] == "Relatório 1"


def test_get_report_by_id_not_found(client: TestClient) -> None:
    response = client.get("/reports/999999")
    assert response.status_code == 200
    assert response.json()["data"] is None
