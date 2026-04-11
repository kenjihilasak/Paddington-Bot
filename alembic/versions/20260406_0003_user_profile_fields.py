"""Add richer WhatsApp profile fields to users."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260406_0003"
down_revision = "20260406_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Rename display_name and add profile snapshot fields."""

    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column(
            "display_name",
            new_column_name="wa_profile_name",
            existing_type=sa.String(length=255),
            existing_nullable=True,
        )
        batch_op.add_column(sa.Column("group_alias", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("confirmed_name", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("profile_photo_source_url", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("phone_country_prefix", sa.String(length=8), nullable=True))
        batch_op.add_column(sa.Column("country_code", sa.String(length=8), nullable=True))
        batch_op.add_column(sa.Column("profile_metadata", sa.JSON(), nullable=True))


def downgrade() -> None:
    """Drop profile snapshot fields and restore display_name."""

    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("profile_metadata")
        batch_op.drop_column("country_code")
        batch_op.drop_column("phone_country_prefix")
        batch_op.drop_column("profile_photo_source_url")
        batch_op.drop_column("confirmed_name")
        batch_op.drop_column("group_alias")
        batch_op.alter_column(
            "wa_profile_name",
            new_column_name="display_name",
            existing_type=sa.String(length=255),
            existing_nullable=True,
        )
