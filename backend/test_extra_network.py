# test_extra_network.py
from app.services.container_service import ensure_project_network, run_container
from app.core.docker_client import client
from app.core.config import settings

SLUG = "testnet2"

net_name = ensure_project_network(SLUG)
print(f"Réseau projet : {net_name}")
print(f"Réseau Traefik : {settings.APP_NETWORK}")

multi_id = run_container(
    image_name="nginx:alpine",
    slug=f"{SLUG}-front",
    network=net_name,
    envs_var=None,
    extra_networks=[settings.APP_NETWORK],
)

c = client.containers.get(multi_id)
c.reload()
networks = c.attrs["NetworkSettings"]["Networks"]
print("Réseaux connectés :", list(networks.keys()))