import logging
from datetime import datetime
from typing import Any

from app.core.config import get_settings
from app.models.schemas import TransactionPatchRequest, TransactionRecord

logger = logging.getLogger(__name__)

_firebase_app_initialized = False


class PersistenceUnavailableError(RuntimeError):
    """Raised when Cloud Firestore is not configured or reachable."""


class ResourceNotFoundError(LookupError):
    """Raised when a requested user-owned Firestore resource does not exist."""


class OwnershipViolationError(PermissionError):
    """Raised when a stored document UID does not match the authenticated user."""


def init_firebase_admin() -> bool:
    """Initialize Firebase Admin SDK once when configured."""
    global _firebase_app_initialized
    settings = get_settings()
    if not settings.is_firebase_configured:
        return False

    import firebase_admin
    from firebase_admin import credentials

    if not _firebase_app_initialized and not firebase_admin._apps:
        if settings.google_application_credentials:
            cred = credentials.Certificate(settings.google_application_credentials)
            firebase_admin.initialize_app(cred, {"projectId": settings.firebase_project_id})
        else:
            firebase_admin.initialize_app(options={"projectId": settings.firebase_project_id})
        _firebase_app_initialized = True
    return True


def _get_db():
    if not init_firebase_admin():
        raise PersistenceUnavailableError(
            "Firebase/Firestore is not configured. Set FIREBASE_PROJECT_ID and service account credentials."
        )
    from firebase_admin import firestore

    return firestore.client()


class FirestoreRepository:
    """
    Strict UID-scoped Firestore repository.
    Because Firebase Admin SDK bypasses Firestore Security Rules, every method
    independently enforces UID scoping and document ownership verification.
    """

    def __init__(self, db: Any | None = None):
        self._db = db

    @property
    def db(self):
        if self._db is None:
            self._db = _get_db()
        return self._db

    def _tx_collection(self, uid: str):
        if not uid or "/" in uid:
            raise ValueError("Invalid authenticated UID.")
        return self.db.collection("users").document(uid).collection("transactions")

    def _budget_collection(self, uid: str):
        if not uid or "/" in uid:
            raise ValueError("Invalid authenticated UID.")
        return self.db.collection("users").document(uid).collection("budgets")

    def get_existing_transaction_ids(self, uid: str) -> set[str]:
        col = self._tx_collection(uid)
        ids: set[str] = set()
        for doc in col.stream():
            data = doc.to_dict() or {}
            if data.get("uid") == uid:
                ids.add(doc.id)
        return ids

    def save_transactions(self, uid: str, transactions: list[TransactionRecord]) -> int:
        if not transactions:
            return 0
        col = self._tx_collection(uid)
        written = 0
        for start in range(0, len(transactions), 450):
            chunk = transactions[start : start + 450]
            batch = self.db.batch()
            for tx in chunk:
                if tx.uid != uid:
                    raise OwnershipViolationError("Transaction UID does not match authenticated user.")
                doc_ref = col.document(tx.id)
                batch.set(doc_ref, tx.model_dump(), merge=False)
                written += 1
            batch.commit()
        return written

    def list_transactions(
        self,
        uid: str,
        category: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        tx_kind: str | None = None,
        search: str | None = None,
        month: str | None = None,
    ) -> list[TransactionRecord]:
        col = self._tx_collection(uid)
        results: list[TransactionRecord] = []
        search_lower = (search or "").strip().lower()

        for doc in col.stream():
            data = doc.to_dict() or {}
            if data.get("uid") != uid:
                continue
            tx = TransactionRecord.model_validate(data)
            if month and not tx.date.startswith(month):
                continue
            if category and tx.category != category:
                continue
            if tx_kind and tx.tx_kind != tx_kind:
                continue
            if start_date and tx.date < start_date:
                continue
            if end_date and tx.date > end_date:
                continue
            if search_lower and (
                search_lower not in tx.merchant.lower()
                and search_lower not in tx.description.lower()
                and search_lower not in (tx.notes or "").lower()
            ):
                continue
            results.append(tx)

        results.sort(key=lambda t: (t.date, t.row_number), reverse=True)
        return results

    def update_transaction(
        self,
        uid: str,
        transaction_id: str,
        patch: TransactionPatchRequest,
    ) -> TransactionRecord:
        if not transaction_id or "/" in transaction_id:
            raise ResourceNotFoundError("Invalid transaction identifier.")

        doc_ref = self._tx_collection(uid).document(transaction_id)
        snapshot = doc_ref.get()
        if not snapshot.exists:
            raise ResourceNotFoundError("Transaction not found.")

        data = snapshot.to_dict() or {}
        if data.get("uid") != uid:
            raise OwnershipViolationError("Access denied: transaction belongs to another user.")

        tx = TransactionRecord.model_validate(data)
        updates: dict[str, Any] = {}

        if patch.category is not None:
            tx.category = patch.category
            tx.category_source = "user"
            tx.category_confidence = 1.0
            tx.user_corrected = True
            updates.update(
                {
                    "category": tx.category,
                    "category_source": "user",
                    "category_confidence": 1.0,
                    "user_corrected": True,
                }
            )

        if patch.merchant is not None:
            tx.merchant = patch.merchant.strip()
            updates["merchant"] = tx.merchant

        if patch.notes is not None:
            tx.notes = patch.notes.strip()
            updates["notes"] = tx.notes

        if updates:
            updates["updated_at"] = datetime.utcnow().isoformat() + "Z"
            doc_ref.update(updates)

        return tx

    def get_budget(self, uid: str, month: str) -> dict[str, float] | None:
        doc_ref = self._budget_collection(uid).document(month)
        snapshot = doc_ref.get()
        if not snapshot.exists:
            return None
        data = snapshot.to_dict() or {}
        if data.get("uid") != uid:
            raise OwnershipViolationError("Access denied: budget belongs to another user.")
        limits = data.get("limits", {})
        return {str(k): float(v) for k, v in limits.items()}

    def upsert_budget(self, uid: str, month: str, limits: dict[str, float]) -> dict[str, float]:
        doc_ref = self._budget_collection(uid).document(month)
        payload = {
            "uid": uid,
            "month": month,
            "limits": {str(k): float(v) for k, v in limits.items()},
            "updated_at": datetime.utcnow().isoformat() + "Z",
        }
        doc_ref.set(payload, merge=True)
        return payload["limits"]


def get_repository() -> FirestoreRepository:
    return FirestoreRepository()
