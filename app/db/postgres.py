from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from app.config import Settings


def create_postgres_engine(settings: Settings) -> Engine:
    return create_engine(settings.postgres_dsn, pool_pre_ping=True)


def create_postgres_session_factory(engine: Engine) -> sessionmaker:
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


def create_alembic_postgres_url(settings: Settings) -> str:
    return settings.postgres_dsn.render_as_string(hide_password=False)


def ping_postgres(engine: Engine) -> bool:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return True
