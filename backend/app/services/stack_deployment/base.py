#app/services/stack_deployment/base.py
from abc import ABC, abstractmethod

from app.services.stack_deployment.context import StackDeploymentContext


class ComponentDeployer(ABC):
    """
    Interface commune à tout déployeur de composant de stack (front/back/database).

    Convention : deploy() ne laisse JAMAIS remonter d'exception vers
    l'orchestrateur. Toute erreur doit être loggée et traduite en
    mark_component_failed + update_pipeline_run, exactement comme le faisait
    l'ancien bloc inline de run_stack_deployment_pipeline.
    """

    @abstractmethod
    def deploy(self, ctx: StackDeploymentContext) -> None:
        raise NotImplementedError
