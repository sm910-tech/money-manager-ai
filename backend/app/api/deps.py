import logging
from fastapi import Header, HTTPException, status

from app.core.config import get_settings
from app.models.schemas import AuthenticatedUser
from app.services.firestore_service import init_firebase_admin

logger = logging.getLogger(__name__)


def verify_firebase_token(token: str) -> AuthenticatedUser:
    """
    Verify a Firebase ID token via Firebase Admin SDK.
    Raises HTTP 401 for expired, revoked, or invalid tokens,
    and HTTP 503 if Firebase is not configured on the server.
    """
    settings = get_settings()
    if not settings.is_firebase_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service is not configured. Set FIREBASE_PROJECT_ID on the server.",
        )

    try:
        from firebase_admin import auth
    except ImportError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Firebase Admin SDK is not installed.",
        ) from exc

    init_firebase_admin()

    try:
        decoded = auth.verify_id_token(token, check_revoked=True)
    except auth.ExpiredIdTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token has expired. Please sign in again.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except auth.RevokedIdTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token has been revoked. Please sign in again.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except auth.InvalidIdTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except Exception as exc:
        logger.warning("Unexpected token verification failure: %s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate authentication credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    uid = str(decoded.get("uid", "")).strip()
    if not uid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token missing subject UID.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return AuthenticatedUser(uid=uid, email=decoded.get("email"))


def get_current_user(
    authorization: str | None = Header(default=None),
) -> AuthenticatedUser:
    """
    FastAPI dependency enforcing strict Bearer token authentication.
    Never falls back to a shared guest identity.
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header format. Expected 'Bearer <token>'.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return verify_firebase_token(token.strip())
