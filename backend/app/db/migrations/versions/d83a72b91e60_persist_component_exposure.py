"""Persist component exposure without guessing legacy private/public choices.

Revision ID: d83a72b91e60
Revises: f2a1c9e04d3b
"""
from alembic import op
import sqlalchemy as sa

revision = "d83a72b91e60"
down_revision = "f2a1c9e04d3b"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("project_services", sa.Column("expose_publicly", sa.Boolean(), nullable=True))


def downgrade():
    op.drop_column("project_services", "expose_publicly")
