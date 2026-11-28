"""Beteiligung von Wehren mit Zeitraum (von–bis)

Revision ID: 0009_incident_org_periods
Revises: 0008_multiple_roles
"""

from alembic import op
import sqlalchemy as sa


revision = "0009_incident_org_periods"
down_revision = "0008_multiple_roles"
branch_labels = None
depends_on = None


def _columns() -> list:
    return [
        sa.Column("added_at", sa.String(32), nullable=False),
        sa.Column("added_by", sa.String(80), nullable=False, server_default=""),
    ]


def _references(*, primary_key: bool) -> list:
    return [
        sa.Column(
            "incident_id", sa.Integer,
            sa.ForeignKey("incidents.id", ondelete="CASCADE"),
            primary_key=primary_key, nullable=False,
        ),
        sa.Column(
            "organization_id", sa.Integer,
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            primary_key=primary_key, nullable=False,
        ),
    ]


def upgrade() -> None:
    # Eine Wehr kann mehrfach beteiligt gewesen sein: eigener Schlüssel je
    # Zeitraum statt (Einsatz, Organisation). Auf die Tabelle verweist nichts.
    op.create_table(
        "incident_organizations_new",
        sa.Column("id", sa.Integer, primary_key=True),
        *_references(primary_key=False),
        *_columns(),
        sa.Column("removed_at", sa.String(32), nullable=True),
        sa.Column("removed_by", sa.String(80), nullable=False, server_default=""),
    )
    op.execute(
        "INSERT INTO incident_organizations_new "
        "(incident_id, organization_id, added_at, added_by) "
        "SELECT incident_id, organization_id, added_at, added_by "
        "FROM incident_organizations ORDER BY added_at"
    )
    op.drop_table("incident_organizations")
    op.rename_table("incident_organizations_new", "incident_organizations")
    op.create_index(
        "ix_incident_organizations_incident", "incident_organizations", ["incident_id"]
    )


def downgrade() -> None:
    # Frühere Zeiträume gehen verloren; es bleiben die aktuell Beteiligten.
    op.create_table(
        "incident_organizations_old",
        *_references(primary_key=True),
        *_columns(),
    )
    op.execute(
        "INSERT INTO incident_organizations_old "
        "(incident_id, organization_id, added_at, added_by) "
        "SELECT incident_id, organization_id, MIN(added_at), added_by "
        "FROM incident_organizations WHERE removed_at IS NULL "
        "GROUP BY incident_id, organization_id"
    )
    op.drop_table("incident_organizations")
    op.rename_table("incident_organizations_old", "incident_organizations")
