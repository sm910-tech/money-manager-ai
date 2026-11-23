from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.main import app
from app.models.schemas import AuthenticatedUser
from app.services.firestore_service import get_repository
from tests.conftest import InMemoryFirestoreRepository

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def authed_client():
    repo = InMemoryFirestoreRepository()
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        uid="uid-api-test", email="tester@example.com"
    )
    app.dependency_overrides[get_repository] = lambda: repo
    client = TestClient(app)
    yield client, repo
    app.dependency_overrides.clear()


def test_health_endpoint():
    client = TestClient(app)
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["integrations"]["chat_model"] == "gemini-4-hydrogen"
    assert body["integrations"]["batch_model"] == "gemini-3.5-flash-lite"


def test_upload_validation_and_full_lifecycle(authed_client):
    client, _ = authed_client

    bad_ext = client.post(
        "/api/upload",
        files={"file": ("statement.pdf", b"%PDF-1.4", "application/pdf")},
    )
    assert bad_ext.status_code == 400

    csv_bytes = (FIXTURES / "sample_statement.csv").read_bytes()
    up_resp = client.post(
        "/api/upload",
        files={"file": ("sample_statement.csv", csv_bytes, "text/csv")},
    )
    assert up_resp.status_code == 201
    up_data = up_resp.json()
    assert up_data["imported_count"] == 12
    assert up_data["duplicate_count"] == 0

    dup_resp = client.post(
        "/api/upload",
        files={"file": ("sample_statement.csv", csv_bytes, "text/csv")},
    )
    assert dup_resp.status_code == 201
    assert dup_resp.json()["imported_count"] == 0
    assert dup_resp.json()["duplicate_count"] == 12

    list_resp = client.get("/api/transactions", params={"category": "Food & Dining"})
    assert list_resp.status_code == 200
    items = list_resp.json()["transactions"]
    assert len(items) == 2

    tx_id = items[0]["id"]
    patch_resp = client.patch(
        f"/api/transactions/{tx_id}",
        json={"category": "Entertainment", "notes": "Team outing"},
    )
    assert patch_resp.status_code == 200
    patched = patch_resp.json()
    assert patched["category"] == "Entertainment"
    assert patched["user_corrected"] is True
    assert patched["category_source"] == "user"


def test_budget_operations_and_analytics_endpoints(authed_client):
    client, _ = authed_client
    csv_bytes = (FIXTURES / "sample_statement.csv").read_bytes()
    client.post("/api/upload", files={"file": ("sample.csv", csv_bytes, "text/csv")})

    put_resp = client.put(
        "/api/budgets",
        json={
            "month": "2026-11",
            "limits": {"Shopping": 2500.0, "Utilities": 2000.0, "Food & Dining": 1500.0},
        },
    )
    assert put_resp.status_code == 200
    b_data = put_resp.json()
    assert b_data["month"] == "2026-11"
    statuses = {s["category"]: s for s in b_data["statuses"]}
    assert statuses["Shopping"]["status"] == "exceeded"

    get_resp = client.get("/api/budgets", params={"month": "2026-11"})
    assert get_resp.status_code == 200
    assert get_resp.json()["limits"]["Shopping"] == 2500.0

    sum_resp = client.get("/api/analytics/summary", params={"month": "2026-11"})
    assert sum_resp.status_code == 200
    assert sum_resp.json()["total_income"] == 65000.0

    mon_resp = client.get("/api/analytics/monthly")
    assert mon_resp.status_code == 200
    assert len(mon_resp.json()["months"]) == 2


def test_chat_ai_unavailable_fallback(authed_client):
    client, _ = authed_client
    csv_bytes = (FIXTURES / "sample_statement.csv").read_bytes()
    client.post("/api/upload", files={"file": ("sample.csv", csv_bytes, "text/csv")})

    fake_settings = MagicMock(
        is_gemini_configured=False,
        gemini_chat_model="gemini-4-hydrogen",
        gemini_timeout_seconds=25,
    )
    with patch("app.services.gemini_service.get_settings", return_value=fake_settings):
        chat_resp = client.post("/api/chat", json={"message": "Summarize my spending"})
        assert chat_resp.status_code == 200
        body = chat_resp.json()
        assert body["ai_available"] is False
        assert body["model_used"] == "deterministic-fallback"
        assert body["grounded_metrics"]["total_income"] == 130000.0
        assert "130,000.00" in body["reply"]
