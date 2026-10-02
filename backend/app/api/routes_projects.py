#app/api/routes_projects.py
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.services.project_service import ProjectService
from app.core.docker_client import client
from fastapi import Query
from app.models.project import ProjectComponent, ProjectStatus, ComponentKind, FailReason
import logging
from app.schemas.deploy import CloneSchema
from app.services.cleanup_service import cleanup_project_resources
from app.services.container_service import (
    manage_container_state,
    recreate_container,
    requires_network_migration,
)
from app.services.deploy_service import DeployService 
from app.services.container_service import get_real_containers_status 



router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/projects")
def list_projects(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Récupère tous les projets de l'utilisateur connecté.
    """
    projects = ProjectService.get_user_projects(db, current_user.id)
    
    return [
        {
            "id": p.id,
            "slug": p.slug,
            "repo_url": p.repo_url,
            "branch": p.branch,
            "replica": p.replica,
            "status": p.status,
            "commit_hash": p.commit_hash,
            "created_at": p.created_at.isoformat() if p.created_at else None,
            "updated_at": p.updated_at.isoformat() if p.updated_at else None
        }
        for p in projects
    ]

@router.get("/projects/dashboard/stats")
def get_dashboard_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Statistiques agrégées pour le dashboard (total, running, failed,
    pourcentage d'échecs dus à des vulnérabilités critiques).
    """
    return ProjectService.get_dashboard_stats(db, current_user.id)

@router.post("/projects/{slug}/action")
def project_action(
    slug: str,
    action: str = Query(..., description="start, stop, ou restart"),
    component_id: int = Query(None, description="ID du composant pour les stacks multi-services"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if action not in ['start', 'stop', 'restart']:
        raise HTTPException(status_code=400, 
                            detail="Action invalide. Utilisez 'start', 'stop' ou 'restart'.")

    # 1. Vérifier le projet et l'autorisation
    project = ProjectService.get_project_by_slug(db, slug)
    if not project or project.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Projet introuvable ou non autorisé.")

    target = project
    if component_id:
        target = db.query(ProjectComponent).filter(
            ProjectComponent.id == component_id,
            ProjectComponent.project_id == project.id,
        ).first()
    if not target or not target.container_ids:
        raise HTTPException(status_code=404, detail="Aucun conteneur associé à cette cible.")
    if project.status in (ProjectStatus.BUILDING, ProjectStatus.PENDING_SECURITY_CONFIRMATION):
        raise HTTPException(status_code=409, detail="Un déploiement est en cours.")
    # Ne pas contourner un scan refusé en redémarrant une ancienne ressource.
    if action != "stop" and (project.status == ProjectStatus.FAILED or target.status == ProjectStatus.FAILED):
        raise HTTPException(status_code=409, detail="Déploiement en échec : utilisez Retry pour relancer le pipeline complet.")

    was_failed = target.status == ProjectStatus.FAILED or project.status == ProjectStatus.FAILED
    ids = list(target.container_ids)
    for index, container_id in enumerate(ids):
        try:
            is_database = bool(
                component_id
                and target.kind == ComponentKind.DATABASE
            )

            # Un ancien conteneur utilisant encore l'architecture réseau
            # globale doit être recréé afin de mettre à jour à la fois
            # ses réseaux ET ses labels Traefik.
            if (
                action != "stop"
                and requires_network_migration(
                    container_id,
                    slug,
                    is_database=is_database,
                )
            ):
                ids[index] = recreate_container(
                    container_id,
                    slug,
                    target.port,
                    is_database=is_database,
                )

            else:
                try:
                    manage_container_state(
                        container_id,
                        action,
                        slug,
                    )
                except Exception as exc:
                    # Compatibilité : si un réseau Docker référencé a été
                    # supprimé, recréer proprement le conteneur.
                    message = str(exc).lower()

                    if (
                        action == "stop"
                        or "network" not in message
                        or "not found" not in message
                    ):
                        raise

                    ids[index] = recreate_container(
                        container_id,
                        slug,
                        target.port,
                        is_database=is_database,
                    )

            # Persister chaque remplacement, même si le réplica suivant échoue.
            target.container_ids = list(ids)
            db.commit()
        except Exception as exc:
            partial_ids = getattr(exc, "container_ids", [])
            if partial_ids:
                ids[index:index + 1] = partial_ids
            target.container_ids = ids
            target.status = ProjectStatus.FAILED
            target.error_message = str(exc)
            target.fail_reason = FailReason.DEPLOY_ERROR
            project.status = ProjectStatus.FAILED
            project.error_message = str(exc)
            db.commit()
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    target.status = ProjectStatus.STOPPED if action == "stop" else ProjectStatus.RUNNING
    # Une action sur des ressources partielles ne transforme pas un échec de
    # pipeline en succès. Un Retry réussi est nécessaire pour cela.
    if was_failed:
        target.status = ProjectStatus.FAILED
    if component_id and project.status != ProjectStatus.FAILED:
        project.status = ProjectService.aggregate_component_status(project.services)
    db.commit()
    return {"message": f"Action '{action}' terminée.", "status": target.status.value}

# =============== pipeline endpoints ===============

@router.get("/deploy/{project_id}/pipeline")
async def get_pipeline_status(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    project = ProjectService.get_project_by_id(db, project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=404, detail="Projet introuvable")

    # Mapping des statuts BDD vers le format attendu par le frontend
    status_map = {
        ProjectStatus.BUILDING: "running",
        ProjectStatus.RUNNING: "success",
        ProjectStatus.FAILED: "failed",
        ProjectStatus.STOPPED: "cancelled"
    }
    global_status = status_map.get(project.status, "running")
    cancelled = project.status == ProjectStatus.STOPPED

    steps = []

    # 1. Étape Clone
    if cancelled:
        clone_status = "completed" if project.commit_hash else "cancelled"
    else:
        clone_status = "completed" if project.commit_hash else ("active" if project.status == ProjectStatus.BUILDING else "pending")
    steps.append({
        "label": "Clone Repository",
        "description": f"Récupération de la branche {project.branch}",
        "status": clone_status,
        "duration_seconds": 3 if clone_status == "completed" else None
    })

    # 2. Étape Build
    if cancelled:
        # Si le clone n'a même pas terminé, le build n'a pas commencé -> pending.
        # Sinon on ne peut pas garantir qu'il ait terminé -> cancelled (jamais "completed",
        # ce serait trompeur pour un build interrompu).
        build_status = "cancelled" if clone_status == "completed" else "pending"
    else:
        build_status = "pending"
        if project.status in [ProjectStatus.RUNNING, ProjectStatus.FAILED]:
            build_status = "completed"
        elif project.status == ProjectStatus.BUILDING and project.commit_hash:
            build_status = "active"
    steps.append({
        "label": "Build Docker Image",
        "description": "Génération du Dockerfile et construction",
        "status": build_status,
        "duration_seconds": 12 if build_status == "completed" else None
    })

    # 3. Étape Security Scan
    if cancelled:
        scan_status = "cancelled" if build_status == "cancelled" else "pending"
    else:
        scan_status = "pending"
        if project.status in [ProjectStatus.RUNNING, ProjectStatus.FAILED]:
            scan_status = "completed"
        elif project.status == ProjectStatus.BUILDING and build_status == "completed":
            scan_status = "active"
    steps.append({
        "label": "Security Scan",
        "description": "Analyse Trivy (vulnérabilités) et Gitleaks (secrets)",
        "status": scan_status,
        "duration_seconds": 8 if scan_status == "completed" else None
    })

    # 4. Étape Deploy
    if cancelled:
        deploy_status = "cancelled" if scan_status == "cancelled" else "pending"
    else:
        deploy_status = "pending"
        if project.status == ProjectStatus.RUNNING:
            deploy_status = "completed"
        elif project.status == ProjectStatus.FAILED:
            deploy_status = "failed"
        elif project.status == ProjectStatus.BUILDING and scan_status == "completed":
            deploy_status = "active"
    steps.append({
        "label": "Deploy to Traefik",
        "description": "Démarrage des conteneurs et configuration du routage",
        "status": deploy_status,
        "duration_seconds": 5 if deploy_status == "completed" else None
    })

    # Si c'est une stack, on détaille en plus les composants dans le pipeline
    components = ProjectService.get_components_by_project(db, project_id)
    if len(components) > 0:
        comp_status_map = {
            ProjectStatus.BUILDING: "active",
            ProjectStatus.RUNNING: "completed",
            ProjectStatus.FAILED: "failed",
            ProjectStatus.STOPPED: "cancelled"
        }
        for comp in components:
            steps.append({
                "label": f"Composant: {comp.name} ({comp.kind.value})",
                "description": comp.error_message or f"Statut: {comp.status.value}",
                "status": comp_status_map.get(comp.status, "pending"),
                "duration_seconds": None
            })

    # Logs (version simplifiée déduite de l'état, sera connectée aux vrais logs plus tard)
    logs = [f"[INFO] Pipeline initialized for project '{project.slug}'"]
    if project.commit_hash:
        logs.append(f"[INFO] Successfully cloned commit {project.commit_hash[:7]}")
    if project.status == ProjectStatus.RUNNING:
        logs.append("[INFO] Docker build completed successfully")
        logs.append("[INFO] Security scan passed")
        logs.append("[INFO] Containers started and attached to Traefik network")
    elif project.status == ProjectStatus.FAILED:
        logs.append(f"[ERROR] Pipeline failed: {project.error_message or 'Unknown error'}")
    elif project.status == ProjectStatus.STOPPED:
        logs.append("[INFO] Pipeline annulé par l'utilisateur")
    else:
        logs.append("[INFO] Pipeline in progress...")

    # Construction de l'URL live (fallback intelligent)
    live_url = None
    if project.status == ProjectStatus.RUNNING:
        port = 8080 # Fallback par défaut
        if len(components) > 0:
            for c in components:
                if c.port:
                    port = c.port
                    break
        live_url = f"http://{project.slug}.localhost:{port}"

    return {
        "status": global_status,
        "project": {
            "slug": project.slug,
            "environment": "local", 
            "commit_sha": project.commit_hash,
            "live_url": live_url
        },
        "steps": steps,
        "logs": logs
    }
    
@router.post("/deploy/{project_id}/cancel")
async def cancel_build(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    project = ProjectService.get_project_by_id(db, project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=404, detail="Projet introuvable")
    
    # Si ce n'est plus en cours de build, on ne fait rien (évite les erreurs si on clique 2 fois)
    if project.status not in (ProjectStatus.BUILDING, ProjectStatus.PENDING_SECURITY_CONFIRMATION):
        return {"message": "Le build n'est plus en cours."}
    
    # 1. Marquer le projet comme STOPPED
    project.status = ProjectStatus.STOPPED
    project.error_message = "Build annulé par l'utilisateur"
    
    # 2. Marquer les composants en cours comme STOPPED
    components = ProjectService.get_components_by_project(db, project_id)
    for comp in components:
        if comp.status == ProjectStatus.BUILDING:
            comp.status = ProjectStatus.STOPPED
            comp.error_message = "Build annulé par l'utilisateur"
            
    # 3.  COMMIT IMMÉDIAT ET OBLIGATOIRE
    db.commit()
    
    return {"message": "Annulation demandée. Le pipeline va s'arrêter."}

@router.post("/deploy/{project_id}/retry")
async def retry_build(
    project_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        project, is_stack, components, run_id = DeployService.retry_deployment(db, project_id, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    
    # Lancer le bon pipeline en background
    if is_stack:
        pipeline_components = [
            {
                "component_id": c.id,
                "name": c.name,
                "kind": c.kind,
                "repo_url": c.repo_url,
                "branch": c.branch,
                "replica": c.replica or 1,
                "envs_var": c.env_vars or {},
                "db_image": c.db_image,
                "volume_name": c.volume_name,
                "expose_publicly": c.expose_publicly,
                "port": c.port,
            }
            for c in components
        ]
        # AJOUT : user_id et run_id pour l'historique et la gestion des threads zombies
        background_tasks.add_task(
            run_in_threadpool,
            DeployService.run_stack_deployment_pipeline,
            project.id,
            project.slug,
            pipeline_components,
            user_id=current_user.id,
            run_id=run_id,
        )
    else:
        payload = CloneSchema(
            slug=project.slug,
            repo_url=project.repo_url,
            branch=project.branch,
            replica=project.replica or 1,
            envs_var=project.env_vars or {},
            port=project.port
        )
        # AJOUT : user_id et run_id pour l'historique et la gestion des threads zombies
        background_tasks.add_task(
            run_in_threadpool,
            DeployService.run_deployment_pipeline,
            project.id,
            payload,
            user_id=current_user.id,
            run_id=run_id,
        )
    
    return {"message": "Build relancé avec succès"}

@router.delete("/projects/{project_id}")
def delete_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Supprime un projet mono-service (ou une stack, la logique est générique)
    et nettoie ses ressources Docker associées.
    """
    project = ProjectService.get_project_by_id(db, project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=404, detail="Projet introuvable ou non autorisé.")

    success = ProjectService.delete_project_and_containers(db, project_id, current_user.id)
    if not success:
        raise HTTPException(status_code=500, detail="Échec de la suppression du projet.")

    return {"message": "Projet supprimé avec succès."}


@router.get("/projects/{slug}/real-status")
def get_real_container_status(
    slug: str,
    component_id: int = Query(None, description="ID du composant pour les stacks multi-services"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Vérifie l'état RÉEL des conteneurs Docker via le service et synchronise la BDD si nécessaire.
    """
    # 1. Vérification des droits
    project = ProjectService.get_project_by_slug(db, slug)
    if not project or project.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Projet introuvable ou non autorisé.")

    # 2. Récupération des IDs et du statut actuel en BDD
    if component_id:
        component = db.query(ProjectComponent).filter(
            ProjectComponent.id == component_id,
            ProjectComponent.project_id == project.id
        ).first()
        if not component:
            raise HTTPException(status_code=404, detail="Composant introuvable.")
        
        container_ids_to_check = component.container_ids or []
        db_status = component.status
        is_component = True
    else:
        container_ids_to_check = project.container_ids or []
        db_status = project.status
        is_component = False

    protected = {ProjectStatus.BUILDING, ProjectStatus.PENDING_SECURITY_CONFIRMATION, ProjectStatus.FAILED}
    if db_status in protected:
        return {"status": db_status.value}
    try:
        if not is_component and project.services:
            for comp in project.services:
                if comp.status not in protected:
                    comp.status = get_real_containers_status(comp.container_ids or [])
            real_status = ProjectService.aggregate_component_status(project.services)
        else:
            real_status = get_real_containers_status(container_ids_to_check)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Impossible de vérifier l'état Docker ; statut conservé.") from exc
    if is_component:
        component.status = real_status
        if project.status not in protected:
            project.status = ProjectService.aggregate_component_status(project.services)
    else:
        project.status = real_status
    db.commit()
    return {"status": real_status.value}
