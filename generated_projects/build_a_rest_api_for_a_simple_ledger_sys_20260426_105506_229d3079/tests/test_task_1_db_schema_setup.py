from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
from src.main import app
from src.routes.users import router as users_router
from src.routes.login import router as login_router
from src.routes.ledger_entries import router as ledger_entries_router

client = TestClient(app)

def test_create_user_success():
    with patch("src.main.SessionLocal") as mock_session:
        mock_db = MagicMock()
        mock_session.return_value = mock_db
        response = client.post("/api/v1/users", json={"username": "test", "password": "test"})
        assert response.status_code == 201
        assert response.json()["username"] == "test"

def test_create_user_failure_invalid_json():
    with patch("src.main.SessionLocal") as mock_session:
        mock_db = MagicMock()
        mock_session.return_value = mock_db
        response = client.post("/api/v1/users", json={"invalid": "json"})
        assert response.status_code == 400

def test_create_user_failure_missing_fields():
    with patch("src.main.SessionLocal") as mock_session:
        mock_db = MagicMock()
        mock_session.return_value = mock_db
        response = client.post("/api/v1/users", json={"username": "test"})
        assert response.status_code == 400

def test_login_success():
    with patch("src.main.SessionLocal") as mock_session:
        mock_db = MagicMock()
        mock_session.return_value = mock_db
        response = client.post("/api/v1/login", json={"username": "test", "password": "test"})
        assert response.status_code == 200
        assert "token" in response.json()

def test_login_failure_invalid_credentials():
    with patch("src.main.SessionLocal") as mock_session:
        mock_db = MagicMock()
        mock_session.return_value = mock_db
        response = client.post("/api/v1/login", json={"username": "test", "password": "wrong"})
        assert response.status_code == 401

def test_create_ledger_entry_success():
    with patch("src.main.SessionLocal") as mock_session:
        mock_db = MagicMock()
        mock_session.return_value = mock_db
        response = client.post("/api/v1/ledger-entries", json={"description": "test", "amount": 10.0})
        assert response.status_code == 201
        assert response.json()["description"] == "test"

def test_create_ledger_entry_failure_invalid_json():
    with patch("src.main.SessionLocal") as mock_session:
        mock_db = MagicMock()
        mock_session.return_value = mock_db
        response = client.post("/api/v1/ledger-entries", json={"invalid": "json"})
        assert response.status_code == 400

def test_get_ledger_entries_success():
    with patch("src.main.SessionLocal") as mock_session:
        mock_db = MagicMock()
        mock_session.return_value = mock_db
        response = client.get("/api/v1/ledger-entries")
        assert response.status_code == 200

def test_get_ledger_entry_success():
    with patch("src.main.SessionLocal") as mock_session:
        mock_db = MagicMock()
        mock_session.return_value = mock_db
        response = client.get("/api/v1/ledger-entries/1")
        assert response.status_code == 200

def test_get_ledger_entry_failure_not_found():
    with patch("src.main.SessionLocal") as mock_session:
        mock_db = MagicMock()
        mock_session.return_value = mock_db
        response = client.get("/api/v1/ledger-entries/999")
        assert response.status_code == 404

def test_update_ledger_entry_success():
    with patch("src.main.SessionLocal") as mock_session:
        mock_db = MagicMock()
        mock_session.return_value = mock_db
        response = client.put("/api/v1/ledger-entries/1", json={"description": "test", "amount": 10.0})
        assert response.status_code == 200

def test_update_ledger_entry_failure_not_found():
    with patch("src.main.SessionLocal") as mock_session:
        mock_db = MagicMock()
        mock_session.return_value = mock_db
        response = client.put("/api/v1/ledger-entries/999", json={"description": "test", "amount": 10.0})
        assert response.status_code == 404

def test_delete_ledger_entry_success():
    with patch("src.main.SessionLocal") as mock_session:
        mock_db = MagicMock()
        mock_session.return_value = mock_db
        response = client.delete("/api/v1/ledger-entries/1")
        assert response.status_code == 204

def test_delete_ledger_entry_failure_not_found():
    with patch("src.main.SessionLocal") as mock_session:
        mock_db = MagicMock()
        mock_session.return_value = mock_db
        response = client.delete("/api/v1/ledger-entries/999")
        assert response.status_code == 404