from unittest.mock import MagicMock, patch
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, verify_firebase_token
from app.core.security import (
    contains_sensitive_credential_request,
    sanitize_csv_cell,
    scrub_pii,
)
from app.main import app
from app.models.schemas import AuthenticatedUser, TransactionRecord
from app.services.firestore_service import get_repository
from tests.conftest import InMemoryFirestoreRepository


def test_pii_scrubbing_removes_sensitive_identifiers():
    raw = (
        "UPI/DR/SWIGGY/john.doe@okicici/9876543210/REF 123456789012 "
        "IFSC HDFC0001234 PAN ABCDE1234F CARD 4111-2222-3333-4444 CVV:999"
    )
    cleaned = scrub_pii(raw)
    assert "john.doe@okicici" not in cleaned
    assert "9876543210" not in cleaned
    assert "123456789012" not in cleaned
    assert "HDFC0001234" not in cleaned
    assert "ABCDE1234F" not in cleaned
    assert "4111-2222-3333-4444" not in cleaned
    assert "999" not in cleaned
    assert "SWIGGY" in cleaned


def test_csv_formula_injection_sanitization():
    assert sanitize_csv_cell("=CMD|' /C calc'!A0").startswith("CMD")
    assert sanitize_csv_cell("+SUM(A1:A5)").startswith("SUM")
    assert sanitize_csv_cell("@HYPERLINK(1)") == "HYPERLINK(1)"
    assert sanitize_csv_cell("UPI-SWIGGY-ORDER") == "UPI-SWIGGY-ORDER"


def test_sensitive_credential_detection():
    assert contains_sensitive_credential_request("My UPI PIN is 1234") is True
    assert contains_sensitive_credential_request("password=secretpass") is True
    assert contains_sensitive_credential_request("How much did I spend on groceries?") is False


def test_missing_authentication_token_rejected():
    client = TestClient(app)
    resp = client.get("/api/transactions")
    assert resp.status_code == 401
    assert "Missing Authorization" in resp.json()["detail"]


def test_malformed_authorization_scheme_rejected():
    client = TestClient(app)
    resp = client.get("/api/transactions", headers={"Authorization": "Basic abc123"})
    assert resp.status_code == 401


def test_invalid_and_expired_tokens_rejected():
    class FakeExpiredError(Exception):
        pass

    class FakeInvalidError(Exception):
        pass

    class FakeRevokedError(Exception):
        pass

    fake_auth = MagicMock()
    fake_auth.ExpiredIdTokenError = FakeExpiredError
    fake_auth.InvalidIdTokenError = FakeInvalidError
    fake_auth.RevokedIdTokenError = FakeRevokedError

    fake_settings = MagicMock(is_firebase_configured=True)

    with (
        patch("app.api.deps.get_settings", return_value=fake_settings),
        patch("app.api.deps.init_firebase_admin", return_value=True),
        patch.dict("sys.modules", {"firebase_admin": MagicMock(auth=fake_auth)}),
    ):
        fake_auth.verify_id_token.side_effect = FakeExpiredError("expired")
        with pytest.raises(HTTPException) as exc_exp:
            verify_firebase_token("expired-token")
        assert exc_exp.value.status_code == 401
        assert "expired" in exc_exp.value.detail.lower()

        fake_auth.verify_id_token.side_effect = FakeInvalidError("bad signature")
        with pytest.raises(HTTPException) as exc_inv:
            verify_firebase_token("tampered-token")
        assert exc_inv.value.status_code == 401
        assert "invalid" in exc_inv.value.detail.lower()


def test_cross_user_access_prevented():
    repo = InMemoryFirestoreRepository()
    user_a_tx = TransactionRecord(
        id="tx-user-a-001",
        uid="user-a",
        date="2026-11-10",
        description="UPI-SWIGGY",
        merchant="Swiggy",
        category="Food & Dining",
        amount=-450.0,
        tx_kind="expense",
    )
    repo.save_transactions("user-a", [user_a_tx])

    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(uid="user-b")
    app.dependency_overrides[get_repository] = lambda: repo
    try:
        client = TestClient(app)

        list_resp = client.get("/api/transactions")
        assert list_resp.status_code == 200
        assert list_resp.json()["total_count"] == 0

        patch_resp = client.patch(
            "/api/transactions/tx-user-a-001",
            json={"category": "Shopping"},
        )
        assert patch_resp.status_code == 404

        a_records = repo.list_transactions("user-a")
        assert a_records[0].category == "Food & Dining"
    finally:
        app.dependency_overrides.clear()
