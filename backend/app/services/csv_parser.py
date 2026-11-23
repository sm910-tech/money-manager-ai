import csv
import hashlib
import io
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import pandas as pd

from app.core.security import sanitize_csv_cell, scrub_pii
from app.models.schemas import ColumnMapping, TransactionKind, TransactionRecord


class CSVValidationError(ValueError):
    """Raised when uploaded CSV fails validation."""


class AmbiguousCSVError(CSVValidationError):
    """Raised when CSV column layout or amount polarity is ambiguous and requires user mapping."""

    def __init__(
        self,
        message: str,
        headers: list[str],
        sample_rows: list[dict[str, str]],
        suggested_mapping: dict[str, str | None] | None = None,
    ):
        super().__init__(message)
        self.headers = headers
        self.sample_rows = sample_rows
        self.suggested_mapping = suggested_mapping or {}


_COLUMN_ALIASES: dict[str, list[str]] = {
    "date": [
        "txn date",
        "transaction date",
        "date",
        "value date",
        "value dt",
        "posting date",
        "trans date",
    ],
    "description": [
        "description",
        "narration",
        "transaction remarks",
        "particulars",
        "details",
        "remarks",
        "merchant",
        "memo",
    ],
    "debit": [
        "withdrawal amt.",
        "withdrawal amt",
        "withdrawal amount (inr )",
        "withdrawal amount (inr)",
        "withdrawal amount",
        "withdrawal",
        "debit",
        "debit amount",
        "dr",
        "dr amount",
    ],
    "credit": [
        "deposit amt.",
        "deposit amt",
        "deposit amount (inr )",
        "deposit amount (inr)",
        "deposit amount",
        "deposit",
        "credit",
        "credit amount",
        "cr",
        "cr amount",
    ],
    "amount": [
        "amount",
        "txn amount",
        "transaction amount",
        "amount (inr)",
        "amount(inr)",
    ],
    "tx_type": [
        "type",
        "transaction type",
        "txn type",
        "dr/cr",
        "cr/dr",
        "direction",
    ],
    "balance": [
        "closing balance",
        "balance (inr )",
        "balance (inr)",
        "balance",
        "running balance",
        "available balance",
    ],
    "reference": [
        "ref no./cheque no.",
        "chq./ref.no.",
        "cheque number",
        "ref no",
        "reference",
        "reference no",
        "utr",
        "transaction id",
    ],
}

_DATE_FORMATS: tuple[str, ...] = (
    "%Y-%m-%d",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%d/%m/%y",
    "%d-%m-%y",
    "%d-%b-%Y",
    "%d %b %Y",
    "%d-%b-%y",
    "%d %b %y",
    "%Y/%m/%d",
    "%d.%m.%Y",
    "%m/%d/%Y",
)

_REFUND_KEYWORDS = (
    "refund",
    "cashback",
    "chargeback",
    "credit adjustment",
    "merchant refund",
    "returned order",
    "return credit",
)
_REVERSAL_KEYWORDS = (
    "reversal",
    "rev/",
    "rev-",
    "auto rev",
    "failed txn",
    "txn rev",
    "upi rev",
)
_INTERNAL_TRANSFER_KEYWORDS = (
    "self transfer",
    "own account",
    "internal transfer",
    "transfer to self",
    "transfer from self",
    "credit card bill",
    "credit card payment",
    "cc bill",
    "cc payment",
    "wallet topup",
    "wallet load",
    "sweep transfer",
    "fd booking",
    "rd installment",
    "savings transfer",
)


def _normalize_header(header: str) -> str:
    return re.sub(r"\s+", " ", str(header or "").strip().lower())


def _detect_header_row_index(raw_text: str) -> int:
    """
    Scan the first 25 lines to locate the true CSV header row.
    Real SBI, HDFC, and ICICI exports often include account summary banners at the top.
    """
    lines = raw_text.splitlines()[:25]
    best_idx = 0
    best_score = -1

    all_date_aliases = set(_COLUMN_ALIASES["date"])
    all_desc_aliases = set(_COLUMN_ALIASES["description"])
    all_amt_aliases = set(
        _COLUMN_ALIASES["amount"] + _COLUMN_ALIASES["debit"] + _COLUMN_ALIASES["credit"]
    )

    for idx, line in enumerate(lines):
        if not line.strip():
            continue
        try:
            cells = next(csv.reader([line]))
        except Exception:
            continue
        if len(cells) < 3:
            continue
        norm_cells = {_normalize_header(c) for c in cells}
        score = 0
        if norm_cells & all_date_aliases:
            score += 3
        if norm_cells & all_desc_aliases:
            score += 3
        if norm_cells & all_amt_aliases:
            score += 3
        if score > best_score:
            best_score = score
            best_idx = idx
        if score >= 9:
            return idx

    return best_idx if best_score >= 6 else 0


