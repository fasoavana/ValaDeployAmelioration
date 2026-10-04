#app/api/routes_security.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.core.security import get_current_user
from app.services.project_service import ProjectService
from app.models.user import User

from app.services.security_confirmation_service import SecurityConfirmationService
from app.services.security_audit_service import SecurityAuditService

from app.models.project import ProjectComponent
from app.services.vulnerability_scan_service import (
    VulnerabilityScanService,
)
from app.models.security_confirmation import ConfirmationStatus
from app.models.project import ComponentKind, FailReason


router = APIRouter()


SEVERITIES = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "UNKNOWN"]
BLOCKING = {FailReason.VULNERABILITY, FailReason.SECRET_LEAK}


def _scanned_sources(project):
    """Composants scannés d'une stack (DB exclue), sinon le projet lui-même."""
    comps = [c for c in project.services if c.kind != ComponentKind.DATABASE]
    return comps or [project]


def _component_report(name: str, role: str, src) -> dict:
    raw = src.vulnerabilities or []
    grouped = {s: [] for s in SEVERITIES}
    if isinstance(raw, dict):            # futur format (chantier 2)
        for s in SEVERITIES:
            grouped[s] = raw.get(s, [])
    else:                                # format actuel : CRITICAL seulement
        grouped["CRITICAL"] = raw
    return {
        "id": getattr(src, "id", None),
        "name": name,
        "role": role,
        "severity_count": src.severity_count or {},
        "vulnerabilities": grouped,
        "secret_count": src.secret_count,
        "secret_found": src.last_secret,
        "fail_reason": src.fail_reason.value if src.fail_reason else None,
        "blocked": src.fail_reason in BLOCKING,
    }


@router.get("/security")
def list_security_reports(db: Session = Depends(get_db),
                          current_user: User = Depends(get_current_user)):
    result = []
    for p in ProjectService.get_user_projects(db, current_user.id):
        sources = _scanned_sources(p)
        result.append({
            "slug": p.slug,
            "status": p.status.value,
            "is_stack": bool(p.services),
            "fail_reason": p.fail_reason.value if p.fail_reason else None,
            "blocked": any(x.fail_reason in BLOCKING for x in [p, *sources]),
            "critical_vuln_count": sum(s.critical_vuln_count or 0 for s in sources),
            "secret_count": sum(s.secret_count or 0 for s in sources),
        })
    return result


@router.get("/security/{slug}")
def get_security_report(slug: str, db: Session = Depends(get_db),
                        current_user: User = Depends(get_current_user)):
    project = ProjectService.get_project_by_slug(db, slug)
    focus = None

    # Filet de sécurité : anciens liens "fao-front" -> projet "fao", composant "front"
    if not project:
        for p in ProjectService.get_user_projects(db, current_user.id):
            prefix = p.slug + "-"
            if slug.startswith(prefix) and any(c.name == slug[len(prefix):] for c in p.services):
                project, focus = p, slug[len(prefix):]
                break

    if not project or project.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Projet introuvable")

    scanned = [c for c in project.services if c.kind != ComponentKind.DATABASE]
    if scanned:
        components = [_component_report(c.name, c.kind.value, c) for c in scanned]
    else:
        components = [_component_report(project.slug, "app", project)]

    return {
        "project_id": project.id,
        "slug": project.slug,
        "status": project.status.value,
        #"is_stack": len(components) > 1,
        "is_stack": bool(project.services),
        "blocked": any(c["blocked"] for c in components),
        "focus": focus,
        "components": components,
    }

