"""Web-Push-Abos der Geräte

Revision ID: 0002_push_subscriptions
Revises: 0001_organisation
"""

from alembic import op
import sqlalchemy as sa


revision = "0002_push_subscriptions"
down_revision = "0001_organisation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "push_subscriptions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("endpoint", sa.String(1000), nullable=False, unique=True),
        sa.Column("p256dh", sa.String(120), nullable=False),
        sa.Column("auth", sa.String(40), nullable=False),
        sa.Column("label", sa.String(80), nullable=False, server_default=""),
        sa.Column("events", sa.Text, nullable=False, server_default="[]"),
        sa.Column("created_at", sa.String(32), nullable=False),
        sa.Column("last_success_at", sa.String(32), nullable=True),
        sa.Column("last_error", sa.String(200), nullable=False, server_default=""),
    )
    op.create_index(
        "ix_push_subscriptions_user_id",
        "push_subscriptions",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_push_subscriptions_user_id", "push_subscriptions")
    op.drop_table("push_subscriptions")
