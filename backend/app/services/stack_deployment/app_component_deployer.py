#app/services/stack_deployment/app_component_deployer.py
import traceback

from app.core.config import settings
from app.models.deployment import DeploymentRun, PipelineStatus
from app.models.project import FailReason
from app.services.build_preparation import prepare_build_environment
from app.services.build_service import build_docker_image, detect_project_type, generate_dockerfile
from app.services.container_service import scale_project
from app.services.deployment_run_tracker import update_pipeline_run
from app.services.git_service import clone_repository
from app.services.project_service import ProjectService
from app.services.scan_service import detect_secret, scan_image
from app.services.stack_deployment.base import ComponentDeployer
from app.services.stack_deployment.context import StackDeploymentContext

from app.services.security_confirmation_service import SecurityConfirmationService
from app.models.security_confirmation import ConfirmationStatus

class AppComponentDeployer(ComponentDeployer):
    """
    Pipeline commun aux composants applicatifs (FRONT / BACK) : clone → gitleaks
    → détection/Dockerfile → build → scan → déploiement du conteneur.

    Les sous-classes (FrontComponentDeployer, BackComponentDeployer) ne
    redéfinissent QUE ce qui diffère réellement entre front et back :
    - build_args()   : build-args Docker supplémentaires (ex: VITE_API_URL)
    - runtime_envs()  : variables d'env en clair injectées au runtime (ex: DB_URL, FRONTEND_URL)
    """

    #  TEMPORAIRE — usage TEST uniquement, à repasser à False avant toute
    # utilisation réelle. Permet de voir la stack tourner malgré des
    # vulnérabilités critiques détectées, pour valider la communication
    # réseau inter-conteneurs. (Point d'attention #3 du résumé de session
    # précédent — toujours non traité, déplacé ici tel quel.)
    skip_security_gate = False

    def build_args(self, ctx: StackDeploymentContext) -> dict:
        """Build-args Docker supplémentaires pour ce composant. Vide par défaut."""
        return {}

    def runtime_envs(self, ctx: StackDeploymentContext) -> dict:
        """Variables d'env en clair injectées au runtime. Vide par défaut."""
        return {}

    # ------------------------------------------------------------------ #
    # Méthode template : orchestre les étapes, s'arrête au premier échec.
    # ------------------------------------------------------------------ #
    def deploy(self, ctx: StackDeploymentContext) -> None:
        comp_payload = ctx.comp_payload
        ctx.destination_path = f"/tmp/ids-repo/{ctx.container_name}"

        if comp_payload.get("port") is None:
            ctx.log(f"  [ERROR] Port d'écoute non renseigné pour {ctx.container_name}")
            self._fail(ctx, "Port d'écoute non renseigné pour ce composant", FailReason.DEPLOY_ERROR, "Port manquant")
            return

        if not self._clone(ctx):
            return
        if self._checkpoint_cancelled(ctx, "après clone"):
            return

        if not self._scan_secrets(ctx):
            return

        if not self._prepare_and_build_dockerfile(ctx):
            return
        if self._checkpoint_cancelled(ctx, "avant build"):
            return

        if not self._build_image(ctx):
            return
        if self._checkpoint_cancelled(ctx, "après build"):
            return

        if not self._scan_vulnerabilities(ctx):
            return
        if self._checkpoint_cancelled(ctx, "avant déploiement du conteneur"):
            return

        self._deploy_container(ctx)

    # ------------------------------------------------------------------ #
    # Étapes individuelles
    # ------------------------------------------------------------------ #
    def _clone(self, ctx: StackDeploymentContext) -> bool:
        comp_payload, log = ctx.comp_payload, ctx.log
        log(f"  [1/5] Clonage du dépôt: {comp_payload['repo_url']} (branche: {comp_payload.get('branch', 'main')})")
        update_pipeline_run(ctx.db, ctx.history_run_id, PipelineStatus.CLONING, f"Clonage de {ctx.container_name}")
        try:
            ctx.clone_result = clone_repository(
                comp_payload["repo_url"], ctx.destination_path, comp_payload.get("branch", "main")
            )
            log(f"         Clone réussi. Commit: {ctx.clone_result['commit_hash']}")

            run_record = ctx.db.query(DeploymentRun).get(ctx.history_run_id)
            if run_record and not run_record.commit_hash:
                run_record.commit_hash = ctx.clone_result["commit_hash"]
                ctx.db.commit()
            return True
        except Exception as e:
            log(f"         Erreur clone: {e}")
            self._fail(ctx, f"Erreur clone: {e}", FailReason.CLONE_ERROR, f"Erreur clone: {e}")
            return False

    def _scan_secrets(self, ctx: StackDeploymentContext) -> bool:
        log = ctx.log
        log("  [2/5] Analyse des secrets (Gitleaks)...")
        gitleak_result = detect_secret(ctx.destination_path)
        ProjectService.save_component_scan_results(ctx.db, ctx.component.id, gitleak_result=gitleak_result)
        if gitleak_result["blocking"]:
            log("         Secret trouvé dans le dépôt - déploiement bloqué")
            self._fail(ctx, "Secret trouvé dans le dépôt", FailReason.SECRET_LEAK, "Secret leak détecté")
            return False
        log("         Aucun secret détecté.")
        return True

    def _prepare_and_build_dockerfile(self, ctx: StackDeploymentContext) -> bool:
        log = ctx.log
        log("  [3/5] Détection du type de projet et génération du Dockerfile...")
        update_pipeline_run(
            ctx.db, ctx.history_run_id, PipelineStatus.BUILDING, f"Génération Dockerfile pour {ctx.container_name}"
        )
        try:
            detect_result = detect_project_type(ctx.destination_path)
            generate_dockerfile(detect_result, ctx.destination_path)
            prepare_build_environment(
                project_path=ctx.destination_path,
                project_type=detect_result,
                env_vars_input=ctx.comp_payload.get("envs_var"),  # variables spécifiques au composant
            )
            log("         Projet détecté et Dockerfile généré.")
            return True
        except Exception as e:
            log(f"         Erreur détection: {e}")
            self._fail(ctx, f"Erreur détection: {e}", FailReason.DETECTION_ERROR, f"Erreur détection: {e}")
            return False

    def _build_image(self, ctx: StackDeploymentContext) -> bool:
        log = ctx.log
        log(f"  [4/5] Build de l'image Docker '{ctx.container_name}'...")
        update_pipeline_run(ctx.db, ctx.history_run_id, PipelineStatus.BUILDING, f"Build de l'image {ctx.container_name}")
        try:
            ctx.build_result = build_docker_image(
                ctx.destination_path,
                ctx.container_name,
                ctx.clone_result["commit_hash"],
                build_args=self.build_args(ctx) or None,
            )
            log("         Build de l'image terminé avec succès.")
            return True
        except Exception as e:
            log(f"         Erreur build: {e}")
            self._fail(ctx, f"Erreur build: {e}", FailReason.BUILD_ERROR, f"Erreur build: {e}")
            return False
        
    def _scan_vulnerabilities(self, ctx: StackDeploymentContext) -> bool:
        log = ctx.log
        log("  [5/5] Analyse des vulnérabilités (Trivy)...")
        update_pipeline_run(ctx.db, ctx.history_run_id, PipelineStatus.SCANNING, f"Scan Trivy pour {ctx.container_name}")
        try:
            trivy_result = scan_image(ctx.build_result, skip_security_gate=self.skip_security_gate)
            ProjectService.save_component_scan_results(ctx.db, ctx.component.id, trivy_result=trivy_result)
        except Exception as e:
            log(f"         Erreur scan vulnérabilités: {e}")
            self._fail(ctx, f"Erreur scan vulnérabilités: {e}", FailReason.SCAN_ERROR, f"Erreur scan: {e}")
            return False

        if trivy_result["blocking"]:
            crit_vulns = trivy_result["critical_vulnerabilities"]
            log(f"         {len(crit_vulns)} faille(s) critique(s) détectée(s) — en attente de confirmation...")

            # NOTE : la confirmation est posée au niveau du Project parent (pas du
            # composant), donc project_id = ctx.component.project_id, cohérent
            # avec l'endroit où le front va poller (project_id, pas component_id).
            confirmation = SecurityConfirmationService.create_pending(
                ctx.db, ctx.component.project_id, crit_vulns, trivy_result["severity_count"]
            )
            update_pipeline_run(
                ctx.db, ctx.history_run_id, PipelineStatus.AWAITING_CONFIRMATION,
                f"{len(crit_vulns)} faille(s) critique(s) sur {ctx.container_name} — en attente de confirmation"
            )

            decision = SecurityConfirmationService.wait_for_decision(
                ctx.db, confirmation.id, timeout_seconds=10, is_cancelled=ctx.is_cancelled
            )

            if ctx.is_cancelled():
                SecurityConfirmationService.discard(ctx.db, confirmation.id)
                self._checkpoint_cancelled(ctx, "pendant l'attente de confirmation sécurité")
                return False

            if decision == ConfirmationStatus.CONFIRMED:
                log("         Utilisateur a choisi de continuer malgré la faille critique.")
                update_pipeline_run(ctx.db, ctx.history_run_id, PipelineStatus.SCANNING, "Confirmé, reprise du pipeline")
            else:
                reason = "Refusé par l'utilisateur" if decision == ConfirmationStatus.REJECTED else "Timeout (10s) sans réponse"
                log(f"         [BLOQUÉ] {reason}")
                SecurityConfirmationService.discard(ctx.db, confirmation.id)
                ProjectService.mark_component_failed(
                    ctx.db, ctx.component.id,
                    f"Déploiement bloqué : {reason}",
                    fail_reason=FailReason.VULNERABILITY,
                    vulnerabilities=crit_vulns,
                )
                update_pipeline_run(ctx.db, ctx.history_run_id, PipelineStatus.FAILED, f"Vulnérabilité critique — {reason}")
                return False

        log("        Scan de sécurité validé.")
        return True

    def _deploy_container(self, ctx: StackDeploymentContext) -> None:
        comp_payload, component, log = ctx.comp_payload, ctx.component, ctx.log
        extra_nets = [settings.APP_NETWORK] if comp_payload.get("expose_publicly") else None
        plain_envs = self.runtime_envs(ctx)

        log(
            f"  [DEPLOY] Démarrage du conteneur (port: {comp_payload['port']}, "
            f"expose: {comp_payload.get('expose_publicly', False)})..."
        )
        update_pipeline_run(ctx.db, ctx.history_run_id, PipelineStatus.DEPLOYING, f"Déploiement de {ctx.container_name}")
        try:
            container_ids = scale_project(
                ctx.build_result,
                slug=ctx.container_name,
                network=ctx.project_network,
                desired_replicas=comp_payload.get("replica", 1),
                envs_var=comp_payload.get("envs_var"),
                extra_networks=extra_nets,
                port=comp_payload["port"],
                plain_envs_var=plain_envs,
                expose_traefik=comp_payload.get("expose_publicly", False),
            )
            ProjectService.finalize_component_success(
                ctx.db, component.id, container_ids=container_ids, commit_hash=ctx.clone_result["commit_hash"]
            )
            log(f"  [DEPLOY]  Composant {ctx.container_name} démarré avec succès\n")
        except Exception as e:
            log(f"  [DEPLOY]  Erreur déploiement: {e}")
            log(traceback.format_exc())
            self._fail(ctx, f"Erreur déploiement: {e}", FailReason.DEPLOY_ERROR, f"Erreur déploiement: {e}")

    # ------------------------------------------------------------------ #
    # Helpers internes
    # ------------------------------------------------------------------ #
    def _fail(self, ctx: StackDeploymentContext, error_message: str, fail_reason: FailReason, run_message: str) -> None:
        ProjectService.mark_component_failed(ctx.db, ctx.component.id, error_message, fail_reason=fail_reason)
        update_pipeline_run(ctx.db, ctx.history_run_id, PipelineStatus.FAILED, run_message)

    def _checkpoint_cancelled(self, ctx: StackDeploymentContext, when: str) -> bool:
        if not ctx.is_cancelled():
            return False
        ctx.log(f"  [ANNULÉ] Arrêt {when} pour {ctx.container_name}")
        ProjectService.mark_component_failed(
            ctx.db, ctx.component.id, "Build annulé par l'utilisateur", fail_reason=FailReason.OTHER
        )
        update_pipeline_run(ctx.db, ctx.history_run_id, PipelineStatus.FAILED, f"Annulé {when}")
        ctx.db.commit()
        ctx.request_stop()  # signale à l'orchestrateur de `break` la boucle des composants
        return True
