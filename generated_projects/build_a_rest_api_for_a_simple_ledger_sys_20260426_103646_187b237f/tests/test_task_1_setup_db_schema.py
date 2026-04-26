import pytest
from fastapi.testclient import TestClient
from src.main import app

@pytest.fixture
def client():
    return TestClient(app)

def test_create_ledger_entry_success(client):
    response = client.post("/api/v1/ledger", json={"user_id": 1, "category_id": 1, "amount": 10.0, "description": "Test entry"})
    assert response.status_code == 201
    assert response.json()["id"] is not None
    assert response.json()["user_id"] == 1
    assert response.json()["category_id"] == 1
    assert response.json()["amount"] == 10.0
    assert response.json()["description"] == "Test entry"

def test_create_ledger_entry_failure_invalid_user_id(client):
    response = client.post("/api/v1/ledger", json={"user_id": "invalid", "category_id": 1, "amount": 10.0, "description": "Test entry"})
    assert response.status_code == 400
    assert "user_id" in response.json()["detail"]

def test_create_ledger_entry_failure_invalid_category_id(client):
    response = client.post("/api/v1/ledger", json={"user_id": 1, "category_id": "invalid", "amount": 10.0, "description": "Test entry"})
    assert response.status_code == 400
    assert "category_id" in response.json()["detail"]

def test_create_ledger_entry_failure_invalid_amount(client):
    response = client.post("/api/v1/ledger", json={"user_id": 1, "category_id": 1, "amount": "invalid", "description": "Test entry"})
    assert response.status_code == 400
    assert "amount" in response.json()["detail"]

def test_create_ledger_entry_failure_missing_description(client):
    response = client.post("/api/v1/ledger", json={"user_id": 1, "category_id": 1, "amount": 10.0})
    assert response.status_code == 400
    assert "description" in response.json()["detail"]

def test_get_all_ledger_entries_success(client):
    response = client.get("/api/v1/ledger")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_get_all_ledger_entries_failure_unauthenticated(client):
    response = client.get("/api/v1/ledger")
    assert response.status_code == 401

def test_get_ledger_entry_success(client):
    response = client.get("/api/v1/ledger/1")
    assert response.status_code == 200
    assert response.json()["id"] == 1

def test_get_ledger_entry_failure_invalid_id(client):
    response = client.get("/api/v1/ledger/invalid")
    assert response.status_code == 404

def test_get_ledger_entry_failure_unauthenticated(client):
    response = client.get("/api/v1/ledger/1")
    assert response.status_code == 401

def test_update_ledger_entry_success(client):
    response = client.put("/api/v1/ledger/1", json={"user_id": 1, "category_id": 1, "amount": 10.0, "description": "Updated entry"})
    assert response.status_code == 200
    assert response.json()["id"] == 1
    assert response.json()["user_id"] == 1
    assert response.json()["category_id"] == 1
    assert response.json()["amount"] == 10.0
    assert response.json()["description"] == "Updated entry"

def test_update_ledger_entry_failure_invalid_id(client):
    response = client.put("/api/v1/ledger/invalid", json={"user_id": 1, "category_id": 1, "amount": 10.0, "description": "Updated entry"})
    assert response.status_code == 404

def test_update_ledger_entry_failure_unauthenticated(client):
    response = client.put("/api/v1/ledger/1", json={"user_id": 1, "category_id": 1, "amount": 10.0, "description": "Updated entry"})
    assert response.status_code == 401

def test_delete_ledger_entry_success(client):
    response = client.delete("/api/v1/ledger/1")
    assert response.status_code == 204

def test_delete_ledger_entry_failure_invalid_id(client):
    response = client.delete("/api/v1/ledger/invalid")
    assert response.status_code == 404

def test_delete_ledger_entry_failure_unauthenticated(client):
    response = client.delete("/api/v1/ledger/1")
    assert response.status_code == 401