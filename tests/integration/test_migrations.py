"""Migration and referential-integrity tests against the dedicated test PostgreSQL.

Skipped unless ``TEST_DATABASE_URL`` is set; the application ``DATABASE_URL``
(Neon) is never used here.
"""

import asyncio
import os
from collections.abc import Iterator
from typing import Any

import pytest
from sqlalchemy import Connection, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from app.core.config import get_settings
from app.models import Base

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL is not set")


@pytest.fixture(scope="module")
def migrated_db(monkeypatch_module: pytest.MonkeyPatch) -> Iterator[str]:
    """Upgrade the test database to ``head`` and downgrade it afterwards.

    Parameters
    ----------
    monkeypatch_module : pytest.MonkeyPatch
        Module-scoped monkeypatch used to point Alembic at the test database.

    Yields
    ------
    str
        Test database URL.
    """
    assert TEST_DATABASE_URL
    monkeypatch_module.setenv("DATABASE_URL", TEST_DATABASE_URL)
    monkeypatch_module.setenv("JWT_SECRET", "test-secret")
    get_settings.cache_clear()
    config = Config("alembic.ini")
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    yield TEST_DATABASE_URL
    command.downgrade(config, "base")
    get_settings.cache_clear()


@pytest.fixture(scope="module")
def monkeypatch_module() -> Iterator[pytest.MonkeyPatch]:
    """Provide a module-scoped ``MonkeyPatch``.

    Yields
    ------
    pytest.MonkeyPatch
        Patcher undone after the module finishes.
    """
    with pytest.MonkeyPatch.context() as patcher:
        yield patcher


def diff_with_models(connection: Connection) -> list[Any]:
    """Compare the migrated schema with the ORM metadata.

    Parameters
    ----------
    connection : Connection
        Synchronous connection facade.

    Returns
    -------
    list[Any]
        Autogenerate differences; empty when the migration matches the models.
    """
    context = MigrationContext.configure(connection, opts={"compare_server_default": True})
    return list(compare_metadata(context, Base.metadata))


async def run(url: str, *statements: str) -> list[Any]:
    """Execute statements in one rolled-back transaction.

    Parameters
    ----------
    url : str
        Database URL.
    *statements : str
        SQL statements; the rows of the last one are returned.

    Returns
    -------
    list[Any]
        Rows returned by the last statement.
    """
    engine = create_async_engine(url)
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            try:
                return await execute_all(connection, statements)
            finally:
                await transaction.rollback()
    finally:
        await engine.dispose()


async def execute_all(connection: AsyncConnection, statements: tuple[str, ...]) -> list[Any]:
    """Execute statements sequentially and return rows of the last one.

    Parameters
    ----------
    connection : AsyncConnection
        Open connection inside a transaction.
    statements : tuple[str, ...]
        SQL statements.

    Returns
    -------
    list[Any]
        Rows of the last statement.
    """
    result = None
    for statement in statements:
        result = await connection.execute(text(statement))
    assert result is not None
    return list(result.all()) if result.returns_rows else []


SEED = (
    "INSERT INTO users (id, email, hashed_password, full_name) VALUES "
    "(1, 'owner@example.com', 'x', 'Owner'), (2, 'member@example.com', 'x', 'Member')",
    "INSERT INTO projects (id, name, owner_id) VALUES (1, 'Project', 1)",
    "INSERT INTO memberships (project_id, user_id, role) VALUES (1, 1, 'owner'), (1, 2, 'member')",
    "INSERT INTO tasks (id, project_id, title, assignee_id) VALUES (1, 1, 'Task', 2)",
    "INSERT INTO comments (task_id, author_id, body) VALUES (1, 2, 'Hi')",
)


async def schema_diff(url: str) -> list[Any]:
    """Connect to the database and diff its schema against the models.

    Parameters
    ----------
    url : str
        Database URL.

    Returns
    -------
    list[Any]
        Autogenerate differences.
    """
    engine = create_async_engine(url)
    try:
        async with engine.connect() as connection:
            return await connection.run_sync(diff_with_models)
    finally:
        await engine.dispose()


def test_migration_matches_models(migrated_db: str) -> None:
    """``alembic upgrade head`` produces exactly the schema described by the models."""
    assert asyncio.run(schema_diff(migrated_db)) == []


def test_task_defaults_applied(migrated_db: str) -> None:
    """Tasks inserted without status/priority get ``todo``/``medium``."""
    rows = asyncio.run(run(migrated_db, *SEED, "SELECT status, priority FROM tasks"))
    assert rows == [("todo", "medium")]


def test_project_deletion_cascades(migrated_db: str) -> None:
    """Deleting a project removes its memberships, tasks and comments."""
    rows = asyncio.run(
        run(
            migrated_db,
            *SEED,
            "DELETE FROM projects WHERE id = 1",
            "SELECT (SELECT count(*) FROM memberships), (SELECT count(*) FROM tasks), "
            "(SELECT count(*) FROM comments)",
        )
    )
    assert rows == [(0, 0, 0)]


def test_owner_with_projects_cannot_be_deleted(migrated_db: str) -> None:
    """The database refuses to delete a user who still owns a project."""
    with pytest.raises(IntegrityError):
        asyncio.run(run(migrated_db, *SEED, "DELETE FROM users WHERE id = 1"))


def test_user_deletion_unassigns_tasks(migrated_db: str) -> None:
    """Deleting an assignee keeps the task with ``assignee_id = NULL``."""
    rows = asyncio.run(
        run(
            migrated_db,
            *SEED,
            "DELETE FROM users WHERE id = 2",
            "SELECT t.assignee_id, (SELECT count(*) FROM memberships) FROM tasks t",
        )
    )
    assert rows == [(None, 1)]


@pytest.mark.parametrize(
    "statement",
    [
        "INSERT INTO memberships (project_id, user_id, role) VALUES (1, 2, 'member')",
        "INSERT INTO users (email, hashed_password, full_name) "
        "VALUES ('owner@example.com', 'x', 'X')",
        "UPDATE tasks SET status = 'blocked'",
        "UPDATE memberships SET role = 'admin'",
    ],
)
def test_constraints_reject_invalid_rows(migrated_db: str, statement: str) -> None:
    """Duplicate membership/email and unknown enum values are rejected."""
    with pytest.raises(IntegrityError):
        asyncio.run(run(migrated_db, *SEED, statement))
