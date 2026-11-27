"""Einsatzkarte mit Quadranten (Suchabschnitten), Kennzeichnung als Übung

Revision ID: 0004_incident_map
Revises: 0003_incidents
"""

from alembic import op
import sqlalchemy as sa


revision = "0004_incident_map"
down_revision = "0003_incidents"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # SQLite kann Spalten direkt anfügen (keine Neuanlage der Tabelle).
    op.add_column(
        "incidents",
        sa.Column("map_revision", sa.Integer, nullable=False, server_default="0"),
    )
    op.add_column(
        "incidents",
        sa.Column("exercise", sa.Boolean, nullable=False, server_default=sa.false()),
    )
    op.create_table(
        "incident_map_items",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "incident_id",
            sa.Integer,
            sa.ForeignKey("incidents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(16), nullable=False, server_default="sector"),
        sa.Column("name", sa.String(40), nullable=False),
        sa.Column("geometry", sa.Text, nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="open"),
        sa.Column("assignee", sa.String(80), nullable=False, server_default=""),
        sa.Column("note", sa.String(300), nullable=False, server_default=""),
        sa.Column("created_by", sa.String(80), nullable=False, server_default=""),
        sa.Column("created_at", sa.String(32), nullable=False),
        sa.Column("updated_by", sa.String(80), nullable=False, server_default=""),
        sa.Column("updated_at", sa.String(32), nullable=False),
    )
    op.create_index("ix_incident_map_items_incident_id", "incident_map_items", ["incident_id"])


def downgrade() -> None:
    op.drop_index("ix_incident_map_items_incident_id", "incident_map_items")
    op.drop_table("incident_map_items")
    with op.batch_alter_table("incidents") as batch:
        batch.drop_column("exercise")
        batch.drop_column("map_revision")
