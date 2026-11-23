from collections import defaultdict
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
import re

from app.models.schemas import (
    BudgetStatus,
    CategorySummary,
    FinancialSummary,
    MerchantSummary,
    MonthlyAnalyticsResponse,
    MonthlyPoint,
    RecurringTransaction,
    TransactionRecord,
)

TWO_PLACES = Decimal("0.01")
ONE_PLACE = Decimal("0.1")

DEFAULT_MONTHLY_BUDGETS: dict[str, float] = {
    "Food & Dining": 6000.0,
    "Groceries": 8000.0,
    "Transport": 4000.0,
    "Utilities": 3500.0,
    "Housing & Rent": 15000.0,
    "Shopping": 5000.0,
    "Subscriptions": 1500.0,
    "Entertainment": 2000.0,
    "Health": 3000.0,
}


def _d(value: float | int | str | Decimal) -> Decimal:
    return Decimal(str(value)).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def _round2(value: Decimal) -> float:
    return float(value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP))


def _round1(value: Decimal) -> float:
    return float(value.quantize(ONE_PLACE, rounding=ROUND_HALF_UP))


def _normalize_merchant_key(merchant: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", " ", (merchant or "").lower()).strip()
    return cleaned or "unknown"


def compute_budget_statuses(
    spent_by_category: dict[str, Decimal],
    monthly_budgets: dict[str, float] | None = None,
) -> list[BudgetStatus]:
    budgets_map = monthly_budgets if monthly_budgets is not None else DEFAULT_MONTHLY_BUDGETS
    statuses: list[BudgetStatus] = []

    for cat, raw_limit in budgets_map.items():
        limit_dec = _d(raw_limit)
        spent_dec = spent_by_category.get(cat, Decimal("0.00"))
        remaining_dec = limit_dec - spent_dec

        if limit_dec > Decimal("0.00"):
            util_dec = (spent_dec / limit_dec) * Decimal("100")
        elif spent_dec > Decimal("0.00"):
            util_dec = Decimal("100.0")
        else:
            util_dec = Decimal("0.0")

        if util_dec > Decimal("100.0"):
            status = "exceeded"
        elif util_dec >= Decimal("80.0"):
            status = "warning"
        else:
            status = "on_track"

        statuses.append(
            BudgetStatus(
                category=cat,
                limit=_round2(limit_dec),
                spent=_round2(spent_dec),
                remaining=_round2(remaining_dec),
                utilization_pct=_round1(util_dec),
                status=status,
            )
        )

    statuses.sort(key=lambda b: b.utilization_pct, reverse=True)
    return statuses


def detect_recurring_transactions(transactions: list[TransactionRecord]) -> list[RecurringTransaction]:
    """
    Detect recurring expense streams deterministically.
    A merchant is flagged as recurring if it appears in >= 2 distinct calendar months
    OR >= 2 occurrences spaced 25-35 days apart with amounts within +/-20% of the mean.
    """
    grouped: dict[str, list[TransactionRecord]] = defaultdict(list)
    for tx in transactions:
        if tx.tx_kind == "expense" and tx.amount < 0:
            key = _normalize_merchant_key(tx.merchant)
            grouped[key].append(tx)

    recurring: list[RecurringTransaction] = []
    for _, items in grouped.items():
        if len(items) < 2:
            continue

        items_sorted = sorted(items, key=lambda x: x.date)
        amounts = [abs(_d(x.amount)) for x in items_sorted]
        avg_amt = sum(amounts, Decimal("0.00")) / Decimal(len(amounts))
        if avg_amt <= Decimal("0.00"):
            continue

        within_band = all(
            abs(a - avg_amt) <= (avg_amt * Decimal("0.20")) for a in amounts
        )
        if not within_band:
            continue

        distinct_months = {x.date[:7] for x in items_sorted}
        dates = [datetime.strptime(x.date, "%Y-%m-%d") for x in items_sorted]
        day_gaps = [(dates[i] - dates[i - 1]).days for i in range(1, len(dates))]
        monthly_cadence = any(25 <= gap <= 35 for gap in day_gaps)

        if len(distinct_months) >= 2 or monthly_cadence:
            recurring.append(
                RecurringTransaction(
                    merchant=items_sorted[-1].merchant,
                    category=items_sorted[-1].category,
                    average_amount=_round2(avg_amt),
                    occurrences=len(items_sorted),
                    frequency="monthly" if monthly_cadence else "periodic",
                    last_date=items_sorted[-1].date,
                )
            )

    recurring.sort(key=lambda r: r.average_amount, reverse=True)
    return recurring


def compute_monthly_analytics(transactions: list[TransactionRecord]) -> MonthlyAnalyticsResponse:
    """Compute deterministic month-by-month income, expenses, refunds, savings, and MoM deltas."""
    if not transactions:
        return MonthlyAnalyticsResponse(months=[])

    buckets: dict[str, dict[str, Decimal]] = defaultdict(
        lambda: {
            "income": Decimal("0.00"),
            "gross_expenses": Decimal("0.00"),
            "refunds": Decimal("0.00"),
        }
    )

    for tx in transactions:
        ym = tx.date[:7]
        amt = _d(tx.amount)
        if tx.tx_kind == "income" and amt > Decimal("0.00"):
            buckets[ym]["income"] += amt
        elif tx.tx_kind == "expense" and amt < Decimal("0.00"):
            buckets[ym]["gross_expenses"] += abs(amt)
        elif tx.tx_kind in {"refund", "reversal"} and amt > Decimal("0.00"):
            buckets[ym]["refunds"] += amt

    months_out: list[MonthlyPoint] = []
    prev_net_expenses: Decimal | None = None

    for ym in sorted(buckets.keys()):
        inc = buckets[ym]["income"]
        gross_exp = buckets[ym]["gross_expenses"]
        refunds = buckets[ym]["refunds"]
        net_exp = max(Decimal("0.00"), gross_exp - refunds)
        net_sav = inc - net_exp
        sav_rate = (net_sav / inc * Decimal("100")) if inc > Decimal("0.00") else Decimal("0.0")

        mom_pct: float | None = None
        if prev_net_expenses is not None and prev_net_expenses > Decimal("0.00"):
            delta_pct = ((net_exp - prev_net_expenses) / prev_net_expenses) * Decimal("100")
            mom_pct = _round1(delta_pct)

        months_out.append(
            MonthlyPoint(
                month=ym,
                income=_round2(inc),
                expenses=_round2(net_exp),
                gross_expenses=_round2(gross_exp),
                refunds=_round2(refunds),
                net_savings=_round2(net_sav),
                savings_rate_pct=_round1(sav_rate),
                mom_expense_change_pct=mom_pct,
            )
        )
        prev_net_expenses = net_exp

    return MonthlyAnalyticsResponse(months=months_out)


def compute_financial_summary(
    transactions: list[TransactionRecord],
    monthly_budgets: dict[str, float] | None = None,
    opening_balance: Decimal | None = None,
) -> FinancialSummary:
    """
    Authoritative Python Decimal financial calculation engine.
    All monetary arithmetic happens here — never delegated to an LLM.
    """
    if not transactions:
        return FinancialSummary(
            total_income=0.0,
            total_expenses=0.0,
            gross_expenses=0.0,
            total_refunds=0.0,
            internal_transfers_in=0.0,
            internal_transfers_out=0.0,
            net_cash_flow=0.0,
            savings_amount=0.0,
            savings_rate_pct=0.0,
            current_balance=_round2(opening_balance) if opening_balance is not None else None,
            has_opening_balance=opening_balance is not None,
            transaction_count=0,
            mom_expense_change_pct=None,
            mom_expense_delta=None,
            category_breakdown=[],
            budgets=compute_budget_statuses({}, monthly_budgets),
            top_merchants=[],
            recurring_transactions=[],
        )

    total_income = Decimal("0.00")
    gross_expenses = Decimal("0.00")
    total_refunds = Decimal("0.00")
    transfers_in = Decimal("0.00")
    transfers_out = Decimal("0.00")
    total_ledger_delta = Decimal("0.00")

    spent_by_cat: dict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))
    count_by_cat: dict[str, int] = defaultdict(int)
    merchant_totals: dict[str, dict] = {}

    for tx in transactions:
        amt = _d(tx.amount)
        total_ledger_delta += amt

        if tx.tx_kind == "income" and amt > Decimal("0.00"):
            total_income += amt
        elif tx.tx_kind == "expense" and amt < Decimal("0.00"):
            abs_amt = abs(amt)
            gross_expenses += abs_amt
            spent_by_cat[tx.category] += abs_amt
            count_by_cat[tx.category] += 1

            m_key = _normalize_merchant_key(tx.merchant)
            if m_key not in merchant_totals:
                merchant_totals[m_key] = {
                    "merchant": tx.merchant,
                    "category": tx.category,
                    "total": Decimal("0.00"),
                    "count": 0,
                }
            merchant_totals[m_key]["total"] += abs_amt
            merchant_totals[m_key]["count"] += 1
        elif tx.tx_kind in {"refund", "reversal"} and amt > Decimal("0.00"):
            total_refunds += amt
        elif tx.tx_kind == "transfer":
            if amt > Decimal("0.00"):
                transfers_in += amt
            elif amt < Decimal("0.00"):
                transfers_out += abs(amt)

    # Net expenses offset refunds/reversals without inflating income
    net_expenses = max(Decimal("0.00"), gross_expenses - total_refunds)
    net_cash_flow = total_income - net_expenses
    savings_amount = net_cash_flow
    savings_rate_pct = (
        (savings_amount / total_income) * Decimal("100")
        if total_income > Decimal("0.00")
        else Decimal("0.0")
    )

    txs_with_balance = [tx for tx in transactions if tx.balance is not None]
    current_balance: float | None = None
    has_opening_balance = opening_balance is not None
    if txs_with_balance:
        latest_bal_tx = max(txs_with_balance, key=lambda t: (t.date, t.row_number))
        current_balance = _round2(_d(latest_bal_tx.balance))  # type: ignore[arg-type]
        has_opening_balance = True
    elif opening_balance is not None:
        current_balance = _round2(opening_balance + total_ledger_delta)

    category_breakdown: list[CategorySummary] = []
    if gross_expenses > Decimal("0.00"):
        for cat, cat_total in sorted(spent_by_cat.items(), key=lambda kv: kv[1], reverse=True):
            pct = (cat_total / gross_expenses) * Decimal("100")
            category_breakdown.append(
                CategorySummary(
                    category=cat,
                    total=_round2(cat_total),
                    percentage=_round1(pct),
                    count=count_by_cat[cat],
                )
            )

    top_merchants = [
        MerchantSummary(
            merchant=item["merchant"],
            category=item["category"],
            total_spent=_round2(item["total"]),
            transaction_count=item["count"],
        )
        for item in sorted(merchant_totals.values(), key=lambda x: x["total"], reverse=True)[:8]
    ]

    monthly_series = compute_monthly_analytics(transactions).months
    mom_pct: float | None = None
    mom_delta: float | None = None
    if len(monthly_series) >= 2:
        latest_m = monthly_series[-1]
        prev_m = monthly_series[-2]
        mom_delta = _round2(_d(latest_m.expenses) - _d(prev_m.expenses))
        mom_pct = latest_m.mom_expense_change_pct

    return FinancialSummary(
        total_income=_round2(total_income),
        total_expenses=_round2(net_expenses),
        gross_expenses=_round2(gross_expenses),
        total_refunds=_round2(total_refunds),
        internal_transfers_in=_round2(transfers_in),
        internal_transfers_out=_round2(transfers_out),
        net_cash_flow=_round2(net_cash_flow),
        savings_amount=_round2(savings_amount),
        savings_rate_pct=_round1(savings_rate_pct),
        current_balance=current_balance,
        has_opening_balance=has_opening_balance,
        transaction_count=len(transactions),
        mom_expense_change_pct=mom_pct,
        mom_expense_delta=mom_delta,
        category_breakdown=category_breakdown,
        budgets=compute_budget_statuses(spent_by_cat, monthly_budgets),
        top_merchants=top_merchants,
        recurring_transactions=detect_recurring_transactions(transactions),
    )
