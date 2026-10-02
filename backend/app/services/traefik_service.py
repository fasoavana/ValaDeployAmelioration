import re
from app.core.config import settings

def build_traefik_labels(
    project_name: str,
    internal_port: int,
    base_domain: str = settings.APP_DOMAIN,
    network_name: str | None = None,
) -> dict[str, str]:
    
    
    # Nom de domaine dynamique (ex: mon-projet.localhost)
    domain = f"{project_name}.{base_domain}"
    
    return {
        "traefik.enable": "true",
        "traefik.docker.network": network_name or settings.APP_NETWORK,
        
        # Le même unique_id lie la règle de route au service correspondant
        f"traefik.http.routers.{project_name}.rule": f"Host(`{domain}`)",
        f"traefik.http.services.{project_name}.loadbalancer.server.port": str(internal_port),
    }