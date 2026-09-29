#app/services/deploy_service.py
import logging
import os
import traceback
import uuid
from app.services.cleanup_service import cleanup_project_resources

from sqlalchemy.orm import Session  # CORRECTION: était "from requests import Session"

from app.db.database import Session_local
from app.schemas.deploy import CloneSchema
from app.services.project_service import ProjectService
from app.services.git_service import clone_repository
from app.services.build_service import detect_project_type, generate_dockerfile, build_docker_image
from app.services.container_service import run_container, scale_project
from app.services.scan_service import scan_image, detect_secret
from app.core.config import settings
from app.core.exceptions import BuildError, DeployError, DetectionError, SecretLeakError, VulnerabilityError
from app.models.project import Project, FailReason, ComponentKind, ProjectStatus, ProjectComponent
from app.services.container_service import ensure_project_network, run_container
from app.services.build_preparation import prepare_build_environment
from app.services.security_profile import get_security_profile

# AJOUTS POUR L'HISTORIQUE
from app.models.deployment import DeploymentRun, PipelineStatus, DeploymentTrigger
from datetime import datetime, timezone

# Extrait dans son propre module pour être partagé avec les ComponentDeployer
# de app/services/stack_deployment/ (voir ce module pour le détail).
from app.services.deployment_run_tracker import update_pipeline_run

# Pattern stratégie pour le déploiement de stack : un ComponentDeployer par
# ComponentKind (front/back/database), voir app/services/stack_deployment/.
from app.services.stack_deployment.context import StackDeploymentContext
from app.services.stack_deployment.factory import get_component_deployer
from app.models.security_confirmation import ConfirmationStatus
from app.services.security_confirmation_service import SecurityConfirmationService


def _make_logger(f):
    """
    Écrit directement dans le fichier de log du build, SANS toucher à sys.stdout/
    sys.stderr (qui sont globaux au process, donc PAS thread-safe). Avant, on
    utilisait contextlib.redirect_stdout/redirect_stderr : si deux pipelines
    tournaient en même temps pour le même ou des projets différents (ex: un
    ancien thread pas encore arrêté + un retry), ils se marchaient dessus sur
    ces variables globales, et fermer le fichier d'un thread pouvait faire
    planter un print() ou un logging.exception() dans l'autre thread avec
    "ValueError: I/O operation on closed file".
    """
    def log(msg=""):
        try:
            f.write(str(msg) + "\n")
            f.flush()
        except Exception:
            # Le fichier peut déjà être en cours de fermeture (fin de run) :
            # on ne veut jamais qu'un problème de logging fasse planter le pipeline.
            pass
    return log


