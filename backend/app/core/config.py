from functools import lru_cache
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_ROOT_ENV = Path(__file__).resolve().parents[3] / ".env"


class Settings(BaseSettings):
    """Environment-driven configuration for Money Manager AI backend."""

    app_name: str = "Money Manager AI API"
    app_version: str = "1.0.0"
    app_env: str = Field(default="development")
    log_level: str = Field(default="INFO")

    # Explicit comma-separated origins for CORS (never wildcard with credentials)
    allowed_origins: str = Field(default="http://localhost:5173,http://127.0.0.1:5173")

    # Official verified Gemini API models (Google AI Studio docs, Nov 2026)
    gemini_api_key: str = Field(default="")
    gemini_chat_model: str = Field(default="gemini-4-hydrogen")
    gemini_batch_model: str = Field(default="gemini-3.5-flash-lite")
    gemini_timeout_seconds: int = Field(default=25, ge=5, le=120)

    # Firebase Admin SDK / Cloud Firestore
    firebase_project_id: str = Field(default="")
    google_application_credentials: str = Field(default="")

    # CSV upload guardrails
    max_csv_upload_mb: int = Field(default=5, ge=1, le=25)
    max_csv_rows: int = Field(default=10000, ge=100, le=50000)

    model_config = SettingsConfigDict(
        env_file=str(_ROOT_ENV) if _ROOT_ENV.exists() else ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_origins(self) -> list[str]:
        origins = [o.strip() for o in self.allowed_origins.split(",") if o.strip()]
        # Refuse wildcard when credentials are enabled
        return [o for o in origins if o != "*"]

    @property
    def max_csv_bytes(self) -> int:
        return self.max_csv_upload_mb * 1024 * 1024

    @property
    def is_gemini_configured(self) -> bool:
        key = self.gemini_api_key.strip()
        return bool(key and not key.lower().startswith("your_"))

    @property
    def is_firebase_configured(self) -> bool:
        pid = self.firebase_project_id.strip()
        return bool(pid and not pid.lower().startswith("your-"))


@lru_cache
def get_settings() -> Settings:
    return Settings()
