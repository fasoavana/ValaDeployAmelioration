#app.services.build.generator
import logging
from pathlib import Path
from .detector import ProjectType

import shutil

# Chaque entrée : (nom du fichier dans templates/assets/, nom qu'il doit avoir
# une fois copié à la racine du contexte de build, pour matcher le COPY du Dockerfile)
REQUIRED_ASSETS = {
    ProjectType.REACT_VITE: [
        ("react_vite__nginx.conf.template", "nginx.conf.template"),
    ],
    ProjectType.LARAVEL: [
        ("laravel__docker-entrypoint.sh", "docker-entrypoint.sh"),
        ("laravel__nginx.conf.template", "nginx.conf.template"),
    ],
    ProjectType.LARAVEL_MONOLITH: [
        ("laravel_monolith__docker-entrypoint.sh", "docker-entrypoint.sh"),
    ],
    # NODEJS / PYTHON : pas d'assets, on omet simplement la clé
}

logger = logging.getLogger(__name__)
def generate_dockerfile(project_type: ProjectType, project_path: str) -> dict:
    """
    Génère un Dockerfile adapté au type de projet détecté.
    Args:
    project_type: Type de projet détecté
    project_path: Chemin vers le répertoire du projet
    
    Returns:
        dict: {"dockerfile_path": str}
        
    Raises:
        ValueError: Si le type est inconnu ou sans template
    """
    path = Path(project_path)

    if project_type == ProjectType.DOCKERFILE:
        dockerfile_path = path / "Dockerfile"
        logger.info(f"Utilisation du Dockerfile existant: {dockerfile_path}")
        return {"dockerfile_path": str(dockerfile_path)}

    if project_type == ProjectType.UNKNOWN:
        raise ValueError("Impossible de générer un Dockerfile : type de projet inconnu.")

    template_files = {
        ProjectType.REACT_VITE: 'react_vite.dockerfile',
        ProjectType.LARAVEL: 'laravel.dockerfile',
        ProjectType.LARAVEL_MONOLITH: 'laravel_monolith.dockerfile',
        ProjectType.NODEJS: 'node.dockerfile',
        ProjectType.PYTHON: 'python.dockerfile',
    }

    template_file_name = template_files.get(project_type)
    if not template_file_name:
        raise ValueError(f"Aucun template disponible pour le type : {project_type}")

    templates_dir = Path(__file__).parent.parent.parent / "templates"
    template_file_path = templates_dir / template_file_name

    if not template_file_path.is_file():
        raise ValueError(f"Template introuvable: {template_file_path}")

    with open(template_file_path, 'r', encoding='utf-8') as f:
        template_content = f.read()

    dockerfile_path = path / "Dockerfile"
    with open(dockerfile_path, 'w', encoding='utf-8') as f:
        f.write(template_content)

    logger.info(f"Dockerfile généré avec succès pour le type : {project_type.value}")

    # --- Copie des fichiers annexes requis par ce Dockerfile (nginx conf, entrypoint...) ---
    # Ces fichiers appartiennent à ValaDeploy (pas au repo utilisateur cloné) : ils doivent
    # être injectés dans le contexte de build, sinon les instructions COPY du Dockerfile
    # échouent puisque le repo cloné ne les contient jamais.
    assets_dir = templates_dir / "assets"
    for asset_name, target_name in REQUIRED_ASSETS.get(project_type, []):
        source = assets_dir / asset_name
        if not source.is_file():
            raise ValueError(f"Asset requis introuvable: {source}")
        shutil.copy2(source, path / target_name)
        logger.info(f"Asset copié: {asset_name} -> {target_name}")

    return {"dockerfile_path": str(dockerfile_path)}