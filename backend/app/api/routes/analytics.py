from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import get_current_user
from app.models.schemas import (
    AuthenticatedUser,
    FinancialSummary,
    MonthlyAnalyticsResponse,
)
from app.services.analytics import (
    compute_financial_summary,
    compute_monthly_analytics,
)
from app.services.firestore_service import (
    FirestoreRepository,
    PersistenceUnavailableError,
    get_repository,
)

router = APIRouter(tags=["Analytics"])


@router.get("/analytics/summary", response_model=FinancialSummary)
def get_analytics_summary(
    month: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}$"),
    start_date: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    end_date: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    user: AuthenticatedUser = Depends(get_current_user),
    repo: FirestoreRepository = Depends(get_repository),
):
    try:
        txs = repo.list_transactions(
            uid=user.uid,
            month=month,
            start_date=start_date,
            end_date=end_date,
        )
        budget_month = month or (txs[0].date[:7] if txs else datetime.utcnow().strftime("%Y-%m"))
        budgets = repo.get_budget(user.uid, budget_month)
    except PersistenceUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc

    return compute_financial_summary(txs, monthly_budgets=budgets)


@router.get("/analytics/monthly", response_model=MonthlyAnalyticsResponse)
def get_monthly_analytics(
    user: AuthenticatedUser = Depends(get_current_user),
    repo: FirestoreRepository = Depends(get_repository),
):
    try:
        txs = repo.list_transactions(uid=user.uid)
    except PersistenceUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc

    return compute_monthly_analytics(txs)
