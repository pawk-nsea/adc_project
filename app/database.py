"""Relational database setup and lifecycle."""

from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    """Base class shared by all relational models."""


class Database:
    """Own the SQLAlchemy engine and create short-lived sessions."""

    def __init__(self, database_url: str) -> None:
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
        """Create the Stage 1 schema if it does not exist."""

        # Importing registers the model metadata before create_all runs.
        from app import models  # noqa: F401

        Base.metadata.create_all(self.engine)

    def sessions(self) -> Iterator[Session]:
        """Yield a session and always close it after request handling."""

        with self.session_factory() as session:
            yield session

    def close(self) -> None:
        """Release pooled database connections during application shutdown."""

        self.engine.dispose()
