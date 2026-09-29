import json
import logging
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)

class ProjectType(str, Enum):
    """Types de projets supportés."""
    DOCKERFILE = "dockerfile"
    REACT_VITE = "react_vite"
    LARAVEL = "laravel"
    LARAVEL_MONOLITH = "laravel_monolith"
    NODEJS = "nodejs"
    PYTHON = "python"
    UNKNOWN = "unknown"
    
def detect_project_type(project_path: str) -> ProjectType:
    """
    Détecte le type de projet
Args:
    project_path: Chemin vers le répertoire du projet
    
Returns:
    ProjectType: Le type de projet détecté
"""

    path = Path(project_path)

    # 1. Si un Dockerfile existe déjà, on l'utilise directement
    if (path / "Dockerfile").is_file():
        logger.info("Dockerfile existant détecté")
        return ProjectType.DOCKERFILE

    # 2. Détection Laravel (via composer.json)
    composer_path = path / "composer.json"
    if composer_path.is_file():
        try:
            with open(composer_path, 'r', encoding='utf-8') as f:
                composer_data = json.load(f)
                deps = {
                    **composer_data.get('require', {}),
                    **composer_data.get('require-dev', {})
                }
                
                if 'laravel/framework' in deps:
                    logger.info("Laravel détecté")
                    
                    # Vérifier s'il y a aussi un build frontend (Vite/Mix)
                    pkg_path = path / "package.json"
                    if pkg_path.is_file():
                        with open(pkg_path, 'r', encoding='utf-8') as pf:
                            pkg_data = json.load(pf)
                            pkg_deps = {
                                **pkg_data.get('dependencies', {}),
                                **pkg_data.get('devDependencies', {})
                            }
                            if any(dep in pkg_deps for dep in ['vite', 'laravel-vite-plugin', 'laravel-mix']):
                                logger.info("Laravel monolithe détecté (avec assets frontend)")
                                return ProjectType.LARAVEL_MONOLITH
                    
                    return ProjectType.LARAVEL
        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"Erreur lecture composer.json: {e}")
        return ProjectType.PYTHON  # Fallback PHP

    # 3. Détection Node.js / React (via package.json)
    pkg_path = path / "package.json"
    if pkg_path.is_file():
        try:
            with open(pkg_path, 'r', encoding='utf-8') as f:
                pkg_data = json.load(f)
                deps = {
                    **pkg_data.get('dependencies', {}),
                    **pkg_data.get('devDependencies', {})
                }
                
                # Détection React + Vite
                if 'vite' in deps and 'react' in deps:
                    logger.info("React + Vite détecté")
                    return ProjectType.REACT_VITE
                
                # Détection Next.js
                if 'next' in deps:
                    logger.info("Next.js détecté (traité comme Node.js pour l'instant)")
                    return ProjectType.NODEJS
                
                # Node.js générique
                logger.info("Node.js détecté")
                return ProjectType.NODEJS
                
        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"Erreur lecture package.json: {e}")
        return ProjectType.NODEJS  # Fallback

    # 4. Détection Python
    if any((path / f).is_file() for f in ["requirements.txt", "Pipfile", "pyproject.toml"]):
        logger.info("Projet Python détecté")
        return ProjectType.PYTHON

    logger.warning("Type de projet inconnu")
    return ProjectType.UNKNOWN