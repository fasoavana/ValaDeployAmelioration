from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

# Charger explicitement tous les modèles participant au même
# registre SQLAlchemy avant l'utilisation de DeploymentRun.
from app.models.project import Project, ProjectComponent
from app.models.user import User
from app.models.security_confirmation import SecurityConfirmation
from app.models.deployment import DeploymentRun
from app.models.security_audit import SecurityAuditLog




class SecurityAuditService:

    @staticmethod
    def create(
        db: Session,
        project_id: int,
        source: str,
        decision: str,
        reasons=None,
        severity_count=None,
        secret_count: int = 0,
        finding_count: Optional[int] = None,
        component_id: Optional[int] = None,
        deployment_run_id: Optional[int] = None,
    ) -> SecurityAuditLog:
        """
        Enregistre une décision PASS / WARN / BLOCK.

        L'utilisateur concerné est déterminé à partir du
        DeploymentRun lorsque celui-ci est disponible.
        """

        reasons = list(reasons or [])
        severity_count = dict(
            severity_count or {}
        )

        user_id = None

        if deployment_run_id is not None:
            run = db.get(
                DeploymentRun,
                deployment_run_id,
            )

            if run is not None:
                user_id = run.user_id

        if finding_count is None:
            finding_count = sum(
                int(
                    severity_count.get(
                        severity,
                        0,
                    )
                    or 0
                )
                for severity in (
                    "CRITICAL",
                    "HIGH",
                )
            )

        audit = SecurityAuditLog(
            project_id=project_id,
            component_id=component_id,
            deployment_run_id=deployment_run_id,
            user_id=user_id,
            source=str(source).lower(),
            decision=str(decision).upper(),
            reasons=reasons,
            severity_count=severity_count,
            finding_count=max(
                int(finding_count or 0),
                0,
            ),
            secret_count=max(
                int(secret_count or 0),
                0,
            ),
        )

        db.add(audit)
        db.commit()
        db.refresh(audit)

        return audit

    @staticmethod
    def get_by_id(
        db: Session,
        audit_id: int,
    ) -> Optional[SecurityAuditLog]:

        return db.get(
            SecurityAuditLog,
            audit_id,
        )

    @staticmethod
    def resolve(
        db: Session,
        audit_id: int,
        outcome: str,
        resolved_by_user_id: Optional[int] = None,
    ) -> Optional[SecurityAuditLog]:
        """
        Complète une décision BLOCK lorsqu'une confirmation
        est résolue.

        L'entrée n'est jamais supprimée.
        """

        audit = SecurityAuditService.get_by_id(
            db,
            audit_id,
        )

        if audit is None:
            return None

        audit.confirmation_outcome = str(
            outcome
        ).lower()

        audit.resolved_by_user_id = (
            resolved_by_user_id
        )

        audit.resolved_at = datetime.now(
            timezone.utc
        )

        db.commit()

        return audit

    @staticmethod
    def list_for_project(
        db: Session,
        project_id: int,
        limit: int = 100,
    ):
        safe_limit = max(
            1,
            min(int(limit), 500),
        )

        return (
            db.query(SecurityAuditLog)
            .filter(
                SecurityAuditLog.project_id
                == project_id
            )
            .order_by(
                SecurityAuditLog.created_at.desc(),
                SecurityAuditLog.id.desc(),
            )
            .limit(safe_limit)
            .all()
        )
