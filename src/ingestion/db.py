from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import DeclarativeBase, sessionmaker


class Base(DeclarativeBase):
    pass


def create_session_factory(database_url: str) -> sessionmaker:
    engine = create_engine(database_url, pool_pre_ping=True, future=True)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def ensure_schema(base_class: type[DeclarativeBase], engine) -> None:
    """Best-effort dev helper: if expected columns are missing, drop and recreate tables.

    This is intentionally destructive for developer convenience in Phase-2 and should be
    replaced by a proper migration tool (e.g., Alembic) in later phases.
    """
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    # Only handle the single known table for now
    expected_table = "papers"
    if expected_table not in existing_tables:
        base_class.metadata.create_all(engine)
        return

    # Compare column names
    existing_columns = {col["name"] for col in inspector.get_columns(expected_table)}
    # Derive expected columns from mapped Table
    expected_columns = {c.name for c in base_class.metadata.tables[expected_table].columns}
    if not expected_columns.issubset(existing_columns):
        # Drop and recreate when schema is behind
        base_class.metadata.drop_all(engine)
        base_class.metadata.create_all(engine)
