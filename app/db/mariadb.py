from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from app.config import Settings


def create_mariadb_engine(settings: Settings) -> Engine:
    return create_engine(settings.mariadb_dsn, pool_pre_ping=True)


def create_mariadb_session_factory(engine: Engine) -> sessionmaker:
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


def ping_mariadb(engine: Engine) -> bool:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return True

