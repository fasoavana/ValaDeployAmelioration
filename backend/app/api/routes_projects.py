from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.services.project_service import ProjectService
from app.core.docker_client import client
from fastapi import Query
from app.models.project import ProjectComponent, ProjectStatus 
import logging
from app.schemas.deploy import CloneSchema
from app.services.cleanup_service import cleanup_project_resources
from app.services.container_service import ensure_project_network, manage_container_state, run_container
from app.services.deploy_service import DeployService 

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

    container_ids_to_manage = []
    new_status = ProjectStatus.RUNNING if action in ['start', 'restart'] else ProjectStatus.STOPPED

    # 2. Déterminer quels conteneurs toucher (Multi-composant vs Mono)
    if component_id:
        component = db.query(ProjectComponent).filter(
            ProjectComponent.id == component_id,
            ProjectComponent.project_id == project.id
        ).first()
        
        if not component or not component.container_ids:
            raise HTTPException(status_code=404, detail="Composant ou conteneurs introuvables pour cet ID.")
        
        container_ids_to_manage = component.container_ids
        component.status = new_status # Mise à jour du statut en BDD
    else:
        if not project.container_ids:
            raise HTTPException(status_code=404, detail="Aucun conteneur associé à ce projet.")
        
        container_ids_to_manage = project.container_ids
        project.status = new_status # Mise à jour du statut en BDD

    new_container_ids = []
    
    # On s'assure que le réseau interne existe
    network_name = ensure_project_network(slug) 
    
    # Fonction helper pour trouver le réseau Traefik automatiquement
    def find_traefik_network():
        for net in client.networks.list():
            if "traefik" in net.name.lower() or net.name == "web":
                return net.name
        return None
    
    #3. Exécuter l'action sur chaque conteneur
    for c_id in container_ids_to_manage:
        try:
            # Tentative normale (Start/Stop/Restart)
            manage_container_state(c_id, action, slug)
            new_container_ids.append(c_id)
            
        except Exception as e:
            error_msg = str(e)
            # DÉTECTION DU BUG RÉSEAU FANTÔME
            if "network" in error_msg.lower() and "not found" in error_msg.lower():
                logger.warning(f"Réseau fantôme détecté pour {c_id}. Recréation automatique du conteneur...")
                try:
                    broken_container = client.containers.get(c_id)
                    
                    # 1. Récupérer les infos vitales du conteneur cassé
                    image_name = broken_container.image.tags[0] if broken_container.image.tags else broken_container.image.short_id
                    container_name = broken_container.name
                    
                    # 2. Supprimer le conteneur cassé
                    broken_container.remove(force=True)
                    
                    # 3. Préparer les paramètres pour la recréation
                    envs = component.env_vars if component_id else project.env_vars
                    port = component.port if component_id else None
                    
                    # Trouver le réseau Traefik pour que le conteneur soit bien exposé
                    traefik_net = find_traefik_network()
                    extra_nets = [traefik_net] if (traefik_net and port) else []

                    # 4. Recréer le conteneur proprement via run_container
                    new_id = run_container(
                        image_name=image_name,
                        slug=container_name, # On garde le même nom (ex: mytest8-back-1)
                        network=network_name,
                        plain_envs_var=envs, # Les vars sont déjà en clair dans la BDD
                        expose_traefik=True if port else False,
                        port=port,
                        extra_networks=extra_nets
                    )
                    
                    new_container_ids.append(new_id)
                    logger.info(f"Conteneur recréé avec succès: {new_id}")
                    
                except Exception as recreate_error:
                    logger.exception("Erreur lors de la recréation du conteneur")
                    raise HTTPException(status_code=500, detail=f"Échec de la recréation du conteneur cassé: {str(recreate_error)}")
            else:
                # Autre erreur inconnue, on la remonte
                raise HTTPException(status_code=500, detail=f"Erreur sur le conteneur {c_id}: {error_msg}")

    # 4. Mettre à jour les IDs en BDD (car l'ID a changé après recréation !)
    if component_id:
        component.container_ids = new_container_ids
    else:
        project.container_ids = new_container_ids
        
    db.commit()

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
    if project.status != ProjectStatus.BUILDING:
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
        raise HTTPException(status_code=404, detail=str(e))
    
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
                "expose_publicly": c.port is not None,
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