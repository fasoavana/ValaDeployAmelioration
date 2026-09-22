#app.services.env_var_service
from sqlalchemy.orm import Session
from app.models.project import Project
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# Liste des clés sensibles à masquer automatiquement
SENSITIVE_KEYS = [
    'password', 'passwd', 'pwd', 'secret', 'token', 'api_key', 'apikey',
    'private_key', 'privatekey', 'auth', 'credential', 'cred'
]


def _is_sensitive_key(key: str) -> bool:
    """Vérifie si une clé de variable d'environnement est sensible"""
    key_lower = key.lower()
    return any(sensitive in key_lower for sensitive in SENSITIVE_KEYS)


def _mask_value(value: str) -> str:
    """Masque une valeur sensible (garde les 2-3 premiers et derniers caractères)"""
    if not value or len(value) < 8:
        return '*' * 12  # Masquage complet si trop court
    
    visible_start = value[:3]
    visible_end = value[-3:]
    masked_length = len(value) - 6
    return f"{visible_start}{'*' * masked_length}{visible_end}"


def get_project_env_vars(db: Session, project_slug: str, user_id: int) -> Optional[dict]:
    """
    Récupère les variables d'environnement d'un projet pour un utilisateur.
    Masque automatiquement les valeurs sensibles.
    """
    project = db.query(Project).filter(
        Project.slug == project_slug,
        Project.user_id == user_id
    ).first()
    
    if not project:
        return None
    
    env_vars = project.env_vars or {}
    
    variables = []
    for key, value in sorted(env_vars.items()):
        is_sensitive = _is_sensitive_key(key)
        displayed_value = _mask_value(value) if is_sensitive else value
        
        variables.append({
            'key': key,
            'value': displayed_value,
            'is_sensitive': is_sensitive
        })
    
    return {
        'project_slug': project_slug,
        'variables': variables,
        'total_count': len(variables)
    }