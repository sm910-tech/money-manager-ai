from collections import defaultdict
from pathlib import Path
import pytest

from app.models.schemas import TransactionPatchRequest, TransactionRecord
from app.services.firestore_service import (
    OwnershipViolationError,
    ResourceNotFoundError,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


class InMemoryFirestoreRepository:
    """
    Strict UID-scoped in-memory repository mirroring FirestoreRepository
    authorization semantics for deterministic unit and API integration tests.
    """

    def __init__(self):
        self._transactions: dict[str, dict[str, TransactionRecord]] = defaultdict(dict)
        self._budgets: dict[str, dict[str, dict[str, float]]] = defaultdict(dict)

    def get_existing_transaction_ids(self, uid: str) -> set[str]:
        return set(self._transactions[uid].keys())

    def save_transactions(self, uid: str, transactions: list[TransactionRecord]) -> int:
        count = 0
        for tx in transactions:
            if tx.uid != uid:
                raise OwnershipViolationError("Cross-user write rejected.")
            self._transactions[uid][tx.id] = tx.model_copy(deep=True)
            count += 1
        return count

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
        items: list[TransactionRecord] = []
        s_low = (search or "").strip().lower()
        for tx in self._transactions[uid].values():
            if tx.uid != uid:
                continue
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
            if s_low and (
                s_low not in tx.merchant.lower()
                and s_low not in tx.description.lower()
                and s_low not in (tx.notes or "").lower()
            ):
                continue
            items.append(tx.model_copy(deep=True))
        items.sort(key=lambda t: (t.date, t.row_number), reverse=True)
        return items

    def update_transaction(
        self,
        uid: str,
        transaction_id: str,
        patch: TransactionPatchRequest,
    ) -> TransactionRecord:
        tx = self._transactions[uid].get(transaction_id)
        if tx is None:
            raise ResourceNotFoundError("Transaction not found.")

        if tx.uid != uid:
            raise OwnershipViolationError("Transaction belongs to another user.")

        updated = tx.model_copy(deep=True)
        if patch.category is not None:
            updated.category = patch.category
            updated.category_source = "user"
            updated.category_confidence = 1.0
            updated.user_corrected = True
        if patch.merchant is not None:
            updated.merchant = patch.merchant.strip()
        if patch.notes is not None:
            updated.notes = patch.notes.strip()

        self._transactions[uid][transaction_id] = updated
        return updated.model_copy(deep=True)

    def get_budget(self, uid: str, month: str) -> dict[str, float] | None:
        raw = self._budgets[uid].get(month)
        return dict(raw) if raw is not None else None

    def upsert_budget(self, uid: str, month: str, limits: dict[str, float]) -> dict[str, float]:
        saved = {str(k): float(v) for k, v in limits.items()}
        self._budgets[uid][month] = saved
        return dict(saved)


@pytest.fixture
def in_memory_repo() -> InMemoryFirestoreRepository:
    return InMemoryFirestoreRepository()
