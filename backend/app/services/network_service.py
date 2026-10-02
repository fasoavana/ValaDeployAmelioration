from __future__ import annotations

import docker

from app.core.config import settings
from app.core.docker_client import client


PRIVATE_NETWORK_PREFIX = "net-"
INGRESS_NETWORK_PREFIX = "ingress-"

MANAGED_LABEL = "io.valadeploy.managed"
PROJECT_LABEL = "io.valadeploy.project"
ROLE_LABEL = "io.valadeploy.network-role"


def get_private_network_name(project_slug: str) -> str:
    """
    Retourne le nom du réseau privé d'un projet.
    """
    return f"{PRIVATE_NETWORK_PREFIX}{project_slug}"


def get_ingress_network_name(project_slug: str) -> str:
    """
    Retourne le nom du réseau d'exposition d'un projet.
    """
    return f"{INGRESS_NETWORK_PREFIX}{project_slug}"


def _ensure_bridge_network(
    network_name: str,
    *,
    project_slug: str,
    role: str,
) -> str:
    """
    Retourne un réseau bridge existant ou le crée.
    """
    try:
        network = client.networks.get(network_name)

        if network.attrs.get("Driver") != "bridge":
            raise RuntimeError(
                f"Le réseau {network_name} existe mais n'utilise pas "
                f"le driver bridge."
            )

        return network_name

    except docker.errors.NotFound:
        client.networks.create(
            network_name,
            driver="bridge",
            labels={
                MANAGED_LABEL: "true",
                PROJECT_LABEL: project_slug,
                ROLE_LABEL: role,
            },
        )

        return network_name


def ensure_private_network(project_slug: str) -> str:
    """
    Crée ou récupère le réseau privé du projet.

    Exemple :
        net-shop
    """
    return _ensure_bridge_network(
        get_private_network_name(project_slug),
        project_slug=project_slug,
        role="private",
    )


def _get_valadeploy_traefik_container():
    """
    Retrouve le conteneur Traefik de cette instance ValaDeploy.
    """
    candidates = client.containers.list(
        all=True,
        filters={
            "label": "com.docker.compose.service=traefik",
        },
    )

    matching = []

    for container in candidates:
        container.reload()

        networks = (
            container.attrs
            .get("NetworkSettings", {})
            .get("Networks", {})
        )

        if settings.APP_NETWORK in networks:
            matching.append(container)

    if len(matching) != 1:
        raise RuntimeError(
            "Impossible d'identifier de manière unique le conteneur "
            f"Traefik ValaDeploy : {len(matching)} candidat(s)."
        )

    return matching[0]


def ensure_traefik_connected(network_name: str) -> None:
    """
    Connecte Traefik au réseau ingress s'il n'y est pas déjà.
    """
    network = client.networks.get(network_name)
    traefik = _get_valadeploy_traefik_container()

    traefik.reload()

    current_networks = (
        traefik.attrs
        .get("NetworkSettings", {})
        .get("Networks", {})
    )

    if network_name not in current_networks:
        network.connect(traefik)


def ensure_ingress_network(project_slug: str) -> str:
    """
    Crée le réseau ingress du projet et y connecte Traefik.

    Exemple :
        ingress-shop
    """
    network_name = _ensure_bridge_network(
        get_ingress_network_name(project_slug),
        project_slug=project_slug,
        role="ingress",
    )

    ensure_traefik_connected(network_name)

    return network_name



def reconcile_traefik_ingress_networks() -> list[str]:
    """
    Rétablit les connexions entre Traefik et tous les réseaux
    ingress gérés par ValaDeploy.

    Cette fonction permet notamment de restaurer automatiquement
    les réseaux ingress après une recréation du conteneur Traefik.
    """
    traefik = _get_valadeploy_traefik_container()
    traefik.reload()

    current_networks = (
        traefik.attrs
        .get("NetworkSettings", {})
        .get("Networks", {})
    )

    connected = []

    for network in client.networks.list():
        labels = (network.attrs or {}).get("Labels") or {}

        if labels.get(MANAGED_LABEL) != "true":
            continue

        if labels.get(ROLE_LABEL) != "ingress":
            continue

        if network.name in current_networks:
            continue

        network.connect(traefik)
        current_networks[network.name] = {}
        connected.append(network.name)

    return connected
