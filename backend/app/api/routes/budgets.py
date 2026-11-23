from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import get_current_user
from app.models.schemas import AuthenticatedUser, BudgetResponse, BudgetUpdateRequest
from app.services.analytics import DEFAULT_MONTHLY_BUDGETS, compute_budget_statuses
from app.services.firestore_service import (
    FirestoreRepository,
    OwnershipViolationError,
    PersistenceUnavailableError,
    get_repository,
)

router = APIRouter(tags=["Budgets"])


def _build_budget_response(
    repo: FirestoreRepository,
    uid: str,
    month: str,
    limits: dict[str, float],
) -> BudgetResponse:
    txs = repo.list_transactions(uid=uid, month=month)
    spent_by_cat: dict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))
    for tx in txs:
        if tx.tx_kind == "expense" and tx.amount < 0:
            spent_by_cat[tx.category] += abs(Decimal(str(tx.amount)))

    statuses = compute_budget_statuses(spent_by_cat, monthly_budgets=limits)
    total_budgeted = round(sum(b.limit for b in statuses), 2)
    total_spent = round(sum(b.spent for b in statuses), 2)
    return BudgetResponse(
        month=month,
        limits=limits,
        statuses=statuses,
        total_budgeted=total_budgeted,
        total_spent_in_budgeted=total_spent,
    )


@router.get("/budgets", response_model=BudgetResponse)
def get_monthly_budgets(
    month: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}$"),
    user: AuthenticatedUser = Depends(get_current_user),
    repo: FirestoreRepository = Depends(get_repository),
):
    target_month = month or datetime.utcnow().strftime("%Y-%m")
    try:
        stored = repo.get_budget(user.uid, target_month)
        limits = stored if stored is not None else dict(DEFAULT_MONTHLY_BUDGETS)
        return _build_budget_response(repo, user.uid, target_month, limits)
    except OwnershipViolationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except PersistenceUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc


@router.put("/budgets", response_model=BudgetResponse)
def upsert_monthly_budgets(
    payload: BudgetUpdateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    repo: FirestoreRepository = Depends(get_repository),
):
    try:
        saved_limits = repo.upsert_budget(user.uid, payload.month, dict(payload.limits))
        return _build_budget_response(repo, user.uid, payload.month, saved_limits)
    except OwnershipViolationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except PersistenceUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
