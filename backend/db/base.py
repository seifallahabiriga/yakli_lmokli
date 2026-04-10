from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

# Naming convention for Alembic auto-generated migrations.
# Without this, constraint names are random and diffs break across environments.
NAMING_CONVENTION: dict[str, str] = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """
    Single declarative base shared by every ORM model in the project.

    The metadata naming convention ensures Alembic produces deterministic
    constraint names across all environments, avoiding migration conflicts
    when running alembic upgrade on a fresh database.
    """

    metadata = MetaData(naming_convention=NAMING_CONVENTION)