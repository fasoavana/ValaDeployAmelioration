"""add security_confirmations table and pending states

Revision ID: f2a1c9e04d3b
Revises: c8994bd7410b
Create Date: 2026-09-23 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'f2a1c9e04d3b'
down_revision: Union[str, Sequence[str], None] = 'c8994bd7410b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE pipelinestatus ADD VALUE IF NOT EXISTS 'AWAITING_CONFIRMATION'")
        op.execute("ALTER TYPE projectstatus ADD VALUE IF NOT EXISTS 'PENDING_SECURITY_CONFIRMATION'")

    # Pattern officiel Alembic pour les ENUM Postgres : sa.Enum générique avec
    # create_type=False ne propage pas toujours fiablement ce flag à la version
    # compilée pour Postgres (gotcha connu). postgresql.ENUM est le type natif
    # du dialecte, il respecte create_type de façon garantie.
    confirmation_status_enum = postgresql.ENUM(
        'PENDING', 'CONFIRMED', 'REJECTED', 'TIMEOUT',
        name='confirmationstatus'
    )
    confirmation_status_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        'security_confirmations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('status', postgresql.ENUM(
            'PENDING', 'CONFIRMED', 'REJECTED', 'TIMEOUT',
            name='confirmationstatus', create_type=False
        ), nullable=False, server_default='PENDING'),
        sa.Column('critical_vulnerabilities', sa.JSON(), nullable=False),
        sa.Column('severity_count', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_security_confirmations_id'), 'security_confirmations', ['id'], unique=False)
    op.create_index(op.f('ix_security_confirmations_project_id'), 'security_confirmations', ['project_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""

    op.drop_index(op.f('ix_security_confirmations_project_id'), table_name='security_confirmations')
    op.drop_index(op.f('ix_security_confirmations_id'), table_name='security_confirmations')
    op.drop_table('security_confirmations')

    confirmation_status_enum = postgresql.ENUM(
        'PENDING', 'CONFIRMED', 'REJECTED', 'TIMEOUT',
        name='confirmationstatus'
    )
    confirmation_status_enum.drop(op.get_bind(), checkfirst=True)