@router.get("/security/{project_id}/pending-confirmation")
def get_pending_confirmation(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Utilisé par le front pour savoir s'il doit afficher le popup, et pour
    peupler la page de détails des vulnérabilités.
    """
    project = ProjectService.get_project_by_id(db, project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=404, detail="Projet introuvable")

    confirmation = SecurityConfirmationService.get_pending_for_project(db, project_id)
    if not confirmation:
        return {"pending": False}

    return {
        "pending": True,
        "confirmation_id": confirmation.id,
        "audit_log_id": confirmation.audit_log_id,
        "blocking_findings": confirmation.critical_vulnerabilities,
        # Compatibilité avec l'ancien frontend/API.
        "critical_vulnerabilities": confirmation.critical_vulnerabilities,
        "severity_count": confirmation.severity_count,
        "created_at": confirmation.created_at.isoformat() if confirmation.created_at else None,
    }


@router.post("/security/{project_id}/confirm")
def confirm_deployment(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    project = ProjectService.get_project_by_id(db, project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=404, detail="Projet introuvable")

    confirmation = SecurityConfirmationService.get_pending_for_project(db, project_id)
    if not confirmation:
        raise HTTPException(status_code=404, detail="Aucune confirmation en attente pour ce projet.")

    SecurityConfirmationService.mark_confirmed(
        db,
        confirmation.id,
        resolved_by_user_id=current_user.id,
    )
    return {"message": "Déploiement confirmé, reprise du pipeline en cours."}


@router.post("/security/{project_id}/reject")
def reject_deployment(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    project = ProjectService.get_project_by_id(db, project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=404, detail="Projet introuvable")

    confirmation = SecurityConfirmationService.get_pending_for_project(db, project_id)
    if not confirmation:
        raise HTTPException(status_code=404, detail="Aucune confirmation en attente pour ce projet.")

    SecurityConfirmationService.mark_rejected(
        db,
        confirmation.id,
        resolved_by_user_id=current_user.id,
    )
    return {"message": "Déploiement annulé."}


@router.get("/security/{project_id}/audit")
def get_security_audit(
    project_id: int,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Journal d'audit persistant du Security Gate v2."""

    project = ProjectService.get_project_by_id(
        db,
        project_id,
        current_user.id,
    )

    if not project:
        raise HTTPException(
            status_code=404,
            detail="Projet introuvable",
        )

    entries = SecurityAuditService.list_for_project(
        db,
        project_id,
        limit=limit,
    )

    return [
        {
            "id": item.id,
            "project_id": item.project_id,
            "component_id": item.component_id,
            "deployment_run_id": item.deployment_run_id,
            "user_id": item.user_id,
            "source": item.source,
            "decision": item.decision,
            "reasons": item.reasons or [],
            "severity_count": item.severity_count or {},
            "finding_count": item.finding_count,
            "secret_count": item.secret_count,
            "confirmation_outcome": (
                item.confirmation_outcome
            ),
            "resolved_by_user_id": (
                item.resolved_by_user_id
            ),
            "created_at": (
                item.created_at.isoformat()
                if item.created_at
                else None
            ),
            "resolved_at": (
                item.resolved_at.isoformat()
                if item.resolved_at
                else None
            ),
        }
        for item in entries
    ]


# ============================================================
# Continuous Vulnerability Monitoring
# ============================================================

def _owned_component(
    db: Session,
    project,
    component_id: int,
):
    component = (
        db.query(ProjectComponent)
        .filter(
            ProjectComponent.id
            == component_id,
            ProjectComponent.project_id
            == project.id,
        )
        .first()
    )

    if component is None:
        raise HTTPException(
            status_code=404,
            detail="Composant introuvable",
        )

    if component.kind == ComponentKind.DATABASE:
        raise HTTPException(
            status_code=400,
            detail=(
                "Les composants DATABASE ne sont "
                "pas rescannés par ce mécanisme."
            ),
        )

    return component


@router.get("/security/{project_id}/scans")
def get_vulnerability_scan_history(
    project_id: int,
    component_id: int | None = None,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        get_current_user
    ),
):
    """
    Historique immuable des scans Trivy.
    """

    project = ProjectService.get_project_by_id(
        db,
        project_id,
        current_user.id,
    )

    if not project:
        raise HTTPException(
            status_code=404,
            detail="Projet introuvable",
        )

    if component_id is not None:
        _owned_component(
            db,
            project,
            component_id,
        )

    scans = (
        VulnerabilityScanService.list_for_project(
            db,
            project.id,
            component_id=component_id,
            limit=limit,
        )
    )

    return [
        VulnerabilityScanService.serialize(
            scan
        )
        for scan in scans
    ]


