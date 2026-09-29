# test_network.py
from app.services.container_service import ensure_project_network, run_container
from app.core.docker_client import client

SLUG = "testnet"

# 1. Créer le réseau du projet
net_name = ensure_project_network(SLUG)
print(f"Réseau créé/trouvé : {net_name}")

# 2. Lancer un conteneur "back" (nginx reste up tout seul, pas besoin de sleep)
back_id = run_container(
    image_name="nginx:alpine",
    slug=f"{SLUG}-back",
    network=net_name,
    envs_var=None,
)
print(f"Conteneur back lancé : {back_id[:12]}")

# 3. Lancer un conteneur "front" sur le MÊME réseau
front_id = run_container(
    image_name="nginx:alpine",
    slug=f"{SLUG}-front",
    network=net_name,
    envs_var=None,
)
print(f"Conteneur front lancé : {front_id[:12]}")

# 4. Test : depuis "front", pinguer "back" PAR SON NOM
front_container = client.containers.get(front_id)
exit_code, output = front_container.exec_run(f"ping -c 2 {SLUG}-back")
print("--- Résultat du ping front -> back ---")
print(output.decode())
print(f"Code retour : {exit_code} (0 = succès)")