"""
Alembic env.py — sync-only, uses psycopg2 driver.

Key behaviours:
  - Reads SYNC_DATABASE_URL from settings (never from alembic.ini).
  - Imports all models via `models` package so autogenerate sees every table.
  - Uses Base.metadata with the naming convention defined in db/base.py
    so constraint names are deterministic across environments.
  - Runs in offline mode (SQL script) or online mode (live connection).
"""
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

# Load app config and models before anything else
from backend.core.config import get_settings
from backend.db.base import Base

# Import all models so their tables are registered on Base.metadata.
# Without this, autogenerate produces empty migrations.
import backend.models  # noqa: F401 — side-effect import registers all ORM classes

settings = get_settings()

# Alembic Config object — provides access to alembic.ini values
config = context.config

# Wire up Python logging from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Target metadata for autogenerate comparison
target_metadata = Base.metadata


def get_url() -> str:
    return settings.SYNC_DATABASE_URL


def run_migrations_offline() -> None:
    """
    Emit migration SQL to stdout without a live DB connection.
    Useful for generating SQL scripts to review before applying.

    Run with: alembic upgrade head --sql
    """
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,              # detect column type changes
        compare_server_default=True,    # detect server_default changes
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Run migrations against a live DB connection.

    Uses NullPool so Alembic doesn't hold a connection open between
    migration steps — important when running in CI or Docker one-shots.
    """
    connectable = create_engine(
        get_url(),
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()