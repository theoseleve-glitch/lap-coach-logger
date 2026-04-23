"""Typed environment settings. Loaded once at import; fail-fast on missing required values."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Every value comes from env vars; no in-code defaults for secrets.

    Tests supply their own Settings(...) instance rather than relying on
    .env.
    """

    database_url: str = Field(
        ...,
        description=(
            "SQLAlchemy async URL, e.g. "
            "postgresql+asyncpg://user:pass@host:5432/lap_coach"
        ),
    )
    secret_key: str = Field(
        ...,
        min_length=32,
        description="HMAC secret for JWT signing. Generate with `openssl rand -hex 32`.",
    )
    session_cookie_name: str = Field(default="lc_session")
    session_ttl_hours: int = Field(default=24 * 30)  # 30 days
    cookie_secure: bool = Field(
        default=True,
        description="Set to False only for http://localhost dev — cookies won't be set over plain HTTP otherwise.",
    )
    cookie_domain: str | None = Field(default=None)

    # CORS — webapp origin(s) allowed to call /auth/* and /sessions etc.
    # Empty list = no CORS, same-origin only (the recommended RC1 deployment).
    cors_origins: list[str] = Field(default_factory=list)

    # Object storage (MinIO / S3-compatible). Required for bundle uploads.
    s3_endpoint: str = Field(default="http://minio:9000")
    s3_access_key: str = Field(default="minioadmin")
    s3_secret_key: str = Field(default="minioadmin")
    s3_bucket: str = Field(default="lap-coach-bundles")
    s3_region: str = Field(default="us-east-1")
    signed_url_ttl_s: int = Field(default=3600)  # 1 hour per D6

    # Rate-limit knobs (honoured by middleware in app/main.py).
    max_batch_rows: int = Field(default=200)
    max_bundle_bytes: int = Field(default=200 * 1024 * 1024)  # 200 MB per D4
    request_body_max_bytes: int = Field(default=2 * 1024 * 1024)  # 2 MB for non-bundle endpoints

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Memoised loader. Tests can replace via dependency override."""
    return Settings()  # type: ignore[call-arg]
