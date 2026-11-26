"""Organisationen, Konten, Mitgliedschaften, Nachweise, Änderungsprotokoll

Revision ID: 0001_organisation
Revises:
"""

from alembic import op
import sqlalchemy as sa


revision = "0001_organisation"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("short_name", sa.String(40), nullable=False, server_default=""),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column(
            "parent_id",
            sa.Integer,
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("latitude", sa.Float, nullable=True),
        sa.Column("longitude", sa.Float, nullable=True),
        sa.Column("archived", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.String(32), nullable=False),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("username", sa.String(32), nullable=False, unique=True),
        sa.Column("display_name", sa.String(80), nullable=False, server_default=""),
        sa.Column("email", sa.String(254), nullable=False, server_default=""),
        sa.Column("password_hash", sa.Text, nullable=False),
        sa.Column(
            "platform_admin",
            sa.Boolean,
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.String(32), nullable=False),
        sa.Column("last_login_at", sa.String(32), nullable=True),
    )
    op.create_table(
        "memberships",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "organization_id",
            sa.Integer,
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(16), nullable=False),
        sa.UniqueConstraint("user_id", "organization_id", name="uq_membership"),
    )
    op.create_table(
        "qualifications",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("reference", sa.String(80), nullable=False, server_default=""),
        sa.Column("valid_until", sa.Date, nullable=True),
        sa.Column("note", sa.String(200), nullable=False, server_default=""),
    )
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("at", sa.String(32), nullable=False),
        sa.Column("actor", sa.String(80), nullable=False, server_default=""),
        sa.Column("action", sa.String(60), nullable=False),
        sa.Column("target", sa.String(200), nullable=False, server_default=""),
        sa.Column("organization_id", sa.Integer, nullable=True),
    )


def downgrade() -> None:
    for table in (
        "audit_log",
        "qualifications",
        "memberships",
        "users",
        "organizations",
    ):
        op.drop_table(table)
