import json
import logging

from app.core.config import get_settings
from app.core.security import contains_sensitive_credential_request, scrub_pii
from app.models.schemas import FinancialSummary, MonthlyAnalyticsResponse

logger = logging.getLogger(__name__)

_SYSTEM_INSTRUCTION = """You are Money Manager AI, a helpful, concise personal finance assistant.
STRICT RULES:
1. Never invent, estimate, or independently recalculate authoritative totals. Rely strictly on the verified Python-computed metrics provided in the context JSON.
2. Never ask for bank passwords, internet banking credentials, card numbers, CVVs, or UPI PINs.
3. If the provided metrics have zero transactions, gently inform the user to upload a bank CSV statement rather than fabricating numbers.
4. Provide practical, empathetic, actionable explanations referencing the exact verified categories, budgets, recurring expenses, and top merchants.
5. Format monetary values clearly in INR (₹) unless the user asks otherwise."""


def _build_deterministic_fallback(summary: FinancialSummary, reason: str) -> str:
    if summary.transaction_count == 0:
        return (
            f"AI assistant is currently unavailable ({reason}). "
            "No transactions are stored in your account yet — upload a CSV bank statement to begin tracking your finances."
        )

    top_cat = summary.category_breakdown[0] if summary.category_breakdown else None
    exceeded = [b.category for b in summary.budgets if b.status == "exceeded"]
    parts = [
        f"AI narrative generation is currently unavailable ({reason}). Here is your verified Python ledger snapshot:",
        f"- Total Income: ₹{summary.total_income:,.2f}",
        f"- Net Expenses: ₹{summary.total_expenses:,.2f} (Refunds offset: ₹{summary.total_refunds:,.2f})",
        f"- Net Savings: ₹{summary.savings_amount:,.2f} ({summary.savings_rate_pct}% savings rate)",
    ]
    if top_cat:
        parts.append(f"- Top Spending Category: {top_cat.category} (₹{top_cat.total:,.2f}, {top_cat.percentage}%)")
    if exceeded:
        parts.append(f"- Exceeded Budgets: {', '.join(exceeded)}")
    return "\n".join(parts)


def generate_financial_advice(
    user_message: str,
    summary: FinancialSummary,
    monthly: MonthlyAnalyticsResponse,
) -> tuple[str, str, bool]:
    """
    Generate grounded conversational insights via gemini-4-hydrogen using ONLY
    backend-computed metrics and PII-scrubbed user text.
    """
    settings = get_settings()

    if contains_sensitive_credential_request(user_message):
        return (
            "For your security, Money Manager AI never accepts or processes bank passwords, "
            "CVVs, OTPs, or UPI PINs. Please rephrase your question without sensitive credentials.",
            "security-guard",
            True,
        )

    if not settings.is_gemini_configured:
        return (
            _build_deterministic_fallback(summary, "GEMINI_API_KEY is not configured on the server"),
            "deterministic-fallback",
            False,
        )

    try:
        from google import genai
        from google.genai import types
    except ImportError:
        logger.error("google-genai package is not installed.")
        return (
            _build_deterministic_fallback(summary, "Google Gen AI SDK is unavailable"),
            "deterministic-fallback",
            False,
        )

    sanitized_context = {
        "total_income": summary.total_income,
        "total_expenses": summary.total_expenses,
        "gross_expenses": summary.gross_expenses,
        "total_refunds": summary.total_refunds,
        "net_cash_flow": summary.net_cash_flow,
        "savings_amount": summary.savings_amount,
        "savings_rate_pct": summary.savings_rate_pct,
        "current_balance": summary.current_balance,
        "transaction_count": summary.transaction_count,
        "mom_expense_change_pct": summary.mom_expense_change_pct,
        "mom_expense_delta": summary.mom_expense_delta,
        "category_breakdown": [c.model_dump() for c in summary.category_breakdown],
        "budgets": [b.model_dump() for b in summary.budgets],
        "top_merchants": [
            {
                "merchant": scrub_pii(m.merchant),
                "category": m.category,
                "total_spent": m.total_spent,
                "transaction_count": m.transaction_count,
            }
            for m in summary.top_merchants
        ],
        "recurring_transactions": [
            {
                "merchant": scrub_pii(r.merchant),
                "category": r.category,
                "average_amount": r.average_amount,
                "occurrences": r.occurrences,
                "frequency": r.frequency,
            }
            for r in summary.recurring_transactions
        ],
        "monthly_trend": [m.model_dump() for m in monthly.months[-6:]],
    }

    safe_question = scrub_pii(user_message)
    prompt = (
        "VERIFIED PYTHON FINANCIAL METRICS (AUTHORITATIVE JSON):\n"
        f"{json.dumps(sanitized_context, ensure_ascii=True)}\n\n"
        f"USER QUESTION:\n{safe_question}"
    )

    try:
        client = genai.Client(
            api_key=settings.gemini_api_key,
            http_options=types.HttpOptions(timeout=settings.gemini_timeout_seconds * 1000),
        )
        response = client.models.generate_content(
            model=settings.gemini_chat_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=_SYSTEM_INSTRUCTION,
                temperature=0.25,
            ),
        )
        reply = (response.text or "").strip()
        if not reply:
            return (
                _build_deterministic_fallback(summary, "empty model response"),
                "deterministic-fallback",
                False,
            )
        return reply, settings.gemini_chat_model, True
    except TimeoutError:
        logger.warning("Gemini request timed out.")
        return (
            _build_deterministic_fallback(summary, "AI request timed out"),
            "deterministic-fallback",
            False,
        )
    except Exception as exc:
        err_name = type(exc).__name__
        err_str = str(exc).lower()
        if "429" in err_str or "quota" in err_str or "resource_exhausted" in err_str:
            reason = "Gemini API quota exceeded — please retry shortly"
        elif "timeout" in err_str or "deadline" in err_str:
            reason = "Gemini API request timed out"
        else:
            reason = f"Gemini service error ({err_name})"
        logger.warning("Gemini conversational request failed: %s", err_name)
        return _build_deterministic_fallback(summary, reason), "deterministic-fallback", False
