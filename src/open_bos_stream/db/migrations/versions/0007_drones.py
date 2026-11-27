"""DJI-Geräte, Zuordnung zu Einsätzen und Telemetrie-Aufzeichnung

Revision ID: 0007_drones
Revises: 0006_user_names
"""

from alembic import op
import sqlalchemy as sa


revision = "0007_drones"
down_revision = "0006_user_names"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "dji_devices",
        sa.Column("serial", sa.String(64), primary_key=True),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("model_type", sa.Integer, nullable=True),
        sa.Column("model_sub_type", sa.Integer, nullable=True),
        sa.Column("name", sa.String(80), nullable=False, server_default=""),
        sa.Column(
            "organization_id",
            sa.Integer,
            sa.ForeignKey("organizations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("gateway_serial", sa.String(64), nullable=True),
        sa.Column("blocked", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("first_seen", sa.String(32), nullable=False),
        sa.Column("last_seen", sa.String(32), nullable=False),
    )
    op.create_table(
        "incident_drones",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "incident_id",
            sa.Integer,
            sa.ForeignKey("incidents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("serial", sa.String(64), nullable=False),
        sa.Column("name", sa.String(80), nullable=False, server_default=""),
        sa.Column("added_at", sa.String(32), nullable=False),
        sa.Column("removed_at", sa.String(32), nullable=True),
    )
    op.create_table(
        "drone_records",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "incident_id",
            sa.Integer,
            sa.ForeignKey("incidents.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("serial", sa.String(64), nullable=False),
        sa.Column("received_at", sa.String(32), nullable=False),
        sa.Column("topic", sa.String(160), nullable=False),
        sa.Column("latitude", sa.Float, nullable=True),
        sa.Column("longitude", sa.Float, nullable=True),
        sa.Column("elevation", sa.Float, nullable=True),
        sa.Column("battery", sa.Integer, nullable=True),
        sa.Column("home_distance", sa.Float, nullable=True),
        sa.Column("payload", sa.Text, nullable=False),
    )
    op.create_index("ix_drone_records_incident", "drone_records", ["incident_id", "serial", "id"])
    op.create_index("ix_drone_records_unassigned", "drone_records", ["serial", "received_at"])


def downgrade() -> None:
    op.drop_table("drone_records")
    op.drop_table("incident_drones")
    op.drop_table("dji_devices")
