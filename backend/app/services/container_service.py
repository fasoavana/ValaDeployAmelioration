#app/services/container_service.py
from app.core.docker_client import client
from app.services.traefik_service import build_traefik_labels
import docker
from app.core.security import decrypt_data
from app.models.project import ProjectStatus 
from app.services.security_profile import SecurityProfile, STANDARD_PROFILE
import logging
import time
import re
import json
from pathlib import Path
from app.core.exceptions import DeployError
from app.core.image_reference import validate_image_reference
from app.core.config import settings
from app.services.security_profile import get_security_profile, get_runtime_port

logger = logging.getLogger(__name__)


def build_container_name(component_slug: str, replica_index: int = 1) -> str:
    """
    Nom de conteneur canonique pour un composant, à un index de replica donné.

    Source de vérité UNIQUE : utilisée par scale_project() pour nommer les
    conteneurs réellement créés, ET par les ComponentDeployer de stack
    (app/services/stack_deployment/) pour construire à l'avance les hostnames
    Traefik (VITE_API_URL, FRONTEND_URL...) avant même que le conteneur
    n'existe. Les deux doivent impérativement rester en phase — voir le point
    d'attention "nommage de conteneur dupliqué et fragile" du résumé de
    session précédent. Si scale_project change un jour sa convention de
    nommage (replicas, autre schéma), ne modifier QUE cette fonction.
    """
    return f"{component_slug}-{replica_index}"


class ContainerDeploymentError(DeployError):
    """Garde les IDs même si Docker échoue après la création."""
    def __init__(self, message, container_ids):
        super().__init__(message)
        self.container_ids = list(container_ids)


def verify_containers_running(container_ids, delay=3.0):
    """Fenêtre de stabilité courte, sans prétendre vérifier la disponibilité HTTP."""
    if not container_ids:
        raise ContainerDeploymentError("Aucun conteneur créé.", [])
    deadline = time.monotonic() + delay
    while True:
        for container_id in container_ids:
            try:
                container = client.containers.get(container_id)
                state = container.attrs.get("State", {})
            except docker.errors.NotFound:
                raise ContainerDeploymentError(
                    f"Conteneur {container_id} introuvable après création.", container_ids
                ) from None
            if container.status != "running":
                raise ContainerDeploymentError(
                    f"Conteneur {container.name} ({container_id[:12]}) arrêté : "
                    f"statut={container.status}, ExitCode={state.get('ExitCode', 'inconnu')}, "
                    f"OOMKilled={state.get('OOMKilled', False)}. "
                    "Conteneur conservé ; consulter ses logs Docker.", container_ids
                )
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return
        time.sleep(min(0.5, remaining))


def run_container(image_name: str, slug: str, network: str, envs_var: dict = None,
                  extra_networks: list = None, volumes: dict = None,
                  expose_traefik: bool = True, plain_envs_var: dict = None, port: int = None,
                  security_profile: SecurityProfile | None = STANDARD_PROFILE,
                  labels: dict = None, command=None, entrypoint=None, user=None,
                  working_dir=None, preserve_volumes=False) -> str:
    # Valider AVANT tout appel Docker ou remplacement du conteneur existant.
    validate_image_reference(image_name)
    if expose_traefik and port is None:
        raise ValueError(f"port est requis quand expose_traefik=True (conteneur: {slug})")

    container_labels = dict(labels or {})
    if expose_traefik:
        container_labels.update(build_traefik_labels(slug, internal_port=port))
    var_envs = {key: decrypt_data(value) for key, value in (envs_var or {}).items()}
    var_envs.update(plain_envs_var or {})
    security_kwargs = security_profile.docker_kwargs() if security_profile is not None else {}
    runtime_kwargs = {key: value for key, value in {
        "command": command, "entrypoint": entrypoint, "user": user,
        "working_dir": working_dir,
    }.items() if value is not None}
    try:
        existing = client.containers.get(slug)
        if preserve_volumes and volumes is None:
            volumes = {
                mount["Name"]: {"bind": mount["Destination"], "mode": "rw" if mount.get("RW") else "ro"}
                for mount in existing.attrs.get("Mounts", []) if mount["Type"] == "volume"
            }
        archive_container_evidence(existing)
        existing.remove(force=True)
    except docker.errors.NotFound:
        pass

    container = None
    try:
        # Séparer create/start permet de conserver l'ID si start() échoue.
        create_kwargs = dict(
            image=image_name, name=slug, network=network, environment=var_envs,
            labels=container_labels, volumes=volumes, detach=True,
            **security_kwargs, **runtime_kwargs,
        )
        try:
            container = client.containers.create(**create_kwargs)
        except docker.errors.ImageNotFound:
            # Comme containers.run(), télécharger une image externe absente.
            client.images.pull(image_name)
            container = client.containers.create(**create_kwargs)
        for net_name in extra_networks or []:
            if net_name != network:
                client.networks.get(net_name).connect(container)
        container.start()
        verify_containers_running([container.id])
        return container.id
    except ContainerDeploymentError:
        raise
    except Exception as exc:
        ids = [container.id] if container is not None else []
        raise ContainerDeploymentError(
            f"Échec de création/démarrage de {slug} : {exc}. "
            f"Ressources conservées : {', '.join(ids) or 'aucun conteneur créé'}", ids
        ) from exc


