#app/api/routes_security.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.core.security import get_current_user
from app.services.project_service import ProjectService
from app.models.user import User

from app.services.security_confirmation_service import SecurityConfirmationService
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

    SecurityConfirmationService.mark_confirmed(db, confirmation.id)
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

    SecurityConfirmationService.mark_rejected(db, confirmation.id)
    return {"message": "Déploiement annulé."}