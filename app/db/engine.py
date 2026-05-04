from pathlib import Path

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import Settings, resolve_path


def is_sqlite_url(database_url: str) -> bool:
    return make_url(database_url).get_backend_name() == "sqlite"


def get_database_backend(database_url: str) -> str:
    return make_url(database_url).get_backend_name()


def _sqlite_connect_args(database_url: str) -> dict:
    url = make_url(database_url)
    if url.database in (None, "", ":memory:"):
        return {"check_same_thread": False}
    return {}


def _ensure_sqlite_parent_dir(database_url: str) -> None:
    url = make_url(database_url)
    if url.database in (None, "", ":memory:"):
        return
    path = Path(url.database)
    if not path.is_absolute():
        path = resolve_path(str(path))
    path.parent.mkdir(parents=True, exist_ok=True)


def _configure_sqlite_pragmas(engine: Engine) -> None:
    @event.listens_for(engine, "connect")
    def set_sqlite_pragmas(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.execute("PRAGMA busy_timeout=5000;")
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.close()


def create_database_engine(settings: Settings) -> Engine:
    database_url = settings.resolved_database_url
    kwargs = {"pool_pre_ping": True}
    if is_sqlite_url(database_url):
        _ensure_sqlite_parent_dir(database_url)
        kwargs["connect_args"] = _sqlite_connect_args(database_url)
        if make_url(database_url).database in (None, "", ":memory:"):
            kwargs["poolclass"] = StaticPool

    engine = create_engine(database_url, **kwargs)
    if is_sqlite_url(database_url):
        _configure_sqlite_pragmas(engine)
    return engine


def create_session_factory(engine: Engine) -> sessionmaker:
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


def create_alembic_database_url(settings: Settings) -> str:
    return settings.resolved_database_url


def ping_database(engine: Engine) -> bool:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return True
