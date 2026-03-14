"""Initial schema."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260314_0001"
down_revision = None
branch_labels = None
depends_on = None


message_direction = sa.Enum("INBOUND", "OUTBOUND", name="messagedirection")
message_type = sa.Enum("TEXT", "UNSUPPORTED", name="messagetype")
record_status = sa.Enum("ACTIVE", "INACTIVE", "EXPIRED", "ARCHIVED", name="recordstatus")
listing_category = sa.Enum("ITEM", "SERVICE", "WANTED", "OTHER", name="listingcategory")
conversation_flow = sa.Enum(
    "IDLE",
    "EXCHANGE_CREATE",
    "EXCHANGE_SEARCH",
    "LISTING_CREATE",
    "LISTING_SEARCH",
    "EVENT_CREATE",
    "SUMMARY",
    name="conversationflow",
)


def upgrade() -> None:
    """Create the initial database schema."""

    bind = op.get_bind()
    for enum_type in (message_direction, message_type, record_status, listing_category, conversation_flow):
        enum_type.create(bind, checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("wa_id", sa.String(length=32), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("wa_id", name="uq_users_wa_id"),
    )
    op.create_index("ix_users_wa_id", "users", ["wa_id"], unique=False)

    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("direction", message_direction, nullable=False),
        sa.Column("message_type", message_type, nullable=False),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("raw_payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_messages_user_id", "messages", ["user_id"], unique=False)
    op.create_index("ix_messages_direction", "messages", ["direction"], unique=False)
    op.create_index("ix_messages_created_at", "messages", ["created_at"], unique=False)

    op.create_table(
        "conversation_states",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("current_flow", conversation_flow, nullable=False),
        sa.Column("current_step", sa.String(length=100), nullable=True),
        sa.Column("draft_data", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", name="uq_conversation_states_user_id"),
    )
    op.create_index("ix_conversation_states_user_id", "conversation_states", ["user_id"], unique=False)
    op.create_index(
        "ix_conversation_states_current_flow", "conversation_states", ["current_flow"], unique=False
    )

    op.create_table(
        "exchange_offers",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("offer_currency", sa.String(length=8), nullable=False),
        sa.Column("want_currency", sa.String(length=8), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("status", record_status, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_exchange_offers_user_id", "exchange_offers", ["user_id"], unique=False)
    op.create_index(
        "ix_exchange_offers_offer_currency", "exchange_offers", ["offer_currency"], unique=False
    )
    op.create_index(
        "ix_exchange_offers_want_currency", "exchange_offers", ["want_currency"], unique=False
    )
    op.create_index("ix_exchange_offers_location", "exchange_offers", ["location"], unique=False)
    op.create_index("ix_exchange_offers_status", "exchange_offers", ["status"], unique=False)
    op.create_index("ix_exchange_offers_created_at", "exchange_offers", ["created_at"], unique=False)

    op.create_table(
        "listings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("category", listing_category, nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("price", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("status", record_status, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_listings_user_id", "listings", ["user_id"], unique=False)
    op.create_index("ix_listings_category", "listings", ["category"], unique=False)
    op.create_index("ix_listings_title", "listings", ["title"], unique=False)
    op.create_index("ix_listings_location", "listings", ["location"], unique=False)
    op.create_index("ix_listings_status", "listings", ["status"], unique=False)
    op.create_index("ix_listings_created_at", "listings", ["created_at"], unique=False)

    op.create_table(
        "community_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("event_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("status", record_status, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_community_events_user_id", "community_events", ["user_id"], unique=False)
    op.create_index("ix_community_events_title", "community_events", ["title"], unique=False)
    op.create_index("ix_community_events_event_date", "community_events", ["event_date"], unique=False)
    op.create_index("ix_community_events_location", "community_events", ["location"], unique=False)
    op.create_index("ix_community_events_status", "community_events", ["status"], unique=False)
    op.create_index("ix_community_events_created_at", "community_events", ["created_at"], unique=False)


def downgrade() -> None:
    """Drop the initial database schema."""

    op.drop_index("ix_community_events_created_at", table_name="community_events")
    op.drop_index("ix_community_events_status", table_name="community_events")
    op.drop_index("ix_community_events_location", table_name="community_events")
    op.drop_index("ix_community_events_event_date", table_name="community_events")
    op.drop_index("ix_community_events_title", table_name="community_events")
    op.drop_index("ix_community_events_user_id", table_name="community_events")
    op.drop_table("community_events")

    op.drop_index("ix_listings_created_at", table_name="listings")
    op.drop_index("ix_listings_status", table_name="listings")
    op.drop_index("ix_listings_location", table_name="listings")
    op.drop_index("ix_listings_title", table_name="listings")
    op.drop_index("ix_listings_category", table_name="listings")
    op.drop_index("ix_listings_user_id", table_name="listings")
    op.drop_table("listings")

    op.drop_index("ix_exchange_offers_created_at", table_name="exchange_offers")
    op.drop_index("ix_exchange_offers_status", table_name="exchange_offers")
    op.drop_index("ix_exchange_offers_location", table_name="exchange_offers")
    op.drop_index("ix_exchange_offers_want_currency", table_name="exchange_offers")
    op.drop_index("ix_exchange_offers_offer_currency", table_name="exchange_offers")
    op.drop_index("ix_exchange_offers_user_id", table_name="exchange_offers")
    op.drop_table("exchange_offers")

    op.drop_index("ix_conversation_states_current_flow", table_name="conversation_states")
    op.drop_index("ix_conversation_states_user_id", table_name="conversation_states")
    op.drop_table("conversation_states")

    op.drop_index("ix_messages_created_at", table_name="messages")
    op.drop_index("ix_messages_direction", table_name="messages")
    op.drop_index("ix_messages_user_id", table_name="messages")
    op.drop_table("messages")

    op.drop_index("ix_users_wa_id", table_name="users")
    op.drop_table("users")

    bind = op.get_bind()
    for enum_type in (conversation_flow, listing_category, record_status, message_type, message_direction):
        enum_type.drop(bind, checkfirst=True)

