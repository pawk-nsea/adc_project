"""Create relational storage, apply additive SQLite updates and manage sessions."""

from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import Engine, create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    """Base class shared by all relational models."""


class Database:
    """Own the SQLAlchemy engine and create short-lived sessions."""

    def __init__(self, database_url: str) -> None:
        """Prepare local storage and session creation without creating tables yet."""

        self.database_url = database_url
        self._prepare_sqlite_directory()

        connect_args = {}
        if make_url(database_url).get_backend_name() == "sqlite":
            connect_args["check_same_thread"] = False

        self.engine: Engine = create_engine(
            database_url,
            connect_args=connect_args,
        )
        self.session_factory = sessionmaker(
            bind=self.engine,
            autoflush=False,
            expire_on_commit=False,
        )

    def _prepare_sqlite_directory(self) -> None:
        """Create the parent directory for a file-backed SQLite database."""

        url = make_url(self.database_url)
        database_path = url.database
        if url.get_backend_name() != "sqlite" or not database_path:
            return
        if database_path == ":memory:":
            return

        Path(database_path).expanduser().parent.mkdir(parents=True, exist_ok=True)

    def create_tables(self) -> None:
        """Create missing tables and add retained-PDF columns to older SQLite files."""

        # Importing registers the model metadata before create_all runs.
        from app import models  # noqa: F401

        Base.metadata.create_all(self.engine)
        self._add_document_columns_for_existing_sqlite_database()

    def _add_document_columns_for_existing_sqlite_database(self) -> None:
        """Apply additive prototype migrations needed by existing workspaces."""

        if make_url(self.database_url).get_backend_name() != "sqlite":
            return
        columns = {column["name"] for column in inspect(self.engine).get_columns("documents")}
        with self.engine.begin() as connection:
            if "content_bytes" not in columns:
                connection.execute(text("ALTER TABLE documents ADD COLUMN content_bytes BLOB"))
            if "authority_metadata_json" not in columns:
                connection.execute(
                    text("ALTER TABLE documents ADD COLUMN authority_metadata_json JSON")
                )

    def sessions(self) -> Iterator[Session]:
        """Yield a session and always close it after request handling."""

        with self.session_factory() as session:
            yield session

    def close(self) -> None:
        """Release pooled database connections during application shutdown."""

        self.engine.dispose()
