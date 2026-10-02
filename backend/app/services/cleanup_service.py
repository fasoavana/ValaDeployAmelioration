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

    # 4. Supprimer les réseaux propres au projet.
    #
    # Le réseau privé doit normalement être vide après suppression
    # des conteneurs. Le réseau ingress peut encore contenir Traefik :
    # dans ce cas on déconnecte uniquement Traefik avant suppression.
    protected_networks = {
        "bridge",
        "host",
        "none",
        settings.APP_NETWORK,
        "traefik",
        "web",
    }

    project_networks = {
        f"net-{slug}",
        f"ingress-{slug}",
    }

    for network in client.networks.list():
        if network.name in protected_networks:
            continue

        if network.name not in project_networks:
            continue

        try:
            network.reload()

            if network.name == f"ingress-{slug}":
                for container in list(network.containers):
                    labels = container.attrs.get("Config", {}).get(
                        "Labels"
                    ) or {}

                    if (
                        labels.get("com.docker.compose.service")
                        == "traefik"
                    ):
                        network.disconnect(container, force=True)

                network.reload()

            if len(network.containers) == 0:
                network.remove()
                logger.info(
                    f" Réseau supprimé: {network.name}"
                )
            else:
                logger.info(
                    f" Réseau {network.name} conservé : "
                    "encore utilisé par des conteneurs."
                )

        except Exception as e:
            logger.warning(
                f" Échec suppression réseau {network.name}: {e}"
            )

    logger.info(f" Nettoyage Docker terminé pour: {slug}")