def recreate_container(container_id, project_slug, configured_port, is_database=False):
    """Répare un réseau absent sans deviner un runtime ou perdre les volumes."""
    old = client.containers.get(container_id)
    config = old.attrs["Config"]
    labels = dict(config.get("Labels") or {})
    runtime_type = (old.image.attrs.get("Config", {}).get("Labels") or {}).get("io.valadeploy.runtime-type")
    if not is_database and (not runtime_type or runtime_type == "unknown"):
        raise ValueError("Ancienne image sans métadonnées runtime : utilisez Retry pour reconstruire avec le template actuel.")
    port = None if is_database else get_runtime_port(runtime_type, configured_port)
    expose = not is_database and labels.get("traefik.enable") == "true"
    networks = list(old.attrs.get("NetworkSettings", {}).get("Networks", {}))
    project_network = f"net-{project_slug}"
    if project_network in networks:
        network = ensure_project_network(project_slug)
    elif settings.APP_NETWORK in networks:
        network = settings.APP_NETWORK
    else:
        raise ValueError("Réseau principal indéterminé ; utilisez Retry.")
    # Les réseaux tiers manquants ne sont pas recréés arbitrairement.
    extra = [name for name in networks if name != network]
    for name in [network, *extra]:
        client.networks.get(name)
    volumes = {}
    for mount in old.attrs.get("Mounts", []):
        if mount["Type"] in ("volume", "bind"):
            source = mount.get("Name") if mount["Type"] == "volume" else mount["Source"]
            volumes[source] = {"bind": mount["Destination"], "mode": "rw" if mount.get("RW") else "ro"}
    envs = dict(item.split("=", 1) for item in config.get("Env", []) if "=" in item)
    return run_container(
        image_name=old.image.id, slug=old.name, network=network,
        extra_networks=extra, volumes=volumes, plain_envs_var=envs,
        expose_traefik=expose, port=port, labels=labels,
        security_profile=None if is_database else get_security_profile(runtime_type),
        command=config.get("Cmd"), entrypoint=config.get("Entrypoint"),
        user=config.get("User"), working_dir=config.get("WorkingDir"),
    )


def scale_project(image_name: str, slug: str, network: str, desired_replicas: int,
                   envs_var: dict = None, extra_networks: list = None,
                   plain_envs_var: dict = None, port: int = None, expose_traefik: bool = True,
                   security_profile: SecurityProfile | None = STANDARD_PROFILE) -> list:
    """
    Scale the number of running containers for a project.

    Args:
        image_name (str): The name of the Docker image to run.
        slug (str): A unique identifier for the container.
        network (str): The name of the Docker network to connect the container to.
        desired_replicas (int): The desired number of replicas to run.
        envs_var (dict, optional): A dictionary of environment variables to set in the container.
                                   The values should be encrypted and will be decrypted before being passed to the container.
        extra_networks (list, optional): réseaux additionnels, transmis tel quel à run_container.
        plain_envs_var (dict, optional): variables déjà en clair, non chiffrées (ex: DATABASE_URL
                                          généré automatiquement par ValaDeploy). None par défaut
                                          = comportement inchangé.

    Returns:
        list: A list of IDs of the running containers after scaling.
    """
    validate_image_reference(image_name)
    if desired_replicas < 1:
        raise ValueError("Au moins un réplica est requis.")
    # Get all containers with names starting with the slug
    existing_containers = client.containers.list(all=True, filters={"name": f"{slug}-"})
    # Extract the replica numbers from existing container names
    existing_numbers = []
    for container in existing_containers:
        if not re.fullmatch(re.escape(slug) + r"-[1-9][0-9]*", container.name):
            continue
        try:
            number = int(container.name.rsplit('-', 1)[-1])
            existing_numbers.append((number, container))
        except ValueError:
            continue  # Skip if the name does not end with a number

    # Sort existing containers by their replica number in descending order
    existing_numbers.sort(key=lambda x: x[0], reverse=True)

    # Stop and remove excess containers if desired_replicas is less than current count
    if desired_replicas < len(existing_numbers):
        to_remove_count = len(existing_numbers) - desired_replicas
        # Prend les 'to_remove_count' premiers éléments (index 0 à to_remove_count - 1)
        for _, container_to_remove in existing_numbers[:to_remove_count]:
            if container_to_remove.status == 'running':
                container_to_remove.stop()
            container_to_remove.remove(force=True)

    # Start or restart containers up to desired_replicas
    running_container_ids = []
    for i in range(1, desired_replicas + 1):
        container_name = build_container_name(slug, i)
        try:
            new_container_id = run_container(
                image_name, container_name, network, envs_var, extra_networks,
                plain_envs_var=plain_envs_var, port=port,
                expose_traefik=expose_traefik, security_profile=security_profile,
            )
            running_container_ids.append(new_container_id)
        except Exception as exc:
            ids = running_container_ids + getattr(exc, "container_ids", [])
            raise ContainerDeploymentError(str(exc), ids) from exc
    try:
        verify_containers_running(running_container_ids, delay=0)
    except Exception as exc:
        raise ContainerDeploymentError(str(exc), running_container_ids) from exc
    return running_container_ids


