"""add Security Gate v2 audit log

Revision ID: 6f4a9b2c1d7e
Revises: d83a72b91e60
Create Date: 2026-10-02

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "6f4a9b2c1d7e"
down_revision: Union[str, None] = "d83a72b91e60"

branch_labels: Union[
    str,
    Sequence[str],
    None,
] = None

depends_on: Union[
    str,
    Sequence[str],
    None,
] = None


def upgrade() -> None:

    op.create_table(
        "security_audit_logs",

        sa.Column(
            "id",
            sa.Integer(),
            nullable=False,
        ),

        sa.Column(
            "project_id",
            sa.Integer(),
            nullable=False,
        ),

        sa.Column(
            "component_id",
            sa.Integer(),
            nullable=True,
        ),

        sa.Column(
            "deployment_run_id",
            sa.Integer(),
            nullable=True,
        ),

        sa.Column(
            "user_id",
            sa.Integer(),
            nullable=True,
        ),

        sa.Column(
            "source",
            sa.String(length=32),
            nullable=False,
        ),

        sa.Column(
            "decision",
            sa.String(length=16),
            nullable=False,
        ),

        sa.Column(
            "reasons",
            sa.JSON(),
            nullable=False,
        ),

        sa.Column(
            "severity_count",
            sa.JSON(),
            nullable=True,
        ),

        sa.Column(
            "finding_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),

        sa.Column(
            "secret_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),

        sa.Column(
            "confirmation_outcome",
            sa.String(length=32),
            nullable=True,
        ),

        sa.Column(
            "resolved_by_user_id",
            sa.Integer(),
            nullable=True,
        ),

        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),

        sa.Column(
            "resolved_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),

        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            ondelete="CASCADE",
        ),

        sa.ForeignKeyConstraint(
            ["component_id"],
            ["project_services.id"],
            ondelete="SET NULL",
        ),

        sa.ForeignKeyConstraint(
            ["deployment_run_id"],
            ["deployment_runs.id"],
            ondelete="SET NULL",
        ),

        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),

        sa.ForeignKeyConstraint(
            ["resolved_by_user_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),

        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_security_audit_logs_id",
        "security_audit_logs",
        ["id"],
    )

    op.create_index(
        "ix_security_audit_logs_project_id",
        "security_audit_logs",
        ["project_id"],
    )

    op.create_index(
        "ix_security_audit_logs_component_id",
        "security_audit_logs",
        ["component_id"],
    )

    op.create_index(
        "ix_security_audit_logs_deployment_run_id",
        "security_audit_logs",
        ["deployment_run_id"],
    )

    op.create_index(
        "ix_security_audit_logs_user_id",
        "security_audit_logs",
        ["user_id"],
    )

    op.create_index(
        "ix_security_audit_logs_source",
        "security_audit_logs",
        ["source"],
    )

    op.create_index(
        "ix_security_audit_logs_decision",
        "security_audit_logs",
        ["decision"],
    )


    op.add_column(
        "security_confirmations",
        sa.Column(
            "audit_log_id",
            sa.Integer(),
            nullable=True,
        ),
    )

    op.create_foreign_key(
        "fk_security_confirmations_audit_log_id",
        "security_confirmations",
        "security_audit_logs",
        ["audit_log_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_index(
        "ix_security_confirmations_audit_log_id",
        "security_confirmations",
        ["audit_log_id"],
    )


def downgrade() -> None:

    op.drop_index(
        "ix_security_confirmations_audit_log_id",
        table_name="security_confirmations",
    )

    op.drop_constraint(
        "fk_security_confirmations_audit_log_id",
        "security_confirmations",
        type_="foreignkey",
    )

    op.drop_column(
        "security_confirmations",
        "audit_log_id",
    )

    op.drop_index(
        "ix_security_audit_logs_decision",
        table_name="security_audit_logs",
    )

    op.drop_index(
        "ix_security_audit_logs_source",
        table_name="security_audit_logs",
    )

    op.drop_index(
        "ix_security_audit_logs_user_id",
        table_name="security_audit_logs",
    )

    op.drop_index(
        "ix_security_audit_logs_deployment_run_id",
        table_name="security_audit_logs",
    )

    op.drop_index(
        "ix_security_audit_logs_component_id",
        table_name="security_audit_logs",
    )

    op.drop_index(
        "ix_security_audit_logs_project_id",
        table_name="security_audit_logs",
    )

    op.drop_index(
        "ix_security_audit_logs_id",
        table_name="security_audit_logs",
    )

    op.drop_table(
        "security_audit_logs"
    )
