#app/services/stack_deployment/database_deployer.py
import traceback

from app.models.deployment import PipelineStatus
from app.models.project import FailReason
from app.services.container_service import run_container
from app.services.deployment_run_tracker import update_pipeline_run
from app.services.project_service import ProjectService
from app.services.stack_deployment.base import ComponentDeployer
from app.services.stack_deployment.context import StackDeploymentContext


class DatabaseComponentDeployer(ComponentDeployer):
    """
    Cas DATABASE : pas de clone, pas de scan sécurité (image officielle),
    juste génération des credentials + démarrage du conteneur.
    """

    def deploy(self, ctx: StackDeploymentContext) -> None:
        component = ctx.component
        comp_payload = ctx.comp_payload
        log = ctx.log

        try:
            volume_binding = None
            if comp_payload.get("volume_name"):
                volume_binding = {
                    comp_payload["volume_name"]: {"bind": "/var/lib/postgresql/data", "mode": "rw"}
                }

            log("  [DB] Génération des credentials PostgreSQL...")
            ProjectService.generate_db_credentials(ctx.db, component.id, ctx.slug)
            ctx.db.refresh(component)
            log(f"  [DB] Credentials générés: user={component.db_user}, db={component.db_name}")

            log(f"  [DB] Démarrage du conteneur avec l'image {comp_payload['db_image']}...")
            container_id = run_container(
                image_name=comp_payload["db_image"],
                slug=ctx.container_name,
                network=ctx.project_network,
                envs_var=comp_payload.get("envs_var"),
                plain_envs_var={
                    "POSTGRES_USER": component.db_user,
                    "POSTGRES_PASSWORD": component.db_password,
                    "POSTGRES_DB": component.db_name,
                },
                extra_networks=None,
                volumes=volume_binding,
                expose_traefik=False,
            )
            ProjectService.finalize_component_success(ctx.db, component.id, container_ids=[container_id])
            ctx.db_component = component
            log(f"  [DB]  Base de données démarrée avec succès (container_id: {container_id[:12]})\n")
        except Exception as e:
            log(f"  [DB]  Erreur démarrage database: {e}")
            log(traceback.format_exc())
            ProjectService.mark_component_failed(
                ctx.db, component.id, f"Erreur démarrage database: {e}", fail_reason=FailReason.DEPLOY_ERROR
            )
            update_pipeline_run(ctx.db, ctx.history_run_id, PipelineStatus.FAILED, f"Erreur DB: {e}")