def detect_bank_format(columns: list[str]) -> str:
    """Identify bank CSV format based on canonical column signatures."""
    norm = {_normalize_header(c) for c in columns}
    if {"narration", "withdrawal amt.", "deposit amt."} <= norm or "chq./ref.no." in norm:
        return "hdfc"
    if {"txn date", "ref no./cheque no."} <= norm or (
        "txn date" in norm and "debit" in norm and "credit" in norm
    ):
        return "sbi"
    if "transaction remarks" in norm or any("withdrawal amount (inr" in c for c in norm):
        return "icici"
    return "generic"


def _match_column(columns: list[str], key: str) -> str | None:
    norm_to_orig = {_normalize_header(c): c for c in columns}
    for alias in _COLUMN_ALIASES[key]:
        if alias in norm_to_orig:
            return norm_to_orig[alias]
    # Secondary substring match for trailing/variant currency annotations
    for alias in _COLUMN_ALIASES[key]:
        for norm_col, orig_col in norm_to_orig.items():
            if alias == norm_col or (len(alias) >= 6 and alias in norm_col):
                return orig_col
    return None


def _parse_date(raw_value: str) -> str | None:
    text = str(raw_value or "").strip()
    if not text or text.lower() in {"nan", "none", "nat", "-"}:
        return None
    # Strip trailing timestamps if present
    text_clean = (
        text.split("T")[0].split(" ")[0]
        if re.match(r"^\d{2,4}[-/.]\d{2}[-/.]\d{2,4}", text)
        else text
    )
    for fmt in _DATE_FORMATS:
        try:
            dt = datetime.strptime(text_clean, fmt)
            if 2000 <= dt.year <= 2100:
                return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def _parse_decimal(raw_value: object) -> Decimal | None:
    if raw_value is None:
        return None
    text = str(raw_value).strip()
    if not text or text.lower() in {"nan", "none", "-", "--", "null"}:
        return None

    is_negative = False
    if text.startswith("(") and text.endswith(")"):
        is_negative = True
        text = text[1:-1].strip()

    upper = text.upper()
    if upper.endswith("DR"):
        is_negative = True
        text = text[:-2].strip()
    elif upper.endswith("CR"):
        text = text[:-2].strip()

    cleaned = re.sub(r"[₹$,\s]|(?i)\b(?:INR|RS\.?)\b", "", text)
    if not cleaned:
        return None
    try:
        dec = Decimal(cleaned)
    except InvalidOperation:
        return None

    if is_negative and dec > 0:
        dec = -dec
    return dec.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def classify_transaction_kind(raw_description: str, signed_amount: Decimal) -> TransactionKind:
    """
    Accurately differentiate income, expenses, refunds, reversals, and internal transfers.
    Does NOT automatically treat every positive inflow as income.
    """
    lower = raw_description.lower()

    if any(kw in lower for kw in _INTERNAL_TRANSFER_KEYWORDS):
        return "transfer"

    if signed_amount > Decimal("0"):
        if any(kw in lower for kw in _REVERSAL_KEYWORDS):
            return "reversal"
        if any(kw in lower for kw in _REFUND_KEYWORDS):
            return "refund"
        return "income"

    return "expense"


def _extract_merchant_hint(scrubbed_description: str) -> str:
    """Extract a clean readable merchant label from a scrubbed narration string."""
    if not scrubbed_description:
        return "Unknown Merchant"
    text = re.sub(
        r"(?i)^(?:upi|neft|imps|rtgs|pos|ecom|ach|nach|atm|bil)[/\-\s]+",
        "",
        scrubbed_description,
    )
    parts = [p.strip() for p in re.split(r"[/\-|]+", text) if p.strip()]
    useful = [
        p
        for p in parts
        if p not in {"[REF]", "[UPI_OR_EMAIL]", "[PHONE]", "[CARD]", "CR", "DR", "IN", "INDIA"}
        and not p.isdigit()
    ]
    label = useful[0] if useful else scrubbed_description
    return label[:48].strip() or "Unknown Merchant"