def ensure_project_network(slug: str) -> str:
    """
    NOUVEAU — Crée un réseau Docker dédié à un projet s'il n'existe pas déjà,
    et retourne son nom. Idempotent : si le réseau existe déjà, ne fait rien
    et retourne juste le nom.

    Ce réseau sert de réseau INTERNE au projet : tous les services d'une même
    stack (front/back/db) y sont connectés pour se joindre par nom de conteneur,
    sans être exposés à l'extérieur (contrairement au réseau Traefik).

    Args:
        slug (str): le slug du projet (ex: "myapp")

    Returns:
        str: le nom du réseau créé (ex: "net-myapp")
    """
    network_name = f"net-{slug}"
    try:
        client.networks.get(network_name)  # déjà existant, rien à faire
    except docker.errors.NotFound:
        client.networks.create(network_name, driver="bridge")
    return network_name


def manage_container_state(container_id: str, action: str, project_slug: str) -> str:
    """
    Démarre, arrête ou redémarre un conteneur par son ID.
    Résout le problème 'network not found' en s'assurant que le réseau
    du projet existe avant toute tentative de démarrage.
    """
    try:
        container = client.containers.get(container_id)
    except docker.errors.NotFound:
        raise ValueError(f"Conteneur {container_id} introuvable dans Docker.")

    # LA CLÉ : On s'assure que le réseau interne du projet existe avant start/restart
    if action in ['start', 'restart']:
        ensure_project_network(project_slug)

    if action == 'start':
        container.start()
    elif action == 'stop':
        container.stop()
    elif action == 'restart':
        container.restart()
    else:
        raise ValueError(f"Action '{action}' non supportée.")

    if action in ['start', 'restart']:
        verify_containers_running([container.id])
    return container.id

def get_real_containers_status(container_ids: list) -> ProjectStatus:
    """RUNNING seulement si tous les IDs sont présents et actifs."""
    if not container_ids:
        return ProjectStatus.STOPPED
    states = []
    for container_id in container_ids:
        try:
            container = client.containers.get(container_id)
        except docker.errors.NotFound:
            return ProjectStatus.FAILED
        # Une panne du daemon doit remonter, pas transformer l'état en STOPPED.
        state = container.attrs.get("State", {})
        if container.status == "exited" and (state.get("ExitCode", 0) != 0 or state.get("OOMKilled")):
            return ProjectStatus.FAILED
        states.append(container.status)
    if all(status == "running" for status in states):
        return ProjectStatus.RUNNING
    if all(status == "exited" for status in states):
        return ProjectStatus.STOPPED
    return ProjectStatus.FAILED


def archive_container_evidence(container):
    """Diagnostic local avant remplacement, sans copier Config.Env."""
    directory = Path("app/logs")
    directory.mkdir(parents=True, exist_ok=True)
    prefix = directory / f"container_{container.id}"
    state_file = prefix.with_suffix(".json")
    state_file.touch(mode=0o600, exist_ok=True)
    state_file.write_text(json.dumps({
        "id": container.id, "name": container.name,
        "image": container.attrs.get("Image"),
        "state": container.attrs.get("State", {}),
    }, indent=2), encoding="utf-8")
    try:
        log_file = prefix.with_suffix(".log")
        log_file.touch(mode=0o600, exist_ok=True)
        log_file.write_bytes(container.logs(tail=200))
    except docker.errors.APIError:
        logger.warning("Logs Docker indisponibles pour %s ; état conservé.", container.id)


def stop_containers_preserving_evidence(container_ids):
    for container_id in container_ids:
        try:
            container = client.containers.get(container_id)
            if container.status == "running":
                container.stop()
        except docker.errors.NotFound:
            continue
