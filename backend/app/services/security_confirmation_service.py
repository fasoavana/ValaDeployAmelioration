# app/services/security_confirmation_service.py

import time

from datetime import datetime, timezone
from typing import Callable, List, Dict, Any, Optional

from sqlalchemy.orm import Session

from app.models.security_confirmation import (
    SecurityConfirmation,
    ConfirmationStatus,
)
from app.services.security_audit_service import (
    SecurityAuditService,
)


class SecurityConfirmationService:

    @staticmethod
    def create_pending(
        db: Session,
        project_id: int,
        critical_vulnerabilities: List[Dict[str, Any]],
        severity_count: Dict[str, int],
        audit_log_id: Optional[int] = None,
    ) -> SecurityConfirmation:

        confirmation = SecurityConfirmation(
            project_id=project_id,
            audit_log_id=audit_log_id,
            status=ConfirmationStatus.PENDING,
            critical_vulnerabilities=critical_vulnerabilities,
            severity_count=severity_count,
        )

        db.add(confirmation)
        db.commit()
        db.refresh(confirmation)

        return confirmation

    @staticmethod
    def get_pending_for_project(
        db: Session,
        project_id: int,
    ) -> Optional[SecurityConfirmation]:

        return (
            db.query(SecurityConfirmation)
            .filter(
                SecurityConfirmation.project_id
                == project_id,

                SecurityConfirmation.status
                == ConfirmationStatus.PENDING,
            )
            .order_by(
                SecurityConfirmation.created_at.desc()
            )
            .first()
        )

    @staticmethod
    def get_by_id(
        db: Session,
        confirmation_id: int,
    ) -> Optional[SecurityConfirmation]:

        return (
            db.query(SecurityConfirmation)
            .filter(
                SecurityConfirmation.id
                == confirmation_id
            )
            .first()
        )

    @staticmethod
    def _resolve_audit(
        db: Session,
        confirmation: SecurityConfirmation,
        outcome: str,
        resolved_by_user_id: Optional[int] = None,
    ) -> None:

        if confirmation.audit_log_id is None:
            return

        SecurityAuditService.resolve(
            db=db,
            audit_id=confirmation.audit_log_id,
            outcome=outcome,
            resolved_by_user_id=resolved_by_user_id,
        )

    @staticmethod
    def mark_confirmed(
        db: Session,
        confirmation_id: int,
        resolved_by_user_id: Optional[int] = None,
    ) -> Optional[SecurityConfirmation]:

        confirmation = (
            SecurityConfirmationService.get_by_id(
                db,
                confirmation_id,
            )
        )

        if (
            confirmation
            and confirmation.status
            == ConfirmationStatus.PENDING
        ):
            confirmation.status = (
                ConfirmationStatus.CONFIRMED
            )

            confirmation.resolved_at = datetime.now(
                timezone.utc
            )

            db.commit()

            SecurityConfirmationService._resolve_audit(
                db,
                confirmation,
                "confirmed",
                resolved_by_user_id,
            )

        return confirmation

    @staticmethod
    def mark_rejected(
        db: Session,
        confirmation_id: int,
        resolved_by_user_id: Optional[int] = None,
    ) -> Optional[SecurityConfirmation]:

        confirmation = (
            SecurityConfirmationService.get_by_id(
                db,
                confirmation_id,
            )
        )

        if (
            confirmation
            and confirmation.status
            == ConfirmationStatus.PENDING
        ):
            confirmation.status = (
                ConfirmationStatus.REJECTED
            )

            confirmation.resolved_at = datetime.now(
                timezone.utc
            )

            db.commit()

            SecurityConfirmationService._resolve_audit(
                db,
                confirmation,
                "rejected",
                resolved_by_user_id,
            )

        return confirmation

    @staticmethod
    def mark_timeout(
        db: Session,
        confirmation_id: int,
    ) -> Optional[SecurityConfirmation]:

        confirmation = (
            SecurityConfirmationService.get_by_id(
                db,
                confirmation_id,
            )
        )

        if (
            confirmation
            and confirmation.status
            == ConfirmationStatus.PENDING
        ):
            confirmation.status = (
                ConfirmationStatus.TIMEOUT
            )

            confirmation.resolved_at = datetime.now(
                timezone.utc
            )

            db.commit()

            SecurityConfirmationService._resolve_audit(
                db,
                confirmation,
                "timeout",
            )

        return confirmation

    @staticmethod
    def mark_cancelled(
        db: Session,
        confirmation_id: int,
    ) -> Optional[SecurityConfirmation]:
        """
        Le modèle historique ne possède pas de statut CANCELLED.

        On clôt donc la confirmation comme REJECTED, tandis que
        le journal d'audit conserve précisément l'outcome
        "cancelled".
        """

        confirmation = (
            SecurityConfirmationService.get_by_id(
                db,
                confirmation_id,
            )
        )

        if (
            confirmation
            and confirmation.status
            == ConfirmationStatus.PENDING
        ):
            confirmation.status = (
                ConfirmationStatus.REJECTED
            )

            confirmation.resolved_at = datetime.now(
                timezone.utc
            )

            db.commit()

            SecurityConfirmationService._resolve_audit(
                db,
                confirmation,
                "cancelled",
            )

        return confirmation

    @staticmethod
    def wait_for_decision(
        db: Session,
        confirmation_id: int,
        timeout_seconds: float = 10.0,
        poll_interval: float = 0.5,
        is_cancelled: Optional[
            Callable[[], bool]
        ] = None,
    ) -> ConfirmationStatus:

        elapsed = 0.0

        while elapsed < timeout_seconds:

            db.expire_all()

            confirmation = (
                SecurityConfirmationService.get_by_id(
                    db,
                    confirmation_id,
                )
            )

            if not confirmation:
                return ConfirmationStatus.REJECTED

            if (
                confirmation.status
                != ConfirmationStatus.PENDING
            ):
                return confirmation.status

            if is_cancelled and is_cancelled():
                return ConfirmationStatus.REJECTED

            time.sleep(poll_interval)
            elapsed += poll_interval

        return ConfirmationStatus.TIMEOUT
