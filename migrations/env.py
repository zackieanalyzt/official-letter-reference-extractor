from logging.config import fileConfig

from alembic import context
from app.config import get_settings
from app.db.base import Base
from app.db import models  # noqa: F401
from app.db.engine import create_alembic_database_url, create_database_engine


config = context.config
settings = get_settings()
config.set_main_option("sqlalchemy.url", create_alembic_database_url(settings))

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_database_engine(settings)

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
