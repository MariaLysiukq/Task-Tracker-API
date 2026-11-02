"""Create users, projects, memberships, tasks and comments tables.

Revision ID: ddff194dc06b
Revises:
Create Date: 2026-10-27 12:00:00+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "ddff194dc06b"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def timestamp_columns() -> list[sa.Column[sa.DateTime]]:
    """Build ``created_at`` and ``updated_at`` columns.

    Returns
    -------
    list[sa.Column[sa.DateTime]]
        Timezone-aware columns defaulting to ``now()``.
    """
    return [
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    ]


def upgrade() -> None:
    """Apply this revision."""
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=100), nullable=False),
        *timestamp_columns(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
    )
    op.create_table(
        "projects",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name=op.f("fk_projects_owner_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_projects")),
    )
    op.create_index(op.f("ix_projects_owner_id"), "projects", ["owner_id"])
    op.create_table(
        "memberships",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=6), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "role IN ('owner', 'member')", name=op.f("ck_memberships_membership_role")
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_memberships_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_memberships_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_memberships")),
        sa.UniqueConstraint(
            "project_id", "user_id", name=op.f("uq_memberships_project_id_user_id")
        ),
    )
    op.create_index(op.f("ix_memberships_user_id"), "memberships", ["user_id"])
    op.create_table(
        "tasks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=150), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=11), server_default="todo", nullable=False),
        sa.Column("priority", sa.String(length=6), server_default="medium", nullable=False),
        sa.Column("assignee_id", sa.Integer(), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        *timestamp_columns(),
        sa.CheckConstraint(
            "status IN ('todo', 'in_progress', 'done')", name=op.f("ck_tasks_task_status")
        ),
        sa.CheckConstraint(
            "priority IN ('low', 'medium', 'high')", name=op.f("ck_tasks_task_priority")
        ),
        sa.ForeignKeyConstraint(
            ["assignee_id"],
            ["users.id"],
            name=op.f("fk_tasks_assignee_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_tasks_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tasks")),
    )
    op.create_index(op.f("ix_tasks_assignee_id"), "tasks", ["assignee_id"])
    op.create_index(
        "ix_tasks_project_id_created_at_id", "tasks", ["project_id", "created_at", "id"]
    )
    op.create_table(
        "comments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("author_id", sa.Integer(), nullable=False),
        sa.Column("body", sa.String(length=2000), nullable=False),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(
            ["author_id"],
            ["users.id"],
            name=op.f("fk_comments_author_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["tasks.id"],
            name=op.f("fk_comments_task_id_tasks"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_comments")),
    )
    op.create_index(op.f("ix_comments_author_id"), "comments", ["author_id"])
    op.create_index(
        "ix_comments_task_id_created_at_id", "comments", ["task_id", "created_at", "id"]
    )


def downgrade() -> None:
    """Revert this revision."""
    op.drop_table("comments")
    op.drop_table("tasks")
    op.drop_table("memberships")
    op.drop_table("projects")
    op.drop_table("users")
