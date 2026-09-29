from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.deployment import DeploymentRun
from app.models.project import Project
from app.services.project_service import ProjectService

router = APIRouter()


# NOUVELLE ROUTE — tous les runs, tous projets confondus, pour l'utilisateur connecté.
# Utilisée par la vue "Pipeline" du sidebar (sans project_id dans l'URL).
@router.get("/deployments")
def get_all_deployments(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    rows = (
        db.query(DeploymentRun, Project.slug)
        .join(Project, Project.id == DeploymentRun.project_id)
        .filter(Project.user_id == current_user.id)
        .order_by(DeploymentRun.started_at.desc())
        .all()
    )

    result = []
    for run, slug in rows:
        result.append({
            "id": run.id,
            "project_id": run.project_id,
            "project_slug": slug,
            "trigger": run.trigger.value if hasattr(run.trigger, 'value') else str(run.trigger),
            "status": run.status.value if hasattr(run.status, 'value') else str(run.status),
            "commit_hash": run.commit_hash,
            "started_at": run.started_at,
            "finished_at": run.finished_at,
            # Pas de "logs" ici volontairement : trop lourd pour une liste, le détail
            # du run (GET /projects/{project_id}/deployments/{run_id}) les fournit déjà.
        })
    return result


@router.get("/projects/{project_id}/deployments")
def get_project_deployments(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    project = ProjectService.get_project_by_id(db, project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=404, detail="Projet introuvable ou accès non autorisé")
    runs = db.query(DeploymentRun).filter(
        DeploymentRun.project_id == project_id
    ).order_by(DeploymentRun.started_at.desc()).all()
    # On construit la réponse manuellement pour inclure le project_slug
    result = []
    for run in runs:
        result.append({
            "id": run.id,
            "project_id": run.project_id,
            "project_slug": project.slug,  # <--- AJOUT CRUCIAL
            "trigger": run.trigger.value if hasattr(run.trigger, 'value') else str(run.trigger),
            "status": run.status.value if hasattr(run.status, 'value') else str(run.status),
            "commit_hash": run.commit_hash,
            "started_at": run.started_at,
            "finished_at": run.finished_at,
            "logs": run.logs
        })
    return result


@router.get("/projects/{project_id}/deployments/{run_id}")
def get_deployment_run_details(
    project_id: int,
    run_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    project = ProjectService.get_project_by_id(db, project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=404, detail="Projet introuvable ou accès non autorisé")
    run = db.query(DeploymentRun).filter(
        DeploymentRun.id == run_id,
        DeploymentRun.project_id == project_id
    ).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run de déploiement introuvable")
    # On inclut aussi le slug ici
    return {
        "id": run.id,
        "project_id": run.project_id,
        "project_slug": project.slug,  # <--- AJOUT CRUCIAL
        "trigger": run.trigger.value if hasattr(run.trigger, 'value') else str(run.trigger),
        "status": run.status.value if hasattr(run.status, 'value') else str(run.status),
        "commit_hash": run.commit_hash,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
        "logs": run.logs
    }