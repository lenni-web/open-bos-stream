"""Checklisten (Vorlagen, Listen, Positionen) und Dokumente

Revision ID: 0005_checklists
Revises: 0004_incident_map
"""

from alembic import op
import sqlalchemy as sa


revision = "0005_checklists"
down_revision = "0004_incident_map"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "checklist_templates",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "organization_id",
            sa.Integer,
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
        sa.Column("items", sa.Text, nullable=False, server_default="[]"),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("archived", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("created_by", sa.String(80), nullable=False, server_default=""),
        sa.Column("created_at", sa.String(32), nullable=False),
        sa.Column("updated_by", sa.String(80), nullable=False, server_default=""),
        sa.Column("updated_at", sa.String(32), nullable=False),
    )
    op.create_table(
        "checklists",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
        sa.Column(
            "template_id",
            sa.Integer,
            sa.ForeignKey("checklist_templates.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("template_version", sa.Integer, nullable=True),
        sa.Column(
            "organization_id",
            sa.Integer,
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "incident_id",
            sa.Integer,
            sa.ForeignKey("incidents.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("status", sa.String(16), nullable=False, server_default="open"),
        sa.Column("created_by", sa.String(80), nullable=False, server_default=""),
        sa.Column("created_at", sa.String(32), nullable=False),
        sa.Column("completed_by", sa.String(80), nullable=True),
        sa.Column("completed_at", sa.String(32), nullable=True),
    )
    op.create_index("ix_checklists_incident_id", "checklists", ["incident_id"])
    op.create_index("ix_checklists_organization_id", "checklists", ["organization_id"])
    op.create_table(
        "checklist_items",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "checklist_id",
            sa.Integer,
            sa.ForeignKey("checklists.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("position", sa.Integer, nullable=False, server_default="0"),
        sa.Column("section", sa.String(80), nullable=False, server_default=""),
        sa.Column("text", sa.String(300), nullable=False),
        sa.Column("hint", sa.String(300), nullable=False, server_default=""),
        sa.Column("required", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("checked", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("checked_by", sa.String(80), nullable=True),
        sa.Column("checked_at", sa.String(32), nullable=True),
        sa.Column("note", sa.String(1000), nullable=False, server_default=""),
        sa.Column("note_by", sa.String(80), nullable=True),
        sa.Column("note_at", sa.String(32), nullable=True),
    )
    op.create_index("ix_checklist_items_checklist_id", "checklist_items", ["checklist_id"])
    op.create_table(
        "documents",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "organization_id",
            sa.Integer,
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("description", sa.String(500), nullable=False, server_default=""),
        sa.Column("stored_name", sa.String(80), nullable=False, unique=True),
        sa.Column("original_name", sa.String(200), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("size", sa.Integer, nullable=False),
        sa.Column("uploaded_by", sa.String(80), nullable=False, server_default=""),
        sa.Column("uploaded_at", sa.String(32), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("documents")
    op.drop_index("ix_checklist_items_checklist_id", "checklist_items")
    op.drop_table("checklist_items")
    op.drop_index("ix_checklists_organization_id", "checklists")
    op.drop_index("ix_checklists_incident_id", "checklists")
    op.drop_table("checklists")
    op.drop_table("checklist_templates")
