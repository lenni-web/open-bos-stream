"""Einsätze mit beteiligten Wehren, Personen, Quellen und Verlauf

Revision ID: 0003_incidents
Revises: 0002_push_subscriptions
"""

from alembic import op
import sqlalchemy as sa


revision = "0003_incidents"
down_revision = "0002_push_subscriptions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "incidents",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("code", sa.String(24), nullable=False, unique=True),
        sa.Column("title", sa.String(120), nullable=False, server_default=""),
        sa.Column("keyword", sa.String(80), nullable=False, server_default=""),
        sa.Column("address", sa.String(200), nullable=False, server_default=""),
        sa.Column("latitude", sa.Float, nullable=True),
        sa.Column("longitude", sa.Float, nullable=True),
        sa.Column("alarm_at", sa.String(32), nullable=False),
        sa.Column("ended_at", sa.String(32), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="running"),
        sa.Column(
            "lead_organization_id",
            sa.Integer,
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("alarm_text", sa.Text, nullable=False, server_default=""),
        sa.Column("alerted_units", sa.String(300), nullable=False, server_default=""),
        sa.Column("dispatch_number", sa.String(40), nullable=False, server_default=""),
        sa.Column("summary", sa.Text, nullable=False, server_default=""),
        sa.Column("weather", sa.Text, nullable=True),
        sa.Column("created_by", sa.String(80), nullable=False, server_default=""),
        sa.Column("created_at", sa.String(32), nullable=False),
        sa.Column("updated_at", sa.String(32), nullable=False),
    )
    op.create_index("ix_incidents_status", "incidents", ["status"])
    op.create_table(
        "incident_organizations",
        sa.Column(
            "incident_id",
            sa.Integer,
            sa.ForeignKey("incidents.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "organization_id",
            sa.Integer,
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column("added_at", sa.String(32), nullable=False),
        sa.Column("added_by", sa.String(80), nullable=False, server_default=""),
    )
    op.create_table(
        "incident_participants",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "incident_id",
            sa.Integer,
            sa.ForeignKey("incidents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Integer,
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("name", sa.String(80), nullable=False, server_default=""),
        sa.Column(
            "organization_id",
            sa.Integer,
            sa.ForeignKey("organizations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("role", sa.String(40), nullable=False),
        sa.Column("from_at", sa.String(32), nullable=True),
        sa.Column("until_at", sa.String(32), nullable=True),
        sa.Column("note", sa.String(200), nullable=False, server_default=""),
    )
    op.create_index(
        "ix_incident_participants_incident_id",
        "incident_participants",
        ["incident_id"],
    )
    op.create_table(
        "incident_sources",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "incident_id",
            sa.Integer,
            sa.ForeignKey("incidents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_id", sa.String(64), nullable=False),
        sa.Column("source_name", sa.String(120), nullable=False, server_default=""),
        sa.Column("added_at", sa.String(32), nullable=False),
        sa.Column("removed_at", sa.String(32), nullable=True),
    )
    op.create_index("ix_incident_sources_incident_id", "incident_sources", ["incident_id"])
    op.create_table(
        "incident_log",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "incident_id",
            sa.Integer,
            sa.ForeignKey("incidents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("at", sa.String(32), nullable=False),
        sa.Column("actor", sa.String(80), nullable=False, server_default=""),
        sa.Column("kind", sa.String(24), nullable=False, server_default="note"),
        sa.Column("text", sa.Text, nullable=False),
    )
    op.create_index("ix_incident_log_incident_id", "incident_log", ["incident_id"])


def downgrade() -> None:
    op.drop_table("incident_log")
    op.drop_table("incident_sources")
    op.drop_table("incident_participants")
    op.drop_table("incident_organizations")
    op.drop_index("ix_incidents_status", "incidents")
    op.drop_table("incidents")
