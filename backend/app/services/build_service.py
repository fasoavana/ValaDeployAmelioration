"""
Facade du service de build.
Expose les fonctions principales pour compatibilité avec le code existant.
"""

from .build import detect_project_type, generate_dockerfile, build_docker_image, ProjectType

__all__ = [
    'detect_project_type',
    'generate_dockerfile',
    'build_docker_image',
    'ProjectType'
]