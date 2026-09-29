#app/services/deployment_run_tracker.py
"""
Extrait de deploy_service.py : mettre à jour le statut/logs d'un DeploymentRun.

Sorti dans son propre module pour être appelé à la fois par deploy_service.py
(run_deployment_pipeline) et par les ComponentDeployer de
app/services/stack_deployment/ (run_stack_deployment_pipeline), sans créer
d'import circulaire entre les deux.

Aucun changement de comportement par rapport à l'ancien _update_pipeline_run.
"""
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.deployment import DeploymentRun, PipelineStatus


def update_pipeline_run(db: Session, run_id: int, status: PipelineStatus, log_message: str) -> None:
    """Met à jour le statut et ajoute un message aux logs du run en cours."""
    run = db.query(DeploymentRun).filter(DeploymentRun.id == run_id).first()
    if run:
        run.status = status
        timestamp = datetime.now(timezone.utc).strftime("%H:%M:%S")
        run.logs = (run.logs or "") + f"[{timestamp}] {status.value.upper()}: {log_message}\n"

        if status in [PipelineStatus.SUCCESS, PipelineStatus.FAILED]:
            run.finished_at = datetime.now(timezone.utc)

        db.commit()
        db.refresh(run)
