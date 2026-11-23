import json
from datetime import datetime
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.models.schemas import AuthenticatedUser, ColumnMapping, UploadResponse
from app.services.analytics import compute_financial_summary
from app.services.categorizer import categorize_transactions
from app.services.csv_parser import (
    AmbiguousCSVError,
    CSVValidationError,
    parse_bank_csv,
)
from app.services.firestore_service import (
    FirestoreRepository,
    PersistenceUnavailableError,
    get_repository,
)

router = APIRouter(tags=["Upload"])

_ALLOWED_MIME_TYPES = {
    "text/csv",
    "application/csv",
    "application/vnd.ms-excel",
    "text/plain",
    "application/octet-stream",
}


@router.post("/upload", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_csv_statement(
    file: UploadFile = File(...),
    column_mapping: str | None = Form(default=None),
    user: AuthenticatedUser = Depends(get_current_user),
    repo: FirestoreRepository = Depends(get_repository),
):
    settings = get_settings()

    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .csv bank statement files are accepted.",
        )

    if file.content_type and file.content_type.lower() not in _ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file content type: {file.content_type}",
        )

    contents = await file.read()
    if len(contents) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded CSV file is empty.",
        )

    if len(contents) > settings.max_csv_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"CSV file exceeds maximum size limit of {settings.max_csv_upload_mb} MB.",
        )

    parsed_mapping: ColumnMapping | None = None
    if column_mapping:
        try:
            parsed_mapping = ColumnMapping.model_validate(json.loads(column_mapping))
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid column_mapping JSON: {exc}",
            ) from exc

    try:
        existing_ids = repo.get_existing_transaction_ids(user.uid)
    except PersistenceUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    try:
        new_transactions, duplicate_count, detected_bank = parse_bank_csv(
            file_bytes=contents,
            uid=user.uid,
            filename=file.filename,
            existing_ids=existing_ids,
            column_mapping=parsed_mapping,
            max_rows=settings.max_csv_rows,
        )
    except AmbiguousCSVError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "AMBIGUOUS_CSV_FORMAT",
                "message": str(exc),
                "headers": exc.headers,
                "sample_rows": exc.sample_rows,
                "suggested_mapping": exc.suggested_mapping,
            },
        ) from exc
    except CSVValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    categorized_txs, ai_count = categorize_transactions(new_transactions, use_ai=True)

    try:
        repo.save_transactions(user.uid, categorized_txs)
        all_user_txs = repo.list_transactions(user.uid)
        current_month = (
            all_user_txs[0].date[:7]
            if all_user_txs
            else datetime.utcnow().strftime("%Y-%m")
        )
        monthly_budgets = repo.get_budget(user.uid, current_month)
    except PersistenceUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    summary = compute_financial_summary(all_user_txs, monthly_budgets=monthly_budgets)

    return UploadResponse(
        filename=file.filename,
        detected_bank=detected_bank,
        imported_count=len(categorized_txs),
        duplicate_count=duplicate_count,
        ai_categorized_count=ai_count,
        transactions=categorized_txs,
        summary=summary,
    )
