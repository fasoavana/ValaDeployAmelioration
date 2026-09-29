#app/services/stack_deployment/back_deployer.py
from app.models.project import ComponentKind
from app.services.container_service import build_container_name
from app.services.stack_deployment.app_component_deployer import AppComponentDeployer
from app.services.stack_deployment.context import StackDeploymentContext


class BackComponentDeployer(AppComponentDeployer):
    """
    Spécificité BACK : injecter au runtime DB_URL (clé lue par Laravel, voir
    résumé de session précédent) vers le composant DATABASE déjà traité, et
    FRONTEND_URL vers le composant FRONT (pour la config CORS du back).
    """

    def runtime_envs(self, ctx: StackDeploymentContext) -> dict:
        if ctx.db_component is None:
            return {}

        envs = {}
        db_container_name = f"{ctx.slug}-{ctx.db_component.name}"
        envs["DB_URL"] = (
            f"pgsql://{ctx.db_component.db_user}:{ctx.db_component.db_password}"
            f"@{db_container_name}:5432/{ctx.db_component.db_name}"
        )
        ctx.log(f"  [INFO] Injection auto de DATABASE_URL vers {db_container_name}")

        front_comp = next((c for c in ctx.components if c["kind"] == ComponentKind.FRONT), None)
        if front_comp:
            front_container_name = build_container_name(f"{ctx.slug}-{front_comp['name']}")
            envs["FRONTEND_URL"] = f"http://{front_container_name}.localhost:8080"
            ctx.log(f"  [INFO] Injection auto de FRONTEND_URL={envs['FRONTEND_URL']}")

        return envs
