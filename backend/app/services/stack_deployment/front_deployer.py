#app/services/stack_deployment/front_deployer.py
from app.models.project import ComponentKind
from app.services.container_service import build_container_name
from app.services.stack_deployment.app_component_deployer import AppComponentDeployer
from app.services.stack_deployment.context import StackDeploymentContext


class FrontComponentDeployer(AppComponentDeployer):
    """
    Spécificité FRONT : injecter VITE_API_URL au build, pointant vers le
    composant BACK de la même stack (convention API Laravel: /api/v1).
    """

    def build_args(self, ctx: StackDeploymentContext) -> dict:
        back_comp = next((c for c in ctx.components if c["kind"] == ComponentKind.BACK), None)
        if not back_comp:
            return {}

        back_container_name = build_container_name(f"{ctx.slug}-{back_comp['name']}")
        back_url = f"http://{back_container_name}.localhost:8080/api/v1"  # convention Laravel
        ctx.log(f"  [INFO] Injection de VITE_API_URL={back_url} pour le build frontend")
        return {"VITE_API_URL": back_url}
