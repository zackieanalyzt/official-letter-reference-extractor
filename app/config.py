from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL
from sqlalchemy.engine import URL as EngineURL


BASE_DIR = Path(__file__).resolve().parent.parent
PROFILE_DEFAULTS: dict[str, dict[str, int | str]] = {
    "development": {
        "app_port": 7777,
        "database_url": "sqlite:///data/olre.sqlite3",
        "input_dir": "data/input",
        "processed_dir": "data/processed",
        "error_dir": "data/error",
        "qr_debug_dir": "data/qr-debug",
        "runtime_tmp_dir": "data/runtime/tmp",
        "failed_retained_dir": "data/runtime/failed-retained",
        "storage_root": "data/storage",
        "export_dir": "data/exports",
        "backup_dir": "data/backups",
        "traversal_storage_dir": "data/runtime/linked-documents",
    },
    "docker": {
        "app_port": 8000,
        "database_url": "sqlite:////app/data/olre.sqlite3",
        "input_dir": "/app/data/input",
        "processed_dir": "/app/data/processed",
        "error_dir": "/app/data/error",
        "qr_debug_dir": "/app/data/qr-debug",
        "runtime_tmp_dir": "/app/data/runtime/tmp",
        "failed_retained_dir": "/app/data/runtime/failed-retained",
        "storage_root": "/app/data/storage",
        "export_dir": "/app/data/exports",
        "backup_dir": "/app/data/backups",
        "traversal_storage_dir": "/app/data/runtime/linked-documents",
    },
    "testing": {
        "app_port": 7777,
        "database_url": "sqlite:///data/olre.sqlite3",
        "input_dir": "data/input",
        "processed_dir": "data/processed",
        "error_dir": "data/error",
        "qr_debug_dir": "data/qr-debug",
        "runtime_tmp_dir": "data/runtime/tmp",
        "failed_retained_dir": "data/runtime/failed-retained",
        "storage_root": "data/storage",
        "export_dir": "data/exports",
        "backup_dir": "data/backups",
        "traversal_storage_dir": "data/runtime/linked-documents",
    },
    "production": {
        "app_port": 8000,
        "database_url": "sqlite:////app/data/olre.sqlite3",
        "input_dir": "/app/data/input",
        "processed_dir": "/app/data/processed",
        "error_dir": "/app/data/error",
        "qr_debug_dir": "/app/data/qr-debug",
        "runtime_tmp_dir": "/app/data/runtime/tmp",
        "failed_retained_dir": "/app/data/runtime/failed-retained",
        "storage_root": "/app/data/storage",
        "export_dir": "/app/data/exports",
        "backup_dir": "/app/data/backups",
        "traversal_storage_dir": "/app/data/runtime/linked-documents",
    },
}
PROFILE_ALIASES = {
    "dev": "development",
    "development": "development",
    "docker": "docker",
    "prod": "production",
    "production": "production",
    "test": "testing",
    "testing": "testing",
}


def resolve_path(path_str: str) -> Path:
    path = Path(path_str)
    if path.is_absolute() or path.anchor in {"/", "\\"}:
        return path
    return (BASE_DIR / path).resolve()


