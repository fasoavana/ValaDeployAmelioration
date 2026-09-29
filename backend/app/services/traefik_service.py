import re
from app.core.config import settings

def build_traefik_labels(
    project_name: str,      # unique identifier for the project (slug)
    internal_port: int,   # Ex: 8000
    base_domain: str = settings.APP_DOMAIN  # Ex: "localhost"
) -> dict[str, str]:
    
    
    # Nom de domaine dynamique (ex: mon-projet.localhost)
    domain = f"{project_name}.{base_domain}"
    
    return {
        "traefik.enable": "true",
        "traefik.docker.network": settings.APP_NETWORK,
        
        # Le même unique_id lie la règle de route au service correspondant
        f"traefik.http.routers.{project_name}.rule": f"Host(`{domain}`)",
        f"traefik.http.services.{project_name}.loadbalancer.server.port": str(internal_port),
    }