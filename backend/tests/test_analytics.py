from decimal import Decimal
from pathlib import Path

from app.models.schemas import TransactionRecord
from app.services.analytics import (
    compute_financial_summary,
    compute_monthly_analytics,
)
from app.services.categorizer import categorize_transactions
from app.services.csv_parser import parse_bank_csv

FIXTURES = Path(__file__).parent / "fixtures"


def test_empty_dataset_analytics():
    summary = compute_financial_summary([])
    assert summary.total_income == 0.0
    assert summary.total_expenses == 0.0
    assert summary.net_cash_flow == 0.0
    assert summary.savings_rate_pct == 0.0
    assert summary.transaction_count == 0
    assert summary.category_breakdown == []
    assert summary.recurring_transactions == []

    monthly = compute_monthly_analytics([])
    assert monthly.months == []


def test_deterministic_income_expense_refund_transfer_and_recurring_calculations():
    raw = (FIXTURES / "sample_statement.csv").read_bytes()
    txs, _, _ = parse_bank_csv(raw, uid="u-an")
    txs, _ = categorize_transactions(txs, use_ai=False)

    summary = compute_financial_summary(
        txs,
        monthly_budgets={"Shopping": 3000.0, "Utilities": 4000.0, "Food & Dining": 2000.0},
    )

    assert summary.total_income == 130000.0
    assert summary.gross_expenses == 11768.0
    assert summary.total_refunds == 400.0
    assert summary.total_expenses == 11368.0
    assert summary.internal_transfers_out == 10000.0
    assert summary.net_cash_flow == 118632.0
    assert summary.savings_amount == 118632.0
    assert summary.savings_rate_pct == 91.3
    assert summary.current_balance == 158632.0

    budget_by_cat = {b.category: b for b in summary.budgets}
    assert budget_by_cat["Shopping"].status == "exceeded"
    assert budget_by_cat["Shopping"].remaining == -400.0
    assert budget_by_cat["Utilities"].status == "warning"

    rec_merchants = {r.merchant.lower() for r in summary.recurring_transactions}
    assert any("netflix" in m for m in rec_merchants)
    assert any("mahavitaran" in m or "electricity" in m for m in rec_merchants)

    monthly = compute_monthly_analytics(txs)
    assert len(monthly.months) == 2
    assert monthly.months[0].month == "2026-10"
    assert monthly.months[1].month == "2026-11"
    assert monthly.months[1].mom_expense_change_pct is not None


def test_negative_cash_flow_and_decimal_precision():
    txs = [
        TransactionRecord(
            id="t1",
            uid="u-neg",
            date="2026-11-01",
            description="SALARY",
            merchant="Employer",
            category="Income",
            amount=10000.00,
            tx_kind="income",
        ),
        TransactionRecord(
            id="t2",
            uid="u-neg",
            date="2026-11-05",
            description="RENT",
            merchant="Landlord",
            category="Housing & Rent",
            amount=-12000.10,
            tx_kind="expense",
        ),
        TransactionRecord(
            id="t3",
            uid="u-neg",
            date="2026-11-06",
            description="CAFE",
            merchant="Cafe",
            category="Food & Dining",
            amount=-499.90,
            tx_kind="expense",
        ),
    ]
    summary = compute_financial_summary(txs, opening_balance=Decimal("5000.00"))
    assert summary.total_income == 10000.0
    assert summary.total_expenses == 12500.0
    assert summary.net_cash_flow == -2500.0
    assert summary.savings_amount == -2500.0
    assert summary.savings_rate_pct == -25.0
    assert summary.current_balance == 2500.0