@router.get(
    "/security/{project_id}/scans/compare"
)
def compare_vulnerability_scans(
    project_id: int,
    older_scan_id: int | None = None,
    newer_scan_id: int | None = None,
    component_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        get_current_user
    ),
):
    """
    Compare deux snapshots.

    Si les IDs ne sont pas fournis, compare les
    deux derniers scans de la cible.
    """

    project = ProjectService.get_project_by_id(
        db,
        project_id,
        current_user.id,
    )

    if not project:
        raise HTTPException(
            status_code=404,
            detail="Projet introuvable",
        )

    if (
        (older_scan_id is None)
        != (newer_scan_id is None)
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "older_scan_id et newer_scan_id "
                "doivent être fournis ensemble."
            ),
        )

    # ----------------------------------------------
    # Comparaison explicite de deux scans
    # ----------------------------------------------
    if older_scan_id is not None:
        older = (
            VulnerabilityScanService.get_by_id(
                db,
                older_scan_id,
            )
        )

        newer = (
            VulnerabilityScanService.get_by_id(
                db,
                newer_scan_id,
            )
        )

        if (
            older is None
            or newer is None
            or older.project_id != project.id
            or newer.project_id != project.id
        ):
            raise HTTPException(
                status_code=404,
                detail="Scan introuvable",
            )

        if (
            older.component_id
            != newer.component_id
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    "Les deux scans doivent "
                    "concerner la même cible."
                ),
            )

    # ----------------------------------------------
    # Comparaison automatique N-1 / N
    # ----------------------------------------------
    else:
        target_component_id = component_id

        scanned_components = [
            component
            for component in project.services
            if (
                component.kind
                != ComponentKind.DATABASE
            )
        ]

        if component_id is not None:
            _owned_component(
                db,
                project,
                component_id,
            )

        elif scanned_components:
            if len(scanned_components) > 1:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "component_id est requis "
                        "pour une stack contenant "
                        "plusieurs composants "
                        "applicatifs."
                    ),
                )

            target_component_id = (
                scanned_components[0].id
            )

        scans = (
            VulnerabilityScanService
            .list_for_project(
                db,
                project.id,
                component_id=(
                    target_component_id
                ),
                limit=2,
            )
        )

        if len(scans) < 2:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Au moins deux scans sont "
                    "nécessaires pour comparer."
                ),
            )

        newer = scans[0]
        older = scans[1]

    comparison = (
        VulnerabilityScanService.compare(
            older,
            newer,
        )
    )

    return {
        **comparison,
        "older_scan": (
            VulnerabilityScanService
            .serialize(older)
        ),
        "newer_scan": (
            VulnerabilityScanService
            .serialize(newer)
        ),
    }


@router.post("/security/{project_id}/rescan")
def rescan_deployed_application(
    project_id: int,
    component_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        get_current_user
    ),
):
    """
    Re-scan manuel de l'image réellement déployée.

    Pour une stack :
    - component_id fourni -> un composant ;
    - component_id absent -> tous les composants
      applicatifs non DATABASE.
    """

    project = ProjectService.get_project_by_id(
        db,
        project_id,
        current_user.id,
    )

    if not project:
        raise HTTPException(
            status_code=404,
            detail="Projet introuvable",
        )

    app_components = [
        component
        for component in project.services
        if (
            component.kind
            != ComponentKind.DATABASE
        )
    ]

    # Stack
    if app_components:
        if component_id is not None:
            targets = [
                _owned_component(
                    db,
                    project,
                    component_id,
                )
            ]
        else:
            targets = app_components

    # Mono-projet
    else:
        if component_id is not None:
            raise HTTPException(
                status_code=400,
                detail=(
                    "component_id n'est pas "
                    "applicable à ce projet "
                    "mono-service."
                ),
            )

        targets = [None]

    results = []

    for component in targets:
        try:
            result = (
                VulnerabilityScanService
                .manual_rescan(
                    db,
                    project=project,
                    component=component,
                    triggered_by_user_id=(
                        current_user.id
                    ),
                )
            )

        except LookupError as exc:
            raise HTTPException(
                status_code=409,
                detail=str(exc),
            ) from exc

        except ValueError as exc:
            raise HTTPException(
                status_code=502,
                detail=(
                    "Le re-scan Trivy a échoué : "
                    f"{exc}"
                ),
            ) from exc

        snapshot = result["scan"]

        results.append({
            "component_id": (
                component.id
                if component is not None
                else None
            ),
            "component_name": (
                component.name
                if component is not None
                else project.slug
            ),
            "scan": (
                VulnerabilityScanService
                .serialize(snapshot)
            ),
            "comparison": (
                result["comparison"]
            ),
        })

    return {
        "project_id": project.id,
        "trigger": "manual",
        "results": results,
    }
