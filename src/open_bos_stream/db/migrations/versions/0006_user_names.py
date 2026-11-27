"""Vorname, Nachname und Spitzname für Konten

Revision ID: 0006_user_names
Revises: 0005_checklists
"""

from alembic import op
import sqlalchemy as sa


revision = "0006_user_names"
down_revision = "0005_checklists"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # SQLite kann Spalten direkt anfügen (keine Neuanlage der Tabelle).
    op.add_column("users", sa.Column("first_name", sa.String(60), nullable=False, server_default=""))
    op.add_column("users", sa.Column("last_name", sa.String(60), nullable=False, server_default=""))
    op.add_column("users", sa.Column("nickname", sa.String(40), nullable=False, server_default=""))


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_column("nickname")
        batch.drop_column("last_name")
        batch.drop_column("first_name")
