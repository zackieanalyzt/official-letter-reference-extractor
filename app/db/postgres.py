from sqlalchemy.engine import Engine

from app.config import Settings
from app.db.engine import (
    create_alembic_database_url,
    create_database_engine,
    create_session_factory,
    ping_database,
)


def create_postgres_engine(settings: Settings) -> Engine:
    return create_database_engine(settings)


def create_postgres_session_factory(engine: Engine):
    return create_session_factory(engine)


def create_alembic_postgres_url(settings: Settings) -> str:
    return create_alembic_database_url(settings)


def ping_postgres(engine: Engine) -> bool:
    return ping_database(engine)
