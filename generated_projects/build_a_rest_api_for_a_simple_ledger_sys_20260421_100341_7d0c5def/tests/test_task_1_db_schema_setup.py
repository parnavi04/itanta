import pytest
from fastapi.testclient import TestClient
from src.main import app

@pytest.fixture
def client():
    return TestClient(app)

def test_create_ledger_entry_success(client):
    response = client.post("/api/v1/ledger-entries", json={"amount": 10.0, "description": "Test", "date": "2022-01-01", "category_id": 1})
    assert response.status_code == 201
    assert response.json()["amount"] == 10.0
    assert response.json()["description"] == "Test"
    assert response.json()["date"] == "2022-01-01"
    assert response.json()["category_id"] == 1

def test_create_ledger_entry_failure_invalid_amount(client):
    response = client.post("/api/v1/ledger-entries", json={"amount": "invalid", "description": "Test", "date": "2022-01-01", "category_id": 1})
    assert response.status_code == 400

def test_create_ledger_entry_failure_missing_description(client):
    response = client.post("/api/v1/ledger-entries", json={"amount": 10.0, "date": "2022-01-01", "category_id": 1})
    assert response.status_code == 400

def test_create_ledger_entry_failure_invalid_date(client):
    response = client.post("/api/v1/ledger-entries", json={"amount": 10.0, "description": "Test", "date": "invalid", "category_id": 1})
    assert response.status_code == 400

def test_create_ledger_entry_failure_missing_category_id(client):
    response = client.post("/api/v1/ledger-entries", json={"amount": 10.0, "description": "Test", "date": "2022-01-01"})
    assert response.status_code == 400

def test_get_ledger_entries_success(client):
    response = client.get("/api/v1/ledger-entries")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_get_ledger_entries_failure_unauthenticated(client):
    response = client.get("/api/v1/ledger-entries")
    assert response.status_code == 401

def test_get_ledger_entry_success(client):
    response = client.get("/api/v1/ledger-entries/1")
    assert response.status_code == 200
    assert response.json()["id"] == 1

def test_get_ledger_entry_failure_invalid_id(client):
    response = client.get("/api/v1/ledger-entries/invalid")
    assert response.status_code == 404

def test_get_ledger_entry_failure_unauthenticated(client):
    response = client.get("/api/v1/ledger-entries/1")
    assert response.status_code == 401

def test_update_ledger_entry_success(client):
    response = client.put("/api/v1/ledger-entries/1", json={"amount": 20.0, "description": "Test updated", "date": "2022-01-02", "category_id": 2})
    assert response.status_code == 200
    assert response.json()["amount"] == 20.0
    assert response.json()["description"] == "Test updated"
    assert response.json()["date"] == "2022-01-02"
    assert response.json()["category_id"] == 2

def test_update_ledger_entry_failure_invalid_id(client):
    response = client.put("/api/v1/ledger-entries/invalid", json={"amount": 20.0, "description": "Test updated", "date": "2022-01-02", "category_id": 2})
    assert response.status_code == 404

def test_update_ledger_entry_failure_unauthenticated(client):
    response = client.put("/api/v1/ledger-entries/1", json={"amount": 20.0, "description": "Test updated", "date": "2022-01-02", "category_id": 2})
    assert response.status_code == 401

def test_delete_ledger_entry_success(client):
    response = client.delete("/api/v1/ledger-entries/1")
    assert response.status_code == 204

def test_delete_ledger_entry_failure_invalid_id(client):
    response = client.delete("/api/v1/ledger-entries/invalid")
    assert response.status_code == 404

def test_delete_ledger_entry_failure_unauthenticated(client):
    response = client.delete("/api/v1/ledger-entries/1")
    assert response.status_code == 401