class Settings(BaseSettings):
    app_name: str = Field(default="Official Letter Reference Extractor", validation_alias="APP_NAME")
    app_env: str = Field(default="development", validation_alias=AliasChoices("APP_ENV", "ENVIRONMENT"))
    app_host: str = Field(default="0.0.0.0", validation_alias="APP_HOST")
    app_port: int | None = Field(default=None, validation_alias="APP_PORT")
    app_lang: str = Field(default="th", validation_alias="APP_LANG")
    enable_auth: bool = Field(default=False, validation_alias="ENABLE_AUTH")
    app_token: str | None = Field(default=None, validation_alias="APP_TOKEN")
    secret_key: str = Field(default="change-me", validation_alias="SECRET_KEY")
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    session_cookie_name: str = Field(default="olre_session", validation_alias="SESSION_COOKIE_NAME")
    session_max_age_seconds: int = Field(default=28800, validation_alias="SESSION_MAX_AGE_SECONDS")

    database_url: str | None = Field(
        default=None,
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

    input_dir: str | None = Field(default=None, validation_alias="INPUT_DIR")
    processed_dir: str | None = Field(default=None, validation_alias="PROCESSED_DIR")
    error_dir: str | None = Field(default=None, validation_alias="ERROR_DIR")
    ocr_enabled: bool = Field(default=False, validation_alias="OCR_ENABLED")
    ocr_engine: str = Field(default="tesseract", validation_alias=AliasChoices("OCR_ENGINE", "OCR_COMMAND"))
    ocr_language: str = Field(default="eng", validation_alias=AliasChoices("OCR_LANG", "OCR_LANGUAGE"))
    ocr_timeout_seconds: int = Field(default=30, validation_alias="OCR_TIMEOUT_SECONDS")
    ocr_min_text_chars: int = Field(default=25, validation_alias="OCR_MIN_TEXT_CHARS")
    ocr_render_scale: float = Field(default=3.0, validation_alias=AliasChoices("OCR_DPI_SCALE", "OCR_RENDER_SCALE"))
    ocr_page_segmentation_mode: int = Field(default=6, validation_alias="OCR_PAGE_SEGMENTATION_MODE")
    qr_debug_export: bool = Field(default=False, validation_alias="QR_DEBUG_EXPORT")
    qr_debug_dir: str | None = Field(default=None, validation_alias="QR_DEBUG_DIR")
    qr_fallback_decoder: str = Field(default="none", validation_alias="QR_FALLBACK_DECODER")
    url_resolve_timeout_seconds: float = Field(default=5.0, validation_alias="URL_RESOLVE_TIMEOUT_SECONDS")
    url_resolve_max_attempts: int = Field(default=2, validation_alias="URL_RESOLVE_MAX_ATTEMPTS")
    url_resolve_user_agent: str = Field(default="OLRE/0.1 URL Resolver", validation_alias="URL_RESOLVE_USER_AGENT")
    storage_backend: str = Field(default="localfs", validation_alias="STORAGE_BACKEND")
    storage_root: str | None = Field(default=None, validation_alias="STORAGE_ROOT")
    export_dir: str | None = Field(default=None, validation_alias="EXPORT_DIR")
    backup_dir: str | None = Field(default=None, validation_alias="BACKUP_DIR")
    file_retention_mode: str = Field(default="retain_failed_only", validation_alias="FILE_RETENTION_MODE")
    success_source_retention_hours: int = Field(default=0, validation_alias="SUCCESS_SOURCE_RETENTION_HOURS")
    failed_source_retention_hours: int = Field(default=720, validation_alias="FAILED_SOURCE_RETENTION_HOURS")
    source_delete_on_cache_reuse: bool = Field(default=True, validation_alias="SOURCE_DELETE_ON_CACHE_REUSE")
    qr_debug_retention_hours: int = Field(default=168, validation_alias="QR_DEBUG_RETENTION_HOURS")
    export_retention_hours: int = Field(default=336, validation_alias="EXPORT_RETENTION_HOURS")
    cleanup_enabled: bool = Field(default=True, validation_alias="CLEANUP_ENABLED")
    cleanup_interval_minutes: int = Field(default=60, validation_alias="CLEANUP_INTERVAL_MINUTES")
    cleanup_startup_sweep: bool = Field(default=True, validation_alias="CLEANUP_STARTUP_SWEEP")
    default_force_reprocess: bool = Field(default=False, validation_alias="DEFAULT_FORCE_REPROCESS")
    extraction_version: int = Field(default=1, validation_alias="EXTRACTION_VERSION")
    temp_file_max_age_hours: int = Field(default=24, validation_alias="TEMP_FILE_MAX_AGE_HOURS")
    runtime_tmp_dir: str | None = Field(default=None, validation_alias="RUNTIME_TMP_DIR")
    failed_retained_dir: str | None = Field(default=None, validation_alias="FAILED_RETAINED_DIR")
    release_metadata_file: str | None = Field(default=None, validation_alias="OLRE_RELEASE_METADATA_FILE")
    release_app_version: str | None = Field(default=None, validation_alias="OLRE_APP_VERSION")
    release_name: str | None = Field(default=None, validation_alias="OLRE_RELEASE_NAME")
    release_date: str | None = Field(default=None, validation_alias="OLRE_RELEASE_DATE")
    release_channel: str | None = Field(default=None, validation_alias="OLRE_RELEASE_CHANNEL")
    release_status: str | None = Field(default=None, validation_alias="OLRE_RELEASE_STATUS")
    release_note: str | None = Field(default=None, validation_alias="OLRE_RELEASE_NOTE")
    release_highlights: str | None = Field(default=None, validation_alias="OLRE_RELEASE_HIGHLIGHTS")
    traversal_enabled: bool = Field(default=False, validation_alias="TRAVERSAL_ENABLED")
    traversal_max_depth: int = Field(default=1, validation_alias="TRAVERSAL_MAX_DEPTH")
    traversal_max_documents_per_batch: int = Field(
        default=20,
        validation_alias="TRAVERSAL_MAX_DOCUMENTS_PER_BATCH",
    )
    traversal_allowed_content_types: str = Field(
        default="application/pdf",
        validation_alias="TRAVERSAL_ALLOWED_CONTENT_TYPES",
    )
    traversal_timeout_seconds: int = Field(default=15, validation_alias="TRAVERSAL_TIMEOUT_SECONDS")
    traversal_max_download_mb: int = Field(default=20, validation_alias="TRAVERSAL_MAX_DOWNLOAD_MB")
    traversal_allowed_domains: str | None = Field(default=None, validation_alias="TRAVERSAL_ALLOWED_DOMAINS")
    traversal_block_private_ips: bool = Field(default=True, validation_alias="TRAVERSAL_BLOCK_PRIVATE_IPS")
    traversal_storage_dir: str | None = Field(default=None, validation_alias="TRAVERSAL_STORAGE_DIR")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("app_env", mode="before")
    @classmethod
    def normalize_app_env(cls, value: str | None) -> str:
        normalized = PROFILE_ALIASES.get(str(value or "development").strip().lower())
        if normalized is None:
            raise ValueError("APP_ENV / ENVIRONMENT must be one of development, docker, testing, production.")
        return normalized

    @field_validator(
        "app_port",
        "database_url",
        "input_dir",
        "processed_dir",
        "error_dir",
        "qr_debug_dir",
        "runtime_tmp_dir",
        "failed_retained_dir",
        "storage_root",
        "export_dir",
        "backup_dir",
        "release_metadata_file",
        "release_app_version",
        "release_name",
        "release_date",
        "release_channel",
        "release_status",
        "release_note",
        "release_highlights",
        "traversal_allowed_domains",
        "traversal_storage_dir",
        mode="before",
    )
    @classmethod
    def blank_values_to_none(cls, value):
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @model_validator(mode="after")
    def apply_profile_defaults(self) -> "Settings":
        profile_defaults = PROFILE_DEFAULTS[self.app_env]
        for field_name, default_value in profile_defaults.items():
            current_value = getattr(self, field_name)
            if current_value is None:
                setattr(self, field_name, default_value)
        return self

    @property
    def input_path(self) -> Path:
        return resolve_path(self.input_dir or PROFILE_DEFAULTS[self.app_env]["input_dir"])

    @property
    def processed_path(self) -> Path:
        return resolve_path(self.processed_dir or PROFILE_DEFAULTS[self.app_env]["processed_dir"])

    @property
    def error_path(self) -> Path:
        return resolve_path(self.error_dir or PROFILE_DEFAULTS[self.app_env]["error_dir"])

    @property
    def qr_debug_path(self) -> Path:
        return resolve_path(self.qr_debug_dir or PROFILE_DEFAULTS[self.app_env]["qr_debug_dir"])

    @property
    def runtime_tmp_path(self) -> Path:
        return resolve_path(self.runtime_tmp_dir or PROFILE_DEFAULTS[self.app_env]["runtime_tmp_dir"])

    @property
    def failed_retained_path(self) -> Path:
        return resolve_path(
            self.failed_retained_dir or PROFILE_DEFAULTS[self.app_env]["failed_retained_dir"]
        )

    @property
    def storage_root_path(self) -> Path:
        return resolve_path(self.storage_root or PROFILE_DEFAULTS[self.app_env]["storage_root"])

    @property
    def export_path(self) -> Path:
        return resolve_path(self.export_dir or PROFILE_DEFAULTS[self.app_env]["export_dir"])

    @property
    def backup_path(self) -> Path:
        return resolve_path(self.backup_dir or PROFILE_DEFAULTS[self.app_env]["backup_dir"])

    @property
    def traversal_storage_path(self) -> Path:
        return resolve_path(
            self.traversal_storage_dir or PROFILE_DEFAULTS[self.app_env]["traversal_storage_dir"]
        )

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
        return str(PROFILE_DEFAULTS[self.app_env]["database_url"])

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
