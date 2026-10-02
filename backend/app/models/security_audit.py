from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    JSON,
    ForeignKey,
)
from sqlalchemy.sql import func

from app.db.database import Base


class SecurityAuditLog(Base):
    """
    Journal persistant des décisions du Security Gate v2.

    Une entrée représente une décision produite par un contrôle
    de sécurité : PASS, WARN ou BLOCK.

    Les valeurs sensibles brutes ne doivent jamais être stockées
    dans cette table.
    """

    __tablename__ = "security_audit_logs"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    project_id = Column(
        Integer,
        ForeignKey(
            "projects.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    component_id = Column(
        Integer,
        ForeignKey(
            "project_services.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    deployment_run_id = Column(
        Integer,
        ForeignKey(
            "deployment_runs.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    # Utilisateur ayant déclenché le déploiement.
    user_id = Column(
        Integer,
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    # trivy / gitleaks
    source = Column(
        String(32),
        nullable=False,
        index=True,
    )

    # PASS / WARN / BLOCK
    decision = Column(
        String(16),
        nullable=False,
        index=True,
    )

    # Raisons ayant conduit à la décision.
    reasons = Column(
        JSON,
        nullable=False,
        default=list,
    )

    severity_count = Column(
        JSON,
        nullable=True,
        default=dict,
    )

    finding_count = Column(
        Integer,
        nullable=False,
        default=0,
    )

    secret_count = Column(
        Integer,
        nullable=False,
        default=0,
    )

    # Pour un BLOCK soumis à confirmation :
    # confirmed / rejected / timeout / cancelled.
    confirmation_outcome = Column(
        String(32),
        nullable=True,
    )

    # Utilisateur ayant répondu à la confirmation.
    resolved_by_user_id = Column(
        Integer,
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    resolved_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )
