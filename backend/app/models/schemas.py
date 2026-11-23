from datetime import datetime
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, Field, field_validator

VALID_CATEGORIES: tuple[str, ...] = (
    "Food & Dining",
    "Groceries",
    "Transport",
    "Utilities",
    "Housing & Rent",
    "Shopping",
    "Entertainment",
    "Health",
    "Education",
    "Subscriptions",
    "Transfers",
    "Refunds",
    "Income",
    "Other",
)

CategoryType = Literal[
    "Food & Dining",
    "Groceries",
    "Transport",
    "Utilities",
    "Housing & Rent",
    "Shopping",
    "Entertainment",
    "Health",
    "Education",
    "Subscriptions",
    "Transfers",
    "Refunds",
    "Income",
    "Other",
]

TransactionKind = Literal["income", "expense", "refund", "reversal", "transfer"]


class AuthenticatedUser(BaseModel):
    uid: str = Field(..., min_length=1)
    email: str | None = None


class ColumnMapping(BaseModel):
    date: str
    description: str
    amount: str | None = None
    debit: str | None = None
    credit: str | None = None
    tx_type: str | None = None
    balance: str | None = None
    reference: str | None = None


class TransactionRecord(BaseModel):
    id: str
    uid: str
    date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    description: str
    merchant: str
    category: CategoryType
    category_source: Literal["rule", "ai", "user"] = "rule"
    category_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    user_corrected: bool = False
    amount: float  # Positive for credit/inflow, Negative for debit/outflow
    tx_kind: TransactionKind
    balance: float | None = None
    source_bank: str = "generic"
    source_filename: str = ""
    row_number: int = 0
    raw_reference: str | None = None
    notes: str | None = None
    imported_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")


class TransactionPatchRequest(BaseModel):
    category: CategoryType | None = None
    merchant: str | None = Field(default=None, min_length=1, max_length=120)
    notes: str | None = Field(default=None, max_length=300)


class TransactionListResponse(BaseModel):
    transactions: list[TransactionRecord]
    total_count: int


class CategorySummary(BaseModel):
    category: str
    total: float
    percentage: float
    count: int


class MerchantSummary(BaseModel):
    merchant: str
    category: str
    total_spent: float
    transaction_count: int


class RecurringTransaction(BaseModel):
    merchant: str
    category: str
    average_amount: float
    occurrences: int
    frequency: Literal["monthly", "periodic"]
    last_date: str


class BudgetStatus(BaseModel):
    category: str
    limit: float
    spent: float
    remaining: float
    utilization_pct: float
    status: Literal["on_track", "warning", "exceeded"]


class BudgetUpdateRequest(BaseModel):
    month: str = Field(..., pattern=r"^\d{4}-\d{2}$")
    limits: dict[CategoryType, float] = Field(..., min_length=1)

    @field_validator("limits")
    @classmethod
    def validate_positive_limits(cls, v: dict[CategoryType, float]) -> dict[CategoryType, float]:
        cleaned: dict[CategoryType, float] = {}
        for cat, val in v.items():
            dec = Decimal(str(val))
            if dec < Decimal("0") or dec > Decimal("100000000"):
                raise ValueError(f"Budget limit for {cat} must be between 0 and 100,000,000.")
            cleaned[cat] = float(dec.quantize(Decimal("0.01")))
        return cleaned


class BudgetResponse(BaseModel):
    month: str
    limits: dict[str, float]
    statuses: list[BudgetStatus]
    total_budgeted: float
    total_spent_in_budgeted: float


class MonthlyPoint(BaseModel):
    month: str
    income: float
    expenses: float
    gross_expenses: float
    refunds: float
    net_savings: float
    savings_rate_pct: float
    mom_expense_change_pct: float | None = None


class MonthlyAnalyticsResponse(BaseModel):
    months: list[MonthlyPoint]


class FinancialSummary(BaseModel):
    total_income: float
    total_expenses: float
    gross_expenses: float
    total_refunds: float
    internal_transfers_in: float
    internal_transfers_out: float
    net_cash_flow: float
    savings_amount: float
    savings_rate_pct: float
    current_balance: float | None = None
    has_opening_balance: bool = False
    transaction_count: int
    mom_expense_change_pct: float | None = None
    mom_expense_delta: float | None = None
    category_breakdown: list[CategorySummary]
    budgets: list[BudgetStatus]
    top_merchants: list[MerchantSummary]
    recurring_transactions: list[RecurringTransaction]


class UploadResponse(BaseModel):
    filename: str
    detected_bank: str
    imported_count: int
    duplicate_count: int
    ai_categorized_count: int
    transactions: list[TransactionRecord]
    summary: FinancialSummary


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=1500)
    month: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}$")


class ChatResponse(BaseModel):
    reply: str
    model_used: str
    ai_available: bool
    grounded_metrics: dict