class DeployService:
    @staticmethod
    def run_deployment_pipeline(project_id: int, payload: CloneSchema, user_id: int = None, run_id: str = None):
        log_dir = "app/logs"
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, f"build_{project_id}.log")

        with open(log_file, 'w', encoding='utf-8') as f:
            log = _make_logger(f)

            log(f"[INFO] ==================================================")
            log(f"[INFO] Démarrage du pipeline pour le projet: {payload.slug} (ID: {project_id})")
            log(f"[INFO] ==================================================")

            db = Session_local()
            destination_path = f"/tmp/ids-repo/{payload.slug}"

            # Helper d'annulation : STOPPED en BDD OU un nouveau run a été démarré (retry concurrent)
            def is_cancelled():
                db.expire_all()
                p = db.query(Project).filter(Project.id == project_id).first()
                if not p:
                    return True
                if p.status == ProjectStatus.STOPPED:
                    return True
                if run_id and p.pipeline_run_id != run_id:
                    return True
                return False

            # Un thread zombie (ancien run) ne doit JAMAIS écrire le statut final
            # si un nouveau run a entre-temps été lancé pour ce projet.
            def is_superseded():
                db.expire_all()
                p = db.query(Project).filter(Project.id == project_id).first()
                return bool(p and run_id and p.pipeline_run_id != run_id)

            def bail_out(reason: str):
                log(f"[ANNULÉ] {reason}")
                if not is_superseded():
                    ProjectService.mark_failed(db, project_id, "Build annulé par l'utilisateur", fail_reason=FailReason.OTHER)
                    db.commit()

            history_run_id = None  # Initialisé pour les blocs except

            try:
                # ---> CRÉATION DE L'HISTORIQUE <---
                new_run = DeploymentRun(
                    project_id=project_id,
                    user_id=user_id,
                    trigger=DeploymentTrigger.MANUAL,
                    status=PipelineStatus.PENDING,
                    commit_hash=None,
                    logs=""
                )
                db.add(new_run)
                db.commit()
                db.refresh(new_run)
                history_run_id = new_run.id

                log(f"[1/6] Clonage du dépôt: {payload.repo_url} (branche: {payload.branch})")
                update_pipeline_run(db, history_run_id, PipelineStatus.CLONING, f"Clonage de {payload.repo_url}")

                clone_result = clone_repository(payload.repo_url, destination_path, payload.branch)

                # Mise à jour du commit hash dans l'historique
                run_record = db.query(DeploymentRun).get(history_run_id)
                if run_record:
                    run_record.commit_hash = clone_result['commit_hash']
                    db.commit()

                log(f"    Clone réussi. Commit: {clone_result['commit_hash']}")

                if is_cancelled():
                    bail_out("Arrêt demandé après le clone.")
                    return

                log("[2/6] Analyse des secrets (Gitleaks)...")
                gitleak_result = detect_secret(destination_path)
                ProjectService.save_scan_results(db, project_id, gitleak_result=gitleak_result)
                if gitleak_result["blocking"]:
                    raise SecretLeakError("Secret trouvé dans le dépôt")

                log("      Aucun secret détecté.")

                log("[3/6] Détection du type de projet et génération du Dockerfile...")
                update_pipeline_run(db, history_run_id, PipelineStatus.BUILDING, "Détection et génération du Dockerfile")

                detect_result = detect_project_type(destination_path)

                prepare_build_environment(
                    project_path=destination_path,
                    project_type=detect_result,
                    env_vars_input=payload.envs_var  # Vient de ton schema CloneSchema
                )
                generate_dockerfile(detect_result, destination_path)
                log(f"      Projet détecté et Dockerfile généré.")

                if is_cancelled():
                    bail_out("Arrêt demandé avant le build Docker.")
                    return

                log(f"[4/6] Build de l'image Docker '{payload.slug}'...")
                update_pipeline_run(db, history_run_id, PipelineStatus.BUILDING, f"Build de l'image {payload.slug}")

                build_result = build_docker_image(destination_path, payload.slug, clone_result["commit_hash"])
                log("      Build de l'image terminé avec succès.")

                if is_cancelled():
                    bail_out("Arrêt demandé après le build Docker.")
                    return

                log("[5/6] Analyse des vulnérabilités (Trivy)...")
                update_pipeline_run(db, history_run_id, PipelineStatus.SCANNING, "Scan de sécurité (Trivy)")

                trivy_result = scan_image(build_result)
                ProjectService.save_scan_results(db, project_id, trivy_result=trivy_result)

                if trivy_result["blocking"]:
                    crit_vulns = trivy_result["critical_vulnerabilities"]
                    log(f"[ATTENTION] {len(crit_vulns)} faille(s) critique(s) patchable(s) détectée(s).")
                    log("[ATTENTION] En attente de confirmation utilisateur (10s max)...")

                    confirmation = SecurityConfirmationService.create_pending(
                        db, project_id, crit_vulns, trivy_result["severity_count"]
                    )
                    ProjectService.update_project_status(db, project_id, ProjectStatus.PENDING_SECURITY_CONFIRMATION)
                    update_pipeline_run(
                        db, history_run_id, PipelineStatus.AWAITING_CONFIRMATION,
                        f"{len(crit_vulns)} faille(s) critique(s) — en attente de confirmation"
                    )

                    decision = SecurityConfirmationService.wait_for_decision(
                        db, confirmation.id, timeout_seconds=10, is_cancelled=is_cancelled
                    )

                    if is_cancelled():
                        SecurityConfirmationService.discard(db, confirmation.id)
                        bail_out("Arrêt demandé pendant l'attente de confirmation sécurité.")
                        return

                    if decision == ConfirmationStatus.CONFIRMED:
                        log("      Utilisateur a choisi de continuer malgré la faille critique.")
                        update_pipeline_run(db, history_run_id, PipelineStatus.SCANNING, "Confirmé par l'utilisateur, reprise du pipeline")
                    else:
                        reason = "Refusé par l'utilisateur" if decision == ConfirmationStatus.REJECTED else "Timeout (10s) sans réponse"
                        log(f"[BLOQUÉ] {reason}")
                        SecurityConfirmationService.discard(db, confirmation.id)
                        raise VulnerabilityError(f"Déploiement bloqué : {reason}", crit_vulns)
                else:
                    log("      Scan de sécurité validé.")

                if is_cancelled():
                    bail_out("Arrêt demandé avant le déploiement des conteneurs.")
                    return

                log(f"[6/6] Déploiement des conteneurs (réplicas: {payload.replica})...")
                update_pipeline_run(db, history_run_id, PipelineStatus.DEPLOYING, f"Démarrage des {payload.replica} conteneur(s)")

                container_ids = scale_project(
                    build_result,
                    payload.slug, settings.APP_NETWORK,
                    payload.replica, payload.envs_var,
                    port=payload.port,
                    security_profile=get_security_profile(detect_result),
                )
                log("      Conteneurs démarrés et connectés au réseau.")

                # Dernier check avant de valider le succès : si annulé pendant le déploiement,
                # ou si un nouveau run a pris le relais, on ne touche pas au statut final.
                if is_cancelled():
                    log("[ANNULÉ] Arrêt demandé pendant le déploiement des conteneurs. Nettoyage...")
                    cleanup_project_resources(payload.slug, container_ids)
                    if not is_superseded():
                        update_pipeline_run(db, history_run_id, PipelineStatus.FAILED, "Annulé par l'utilisateur")
                        ProjectService.mark_failed(db, project_id, "Build annulé par l'utilisateur", fail_reason=FailReason.OTHER)
                        db.commit()
                    return

                if is_superseded():
                    log("[INFO] Un nouveau run a été démarré entre-temps, ce thread ne finalise rien.")
                    return

                log("[INFO] ==================================================")
                log("[INFO] DÉPLOIEMENT TERMINÉ AVEC SUCCÈS")
                log("[INFO] ==================================================")

                update_pipeline_run(db, history_run_id, PipelineStatus.SUCCESS, "Déploiement terminé avec succès")

                ProjectService.finalize_success(
                    db, project_id,
                    container_ids=container_ids,
                    commit_hash=clone_result["commit_hash"],
                )
                db.commit()

            except VulnerabilityError as e:
                log(f"[ERREUR] {e}")
                if not is_superseded():
                    update_pipeline_run(db, history_run_id, PipelineStatus.FAILED, f"Vulnérabilité: {e}")
                    ProjectService.mark_failed(db, project_id, str(e), fail_reason=FailReason.VULNERABILITY, vulnerabilities=e.vulnerabilities)
                    db.commit()
            except SecretLeakError as e:
                log(f"[ERREUR] {e}")
                if not is_superseded():
                    update_pipeline_run(db, history_run_id, PipelineStatus.FAILED, f"Secret leak: {e}")
                    ProjectService.mark_failed(db, project_id, str(e), fail_reason=FailReason.SECRET_LEAK)
                    db.commit()
            except DetectionError as e:
                log(f"[ERREUR] {e}")
                if not is_superseded():
                    update_pipeline_run(db, history_run_id, PipelineStatus.FAILED, f"Erreur détection: {e}")
                    ProjectService.mark_failed(db, project_id, str(e), fail_reason=FailReason.DETECTION_ERROR)
                    db.commit()
            except BuildError as e:
                log(f"[ERREUR] {e}")
                if not is_superseded():
                    update_pipeline_run(db, history_run_id, PipelineStatus.FAILED, f"Erreur build: {e}")
                    ProjectService.mark_failed(db, project_id, str(e), fail_reason=FailReason.BUILD_ERROR)
                    db.commit()
            except DeployError as e:
                log(f"[ERREUR] {e}")
                if not is_superseded():
                    update_pipeline_run(db, history_run_id, PipelineStatus.FAILED, f"Erreur déploiement: {e}")
                    ProjectService.mark_failed(db, project_id, str(e), fail_reason=FailReason.DEPLOY_ERROR)
                    db.commit()
            except ValueError as e:
                log(f"[ERREUR] {e}")
                if not is_superseded():
                    update_pipeline_run(db, history_run_id, PipelineStatus.FAILED, f"Erreur valeur: {e}")
                    ProjectService.mark_failed(db, project_id, str(e), fail_reason=FailReason.CLONE_ERROR)
                    db.commit()
            except Exception as e:
                log(f"[ERREUR CRITIQUE] Erreur inattendue: {e}")
                log(traceback.format_exc())
                if not is_superseded():
                    update_pipeline_run(db, history_run_id, PipelineStatus.FAILED, f"Erreur critique: {e}")
                    ProjectService.mark_failed(db, project_id, f"Erreur inattendue: {e}", fail_reason=FailReason.OTHER)
                    db.commit()
            finally:
                db.close()

    @staticmethod
    def run_stack_deployment_pipeline(project_id: int, slug: str, components: list, user_id: int = None, run_id: str = None):
        """
        Déploie une stack multi-composants (front/back/database) pour un Project.
        Les logs sont écrits directement dans un fichier pour être streamés via WebSocket.

        Cette méthode est un ORCHESTRATEUR : elle gère le cycle de vie du run
        (historique, annulation, agrégation du statut global) et délègue le
        détail du déploiement de chaque composant à un ComponentDeployer
        (voir app/services/stack_deployment/), un par ComponentKind.
        """
        log_dir = "app/logs"
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, f"build_{project_id}.log")

        with open(log_file, 'w', encoding='utf-8') as f:
            log = _make_logger(f)

            log(f"[INFO] ==================================================")
            log(f"[INFO] Démarrage du pipeline STACK pour: {slug} (ID: {project_id})")
            log(f"[INFO] Composants à déployer: {len(components)}")
            log(f"[INFO] ==================================================\n")

            db = Session_local()
            project_network = ensure_project_network(slug)

            # Le composant DATABASE doit être traité avant BACK, pour que ses credentials
            # (générés par DatabaseComponentDeployer) soient déjà en base au moment où
            # BackComponentDeployer construit DB_URL. On trie sans modifier l'ordre relatif
            # du reste.
            components = sorted(
                components,
                key=lambda c: 0 if c["kind"] == ComponentKind.DATABASE else 1
            )

            # Helper d'annulation : STOPPED en BDD OU un nouveau run a été démarré (retry concurrent).
            # db.expire_all() est indispensable, sinon SQLAlchemy peut resservir un statut en cache
            # de session et ne jamais voir le changement fait par un autre thread/requête.
            def is_cancelled():
                db.expire_all()
                p = db.query(Project).filter(Project.id == project_id).first()
                if not p:
                    return True
                if p.status == ProjectStatus.STOPPED:
                    return True
                if run_id and p.pipeline_run_id != run_id:
                    return True
                return False

            # Distinct de is_cancelled : sert uniquement à savoir si CE thread doit
            # encore avoir le droit d'écrire le statut final agrégé du projet.
            # Un thread zombie (ancien run supplanté par un retry) ne doit jamais
            # écraser le statut posé par le run actuellement responsable.
            def is_superseded():
                db.expire_all()
                p = db.query(Project).filter(Project.id == project_id).first()
                return bool(p and run_id and p.pipeline_run_id != run_id)

            history_run_id = None  # Initialisé pour les blocs except

            try:
                # ---> CRÉATION DE L'HISTORIQUE <---
                new_run = DeploymentRun(
                    project_id=project_id,
                    user_id=user_id,
                    trigger=DeploymentTrigger.MANUAL,
                    status=PipelineStatus.PENDING,
                    commit_hash=None,
                    logs=""
                )
                db.add(new_run)
                db.commit()
                db.refresh(new_run)
                history_run_id = new_run.id

                ctx = StackDeploymentContext(
                    db=db,
                    slug=slug,
                    project_network=project_network,
                    components=components,
                    log=log,
                    history_run_id=history_run_id,
                    is_cancelled=is_cancelled,
                )

                total_components = len(components)
                for idx, comp_payload in enumerate(components, 1):
                    component = ProjectService.get_component_by_id(db, comp_payload["component_id"])
                    if not component:
                        log(f"[WARN] Composant ID {comp_payload['component_id']} introuvable, skip.")
                        continue

                    # CHECKPOINT D'ANNULATION ROBUSTE (requête fraîche en BDD), avant de
                    # démarrer le traitement de ce composant.
                    if is_cancelled():
                        log(f"\n[INFO]  BUILD ANNULÉ DÉTECTÉ EN BDD. Arrêt immédiat du traitement.")
                        ProjectService.mark_component_failed(
                            db, component.id, "Build annulé par l'utilisateur", fail_reason=FailReason.OTHER
                        )
                        update_pipeline_run(db, history_run_id, PipelineStatus.FAILED, "Annulé par l'utilisateur")
                        db.commit()
                        break  # on ne traite PAS les composants suivants

                    ctx.comp_payload = comp_payload
                    ctx.component = component
                    ctx.container_name = f"{slug}-{comp_payload['name']}"
                    ctx.stop_requested = False

                    log(f"[{idx}/{total_components}] Traitement du composant: {ctx.container_name} ({comp_payload['kind'].value})")

                    deployer = get_component_deployer(comp_payload["kind"])
                    deployer.deploy(ctx)

                    # Un ComponentDeployer lève ce signal uniquement sur un checkpoint
                    # d'annulation (jamais sur un échec ordinaire, qui passe au composant
                    # suivant) : dans ce cas on arrête toute la stack, comme avant.
                    if ctx.stop_requested:
                        break

                # Statut global du Project parent

                log(f"[INFO] ==================================================")
                log(f"[INFO] Calcul du statut global de la stack...")

                # SÉCURITÉ CRITIQUE : si un nouveau run a été lancé entre-temps (retry
                # pendant que ce thread tournait encore), on ne touche à RIEN. C'est ce
                # qui causait le bug "projet marqué RUNNING alors que des composants
                # sont cancelled" : un vieux thread zombie finissait sa propre logique
                # (basée sur une vue périmée des composants) et écrasait le bon statut
                # posé entre-temps par le run réellement actif.
                if is_superseded():
                    log(f"[INFO] Un nouveau run a été démarré entre-temps pour ce projet. "
                        f"Ce thread (obsolète) ne finalise pas le statut global.")
                    db.close()
                    return

                # On recharge le projet pour avoir le statut le plus à jour (au cas où il a été annulé)
                db.expire_all()
                current_project = db.query(Project).filter(Project.id == project_id).first()
                all_components = ProjectService.get_components_by_project(db, project_id)

                if current_project and current_project.status == ProjectStatus.STOPPED:
                    log(f"[INFO]  Stack annulée. Nettoyage des ressources Docker...")
                    all_container_ids = []
                    for c in all_components:
                        if c.container_ids:
                            all_container_ids.extend(c.container_ids)
                    if all_container_ids:
                        cleanup_project_resources(slug, all_container_ids)
                    update_pipeline_run(db, history_run_id, PipelineStatus.FAILED, "Stack annulée et nettoyée")

                elif all_components and all(c.status == ProjectStatus.RUNNING for c in all_components):
                    ProjectService.update_project_status(db, project_id, ProjectStatus.RUNNING)
                    update_pipeline_run(db, history_run_id, PipelineStatus.SUCCESS, "Stack entièrement déployée et RUNNING")
                    log(f"[INFO]  STACK ENTIÈREMENT DÉPLOYÉE ET RUNNING")
                elif any(c.status == ProjectStatus.FAILED for c in all_components):
                    ProjectService.update_project_status(db, project_id, ProjectStatus.FAILED)
                    failed_count = sum(1 for c in all_components if c.status == ProjectStatus.FAILED)
                    update_pipeline_run(db, history_run_id, PipelineStatus.FAILED, f"Stack partiellement en échec ({failed_count} composants)")
                    log(f"[INFO]  STACK PARTIELLEMENT EN ÉCHEC ({failed_count}/{len(all_components)} composants failed)")
                else:
                    log(f"[INFO] Statut stack mis à jour.")

                db.commit()  # Sauvegarde finale
                log(f"[INFO] ==================================================\n")

            except Exception as e:
                log(f"[ERREUR CRITIQUE STACK] Échec du déploiement du projet {project_id}")
                log(traceback.format_exc())
                logging.error(f"[ERREUR CRITIQUE STACK] Échec du déploiement du projet {project_id}: {e}")

                try:
                    db.rollback()
                    if not is_superseded():
                        ProjectService.update_project_status(db, project_id, ProjectStatus.FAILED)
                        if history_run_id:
                            update_pipeline_run(db, history_run_id, PipelineStatus.FAILED, f"Erreur critique: {e}")
                        db.commit()
                except Exception as rollback_error:
                    log(f"Impossible de mettre à jour le statut FAILED après erreur: {rollback_error}")
                    db.rollback()
            finally:
                db.close()

    @staticmethod
    def retry_deployment(db: Session, project_id: int, user_id: int):
        """
        Relance un déploiement échoué ou annulé.
        Nettoie les anciennes ressources, reset la BDD, et relance le bon pipeline.
        Retourne un tuple (project, is_stack, components, run_id) pour que la route puisse
        lancer le pipeline en background avec le run_id courant.
        """

        project = ProjectService.get_project_by_id(db, project_id, user_id)
        if not project:
            raise ValueError("Projet introuvable")

        # 1. Nettoyer les anciennes ressources Docker
        container_ids_to_clean = list(project.container_ids or [])
        components = ProjectService.get_components_by_project(db, project_id)
        for comp in components:
            if comp.container_ids:
                container_ids_to_clean.extend(comp.container_ids)

        cleanup_project_resources(project.slug, container_ids_to_clean)

        # 2. Réinitialiser le projet en BDD
        # Nouveau pipeline_run_id à chaque retry : tout thread encore actif de l'ancien
        # run verra, à son prochain checkpoint, que run_id ne correspond plus et s'arrêtera,
        # même si le statut n'est pas (encore) STOPPED.
        new_run_id = str(uuid.uuid4())
        project.status = ProjectStatus.BUILDING
        project.error_message = None
        project.fail_reason = None
        project.container_ids = None
        project.commit_hash = None
        project.vulnerabilities = []
        project.critical_vuln_count = 0
        project.pipeline_run_id = new_run_id

        # 3. Réinitialiser les composants (si stack)
        is_stack = len(components) > 0
        if is_stack:
            for comp in components:
                comp.status = ProjectStatus.BUILDING
                comp.error_message = None
                comp.fail_reason = None
                comp.container_ids = None
                comp.commit_hash = None
                comp.vulnerabilities = []
                comp.critical_vuln_count = 0

        db.commit()

        return project, is_stack, components, new_run_id
