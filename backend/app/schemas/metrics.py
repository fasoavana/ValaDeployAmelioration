from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class ContainerStats(BaseModel):
    """Stats pour un conteneur individuel"""
    container_id: str
    container_name: str
    cpu_percent: float = Field(..., description="Pourcentage d'utilisation CPU")
    memory_usage: int = Field(..., description="Mémoire utilisée en bytes")
    memory_limit: int = Field(..., description="Limite de mémoire en bytes")
    memory_percent: float = Field(..., description="Pourcentage d'utilisation mémoire")
    network_rx: int = Field(default=0, description="Octets reçus")
    network_tx: int = Field(default=0, description="Octets transmis")


class ProjectMetricsResponse(BaseModel):
    """Réponse agrégée pour les métriques d'un projet"""
    project_slug: str
    total_cpu_percent: float = Field(..., description="CPU total tous conteneurs")
    total_memory_usage: int = Field(..., description="Mémoire totale utilisée en bytes")
    total_memory_limit: int = Field(..., description="Limite mémoire totale en bytes")
    memory_usage_formatted: str = Field(..., description="Mémoire formatée (ex: '256MB / 1GB')")
    container_count: int = Field(..., description="Nombre de conteneurs actifs")
    containers: list[ContainerStats] = Field(default_factory=list)
    last_updated: datetime = Field(default_factory=datetime.utcnow)


class EnvVarItem(BaseModel):
    """Une variable d'environnement individuelle"""
    key: str
    value: str  # Sera masquée si sensible
    is_sensitive: bool = Field(default=False, description="Indique si la valeur est masquée")


class EnvVarsResponse(BaseModel):
    """Réponse pour les variables d'environnement"""
    project_slug: str
    variables: list[EnvVarItem]
    total_count: int