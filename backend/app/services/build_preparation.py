# app/services/build_preparation.py
import logging
from pathlib import Path
from typing import Dict, Any, Union
import re

# Assure-toi que l'import correspond à ton architecture
from app.services.build_service import ProjectType 

logger = logging.getLogger(__name__)

# Templates de .dockerignore par type de projet
# Note : On n'exclut PAS ".env" ici, car on veut que Docker le copie 
# pendant l'étape de build (pour que Vite/Laravel le lise), 
# mais il ne sera pas copié dans l'image finale grâce aux multi-stage builds.
DOCKERIGNORE_TEMPLATES = {
    ProjectType.REACT_VITE: """node_modules
dist
.env.local
.env.*.local
.git
.gitignore
README.md
.vscode
.idea
*.log
""",
    ProjectType.LARAVEL: """vendor
node_modules
storage/logs/*
storage/framework/cache/*
storage/framework/sessions/*
storage/framework/views/*
.git
.gitignore
README.md
tests
""",
    ProjectType.LARAVEL_MONOLITH: """vendor
node_modules
.git
.gitignore
README.md
tests
""",
    ProjectType.PYTHON: """__pycache__
*.pyc
*.pyo
*.pyd
.Python
.venv
venv
env/
.git
.gitignore
README.md
tests
.pytest_cache
""",
    ProjectType.NODEJS: """node_modules
.git
.gitignore
README.md
npm-debug.log
"""
}

def normalize_env_vars(env_vars_input: Union[Dict[str, str], list, None]) -> Dict[str, str]:
    """
    Normalise les variables d'environnement en dictionnaire {key: value}.
    Gère le cas où le frontend envoie une liste d'objets [{"key": "A", "value": "B"}] 
    ou directement un dictionnaire {"A": "B"}.
    """
    if not env_vars_input:
        return {}
    
    if isinstance(env_vars_input, dict):
        return {str(k): str(v) for k, v in env_vars_input.items()}
    
    if isinstance(env_vars_input, list):
        normalized = {}
        for item in env_vars_input:
            if isinstance(item, dict) and "key" in item and "value" in item:
                normalized[str(item["key"])] = str(item["value"])
        return normalized
        
    return {}


def _format_env_value(value: str) -> str:
    """
    Formate une valeur pour l'écriture dans un fichier .env, en l'entourant
    de guillemets doubles si elle contient des caractères qui casseraient
    un parser dotenv strict (espace, #, ", $, retour à la ligne).
    Les guillemets doubles internes sont échappés.
    """
    if value == "":
        return '""'

    needs_quoting = bool(re.search(r'[\s#"\'$\\]', value)) or "\n" in value

    if not needs_quoting:
        return value

    escaped = value.replace('\\', '\\\\').replace('"', '\\"')
    return f'"{escaped}"'


def prepare_build_environment(project_path: str, project_type: ProjectType, env_vars_input: Any) -> None:
    """
    Génère le .env et le .dockerignore dans le dossier de build avant le docker build.
    Args:
        project_path: Chemin vers le répertoire du projet cloné
        project_type: Type de projet détecté (ProjectType)
        env_vars_input: Variables d'environnement fournies par l'utilisateur
    """
    path = Path(project_path)
    # 1. Génération du .env temporaire
    env_vars = normalize_env_vars(env_vars_input)
    if env_vars:
        env_content = "\n".join(
            f"{key}={_format_env_value(value)}" for key, value in env_vars.items()
        )
        env_file = path / ".env"
        env_file.write_text(env_content, encoding="utf-8")
        logger.info(f"[PREP-BUILD] Fichier .env généré avec {len(env_vars)} variable(s) dans {project_path}")
    else:
        logger.info(f"[PREP-BUILD] Aucune variable d'environnement fournie, pas de .env généré.")

    # 2. Génération du .dockerignore
    ignore_content = DOCKERIGNORE_TEMPLATES.get(project_type, ".git\n.gitignore\n")
    dockerignore_file = path / ".dockerignore"
    dockerignore_file.write_text(ignore_content, encoding="utf-8")
    logger.info(f"[PREP-BUILD] Fichier .dockerignore généré pour le type {project_type.value}")