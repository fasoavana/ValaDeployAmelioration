"""ajout des tables pour chaque service

Revision ID: b9a50e61cefe
Revises: 42a36d00e056
Create Date: 2026-08-27 08:33:12.282357

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql  # AJOUTÉ


# revision identifiers, used by Alembic.
revision: str = 'b9a50e61cefe'
down_revision: Union[str, Sequence[str], None] = '42a36d00e056'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('project_services',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('kind', sa.Enum('FRONT', 'BACK', 'DATABASE', name='componentkind'), nullable=False),
        # CORRIGÉ : create_type=False car ce type existe déjà (créé par la table "projects")
        sa.Column('status', postgresql.ENUM('RUNNING', 'STOPPED', 'BUILDING', 'FAILED', name='projectstatus', create_type=False), nullable=False, server_default='BUILDING'),
        sa.Column('repo_url', sa.String(), nullable=True),
        sa.Column('branch', sa.String(), nullable=True),
        sa.Column('replica', sa.Integer(), nullable=False, server_default='1'),  # AJOUTÉ server_default
        sa.Column('container_ids', sa.JSON(), nullable=True),
        sa.Column('commit_hash', sa.String(), nullable=True),
        sa.Column('env_vars', sa.JSON(), nullable=False, server_default='{}'),  # AJOUTÉ server_default
        sa.Column('db_image', sa.String(), nullable=True),
        sa.Column('volume_name', sa.String(), nullable=True),
        sa.Column('vulnerabilities', sa.JSON(), nullable=True),
        sa.Column('critical_vuln_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('severity_count', sa.JSON(), nullable=True, server_default='{}'),  # CORRIGÉ : '0' n'a pas de sens pour un JSON
        sa.Column('secret_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_secret', sa.JSON(), nullable=True),
        sa.Column('error_message', sa.String(), nullable=True),
        # CORRIGÉ : create_type=False car ce type existe déjà (créé par la table "projects")
        sa.Column('fail_reason', postgresql.ENUM('VULNERABILITY', 'SECRET_LEAK', 'BUILD_ERROR', 'CLONE_ERROR', 'DEPLOY_ERROR', 'DETECTION_ERROR', 'OTHER', name='failreason', create_type=False), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_project_services_id'), 'project_services', ['id'], unique=False)
    op.create_index(op.f('ix_project_services_project_id'), 'project_services', ['project_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_project_services_project_id'), table_name='project_services')
    op.drop_index(op.f('ix_project_services_id'), table_name='project_services')
    op.drop_table('project_services')
    # AJOUTÉ : on supprime le type "componentkind" créé par cette migration (nouveau, propre à cette table).
    # On NE touche PAS à "projectstatus" ni "failreason" : ils sont partagés avec la table "projects".
    postgresql.ENUM(name='componentkind').drop(op.get_bind(), checkfirst=True)