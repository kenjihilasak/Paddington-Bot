"""Rename confirmed user name and remove group alias."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260429_0004"
down_revision = "20260406_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Use name for the bot-confirmed user name and drop unused group aliases."""

    column_names = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("users")}

    with op.batch_alter_table("users") as batch_op:
        if "confirmed_name" in column_names and "name" not in column_names:
            batch_op.alter_column(
                "confirmed_name",
                new_column_name="name",
                existing_type=sa.String(length=255),
                existing_nullable=True,
            )
        elif "name" not in column_names:
            batch_op.add_column(sa.Column("name", sa.String(length=255), nullable=True))

        if "group_alias" in column_names:
            batch_op.drop_column("group_alias")


def downgrade() -> None:
    """Restore the previous confirmed_name/group_alias shape."""

    column_names = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("users")}

    with op.batch_alter_table("users") as batch_op:
        if "group_alias" not in column_names:
            batch_op.add_column(sa.Column("group_alias", sa.String(length=255), nullable=True))
        if "name" in column_names and "confirmed_name" not in column_names:
            batch_op.alter_column(
                "name",
                new_column_name="confirmed_name",
                existing_type=sa.String(length=255),
                existing_nullable=True,
            )
