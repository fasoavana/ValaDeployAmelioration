#app/schemas/stack_deploy.py
from pydantic import BaseModel, model_validator
from app.models.project import ComponentKind


class StackComponentSchema(BaseModel):
    """
    Un composant de la stack (front, back, ou database).
    """
    name: str                      # ex: "front", "back", "database"
    kind: ComponentKind            # FRONT / BACK / DATABASE

    # --- Champs pour FRONT / BACK ---
    repo_url: str | None = None
    branch: str = 'main'
    replica: int = 1
    envs_var: dict[str, str] | None = None
    expose_publicly: bool = False  # True = routable via Traefik (ex: front, ou back si son API est publique)
    port: int | None = None        # port d'écoute de l'appli dans le conteneur (obligatoire pour front/back)

    # --- Champs pour DATABASE ---
    db_image: str | None = None
    volume_name: str | None = None

    @model_validator(mode="after")
    def check_port_for_front_back(self):
        if self.kind in (ComponentKind.FRONT, ComponentKind.BACK):
            if self.port is None:
                raise ValueError(
                    f"Le champ 'port' est obligatoire pour un composant de type '{self.kind}' "
                    f"(port d'écoute de l'application, ex: 3000 pour Node.js)."
                )
            if not (1 <= self.port <= 65535):
                raise ValueError(f"Le port {self.port} n'est pas valide (doit être entre 1 et 65535).")
        return self


class StackDeploySchema(BaseModel):
    """
    Format de la requête pour déployer une stack multi-composants (front/back/db) en une fois.
    """
    slug: str
    components: list[StackComponentSchema]