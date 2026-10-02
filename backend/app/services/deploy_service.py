#app/services/deploy_service.py
import logging
import os
import traceback
import uuid
import shutil
from app.services.container_service import stop_containers_preserving_evidence

from sqlalchemy.orm import Session  # CORRECTION: était "from requests import Session"

from app.db.database import Session_local
from app.schemas.deploy import CloneSchema
from app.services.project_service import ProjectService
from app.services.git_service import clone_repository
from app.services.build_service import detect_project_type, generate_dockerfile, build_docker_image
from app.services.container_service import scale_project, verify_containers_running
from app.services.scan_service import scan_image, detect_secret
from app.core.config import settings
from app.core.exceptions import BuildError, DeployError, DetectionError, SecretLeakError, VulnerabilityError
from app.models.project import Project, FailReason, ComponentKind, ProjectStatus, ProjectComponent
from app.services.network_service import (
    ensure_private_network,
    ensure_ingress_network,
)
from app.services.deployment_lock import project_deployment_lock
from app.core.docker_client import client
from app.core.image_reference import validate_image_reference
import docker
from app.services.build_preparation import prepare_build_environment
from app.services.security_profile import get_security_profile, get_runtime_port

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
from app.services.security_audit_service import SecurityAuditService


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

        with project_deployment_lock(project_id), open(log_file, 'a', encoding='utf-8') as f:
            log = _make_logger(f)

            log(f"[INFO] ==================================================")
            log(f"[INFO] Démarrage du pipeline pour le projet: {payload.slug} (ID: {project_id})")
            log(f"[INFO] ==================================================")

            db = Session_local()
            destination_path = f"/tmp/ids-repo/{payload.slug}-{uuid.uuid4().hex}"

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
                update_pipeline_run(db, history_run_id, PipelineStatus.FAILED, reason)
                if not is_superseded():
                    ProjectService.mark_failed(db, project_id, "Build annulé par l'utilisateur", fail_reason=FailReason.OTHER)
                    db.commit()

            history_run_id = None  # Initialisé pour les blocs except
            failure_stage = FailReason.CLONE_ERROR

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

                if is_cancelled():
                    update_pipeline_run(db, history_run_id, PipelineStatus.FAILED, "Run obsolète ou annulé")
                    return
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
                failure_stage = FailReason.SCAN_ERROR
                gitleak_result = detect_secret(destination_path)
                ProjectService.save_scan_results(db, project_id, gitleak_result=gitleak_result)
                gitleaks_decision = gitleak_result.get(
                    "decision",
                    "BLOCK" if gitleak_result.get("blocking") else "PASS",
                )

                SecurityAuditService.create(
                    db=db,
                    project_id=project_id,
                    deployment_run_id=history_run_id,
                    source="gitleaks",
                    decision=gitleaks_decision,
                    reasons=gitleak_result.get("reasons") or [],
                    secret_count=gitleak_result.get(
                        "secret_count",
                        0,
                    ),
                    finding_count=0,
                )

                if gitleaks_decision == "BLOCK":
                    log(
                        "[SECURITY GATE] BLOCK — "
                        "secret détecté par Gitleaks."
                    )
                    raise SecretLeakError(
                        "Secret trouvé dans le dépôt"
                    )

                log(
                    "[SECURITY GATE] PASS — "
                    "aucun secret détecté."
                )

                log("[3/6] Détection du type de projet et génération du Dockerfile...")
                update_pipeline_run(db, history_run_id, PipelineStatus.BUILDING, "Détection et génération du Dockerfile")

                failure_stage = FailReason.DETECTION_ERROR
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

                failure_stage = FailReason.BUILD_ERROR
                build_result = build_docker_image(destination_path, payload.slug, clone_result["commit_hash"], project_type=detect_result)
                log("      Build de l'image terminé avec succès.")

                if is_cancelled():
                    bail_out("Arrêt demandé après le build Docker.")
                    return

                log("[5/6] Analyse des vulnérabilités (Trivy)...")
                update_pipeline_run(db, history_run_id, PipelineStatus.SCANNING, "Scan de sécurité (Trivy)")

                failure_stage = FailReason.SCAN_ERROR
                trivy_result = scan_image(build_result)
                ProjectService.save_scan_results(db, project_id, trivy_result=trivy_result)

                gate_decision = trivy_result.get(
                    "decision",
                    "BLOCK" if trivy_result.get("blocking") else "PASS",
                )
                gate_reasons = trivy_result.get("reasons") or []

                security_audit = SecurityAuditService.create(
                    db=db,
                    project_id=project_id,
                    deployment_run_id=history_run_id,
                    source="trivy",
                    decision=gate_decision,
                    reasons=gate_reasons,
                    severity_count=trivy_result.get(
                        "severity_count"
                    ) or {},
                )

                if gate_decision == "BLOCK":
                    blocking_findings = (
                        trivy_result.get("blocking_findings")
                        or trivy_result.get("critical_vulnerabilities")
                        or []
                    )

                    log(
                        f"[SECURITY GATE] BLOCK — "
                        f"{len(blocking_findings)} "
                        "vulnérabilité(s) bloquante(s)."
                    )

                    for reason_text in gate_reasons:
                        log(f"      Raison: {reason_text}")

                    log(
                        "[SECURITY GATE] En attente de confirmation "
                        "utilisateur (10s max)..."
                    )

                    confirmation = (
                        SecurityConfirmationService.create_pending(
                            db,
                            project_id,
                            blocking_findings,
                            trivy_result["severity_count"],
                            audit_log_id=security_audit.id,
                        )
                    )

                    ProjectService.update_project_status(
                        db,
                        project_id,
                        ProjectStatus.PENDING_SECURITY_CONFIRMATION,
                    )

                    update_pipeline_run(
                        db,
                        history_run_id,
                        PipelineStatus.AWAITING_CONFIRMATION,
                        (
                            "Security Gate BLOCK — "
                            f"{len(blocking_findings)} "
                            "vulnérabilité(s) — "
                            "confirmation requise"
                        ),
                    )

                    decision = (
                        SecurityConfirmationService.wait_for_decision(
                            db,
                            confirmation.id,
                            timeout_seconds=10,
                            is_cancelled=is_cancelled,
                        )
                    )

                    if is_cancelled():
                        SecurityConfirmationService.mark_cancelled(
                            db,
                            confirmation.id,
                        )
                        bail_out(
                            "Arrêt demandé pendant l'attente "
                            "de confirmation sécurité."
                        )
                        return

                    if decision == ConfirmationStatus.CONFIRMED:
                        log(
                            "[SECURITY GATE] BLOCK outrepassé "
                            "explicitement par l'utilisateur."
                        )

                        update_pipeline_run(
                            db,
                            history_run_id,
                            PipelineStatus.SCANNING,
                            (
                                "Security Gate BLOCK confirmé "
                                "par l'utilisateur — reprise"
                            ),
                        )

                    else:
                        reason = (
                            "Refusé par l'utilisateur"
                            if decision
                            == ConfirmationStatus.REJECTED
                            else "Timeout (10s) sans réponse"
                        )

                        log(
                            f"[SECURITY GATE] BLOCK — {reason}"
                        )

                        if (
                            decision
                            == ConfirmationStatus.TIMEOUT
                        ):
                            SecurityConfirmationService.mark_timeout(
                                db,
                                confirmation.id,
                            )

                        raise VulnerabilityError(
                            f"Déploiement bloqué : {reason}",
                            blocking_findings,
                        )

                elif gate_decision == "WARN":
                    log(
                        "[SECURITY GATE] WARN — "
                        "le déploiement peut continuer."
                    )

                    for reason_text in gate_reasons:
                        log(f"      Raison: {reason_text}")

                else:
                    log(
                        "[SECURITY GATE] PASS — "
                        "scan de sécurité validé."
                    )

                if is_cancelled():
                    bail_out("Arrêt demandé avant le déploiement des conteneurs.")
                    return

                log(f"[6/6] Déploiement des conteneurs (réplicas: {payload.replica})...")
                update_pipeline_run(db, history_run_id, PipelineStatus.DEPLOYING, f"Démarrage des {payload.replica} conteneur(s)")

                failure_stage = FailReason.DEPLOY_ERROR
                # Isolation réseau :
                # - réseau privé propre au projet
                # - réseau ingress propre au projet pour Traefik
                project_network = ensure_private_network(payload.slug)
                ingress_network = ensure_ingress_network(payload.slug)

                container_ids = scale_project(
                    build_result,
                    slug=payload.slug,
                    network=project_network,
                    desired_replicas=payload.replica,
                    envs_var=payload.envs_var,
                    extra_networks=[ingress_network],
                    port=get_runtime_port(detect_result, payload.port),
                    security_profile=get_security_profile(detect_result),
                    traefik_network=ingress_network,
                )
                log("      Conteneurs démarrés et connectés au réseau.")

                # Dernier check avant de valider le succès : si annulé pendant le déploiement,
                # ou si un nouveau run a pris le relais, on ne touche pas au statut final.
                if is_cancelled():
                    log("[ANNULÉ] Arrêt demandé pendant le déploiement des conteneurs. Nettoyage...")
                    stop_containers_preserving_evidence(container_ids)
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

                ProjectService.finalize_success(
                    db, project_id,
                    container_ids=container_ids,
                    commit_hash=clone_result["commit_hash"],
                )
                update_pipeline_run(db, history_run_id, PipelineStatus.SUCCESS, "Déploiement terminé avec succès")
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
                if not is_superseded() and hasattr(e, "container_ids"):
                    ProjectService.update_project_container_ids(db, project_id, e.container_ids)
                log(f"[ERREUR] {e}")
                if not is_superseded():
                    update_pipeline_run(db, history_run_id, PipelineStatus.FAILED, f"Erreur déploiement: {e}")
                    ProjectService.mark_failed(db, project_id, str(e), fail_reason=FailReason.DEPLOY_ERROR)
                    db.commit()
            except ValueError as e:
                log(f"[ERREUR] {e}")
                if not is_superseded():
                    update_pipeline_run(db, history_run_id, PipelineStatus.FAILED, f"Erreur valeur: {e}")
                    ProjectService.mark_failed(db, project_id, str(e), fail_reason=failure_stage)
                    db.commit()
            except Exception as e:
                log(f"[ERREUR CRITIQUE] Erreur inattendue: {e}")
                log(traceback.format_exc())
                if not is_superseded():
                    update_pipeline_run(db, history_run_id, PipelineStatus.FAILED, f"Erreur critique: {e}")
                    ProjectService.mark_failed(db, project_id, f"Erreur inattendue: {e}", fail_reason=FailReason.OTHER)
                    db.commit()
            finally:
                shutil.rmtree(destination_path, ignore_errors=True)
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

        with project_deployment_lock(project_id), open(log_file, 'a', encoding='utf-8') as f:
            log = _make_logger(f)

            log(f"[INFO] ==================================================")
            log(f"[INFO] Démarrage du pipeline STACK pour: {slug} (ID: {project_id})")
            log(f"[INFO] Composants à déployer: {len(components)}")
            log(f"[INFO] ==================================================\n")

            db = Session_local()
            project_network = None

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
            failure_stage = FailReason.CLONE_ERROR

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

                if is_cancelled():
                    update_pipeline_run(db, history_run_id, PipelineStatus.FAILED, "Run obsolète ou annulé")
                    return
                project_network = ensure_private_network(slug)
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
                    try:
                        if comp_payload["kind"] == ComponentKind.BACK and any(
                            c["kind"] == ComponentKind.DATABASE for c in components
                        ) and ctx.db_component is None:
                            raise DeployError("Base de données de la stack en échec ; backend non démarré.")
                        deployer.deploy(ctx)
                    except Exception as exc:
                        log(f"[ERREUR COMPOSANT] {ctx.container_name}: {exc}")
                        ProjectService.mark_component_failed(db, component.id, str(exc), FailReason.DEPLOY_ERROR)
                    finally:
                        if ctx.destination_path:
                            shutil.rmtree(ctx.destination_path, ignore_errors=True)
                            ctx.destination_path = None

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

                for comp in all_components:
                    if comp.status == ProjectStatus.RUNNING:
                        try:
                            verify_containers_running(comp.container_ids or [], delay=0)
                        except Exception as exc:
                            ProjectService.mark_component_failed(db, comp.id, str(exc), FailReason.DEPLOY_ERROR)

                if current_project and current_project.status == ProjectStatus.STOPPED:
                    for comp in all_components:
                        if comp.status in (ProjectStatus.BUILDING, ProjectStatus.RUNNING):
                            comp.status = ProjectStatus.STOPPED
                    log(f"[INFO]  Stack annulée. Nettoyage des ressources Docker...")
                    all_container_ids = []
                    for c in all_components:
                        if c.container_ids:
                            all_container_ids.extend(c.container_ids)
                    if all_container_ids:
                        stop_containers_preserving_evidence(all_container_ids)
                    update_pipeline_run(db, history_run_id, PipelineStatus.FAILED, "Stack annulée ; ressources arrêtées et conservées")

                elif all_components and all(c.status == ProjectStatus.RUNNING for c in all_components):
                    ProjectService.update_project_status(db, project_id, ProjectStatus.RUNNING)
                    update_pipeline_run(db, history_run_id, PipelineStatus.SUCCESS, "Stack entièrement déployée et RUNNING")
                    log(f"[INFO]  STACK ENTIÈREMENT DÉPLOYÉE ET RUNNING")
                elif any(c.status == ProjectStatus.FAILED for c in all_components):
                    ProjectService.mark_failed(db, project_id, "Stack partiellement en échec ; consulter les composants et leurs IDs conservés.", FailReason.DEPLOY_ERROR)
                    failed_count = sum(1 for c in all_components if c.status == ProjectStatus.FAILED)
                    update_pipeline_run(db, history_run_id, PipelineStatus.FAILED, f"Stack partiellement en échec ({failed_count} composants)")
                    log(f"[INFO]  STACK PARTIELLEMENT EN ÉCHEC ({failed_count}/{len(all_components)} composants failed)")
                else:
                    ProjectService.mark_failed(db, project_id, "Stack incomplète : tous les composants ne sont pas RUNNING.", FailReason.DEPLOY_ERROR)
                    update_pipeline_run(db, history_run_id, PipelineStatus.FAILED, "Stack incomplète")

                db.commit()  # Sauvegarde finale
                log(f"[INFO] ==================================================\n")

            except Exception as e:
                log(f"[ERREUR CRITIQUE STACK] Échec du déploiement du projet {project_id}")
                log(traceback.format_exc())
                logging.error(f"[ERREUR CRITIQUE STACK] Échec du déploiement du projet {project_id}: {e}")

                try:
                    db.rollback()
                    if not is_superseded():
                        ProjectService.mark_failed(db, project_id, str(e), FailReason.DEPLOY_ERROR)
                        for comp in ProjectService.get_components_by_project(db, project_id):
                            if comp.status == ProjectStatus.BUILDING:
                                ProjectService.mark_component_failed(db, comp.id, "Pipeline interrompu : " + str(e), FailReason.DEPLOY_ERROR)
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
        Préserve les données et preuves, reset le statut et relance le pipeline complet.
        Retourne un tuple (project, is_stack, components, run_id) pour que la route puisse
        lancer le pipeline en background avec le run_id courant.
        """

        project = ProjectService.get_project_by_id(db, project_id, user_id)
        if not project:
            raise ValueError("Projet introuvable")

        # Sérialiser les demandes simultanées et refuser un double Retry.
        project = db.query(Project).filter(Project.id == project_id).with_for_update().populate_existing().one()
        if project.status in (ProjectStatus.BUILDING, ProjectStatus.PENDING_SECURITY_CONFIRMATION):
            raise ValueError("Un déploiement est déjà en cours ; attendez sa fin ou annulez-le.")
        components = ProjectService.get_components_by_project(db, project_id)
        for comp in components:
            if comp.kind == ComponentKind.DATABASE:
                validate_image_reference(comp.db_image)
                comp.expose_publicly = False
            elif comp.expose_publicly is None:
                # Ancien schéma : un port ne signifie pas une exposition publique.
                exposure = set()
                for container_id in comp.container_ids or []:
                    try:
                        old = client.containers.get(container_id)
                        exposure.add((old.attrs.get("Config", {}).get("Labels") or {}).get("traefik.enable") == "true")
                    except docker.errors.NotFound:
                        continue
                if len(exposure) != 1:
                    raise ValueError(f"Exposition inconnue pour l'ancien composant {comp.name}. Renseignez expose_publicly avant Retry ; aucun choix public n'est imposé.")
                comp.expose_publicly = exposure.pop()
        # Aucun nettoyage global : le remplacement cible uniquement les noms
        # canoniques après build/scan. Volumes, images et preuves restent intacts.

        # 2. Réinitialiser le projet en BDD
        # Nouveau pipeline_run_id à chaque retry : tout thread encore actif de l'ancien
        # run verra, à son prochain checkpoint, que run_id ne correspond plus et s'arrêtera,
        # même si le statut n'est pas (encore) STOPPED.
        new_run_id = str(uuid.uuid4())
        project.status = ProjectStatus.BUILDING
        project.error_message = None
        project.fail_reason = None
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
                comp.commit_hash = None
                comp.vulnerabilities = []
                comp.critical_vuln_count = 0

        db.commit()

        return project, is_stack, components, new_run_id
