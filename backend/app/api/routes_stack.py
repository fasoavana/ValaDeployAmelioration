from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from starlette.concurrency import run_in_threadpool
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.project import ProjectStatus
from app.services.project_service import ProjectService
from app.services.deploy_service import DeployService
from app.schemas.stack_deploy import StackDeploySchema

router = APIRouter()

@router.post("/deploy/stack", status_code=202)
async def deploy_stack(
    payload: StackDeploySchema,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Déploie une stack multi-composants (front/back/database) en une fois.
    Même pattern que /deploy : création en base (BUILDING) en synchrone,
    puis pipeline lancé en tâche de fond.
    """
    # Traduction vers le format attendu par create_pending_stack (clé "env_vars")
    components_for_creation = [
        {
            "name": c.name,
            "kind": c.kind,
            "repo_url": c.repo_url,
            "branch": c.branch,
            "replica": c.replica,
            "env_vars": c.envs_var or {},
            "db_image": c.db_image,
            "volume_name": c.volume_name,
            "port": c.port,
        }
        for c in payload.components
    ]

    try:
        new_project = ProjectService.create_pending_stack(
            db=db,
            user=current_user,
            slug=payload.slug,
            components=components_for_creation,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Associe chaque component_id généré (par nom) au payload d'origine,
    # et traduit vers le format attendu par run_stack_deployment_pipeline (clé "envs_var")
    components_by_name = {s.name: s.id for s in new_project.services}
    pipeline_components = [
        {
            "component_id": components_by_name[c.name],
            "name": c.name,
            "kind": c.kind,
            "repo_url": c.repo_url,
            "branch": c.branch,
            "replica": c.replica,
            "envs_var": c.envs_var,
            "db_image": c.db_image,
            "volume_name": c.volume_name,
            "expose_publicly": c.expose_publicly,
            "port": c.port,
        }
        for c in payload.components
    ]

    # AJOUT : transmission du user_id pour l'historique
    background_tasks.add_task(
        run_in_threadpool,
        DeployService.run_stack_deployment_pipeline,
        new_project.id,
        payload.slug,
        pipeline_components,
        user_id=current_user.id,
    )

    return {
        "project_id": new_project.id,
        "status": new_project.status,
        "components": [{"name": s.name, "kind": s.kind, "status": s.status} for s in new_project.services],
        "message": "Déploiement de la stack lancé."
    }

@router.get("/deploy/stacks")
async def list_stacks(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Liste résumée (1 ligne/stack) — détail des composants chargé à la demande via l'endpoint existant /deploy/stack/{project_id}/status."""
    stacks = ProjectService.get_user_stacks(db, current_user.id)
    result = []
    for project in stacks:
        components = ProjectService.get_components_by_project(db, project.id)
        
        # On récupère les valeurs des enums sous forme de chaîne pour comparaison
        comp_statuses = [c.status.value if hasattr(c.status, 'value') else str(c.status) for c in components]
        
        if 'building' in comp_statuses:
            aggregated_status = ProjectStatus.BUILDING
        elif 'failed' in comp_statuses:
            aggregated_status = ProjectStatus.FAILED
        elif 'running' in comp_statuses:
            aggregated_status = ProjectStatus.RUNNING
        else:
            aggregated_status = ProjectStatus.STOPPED
            
        # Mise à jour du statut en BDD pour maintenir la cohérence
        if project.status != aggregated_status:
            project.status = aggregated_status
            db.commit()
            
        result.append({
            "project_id": project.id,
            "slug": project.slug,
            "status": aggregated_status.value if hasattr(aggregated_status, 'value') else aggregated_status,
            "created_at": project.created_at,
            "component_count": len(components),
        })
    return result

@router.get("/deploy/stack/{project_id}/status")
async def get_stack_status(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Statut global du Project parent + détail de chaque composant.
    """
    project = ProjectService.get_project_by_id(db, project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=404, detail="Projet introuvable")

    components = ProjectService.get_components_by_project(db, project_id)

    return {
        "project_id": project.id,
        "status": project.status,
        "components": [
            {
                "id": c.id,
                "name": c.name,
                "kind": c.kind,
                "status": c.status,
                "error_message": c.error_message,
                "container_ids": c.container_ids if c.status == ProjectStatus.RUNNING else None,
            }
            for c in components
        ],
    }
    
@router.delete("/deploy/stack/{project_id}")
async def delete_stack(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Supprime une stack, ses conteneurs Docker et ses entrées en base de données."""
    # Vérification de l'appartenance
    project = ProjectService.get_project_by_id(db, project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=404, detail="Stack introuvable ou accès non autorisé")

    # Appel au service pour nettoyer Docker + BDD
    success = ProjectService.delete_project_and_containers(db, project_id, current_user.id)
    
    if not success:
        raise HTTPException(status_code=500, detail="Erreur lors de la suppression de la stack")

    return {"message": "Stack supprimée avec succès"}