from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.services.metrics_service import get_project_metrics
from app.services.env_var_service import get_project_env_vars
from app.schemas.metrics import ProjectMetricsResponse, EnvVarsResponse, EnvVarItem
from app.models.project import Project

router = APIRouter()


@router.get("/projects/{slug}/metrics", response_model=ProjectMetricsResponse)
def get_project_metrics_endpoint(
    slug: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Récupère les métriques système (CPU, RAM) en temps réel pour un projet.
    Agrège les stats de tous les conteneurs du projet.
    """
    # Vérifier que le projet existe et appartient à l'utilisateur
    project = db.query(Project).filter(
        Project.slug == slug,
        Project.user_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(status_code=404, detail="Projet introuvable")
    
    # Récupérer les container_ids (projet mono ou multi-composants)
    container_ids = []
    
    if project.container_ids:
        container_ids.extend(project.container_ids)
    
    # Pour les stacks, ajouter les conteneurs des composants
    if hasattr(project, 'services') and project.services:
        for component in project.services:
            if component.container_ids:
                container_ids.extend(component.container_ids)
    
    # Obtenir les métriques
    metrics_data = get_project_metrics(slug, container_ids)
    
    return ProjectMetricsResponse(**metrics_data)


@router.get("/projects/{slug}/env-vars", response_model=EnvVarsResponse)
def get_project_env_vars_endpoint(
    slug: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Récupère les variables d'environnement d'un projet.
    Les valeurs sensibles sont automatiquement masquées.
    """
    env_data = get_project_env_vars(db, slug, current_user.id)
    
    if not env_data:
        raise HTTPException(status_code=404, detail="Projet introuvable")
    
    # Conversion explicite pour Pydantic v2
    variables = [EnvVarItem(**v) for v in env_data['variables']]
    
    return EnvVarsResponse(
        project_slug=env_data['project_slug'],
        variables=variables,
        total_count=env_data['total_count']
    )