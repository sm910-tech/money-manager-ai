from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_user
from app.models.schemas import AuthenticatedUser, ChatRequest, ChatResponse
from app.services.analytics import (
    compute_financial_summary,
    compute_monthly_analytics,
)
from app.services.firestore_service import (
    FirestoreRepository,
    PersistenceUnavailableError,
    get_repository,
)
from app.services.gemini_service import generate_financial_advice

router = APIRouter(tags=["AI Assistant"])


@router.post("/chat", response_model=ChatResponse)
def chat_with_assistant(
    payload: ChatRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    repo: FirestoreRepository = Depends(get_repository),
):
    try:
        all_txs = repo.list_transactions(uid=user.uid)
        filtered_txs = (
            [t for t in all_txs if t.date.startswith(payload.month)]
            if payload.month
            else all_txs
        )
        budget_month = payload.month or (
            filtered_txs[0].date[:7] if filtered_txs else datetime.utcnow().strftime("%Y-%m")
        )
        budgets = repo.get_budget(user.uid, budget_month)
    except PersistenceUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc

    summary = compute_financial_summary(filtered_txs, monthly_budgets=budgets)
    monthly = compute_monthly_analytics(all_txs)

    reply, model_used, ai_available = generate_financial_advice(
        user_message=payload.message,
        summary=summary,
        monthly=monthly,
    )

    return ChatResponse(
        reply=reply,
        model_used=model_used,
        ai_available=ai_available,
        grounded_metrics={
            "total_income": summary.total_income,
            "total_expenses": summary.total_expenses,
            "total_refunds": summary.total_refunds,
            "net_cash_flow": summary.net_cash_flow,
            "savings_rate_pct": summary.savings_rate_pct,
            "transaction_count": summary.transaction_count,
        },
    )
