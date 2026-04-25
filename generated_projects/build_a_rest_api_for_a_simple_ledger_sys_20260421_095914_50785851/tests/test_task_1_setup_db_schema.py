import pytest
from fastapi.testclient import TestClient
from src.routes.ledger_entries import router
from src.database import SessionLocal

@pytest.fixture
def client():
    return TestClient(router)

def test_create_ledger_entry_success(client):
    response = client.post("/api/v1/ledger-entries", json={
        "amount": 10.99,
        "description": "Test entry",
        "date": "2022-01-01",
        "category_id": 1,
        "transaction_id": 1
    })
    assert response.status_code == 201
    assert response.json()["amount"] == 10.99
    assert response.json()["description"] == "Test entry"

def test_create_ledger_entry_failure_invalid_amount(client):
    response = client.post("/api/v1/ledger-entries", json={
        "amount": "invalid",
        "description": "Test entry",
        "date": "2022-01-01",
        "category_id": 1,
        "transaction_id": 1
    })
    assert response.status_code == 400
    assert "amount" in response.json()["detail"]

def test_create_ledger_entry_failure_missing_description(client):
    response = client.post("/api/v1/ledger-entries", json={
        "amount": 10.99,
        "date": "2022-01-01",
        "category_id": 1,
        "transaction_id": 1
    })
    assert response.status_code == 400
    assert "description" in response.json()["detail"]

def test_get_all_ledger_entries_success(client):
    response = client.get("/api/v1/ledger-entries")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_get_ledger_entry_by_id_success(client):
    response = client.get("/api/v1/ledger-entries/1")
    assert response.status_code == 200
    assert response.json()["id"] == 1

def test_get_ledger_entry_by_id_failure_invalid_id(client):
    response = client.get("/api/v1/ledger-entries/invalid")
    assert response.status_code == 404
    assert "id" in response.json()["detail"]

def test_update_ledger_entry_success(client):
    response = client.put("/api/v1/ledger-entries/1", json={
        "amount": 10.99,
        "description": "Test entry",
        "date": "2022-01-01",
        "category_id": 1,
        "transaction_id": 1
    })
    assert response.status_code == 200
    assert response.json()["amount"] == 10.99
    assert response.json()["description"] == "Test entry"

def test_update_ledger_entry_failure_invalid_id(client):
    response = client.put("/api/v1/ledger-entries/invalid", json={
        "amount": 10.99,
        "description": "Test entry",
        "date": "2022-01-01",
        "category_id": 1,
        "transaction_id": 1
    })
    assert response.status_code == 404
    assert "id" in response.json()["detail"]

def test_delete_ledger_entry_success(client):
    response = client.delete("/api/v1/ledger-entries/1")
    assert response.status_code == 204

def test_delete_ledger_entry_failure_invalid_id(client):
    response = client.delete("/api/v1/ledger-entries/invalid")
    assert response.status_code == 404
    assert "id" in response.json()["detail"]