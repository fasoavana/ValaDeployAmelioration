#app/services/stack_deployment/factory.py
from app.models.project import ComponentKind
from app.services.stack_deployment.back_deployer import BackComponentDeployer
from app.services.stack_deployment.base import ComponentDeployer
from app.services.stack_deployment.database_deployer import DatabaseComponentDeployer
from app.services.stack_deployment.front_deployer import FrontComponentDeployer

# Les deployers sont sans état propre (tout l'état vit dans StackDeploymentContext),
# donc une instance unique par type suffit et peut être réutilisée à chaque itération.
_DEPLOYERS: dict[ComponentKind, ComponentDeployer] = {
    ComponentKind.FRONT: FrontComponentDeployer(),
    ComponentKind.BACK: BackComponentDeployer(),
    ComponentKind.DATABASE: DatabaseComponentDeployer(),
}


def get_component_deployer(kind: ComponentKind) -> ComponentDeployer:
    try:
        return _DEPLOYERS[kind]
    except KeyError:
        raise ValueError(f"Aucun ComponentDeployer enregistré pour le type de composant: {kind}")
