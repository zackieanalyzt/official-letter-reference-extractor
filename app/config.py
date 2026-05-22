from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL
from sqlalchemy.engine import URL as EngineURL


BASE_DIR = Path(__file__).resolve().parent.parent


def resolve_path(path_str: str) -> Path:
    path = Path(path_str)
    if path.is_absolute() or path.anchor in {"/", "\\"}:
        return path
    return (BASE_DIR / path).resolve()


class Settings(BaseSettings):
    app_name: str = Field(default="Official Letter Reference Extractor", validation_alias="APP_NAME")
    app_env: str = Field(default="development", validation_alias="APP_ENV")
    app_host: str = Field(default="0.0.0.0", validation_alias="APP_HOST")
    app_port: int = Field(default=7777, validation_alias="APP_PORT")
    app_lang: str = Field(default="th", validation_alias="APP_LANG")
    enable_auth: bool = Field(default=False, validation_alias="ENABLE_AUTH")
    app_token: str | None = Field(default=None, validation_alias="APP_TOKEN")
    secret_key: str = Field(default="change-me", validation_alias="SECRET_KEY")
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    session_cookie_name: str = Field(default="olre_session", validation_alias="SESSION_COOKIE_NAME")
    session_max_age_seconds: int = Field(default=28800, validation_alias="SESSION_MAX_AGE_SECONDS")

    database_url: str | None = Field(
        default="sqlite:////app/data/olre.sqlite3",
        validation_alias=AliasChoices("DATABASE_URL", "POSTGRES_DSN"),
    )
    postgres_host: str | None = Field(default=None, validation_alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, validation_alias="POSTGRES_PORT")
    postgres_db: str | None = Field(default=None, validation_alias="POSTGRES_DB")
    postgres_user: str | None = Field(default=None, validation_alias="POSTGRES_USER")
    postgres_password: str | None = Field(default=None, validation_alias="POSTGRES_PASSWORD")

    mariadb_host: str | None = Field(default=None, validation_alias="MARIADB_HOST")
    mariadb_port: int = Field(default=3306, validation_alias="MARIADB_PORT")
    mariadb_db: str | None = Field(default=None, validation_alias="MARIADB_DB")
    mariadb_user: str | None = Field(default=None, validation_alias="MARIADB_USER")
    mariadb_password: str | None = Field(default=None, validation_alias="MARIADB_PASSWORD")

    input_dir: str = Field(default="/app/data/input", validation_alias="INPUT_DIR")
    processed_dir: str = Field(default="/app/data/processed", validation_alias="PROCESSED_DIR")
    error_dir: str = Field(default="/app/data/error", validation_alias="ERROR_DIR")
    ocr_enabled: bool = Field(default=False, validation_alias="OCR_ENABLED")
    ocr_engine: str = Field(default="tesseract", validation_alias=AliasChoices("OCR_ENGINE", "OCR_COMMAND"))
    ocr_language: str = Field(default="eng", validation_alias=AliasChoices("OCR_LANG", "OCR_LANGUAGE"))
    ocr_timeout_seconds: int = Field(default=30, validation_alias="OCR_TIMEOUT_SECONDS")
    ocr_min_text_chars: int = Field(default=25, validation_alias="OCR_MIN_TEXT_CHARS")
    ocr_render_scale: float = Field(default=3.0, validation_alias=AliasChoices("OCR_DPI_SCALE", "OCR_RENDER_SCALE"))
    ocr_page_segmentation_mode: int = Field(default=6, validation_alias="OCR_PAGE_SEGMENTATION_MODE")
    qr_debug_export: bool = Field(default=False, validation_alias="QR_DEBUG_EXPORT")
    qr_debug_dir: str = Field(default="/app/data/debug/qr", validation_alias="QR_DEBUG_DIR")
    qr_fallback_decoder: str = Field(default="none", validation_alias="QR_FALLBACK_DECODER")
    url_resolve_timeout_seconds: float = Field(default=5.0, validation_alias="URL_RESOLVE_TIMEOUT_SECONDS")
    url_resolve_max_attempts: int = Field(default=2, validation_alias="URL_RESOLVE_MAX_ATTEMPTS")
    url_resolve_user_agent: str = Field(default="OLRE/0.1 URL Resolver", validation_alias="URL_RESOLVE_USER_AGENT")
    file_retention_mode: str = Field(default="retain_failed_only", validation_alias="FILE_RETENTION_MODE")
    success_source_retention_hours: int = Field(default=0, validation_alias="SUCCESS_SOURCE_RETENTION_HOURS")
    failed_source_retention_hours: int = Field(default=168, validation_alias="FAILED_SOURCE_RETENTION_HOURS")
    source_delete_on_cache_reuse: bool = Field(default=True, validation_alias="SOURCE_DELETE_ON_CACHE_REUSE")
    qr_debug_retention_hours: int = Field(default=72, validation_alias="QR_DEBUG_RETENTION_HOURS")
    cleanup_enabled: bool = Field(default=True, validation_alias="CLEANUP_ENABLED")
    cleanup_interval_minutes: int = Field(default=60, validation_alias="CLEANUP_INTERVAL_MINUTES")
    cleanup_startup_sweep: bool = Field(default=True, validation_alias="CLEANUP_STARTUP_SWEEP")
    default_force_reprocess: bool = Field(default=False, validation_alias="DEFAULT_FORCE_REPROCESS")
    extraction_version: int = Field(default=1, validation_alias="EXTRACTION_VERSION")
    temp_file_max_age_hours: int = Field(default=24, validation_alias="TEMP_FILE_MAX_AGE_HOURS")
    runtime_tmp_dir: str = Field(default="/app/data/runtime/tmp", validation_alias="RUNTIME_TMP_DIR")
    failed_retained_dir: str = Field(default="/app/data/runtime/failed-retained", validation_alias="FAILED_RETAINED_DIR")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def input_path(self) -> Path:
        return resolve_path(self.input_dir)

    @property
    def processed_path(self) -> Path:
        return resolve_path(self.processed_dir)

    @property
    def error_path(self) -> Path:
        return resolve_path(self.error_dir)

    @property
    def qr_debug_path(self) -> Path:
        return resolve_path(self.qr_debug_dir)

    @property
    def runtime_tmp_path(self) -> Path:
        return resolve_path(self.runtime_tmp_dir)

    @property
    def failed_retained_path(self) -> Path:
        return resolve_path(self.failed_retained_dir)

    @property
    def postgres_dsn(self) -> EngineURL:
        if not all([self.postgres_host, self.postgres_db, self.postgres_user, self.postgres_password]):
            raise ValueError("PostgreSQL settings are required when DATABASE_URL is not set.")
        return URL.create(
            drivername="postgresql+psycopg",
            username=self.postgres_user,
            password=self.postgres_password,
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
        )

    @property
    def resolved_database_url(self) -> str:
        if self.database_url and self.database_url.strip():
            return self.database_url
        return "sqlite:////app/data/olre.sqlite3"

    @property
    def mariadb_dsn(self) -> EngineURL:
        if not all(
            [
                self.mariadb_host,
                self.mariadb_db,
                self.mariadb_user,
                self.mariadb_password,
            ]
        ):
            raise ValueError("MariaDB settings are required when authentication is enabled.")
        return URL.create(
            drivername="mysql+pymysql",
            username=self.mariadb_user,
            password=self.mariadb_password,
            host=self.mariadb_host,
            port=self.mariadb_port,
            database=self.mariadb_db,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
