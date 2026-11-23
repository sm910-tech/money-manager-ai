from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import get_current_user
from app.models.schemas import (
    AuthenticatedUser,
    TransactionListResponse,
    TransactionPatchRequest,
    TransactionRecord,
)
from app.services.firestore_service import (
    FirestoreRepository,
    OwnershipViolationError,
    PersistenceUnavailableError,
    ResourceNotFoundError,
    get_repository,
)

router = APIRouter(tags=["Transactions"])


@router.get("/transactions", response_model=TransactionListResponse)
def list_user_transactions(
    category: str | None = Query(default=None),
    start_date: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    end_date: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    month: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}$"),
    tx_kind: str | None = Query(default=None),
    search: str | None = Query(default=None, max_length=100),
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    user: AuthenticatedUser = Depends(get_current_user),
    repo: FirestoreRepository = Depends(get_repository),
):
    try:
        items = repo.list_transactions(
            uid=user.uid,
            category=category,
            start_date=start_date,
            end_date=end_date,
            tx_kind=tx_kind,
            search=search,
            month=month,
        )
    except PersistenceUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    total = len(items)
    sliced = items[offset : offset + limit]
    return TransactionListResponse(transactions=sliced, total_count=total)


@router.patch("/transactions/{transaction_id}", response_model=TransactionRecord)
def update_user_transaction(
    transaction_id: str,
    patch: TransactionPatchRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    repo: FirestoreRepository = Depends(get_repository),
):
    if patch.category is None and patch.merchant is None and patch.notes is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one field (category, merchant, or notes) must be provided.",
        )

    try:
        return repo.update_transaction(user.uid, transaction_id, patch)
    except ResourceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except OwnershipViolationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except PersistenceUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
