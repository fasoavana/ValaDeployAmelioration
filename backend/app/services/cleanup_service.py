# app/services/cleanup_service.py
import logging
from app.core.docker_client import client
from app.core.config import settings

logger = logging.getLogger(__name__)

def cleanup_project_resources(slug: str, container_ids: list = None):
    """
    Nettoie proprement les ressources Docker associées à un projet/stack.
    Supprime : conteneurs, volumes, images et réseaux liés au slug.
    PROTÈGE explicitement le réseau principal de la plateforme.
    """
    if not slug:
        logger.warning("Slug vide, impossible de nettoyer les ressources Docker.")
        return

    logger.info(f" Début du nettoyage Docker pour le projet: {slug}")

    # 1. Supprimer les conteneurs
    if container_ids:
        for c_id in container_ids:
            try:
                container = client.containers.get(c_id)
                container.remove(force=True)
                logger.info(f" Conteneur supprimé: {c_id}")
            except Exception as e:
                logger.warning(f" Conteneur {c_id} introuvable ou déjà supprimé: {e}")

    # 2. Supprimer les volumes (préfixe: slug-)
    for volume in client.volumes.list():
        if volume.name.startswith(f"{slug}-") or volume.name == slug:
            try:
                volume.remove(force=True)
                logger.info(f" Volume supprimé: {volume.name}")
            except Exception as e:
                logger.warning(f" Échec suppression volume {volume.name}: {e}")

    # 3. Supprimer les images (tag commence par slug- ou est exactement slug)
    for image in client.images.list():
        for tag in image.tags:
            image_name = tag.split(":")[0]
            if image_name.startswith(f"{slug}-") or image_name == slug:
                try:
                    client.images.remove(tag, force=True)
                    logger.info(f" Image supprimée: {tag}")
                except Exception as e:
                    logger.warning(f" Échec suppression image {tag}: {e}")

    # 4. Supprimer le réseau spécifique au projet (avec protections)
    protected_networks = [
        "bridge", "host", "none", 
        settings.APP_NETWORK,       # Le réseau principal de ValaDeploy
        "traefik", "web",           # Réseaux classiques de routage
                                    # Protection explicite au cas où
    ]
    
    for network in client.networks.list():
        # Ignorer immédiatement les réseaux protégés
        if network.name in protected_networks:
            continue
            
        # Cibler uniquement les réseaux créés pour CE projet (nom exact ou préfixe slug-)
        if network.name == slug or network.name.startswith(f"{slug}-"):
            try:
                # Sécurité ultime : ne supprimer que si aucun conteneur n'est encore attaché
                if len(network.containers) == 0:
                    network.remove()
                    logger.info(f" Réseau supprimé: {network.name}")
                else:
                    logger.info(f"ℹ Réseau {network.name} conservé : encore utilisé par d'autres conteneurs.")
            except Exception as e:
                logger.warning(f" Échec suppression réseau {network.name}: {e}")
                
    logger.info(f" Nettoyage Docker terminé pour: {slug}")