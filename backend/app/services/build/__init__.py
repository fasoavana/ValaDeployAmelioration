"""
Module de build : détection, génération et compilation Docker.
"""

from app.services.build.detector import detect_project_type, ProjectType
from app.services.build.generator import generate_dockerfile
from app.services.build.builder import build_docker_image

__all__ = [
    'detect_project_type',
    'ProjectType',
    'generate_dockerfile',
    'build_docker_image'
]