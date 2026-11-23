import json
import logging
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.security import scrub_pii
from app.models.schemas import CategoryType, TransactionRecord, VALID_CATEGORIES

logger = logging.getLogger(__name__)

# Deterministic merchant/narration keyword rules: (keywords, category, clean_merchant_optional)
_RULE_DEFINITIONS: list[tuple[tuple[str, ...], CategoryType, str | None]] = [
    (
        ("swiggy", "zomato", "starbucks", "mcdonald", "domino", "kfc", "burger king", "cafe", "restaurant", "bakery", "dining"),
        "Food & Dining",
        None,
    ),
    (
        ("bigbasket", "blinkit", "zepto", "instamart", "dmart", "d-mart", "reliance fresh", "supermarket", "grocery", "kirana", "more retail"),
        "Groceries",
        None,
    ),
    (
        ("uber", "ola", "rapido", "irctc", "metro", "petrol", "fuel", "hpcl", "bpcl", "iocl", "shell", "fastag", "indigo", "air india", "makemytrip"),
        "Transport",
        None,
    ),
    (
        ("electricity", "mahavitaran", "msedcl", "bescom", "tata power", "adani electricity", "airtel", "jio", "vi ", "bsnl", "broadband", "act fibernet", "water bill", "piped gas", "indane", "bharatgas"),
        "Utilities",
        None,
    ),
    (
        ("rent", "landlord", "nobroker", "society maintenance", "housing", "mortgage", "home loan emi"),
        "Housing & Rent",
        None,
    ),
    (
        ("netflix", "spotify", "prime video", "youtube premium", "hotstar", "icloud", "google one", "chatgpt", "github", "notion", "microsoft 365", "adobe"),
        "Subscriptions",
        None,
    ),
    (
        ("bookmyshow", "pvr", "inox", "cinema", "steam", "playstation", "xbox", "bowling", "concert"),
        "Entertainment",
        None,
    ),
    (
        ("amazon", "flipkart", "myntra", "ajio", "nykaa", "decathlon", "croma", "reliance digital", "ikea", "zara", "h&m"),
        "Shopping",
        None,
    ),
    (
        ("apollo", "medplus", "1mg", "pharmeasy", "pharmacy", "hospital", "clinic", "practo", "diagnostic", "pathology", "dental"),
        "Health",
        None,
    ),
    (
        ("udemy", "coursera", "tuition", "college", "university", "exam fee", "school fee", "books", "nptel"),
        "Education",
        None,
    ),
    (
        ("salary", "payroll", "stipend", "dividend", "interest credited", "int.pd", "freelance payout", "consulting fee"),
        "Income",
        None,
    ),
]

_VALID_CATEGORY_SET = set(VALID_CATEGORIES)
_BATCH_SIZE = 50


class _BatchItemOut(BaseModel):
    key: str
    category: str
    merchant_clean: str = Field(default="")


class _BatchCategorizationOut(BaseModel):
    items: list[_BatchItemOut]


def apply_deterministic_rules(tx: TransactionRecord) -> TransactionRecord:
    """Apply rule-based categorization while never overwriting user-corrected transactions."""
    if tx.user_corrected:
        return tx

    if tx.tx_kind in {"refund", "reversal"}:
        tx.category = "Refunds"
        tx.category_source = "rule"
        tx.category_confidence = 0.95
        return tx

    if tx.tx_kind == "transfer":
        tx.category = "Transfers"
        tx.category_source = "rule"
        tx.category_confidence = 0.95
        return tx

    haystack = f"{tx.merchant} {tx.description}".lower()
    for keywords, category, _ in _RULE_DEFINITIONS:
        if any(kw in haystack for kw in keywords):
            # Guard: do not misclassify genuine salary/income credits as Shopping or Food
            if tx.tx_kind == "income" and category != "Income":
                continue
            tx.category = category
            tx.category_source = "rule"
            tx.category_confidence = 0.92
            return tx

    if tx.tx_kind == "income":
        tx.category = "Income"
        tx.category_source = "rule"
        tx.category_confidence = 0.85
        return tx

    tx.category = "Other"
    tx.category_source = "rule"
    tx.category_confidence = 0.30
    return tx


