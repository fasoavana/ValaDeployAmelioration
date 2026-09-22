from pydantic import BaseModel, field_validator

class CloneSchema(BaseModel):
    """ 
Format de la requête attendue pour le clonage d'un dépôt Git.
Attributes:
    repo_url (str): L'URL du dépôt Git à cloner.
    branch (str): La branche à cloner. Par défaut, c'est 'main'.
    slug (str): Le nom du répertoire local où le dépôt sera cloné.
    replica (int): Le nombre de réplicas à créer pour le projet. Par défaut, c'est 1.
    envs_var (dict | None): Un dictionnaire d'environnements variables à passer au
"""
    repo_url: str
    branch: str = 'main'
    slug: str
    replica : int = 1
    envs_var: dict[str, str] | None = None 
    port: int

    @field_validator("port")
    @classmethod
    def check_port_range(cls, v: int) -> int:
        if not (1 <= v <= 65535):
            raise ValueError(f"Le port {v} n'est pas valide (doit être entre 1 et 65535).")
        return v