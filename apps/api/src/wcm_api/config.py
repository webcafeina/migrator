"""Configuración de la API leída desde el entorno (.env).

Usamos `pydantic-settings` por su integración natural con Pydantic v2 y
porque permite construir un objeto inmutable validado al arranque. Si una
variable obligatoria falta, la app no levanta — preferimos fallar rápido
en producción a tener defaults silenciosos.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ApiSettings(BaseSettings):
    """Configuración runtime. Una instancia por proceso."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # otras vars del .env no nos afectan
        case_sensitive=False,
    )

    # ---- entorno ----
    env: Literal["development", "staging", "production"] = Field(default="development", alias="ENV")
    app_name: str = Field(default="webcafeina-migrator", alias="APP_NAME")
    api_url: str = Field(default="http://localhost:8000", alias="API_URL")
    app_url: str = Field(default="http://localhost:3000", alias="APP_URL")
    log_level: str = Field(default="info", alias="LOG_LEVEL")

    # ---- secrets ----
    secret_key: str = Field(alias="SECRET_KEY", min_length=16)
    jwt_secret: str = Field(alias="JWT_SECRET", min_length=16)
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    jwt_expiry_minutes: int = Field(default=480, alias="JWT_EXPIRY_MINUTES")
    session_cookie_name: str = Field(default="wcm_session", alias="SESSION_COOKIE_NAME")

    # ---- DB ----
    database_url: str = Field(alias="DATABASE_URL")  # async
    database_sync_url: str = Field(alias="DATABASE_SYNC_URL")  # alembic
    database_pool_size: int = Field(default=10, alias="DATABASE_POOL_SIZE")
    database_max_overflow: int = Field(default=20, alias="DATABASE_MAX_OVERFLOW")

    # ---- Redis / Celery ----
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    celery_broker_url: str = Field(default="redis://localhost:6379/1", alias="CELERY_BROKER_URL")
    celery_result_backend: str = Field(
        default="redis://localhost:6379/2", alias="CELERY_RESULT_BACKEND"
    )

    # ---- CORS ----
    # Almacenado como string CSV en .env porque pydantic-settings intenta
    # parse JSON estricto para `list[str]`. Exponemos `cors_origins` como
    # property derivada.
    cors_origins_raw: str = Field(default="http://localhost:3000", alias="CORS_ORIGINS")

    @property
    def cors_origins(self) -> list[str]:
        """Lista parseada de orígenes CORS permitidos."""
        return [item.strip() for item in self.cors_origins_raw.split(",") if item.strip()]

    # ---- Empresa (para outreach legal) ----
    company_legal_name: str = Field(default="Webcafeína S.L.", alias="COMPANY_LEGAL_NAME")
    company_contact_email: str = Field(default="info@webcafeina.com", alias="COMPANY_CONTACT_EMAIL")
    company_privacy_policy_url: str = Field(
        default="https://webcafeina.com/politica-de-privacidad",
        alias="COMPANY_PRIVACY_POLICY_URL",
    )

    # ---- Outreach (opt-out) ----
    outreach_opt_out_url_base: str = Field(
        default="https://migrator.webcafeina.com/opt-out",
        alias="OUTREACH_OPT_OUT_URL_BASE",
    )

    # ---- Email branding (v0.14.0) ----
    # URL pública del logo Webcafeína en R2 que el layout HTML embebe en
    # el header del correo. Subir con `python scripts/upload_email_logo.py`.
    # Si está vacío, el layout pinta `webcafeína` como texto estilado
    # (fallback grácil documentado en docstring del layout maestro).
    email_logo_url: str | None = Field(default=None, alias="EMAIL_LOGO_URL")

    # ---- Observabilidad ----
    sentry_dsn_api: str | None = Field(default=None, alias="SENTRY_DSN_API")
    sentry_environment: str = Field(default="development", alias="SENTRY_ENVIRONMENT")
    sentry_traces_sample_rate: float = Field(default=0.2, alias="SENTRY_TRACES_SAMPLE_RATE")
    logtail_source_token: str | None = Field(default=None, alias="LOGTAIL_SOURCE_TOKEN")

    # ---- ClickUp webhook secret (para validar firmas) ----
    clickup_webhook_secret: str | None = Field(default=None, alias="CLICKUP_WEBHOOK_SECRET")

    # ---- Resend webhook secret (HMAC sobre body crudo) ----
    resend_webhook_secret: str | None = Field(default=None, alias="RESEND_WEBHOOK_SECRET")

    @property
    def is_production(self) -> bool:
        return self.env == "production"


@lru_cache(maxsize=1)
def get_settings() -> ApiSettings:
    """Singleton lazy. En tests, hacer `get_settings.cache_clear()` o
    instanciar `ApiSettings(...)` directamente con kwargs.
    """
    return ApiSettings()  # type: ignore[call-arg]
