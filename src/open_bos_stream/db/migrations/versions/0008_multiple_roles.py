"""Mehrere Rollen je Konto und Organisation

Revision ID: 0008_multiple_roles
Revises: 0007_drones
"""

from alembic import op


revision = "0008_multiple_roles"
down_revision = "0007_drones"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # SQLite kann Constraints nicht ändern: die Tabelle wird neu angelegt.
    # Auf memberships verweist keine andere Tabelle, Daten bleiben erhalten.
    with op.batch_alter_table("memberships", recreate="always") as batch:
        batch.drop_constraint("uq_membership", type_="unique")
        batch.create_unique_constraint(
            "uq_membership_role", ["user_id", "organization_id", "role"]
        )


def downgrade() -> None:
    # Je Organisation bleibt nur die Rolle mit den meisten Rechten.
    op.execute(
        """
        DELETE FROM memberships WHERE id NOT IN (
            SELECT id FROM (
                SELECT id, ROW_NUMBER() OVER (
                    PARTITION BY user_id, organization_id
                    ORDER BY CASE role
                        WHEN 'ortsbrandmeister' THEN 4
                        WHEN 'admin' THEN 3
                        WHEN 'operator' THEN 2
                        ELSE 1
                    END DESC
                ) AS position FROM memberships
            ) WHERE position = 1
        )
        """
    )
    with op.batch_alter_table("memberships", recreate="always") as batch:
        batch.drop_constraint("uq_membership_role", type_="unique")
        batch.create_unique_constraint("uq_membership", ["user_id", "organization_id"])
