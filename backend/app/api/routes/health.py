from fastapi import APIRouter
from app.core.config import get_settings

router = APIRouter(tags=["Health"])


@router.get("/health")
def health_check():
    settings = get_settings()
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.app_version,
        "environment": settings.app_env,
        "integrations": {
            "gemini_configured": settings.is_gemini_configured,
            "firebase_configured": settings.is_firebase_configured,
            "chat_model": settings.gemini_chat_model,
            "batch_model": settings.gemini_batch_model,
        },
    }
