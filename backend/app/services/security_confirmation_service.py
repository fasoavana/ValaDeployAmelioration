# app/services/security_confirmation_service.py
import time
from datetime import datetime
from typing import Callable, List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.models.security_confirmation import SecurityConfirmation, ConfirmationStatus


class SecurityConfirmationService:

    @staticmethod
    def create_pending(
        db: Session,
        project_id: int,
        critical_vulnerabilities: List[Dict[str, Any]],
        severity_count: Dict[str, int],
    ) -> SecurityConfirmation:
        confirmation = SecurityConfirmation(
            project_id=project_id,
            status=ConfirmationStatus.PENDING,
            critical_vulnerabilities=critical_vulnerabilities,
            severity_count=severity_count,
        )
        db.add(confirmation)
        db.commit()
        db.refresh(confirmation)
        return confirmation

    @staticmethod
    def get_pending_for_project(db: Session, project_id: int) -> Optional[SecurityConfirmation]:
        return (
            db.query(SecurityConfirmation)
            .filter(
                SecurityConfirmation.project_id == project_id,
                SecurityConfirmation.status == ConfirmationStatus.PENDING,
            )
            .order_by(SecurityConfirmation.created_at.desc())
            .first()
        )

    @staticmethod
    def get_by_id(db: Session, confirmation_id: int) -> Optional[SecurityConfirmation]:
        return db.query(SecurityConfirmation).filter(SecurityConfirmation.id == confirmation_id).first()

    @staticmethod
    def mark_confirmed(db: Session, confirmation_id: int) -> Optional[SecurityConfirmation]:
        """Appelé par la route quand l'utilisateur clique 'Continuer'."""
        confirmation = SecurityConfirmationService.get_by_id(db, confirmation_id)
        if confirmation and confirmation.status == ConfirmationStatus.PENDING:
            confirmation.status = ConfirmationStatus.CONFIRMED
            confirmation.resolved_at = datetime.utcnow()
            db.commit()
        return confirmation

    @staticmethod
    def mark_rejected(db: Session, confirmation_id: int) -> Optional[SecurityConfirmation]:
        """Appelé par la route quand l'utilisateur clique 'Annuler'."""
        confirmation = SecurityConfirmationService.get_by_id(db, confirmation_id)
        if confirmation and confirmation.status == ConfirmationStatus.PENDING:
            confirmation.status = ConfirmationStatus.REJECTED
            confirmation.resolved_at = datetime.utcnow()
            db.commit()
        return confirmation

    @staticmethod
    def discard(db: Session, confirmation_id: int) -> None:
        """
        Supprime définitivement la trace de confirmation. Appelé par le pipeline
        UNIQUEMENT si le déploiement a été refusé ou a timeout — jamais si confirmé
        (dans ce cas on garde le rapport, consultable ensuite sur la page dédiée).
        """
        confirmation = SecurityConfirmationService.get_by_id(db, confirmation_id)
        if confirmation:
            db.delete(confirmation)
            db.commit()

    @staticmethod
    def wait_for_decision(
        db: Session,
        confirmation_id: int,
        timeout_seconds: float = 10.0,
        poll_interval: float = 0.5,
        is_cancelled: Optional[Callable[[], bool]] = None,
    ) -> ConfirmationStatus:
        """
        Bloque le thread du pipeline (on est déjà en background task, donc pas
        d'impact sur l'API) en attendant que l'utilisateur réponde via la route
        confirm/reject, ou jusqu'au timeout.
        """
        elapsed = 0.0
        while elapsed < timeout_seconds:
            db.expire_all()  # sinon SQLAlchemy peut resservir un statut en cache de session
            confirmation = SecurityConfirmationService.get_by_id(db, confirmation_id)

            if not confirmation:
                # Supprimé entre-temps (ex: projet supprimé pendant l'attente)
                return ConfirmationStatus.REJECTED

            if confirmation.status != ConfirmationStatus.PENDING:
                return confirmation.status

            if is_cancelled and is_cancelled():
                return ConfirmationStatus.REJECTED

            time.sleep(poll_interval)
            elapsed += poll_interval

        return ConfirmationStatus.TIMEOUT