def _compute_stable_tx_id(
    uid: str,
    iso_date: str,
    signed_amount: Decimal,
    normalized_desc: str,
    raw_ref: str | None,
    balance: Decimal | None,
) -> str:
    """
    Generate a deterministic SHA-256 transaction ID scoped to the user.
    Including reference number or closing balance preserves distinct identical same-day
    purchases while reliably catching re-uploads of the exact same statement rows.
    """
    ref_part = (raw_ref or "").strip().lower()
    bal_part = f"{balance:.2f}" if balance is not None else ""
    payload = f"{uid}|{iso_date}|{signed_amount:.2f}|{normalized_desc}|{ref_part}|{bal_part}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


def parse_bank_csv(
    file_bytes: bytes,
    uid: str,
    filename: str = "statement.csv",
    existing_ids: set[str] | None = None,
    column_mapping: ColumnMapping | None = None,
    max_rows: int = 10000,
) -> tuple[list[TransactionRecord], int, str]:
    """
    Parse SBI, HDFC, ICICI, or generic bank CSV bytes into normalized TransactionRecords.
    """
    if not file_bytes or not file_bytes.strip():
        raise CSVValidationError("Uploaded CSV file is empty.")

    try:
        raw_text = file_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            raw_text = file_bytes.decode("latin-1")
        except UnicodeDecodeError as exc:
            raise CSVValidationError("CSV file encoding is not supported. Use UTF-8.") from exc

    header_row_idx = _detect_header_row_index(raw_text)
    try:
        df = pd.read_csv(
            io.StringIO(raw_text),
            skiprows=header_row_idx,
            dtype=str,
            keep_default_na=False,
        )
    except Exception as exc:
        raise CSVValidationError(f"Malformed CSV file: {exc}") from exc

    # Drop completely empty rows and unnamed empty trailing columns
    df = df.loc[:, [c for c in df.columns if str(c).strip() and not str(c).startswith("Unnamed:")]]
    df = df.dropna(how="all")

    if df.empty or len(df.columns) < 2:
        raise CSVValidationError("CSV contains no usable columns or transaction rows.")

    if len(df) > max_rows:
        raise CSVValidationError(
            f"CSV exceeds maximum supported row limit ({max_rows} rows)."
        )

    columns = [str(c) for c in df.columns]
    detected_bank = detect_bank_format(columns)
    sample_rows = df.head(5).to_dict(orient="records")

    if column_mapping:
        date_col = column_mapping.date
        desc_col = column_mapping.description
        amount_col = column_mapping.amount
        debit_col = column_mapping.debit
        credit_col = column_mapping.credit
        type_col = column_mapping.tx_type
        balance_col = column_mapping.balance
        ref_col = column_mapping.reference
        for col_name in [
            c
            for c in (date_col, desc_col, amount_col, debit_col, credit_col, type_col, balance_col, ref_col)
            if c
        ]:
            if col_name not in columns:
                raise CSVValidationError(f"Mapped column '{col_name}' does not exist in CSV headers.")
    else:
        date_col = _match_column(columns, "date")
        desc_col = _match_column(columns, "description")
        debit_col = _match_column(columns, "debit")
        credit_col = _match_column(columns, "credit")
        amount_col = _match_column(columns, "amount")
        type_col = _match_column(columns, "tx_type")
        balance_col = _match_column(columns, "balance")
        ref_col = _match_column(columns, "reference")

    suggested = {
        "date": date_col,
        "description": desc_col,
        "debit": debit_col,
        "credit": credit_col,
        "amount": amount_col,
        "tx_type": type_col,
        "balance": balance_col,
        "reference": ref_col,
    }

    if not date_col or not desc_col:
        raise AmbiguousCSVError(
            "Could not unambiguously identify Date and Description columns. Please confirm column mapping.",
            headers=columns,
            sample_rows=sample_rows,
            suggested_mapping=suggested,
        )

    has_split_dc = bool(debit_col or credit_col)
    if not amount_col and not has_split_dc:
        raise AmbiguousCSVError(
            "Could not identify Amount or Debit/Credit columns. Please specify column mapping.",
            headers=columns,
            sample_rows=sample_rows,
            suggested_mapping=suggested,
        )

    # Detect ambiguous unsigned single-amount CSV (all positive amounts, no Type column, no DR/CR suffix)
    if amount_col and not has_split_dc and not type_col and column_mapping is None:
        raw_vals = [str(v).strip() for v in df[amount_col].tolist() if str(v).strip()]
        parsed_vals = [_parse_decimal(v) for v in raw_vals]
        non_zero = [v for v in parsed_vals if v is not None and v != Decimal("0.00")]
        has_negative = any(v < Decimal("0.00") for v in non_zero)
        has_dr_cr_marker = any(v.upper().endswith(("DR", "CR")) for v in raw_vals)
        if len(non_zero) >= 2 and not has_negative and not has_dr_cr_marker:
            raise AmbiguousCSVError(
                "Amount column contains only unsigned positive values with no Debit/Credit Type column. "
                "Please map Debit/Credit or Transaction Type columns explicitly.",
                headers=columns,
                sample_rows=sample_rows,
                suggested_mapping=suggested,
            )

    seen_ids: set[str] = set(existing_ids or set())
    transactions: list[TransactionRecord] = []
    duplicate_count = 0

    for row_idx, row in df.iterrows():
        iso_date = _parse_date(row.get(date_col, ""))
        raw_desc_raw = sanitize_csv_cell(str(row.get(desc_col, "")).strip())
        if not iso_date or not raw_desc_raw:
            continue

        # Compute signed Decimal amount
        signed_amount: Decimal | None = None
        if has_split_dc and not (column_mapping and column_mapping.amount):
            dr = _parse_decimal(row.get(debit_col)) if debit_col else None
            cr = _parse_decimal(row.get(credit_col)) if credit_col else None
            dr_abs = abs(dr) if dr is not None else Decimal("0.00")
            cr_abs = abs(cr) if cr is not None else Decimal("0.00")
            if dr_abs == Decimal("0.00") and cr_abs == Decimal("0.00"):
                continue
            signed_amount = (cr_abs - dr_abs).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        elif amount_col:
            raw_amt_str = str(row.get(amount_col, "")).strip()
            amt = _parse_decimal(raw_amt_str)
            if amt is None or amt == Decimal("0.00"):
                continue
            if type_col:
                tx_type_val = str(row.get(type_col, "")).strip().lower()
                if tx_type_val in {"dr", "debit", "withdrawal", "outflow", "expense", "d"}:
                    signed_amount = -abs(amt)
                elif tx_type_val in {"cr", "credit", "deposit", "inflow", "income", "c"}:
                    signed_amount = abs(amt)
                else:
                    signed_amount = amt
            else:
                signed_amount = amt

        if signed_amount is None or signed_amount == Decimal("0.00"):
            continue

        balance_dec = _parse_decimal(row.get(balance_col)) if balance_col else None
        raw_ref_val = sanitize_csv_cell(str(row.get(ref_col, "")).strip()) if ref_col else ""

        normalized_raw_desc = re.sub(r"\s+", " ", raw_desc_raw).strip().lower()
        tx_id = _compute_stable_tx_id(
            uid=uid,
            iso_date=iso_date,
            signed_amount=signed_amount,
            normalized_desc=normalized_raw_desc,
            raw_ref=raw_ref_val or None,
            balance=balance_dec,
        )

        if tx_id in seen_ids:
            duplicate_count += 1
            continue
        seen_ids.add(tx_id)

        tx_kind = classify_transaction_kind(raw_desc_raw, signed_amount)
        scrubbed_desc = scrub_pii(raw_desc_raw)
        merchant_hint = _extract_merchant_hint(scrubbed_desc)
        scrubbed_ref = scrub_pii(raw_ref_val) if raw_ref_val else None

        initial_category = (
            "Income"
            if tx_kind == "income"
            else "Refunds"
            if tx_kind in {"refund", "reversal"}
            else "Transfers"
            if tx_kind == "transfer"
            else "Other"
        )

        transactions.append(
            TransactionRecord(
                id=tx_id,
                uid=uid,
                date=iso_date,
                description=scrubbed_desc,
                merchant=merchant_hint,
                category=initial_category,
                category_source="rule",
                category_confidence=0.0,
                user_corrected=False,
                amount=float(signed_amount),
                tx_kind=tx_kind,
                balance=float(balance_dec) if balance_dec is not None else None,
                source_bank=detected_bank,
                source_filename=sanitize_csv_cell(filename)[:120],
                row_number=int(row_idx) + header_row_idx + 2,
                raw_reference=scrubbed_ref,
            )
        )

    if not transactions and duplicate_count == 0:
        raise CSVValidationError(
            "No valid financial transactions could be parsed from the uploaded CSV."
        )

    transactions.sort(key=lambda t: (t.date, t.row_number), reverse=True)
    return transactions, duplicate_count, detected_bank
