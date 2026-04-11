"""Add exchange target lists and richer record statuses."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260406_0002"
down_revision = "20260314_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add multi-target exchange preferences and richer lifecycle statuses."""

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TYPE recordstatus ADD VALUE IF NOT EXISTS 'RESOLVED'")
        op.execute("ALTER TYPE recordstatus ADD VALUE IF NOT EXISTS 'CANCELLED'")

    with op.batch_alter_table("exchange_offers") as batch_op:
        batch_op.add_column(sa.Column("want_currencies", sa.JSON(), nullable=True))

    if bind.dialect.name == "postgresql":
        op.execute(
            """
            UPDATE exchange_offers
            SET want_currencies = json_build_array(want_currency)
            WHERE want_currencies IS NULL
            """
        )
    else:
        op.execute(
            """
            UPDATE exchange_offers
            SET want_currencies = json_array(want_currency)
            WHERE want_currencies IS NULL
            """
        )

    with op.batch_alter_table("exchange_offers") as batch_op:
        batch_op.alter_column("want_currencies", nullable=False)


def downgrade() -> None:
    """Remove multi-target exchange preferences and collapse new statuses."""

    bind = op.get_bind()

    with op.batch_alter_table("exchange_offers") as batch_op:
        batch_op.drop_column("want_currencies")

    if bind.dialect.name != "postgresql":
        return

    for table_name in ("exchange_offers", "listings", "community_events"):
        op.execute(
            f"""
            UPDATE {table_name}
            SET status = 'INACTIVE'
            WHERE status IN ('RESOLVED', 'CANCELLED')
            """
        )

    legacy_record_status = postgresql.ENUM(
        "ACTIVE",
        "INACTIVE",
        "EXPIRED",
        "ARCHIVED",
        name="recordstatus_old",
    )
    legacy_record_status.create(bind, checkfirst=False)

    for table_name in ("exchange_offers", "listings", "community_events"):
        op.execute(
            f"""
            ALTER TABLE {table_name}
            ALTER COLUMN status TYPE recordstatus_old
            USING status::text::recordstatus_old
            """
        )

    op.execute("DROP TYPE recordstatus")
    op.execute("ALTER TYPE recordstatus_old RENAME TO recordstatus")
