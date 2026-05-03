from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL
from sqlalchemy.engine import URL as EngineURL


BASE_DIR = Path(__file__).resolve().parent.parent


def resolve_path(path_str: str) -> Path:
    path = Path(path_str)
    if path.is_absolute():
        return path
    return (BASE_DIR / path).resolve()


class Settings(BaseSettings):
    app_name: str = Field(default="Official Letter Reference Extractor", validation_alias="APP_NAME")
    app_env: str = Field(default="development", validation_alias="APP_ENV")
    app_host: str = Field(default="0.0.0.0", validation_alias="APP_HOST")
    app_port: int = Field(default=8080, validation_alias="APP_PORT")
    enable_auth: bool = Field(default=False, validation_alias="ENABLE_AUTH")
    app_token: str | None = Field(default=None, validation_alias="APP_TOKEN")
    secret_key: str = Field(default="change-me", validation_alias="SECRET_KEY")
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    session_cookie_name: str = Field(default="olre_session", validation_alias="SESSION_COOKIE_NAME")
    session_max_age_seconds: int = Field(default=28800, validation_alias="SESSION_MAX_AGE_SECONDS")

    postgres_host: str = Field(validation_alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, validation_alias="POSTGRES_PORT")
    postgres_db: str = Field(validation_alias="POSTGRES_DB")
    postgres_user: str = Field(validation_alias="POSTGRES_USER")
    postgres_password: str = Field(validation_alias="POSTGRES_PASSWORD")

    mariadb_host: str | None = Field(default=None, validation_alias="MARIADB_HOST")
    mariadb_port: int = Field(default=3306, validation_alias="MARIADB_PORT")
    mariadb_db: str | None = Field(default=None, validation_alias="MARIADB_DB")
    mariadb_user: str | None = Field(default=None, validation_alias="MARIADB_USER")
    mariadb_password: str | None = Field(default=None, validation_alias="MARIADB_PASSWORD")

    input_dir: str = Field(default="data/input", validation_alias="INPUT_DIR")
    processed_dir: str = Field(default="data/processed", validation_alias="PROCESSED_DIR")
    error_dir: str = Field(default="data/error", validation_alias="ERROR_DIR")
    ocr_enabled: bool = Field(default=True, validation_alias="OCR_ENABLED")
    ocr_engine: str = Field(default="tesseract", validation_alias=AliasChoices("OCR_ENGINE", "OCR_COMMAND"))
    ocr_language: str = Field(default="eng", validation_alias=AliasChoices("OCR_LANG", "OCR_LANGUAGE"))
    ocr_timeout_seconds: int = Field(default=30, validation_alias="OCR_TIMEOUT_SECONDS")
    ocr_min_text_chars: int = Field(default=25, validation_alias="OCR_MIN_TEXT_CHARS")
    ocr_render_scale: float = Field(default=3.0, validation_alias=AliasChoices("OCR_DPI_SCALE", "OCR_RENDER_SCALE"))
    ocr_page_segmentation_mode: int = Field(default=6, validation_alias="OCR_PAGE_SEGMENTATION_MODE")
    qr_debug_export: bool = Field(default=False, validation_alias="QR_DEBUG_EXPORT")
    qr_debug_dir: str = Field(default="data/debug/qr", validation_alias="QR_DEBUG_DIR")
    url_resolve_timeout_seconds: float = Field(default=5.0, validation_alias="URL_RESOLVE_TIMEOUT_SECONDS")
    url_resolve_max_attempts: int = Field(default=2, validation_alias="URL_RESOLVE_MAX_ATTEMPTS")
    url_resolve_user_agent: str = Field(default="OLRE/0.1 URL Resolver", validation_alias="URL_RESOLVE_USER_AGENT")

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
    def postgres_dsn(self) -> EngineURL:
        return URL.create(
            drivername="postgresql+psycopg",
            username=self.postgres_user,
            password=self.postgres_password,
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
        )

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