def _call_gemini_batch(items: list[dict[str, str]]) -> dict[str, tuple[CategoryType, str]]:
    """
    Send a scrubbed, minimal batch of low-confidence merchant descriptors to
    gemini-3.5-flash-lite using structured JSON output.
    Returns mapping: key -> (validated_category, clean_merchant_name).
    """
    settings = get_settings()
    if not settings.is_gemini_configured or not items:
        return {}

    try:
        from google import genai
        from google.genai import types
    except ImportError:
        logger.warning("google-genai SDK not installed; using deterministic categorization fallback.")
        return {}

    prompt = (
        "Classify each personal finance transaction hint into EXACTLY ONE category from this allowed list:\n"
        f"{', '.join(VALID_CATEGORIES)}\n\n"
        "Return strict JSON matching the schema. Do not invent categories.\n"
        "Transactions (already PII-scrubbed):\n"
        f"{json.dumps(items, ensure_ascii=True)}"
    )

    try:
        client = genai.Client(
            api_key=settings.gemini_api_key,
            http_options=types.HttpOptions(timeout=settings.gemini_timeout_seconds * 1000),
        )
        response = client.models.generate_content(
            model=settings.gemini_batch_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.1,
                response_mime_type="application/json",
                response_schema=_BatchCategorizationOut,
            ),
        )
        raw_json = response.text or "{}"
        parsed = _BatchCategorizationOut.model_validate_json(raw_json)
    except Exception as exc:
        logger.warning("Gemini batch categorization failed; falling back to rules: %s", type(exc).__name__)
        return {}

    validated: dict[str, tuple[CategoryType, str]] = {}
    for entry in parsed.items:
        cat = entry.category.strip()
        if cat in _VALID_CATEGORY_SET:
            clean_merchant = scrub_pii(entry.merchant_clean)[:48].strip()
            validated[entry.key] = (cat, clean_merchant)  # type: ignore[assignment]
    return validated


def categorize_transactions(
    transactions: list[TransactionRecord],
    use_ai: bool = True,
) -> tuple[list[TransactionRecord], int]:
    """
    Hybrid categorizer:
    1. Preserves any user-corrected categories.
    2. Applies fast deterministic rules first.
    3. Batches remaining low-confidence unique merchant descriptors to gemini-3.5-flash-lite.
    4. Validates all AI outputs against VALID_CATEGORIES with deterministic fallback.
    """
    for tx in transactions:
        apply_deterministic_rules(tx)

    if not use_ai:
        return transactions, 0

    ambiguous_by_key: dict[str, list[TransactionRecord]] = {}
    batch_payload_items: list[dict[str, str]] = []

    for tx in transactions:
        if tx.user_corrected or tx.category_confidence >= 0.75:
            continue
        safe_hint = scrub_pii(f"{tx.merchant} - {tx.description}")[:90]
        key = safe_hint.lower()
        if key not in ambiguous_by_key:
            ambiguous_by_key[key] = []
            batch_payload_items.append(
                {
                    "key": key,
                    "merchant_hint": safe_hint,
                    "direction": "inflow" if tx.amount > 0 else "outflow",
                }
            )
        ambiguous_by_key[key].append(tx)

    if not batch_payload_items:
        return transactions, 0

    ai_updated_count = 0
    for start in range(0, len(batch_payload_items), _BATCH_SIZE):
        chunk = batch_payload_items[start : start + _BATCH_SIZE]
        ai_results = _call_gemini_batch(chunk)
        for key, (category, clean_merchant) in ai_results.items():
            for tx in ambiguous_by_key.get(key, []):
                if tx.user_corrected:
                    continue
                tx.category = category
                tx.category_source = "ai"
                tx.category_confidence = 0.80
                if clean_merchant:
                    tx.merchant = clean_merchant
                ai_updated_count += 1

    return transactions, ai_updated_count
