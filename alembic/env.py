from logging.config import fileConfig

from alembic import context

from app.config import settings
from app.db import Base, make_engine
from app import models  # noqa: F401  регистрирует таблицы

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def url() -> str:
    return config.get_main_option("sqlalchemy.url") or settings.database_url


def run_offline() -> None:
    context.configure(url=url(), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_online() -> None:
    engine = make_engine(url())
    with engine.connect() as conn:
        context.configure(connection=conn, target_metadata=target_metadata, render_as_batch=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_offline()
else:
    run_online()
