import re

# Sensitive identifier redaction patterns applied prior to persistence or LLM calls
_EMAIL_OR_UPI_RE = re.compile(r"\b[\w.%+-]+@[a-zA-Z0-9.-]+\b")
_CARD_NUMBER_RE = re.compile(r"(?<!\d)(?:\d[\s-]?){13,19}(?!\d)")
_GROUPED_12_DIGIT_RE = re.compile(r"\b\d{4}[\s-]\d{4}[\s-]\d{4}\b")
_PHONE_RE = re.compile(r"(?<!\d)(?:\+?91[\s-]?)?[6-9]\d{9}(?!\d)")
_IFSC_RE = re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b")
_PAN_RE = re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")
_SENSITIVE_KV_RE = re.compile(
    r"(?i)\b(?:cvv|cvc|upi\s*pin|mpin|pin|password|passwd|pwd|otp)\s*(?:is\b|[:=\-])?\s*\S+"
)
_ACCOUNT_OR_REF_RE = re.compile(r"\b\d{6,}\b")
_FORMULA_PREFIXES = ("=", "+", "@", "\t", "\r")


def scrub_pii(text: str) -> str:
    """
    Redact sensitive personal and banking identifiers before storage or AI transmission.
    Strips UPI IDs, emails, card numbers, phone numbers, IFSC/PAN codes,
    secret credentials (CVV/PIN/password), and long account/reference numbers.
    """
    if not text:
        return ""
    cleaned = str(text)
    cleaned = _SENSITIVE_KV_RE.sub("[REDACTED_SECRET]", cleaned)
    cleaned = _EMAIL_OR_UPI_RE.sub("[UPI_OR_EMAIL]", cleaned)
    cleaned = _CARD_NUMBER_RE.sub("[CARD]", cleaned)
    cleaned = _GROUPED_12_DIGIT_RE.sub("[ID_NUMBER]", cleaned)
    cleaned = _PHONE_RE.sub("[PHONE]", cleaned)
    cleaned = _IFSC_RE.sub("[IFSC]", cleaned)
    cleaned = _PAN_RE.sub("[PAN]", cleaned)
    cleaned = _ACCOUNT_OR_REF_RE.sub("[REF]", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def sanitize_csv_cell(value: str) -> str:
    """Neutralize spreadsheet formula injection characters in untrusted CSV text."""
    if not value:
        return ""
    cleaned = str(value).strip()
    while cleaned and cleaned[0] in _FORMULA_PREFIXES:
        cleaned = cleaned[1:].lstrip()
    # Strip leading '-' only when followed by formula expressions like -( or -SUM(
    if re.match(r"^-(?:[A-Za-z_]+\(|\()", cleaned):
        cleaned = cleaned[1:].lstrip()
    return cleaned


def contains_sensitive_credential_request(text: str) -> bool:
    """Detect if user text accidentally includes raw passwords, CVVs, or UPI PINs."""
    return bool(_SENSITIVE_KV_RE.search(text or ""))
