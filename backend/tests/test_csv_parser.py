from pathlib import Path
import pytest

from app.models.schemas import ColumnMapping
from app.services.categorizer import categorize_transactions
from app.services.csv_parser import (
    AmbiguousCSVError,
    CSVValidationError,
    parse_bank_csv,
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_generic_statement_and_refund_transfer_classification():
    raw = (FIXTURES / "sample_statement.csv").read_bytes()
    txs, dupes, bank = parse_bank_csv(raw, uid="uid-test", filename="sample_statement.csv")
    assert bank == "generic"
    assert dupes == 0
    assert len(txs) == 12

    by_desc = {t.description: t for t in txs}
    assert by_desc["AMAZON MERCHANT REFUND"].tx_kind == "refund"
    assert by_desc["SELF TRANSFER TO SAVINGS ACCOUNT"].tx_kind == "transfer"
    assert any(t.tx_kind == "income" and t.amount == 65000.0 for t in txs)


def test_parse_sbi_hdfc_icici_bank_formats():
    sbi_txs, _, sbi_bank = parse_bank_csv((FIXTURES / "sbi_sample.csv").read_bytes(), uid="u1")
    assert sbi_bank == "sbi"
    assert len(sbi_txs) == 4
    assert any(t.tx_kind == "reversal" and t.amount == 450.50 for t in sbi_txs)
    assert all("testuser@oksbi" not in t.description for t in sbi_txs)

    hdfc_txs, _, hdfc_bank = parse_bank_csv((FIXTURES / "hdfc_sample.csv").read_bytes(), uid="u1")
    assert hdfc_bank == "hdfc"
    assert len(hdfc_txs) == 4
    assert any(t.tx_kind == "transfer" and t.amount == -5000.0 for t in hdfc_txs)
    assert all("9876543210" not in t.description for t in hdfc_txs)

    icici_txs, _, icici_bank = parse_bank_csv((FIXTURES / "icici_sample.csv").read_bytes(), uid="u1")
    assert icici_bank == "icici"
    assert len(icici_txs) == 3
    assert any(t.tx_kind == "refund" and t.amount == 150.0 for t in icici_txs)


def test_duplicate_detection_across_reuploads():
    raw = (FIXTURES / "sample_statement.csv").read_bytes()
    first_txs, first_dupes, _ = parse_bank_csv(raw, uid="u-dup")
    assert first_dupes == 0
    existing_ids = {t.id for t in first_txs}

    second_txs, second_dupes, _ = parse_bank_csv(raw, uid="u-dup", existing_ids=existing_ids)
    assert len(second_txs) == 0
    assert second_dupes == len(first_txs)


def test_different_date_formats_and_debit_credit_type_column():
    csv_text = (
        "Date,Description,Amount,Type\n"
        "15/11/2026,UPI-SWIGGY,420.00,DR\n"
        "16-Nov-2026,SALARY BONUS,5000.00,CR\n"
        "2026-11-17,UPI-UBER,215.50,Debit\n"
    ).encode("utf-8")
    txs, _, _ = parse_bank_csv(csv_text, uid="u-dates")
    assert len(txs) == 3
    dates = {t.date for t in txs}
    assert dates == {"2026-11-15", "2026-11-16", "2026-11-17"}
    amounts = {t.date: t.amount for t in txs}
    assert amounts["2026-11-15"] == -420.0
    assert amounts["2026-11-16"] == 5000.0
    assert amounts["2026-11-17"] == -215.5


def test_missing_columns_raises_ambiguous_error_and_explicit_mapping_resolves():
    odd_csv = (
        "ColA,ColB,ColC\n"
        "2026-11-01,METRO CARD RECHARGE,-300.00\n"
        "2026-11-02,SALARY CREDIT,25000.00\n"
    ).encode("utf-8")
    with pytest.raises(AmbiguousCSVError) as exc_info:
        parse_bank_csv(odd_csv, uid="u-odd")
    assert exc_info.value.headers == ["ColA", "ColB", "ColC"]

    mapping = ColumnMapping(date="ColA", description="ColB", amount="ColC")
    txs, _, _ = parse_bank_csv(odd_csv, uid="u-odd", column_mapping=mapping)
    assert len(txs) == 2


def test_ambiguous_unsigned_positive_amount_column_rejected():
    ambiguous = (
        "Date,Description,Amount\n"
        "2026-11-01,SWIGGY,400.00\n"
        "2026-11-02,SALARY,50000.00\n"
    ).encode("utf-8")
    with pytest.raises(AmbiguousCSVError):
        parse_bank_csv(ambiguous, uid="u-amb")


def test_invalid_empty_csv_raises_validation_error():
    with pytest.raises(CSVValidationError):
        parse_bank_csv(b"", uid="u-empty")

    with pytest.raises(CSVValidationError):
        parse_bank_csv(b"Date,Description,Amount\n", uid="u-header-only")


def test_categorizer_preserves_user_corrected_categories():
    raw = (FIXTURES / "sample_statement.csv").read_bytes()
    txs, _, _ = parse_bank_csv(raw, uid="u-cat")
    txs[0].category = "Education"
    txs[0].user_corrected = True
    txs[0].category_source = "user"

    categorized, _ = categorize_transactions(txs, use_ai=False)
    assert categorized[0].category == "Education"
    assert categorized[0].user_corrected is True
