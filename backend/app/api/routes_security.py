from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.core.security import get_current_user
from app.services.project_service import ProjectService
from app.models.user import User

router = APIRouter()

@router.get("/security")
def list_security_reports(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    projects = ProjectService.get_user_projects(db, current_user.id)
    return [
        {
            "slug": p.slug,
            "status": p.status,
            "fail_reason": p.fail_reason,
            "critical_vuln_count": p.critical_vuln_count,
            "secret_count": p.secret_count,
        }
        for p in projects
    ]
    
    
@router.get("/security/{slug}")
def get_security_report(
    slug: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    project = ProjectService.get_project_by_slug(db, slug)
    if not project or project.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Projet introuvable")

    return {
        "severity_count": project.severity_count or {},
        "secret_count": project.secret_count,
        "secret_found": project.last_secret,
        "critical_vuln_count": project.critical_vuln_count,
        "status": project.status,
        "fail_reason": project.fail_reason,
    }