from sqlalchemy import exists
from sqlalchemy.orm import Session
from app.models.project import FailReason, Project, ProjectStatus, ProjectComponent, ComponentKind
from app.models.user import User
from datetime import datetime
from typing import List, Dict, Any
import secrets
from app.services.cleanup_service import cleanup_project_resources

class ProjectService:
    """Service pour la gestion des projets en base de données"""
    
    @staticmethod
    def get_user_projects(db: Session, user_id: int) -> List[Project]:
        """
        Récupère tous les projets d'un utilisateur
        """
        return db.query(Project).filter(Project.user_id == user_id).all()
    
    @staticmethod
    def get_project_by_slug(db: Session, slug: str) -> Project | None:
        """
        Récupère un projet par son slug
        """
        return db.query(Project).filter(Project.slug == slug).first()
    
    @staticmethod
    def create_project(
        db: Session,
        user: User,
        slug: str,
        repo_url: str,
        branch: str,
        replica: int,
        env_vars: Dict[str, str],
        container_ids: List[str],
        commit_hash: str,
        status: ProjectStatus = ProjectStatus.RUNNING
    ) -> Project:
        """
        Crée un nouveau projet en base de données
        """
        # Vérifier si un projet avec ce slug existe déjà
        existing = ProjectService.get_project_by_slug(db, slug)
        if existing:
            raise ValueError(f"Un projet avec le nom '{slug}' existe déjà")
        
        # Créer le projet
        new_project = Project(
            user_id=user.id,
            slug=slug,
            repo_url=repo_url,
            branch=branch,
            replica=replica,
            env_vars=env_vars,
            status=status,
            container_ids=container_ids,
            commit_hash=commit_hash,
            created_at=datetime.utcnow()
        )
        
        db.add(new_project)
        db.commit()
        db.refresh(new_project)
        
        return new_project
    
    @staticmethod
    def update_project_status(db: Session, project_id: int, status: ProjectStatus) -> Project | None:
        """
        Met à jour le statut d'un projet
        """
        project = db.query(Project).filter(Project.id == project_id).first()
        if project:
            project.status = status
            project.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(project)
        return project
    
    @staticmethod
    def update_project_container_ids(db: Session, project_id: int, container_ids: List[str]) -> Project | None:
        """
        Met à jour les container IDs d'un projet
        """
        project = db.query(Project).filter(Project.id == project_id).first()
        if project:
            project.container_ids = container_ids
            project.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(project)
        return project
    
    # ======== METHODE SUPPLEMENTAIRE ===============
    
    @staticmethod
    def create_pending_project(
        db: Session,
        user: User,
        slug: str,
        repo_url: str,
        branch: str,
        replica: int,
        env_vars: Dict[str, str],
        port: int = None
    ) -> Project:
        """
        Crée le projet en base immédiatement, statut BUILDING,
        sans container_ids/commit_hash (pas encore connus).
        """
        existing = ProjectService.get_project_by_slug(db, slug)
        if existing:
            raise ValueError(f"Un projet avec le nom '{slug}' existe déjà")

        new_project = Project(
            user_id=user.id,
            slug=slug,
            repo_url=repo_url,
            branch=branch,
            replica=replica,
            env_vars=env_vars,
            status=ProjectStatus.BUILDING,
            container_ids=None,
            commit_hash=None,
            port=port,
            created_at=datetime.utcnow()
        )
        db.add(new_project)
        db.commit()
        db.refresh(new_project)
        return new_project

    @staticmethod
    def finalize_success(db, project_id, container_ids, commit_hash):
        project = db.query(Project).filter(Project.id == project_id).first()
        if project:
            project.status = ProjectStatus.RUNNING
            project.container_ids = container_ids
            project.commit_hash = commit_hash
            project.error_message = None
            project.fail_reason = None
            project.vulnerabilities = []
            project.critical_vuln_count = 0
            project.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(project)
        return project

    @staticmethod
    def mark_failed(
        db: Session,
        project_id: int,
        error_message: str,
        fail_reason: FailReason = FailReason.OTHER,
        vulnerabilities: List[Dict[str, Any]] | None = None,
    ) -> Project | None:
        """
        Marque le projet en échec avec le détail de l'erreur.
        """
        project = db.query(Project).filter(Project.id == project_id).first()
        if project:
            project.status = ProjectStatus.FAILED
            project.error_message = error_message
            project.fail_reason = fail_reason
            if vulnerabilities is not None:
                project.vulnerabilities = vulnerabilities
                project.critical_vuln_count = len(vulnerabilities)
            project.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(project)
        return project

    @staticmethod
    def get_project_by_id(db: Session, project_id: int, user_id: int) -> Project | None:
        """
        Récupère un projet par ID, restreint à son propriétaire.
        """
        return db.query(Project).filter(
            Project.id == project_id,
            Project.user_id == user_id
        ).first()
        
    @staticmethod
    def get_dashboard_stats(db: Session, user_id: int) -> dict:
        total = db.query(Project).filter(Project.user_id == user_id).count()
        running = db.query(Project).filter(
            Project.user_id == user_id, Project.status == ProjectStatus.RUNNING
        ).count()
        failed = db.query(Project).filter(
            Project.user_id == user_id, Project.status == ProjectStatus.FAILED
        ).count()
        failed_vuln = db.query(Project).filter(
            Project.user_id == user_id,
            Project.status == ProjectStatus.FAILED,
            Project.fail_reason == FailReason.VULNERABILITY,
        ).count()

        critical_vuln_percentage = round((failed_vuln / failed) * 100, 1) if failed > 0 else 0.0

        return {
            "total_projects": total,
            "running_projects": running,
            "failed_projects": failed,
            "critical_vuln_percentage": critical_vuln_percentage,
        }
        
    @staticmethod
    def save_scan_results(db: Session, project_id: int, trivy_result: dict = None, gitleak_result: dict = None):
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            return
        if trivy_result is not None:
            project.severity_count = trivy_result["severity_count"]
            project.vulnerabilities = trivy_result["critical_vulnerabilities"]
            project.critical_vuln_count = len(trivy_result["critical_vulnerabilities"])
        if gitleak_result is not None:
            project.secret_count = gitleak_result.get("secret_count", 0)
            project.last_secret = gitleak_result.get("secret_found")
        db.commit()
        
    
    @staticmethod
    def save_component_scan_results(db: Session, component_id: int, trivy_result: dict = None, gitleak_result: dict = None):
        """
        Équivalent de save_scan_results, mais écrit sur un ProjectComponent
        (composant front/back d'une stack) au lieu d'un Project. Même logique exactement.
        """
        component = db.query(ProjectComponent).filter(ProjectComponent.id == component_id).first()
        if not component:
            return
        if trivy_result is not None:
            component.severity_count = trivy_result["severity_count"]
            component.vulnerabilities = trivy_result["critical_vulnerabilities"]
            component.critical_vuln_count = len(trivy_result["critical_vulnerabilities"])
        if gitleak_result is not None:
            component.secret_count = gitleak_result.get("secret_count", 0)
            component.last_secret = gitleak_result.get("secret_found")
        db.commit()

    @staticmethod
    def finalize_component_success(db: Session, component_id: int, container_ids: List[str], commit_hash: str = None) -> "ProjectComponent | None":
        """
        Équivalent de finalize_success, pour un ProjectComponent.
        """
        component = db.query(ProjectComponent).filter(ProjectComponent.id == component_id).first()
        if component:
            component.status = ProjectStatus.RUNNING
            component.container_ids = container_ids
            component.commit_hash = commit_hash
            component.error_message = None
            component.fail_reason = None
            component.vulnerabilities = []
            component.critical_vuln_count = 0
            component.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(component)
        return component

    @staticmethod
    def mark_component_failed(
        db: Session,
        component_id: int,
        error_message: str,
        fail_reason: FailReason = FailReason.OTHER,
        vulnerabilities: List[Dict[str, Any]] | None = None,
    ) -> "ProjectComponent | None":
        """
        Équivalent de mark_failed, pour un ProjectComponent.
        Marque UN composant de la stack en échec (pas toute la stack).
        """
        component = db.query(ProjectComponent).filter(ProjectComponent.id == component_id).first()
        if component:
            component.status = ProjectStatus.FAILED
            component.error_message = error_message
            component.fail_reason = fail_reason
            if vulnerabilities is not None:
                component.vulnerabilities = vulnerabilities
                component.critical_vuln_count = len(vulnerabilities)
            component.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(component)
        return component

    @staticmethod
    def get_component_by_id(db: Session, component_id: int) -> "ProjectComponent | None":
        """
        Récupère un composant par son ID (utilisé dans le pipeline de la stack).
        """
        return db.query(ProjectComponent).filter(ProjectComponent.id == component_id).first()

    @staticmethod
    def get_components_by_project(db: Session, project_id: int) -> List["ProjectComponent"]:
        """
        Récupère tous les composants (front/back/db) d'un projet stack.
        """
        return db.query(ProjectComponent).filter(ProjectComponent.project_id == project_id).all()
    
    

    @staticmethod
    def create_pending_stack(
        db: Session,
        user: User,
        slug: str,
        components: List[Dict[str, Any]],
    ) -> Project:
        """
        Crée le Project parent (statut BUILDING) + un ProjectComponent
        par composant de la stack (front/back/database), tous en BUILDING.
        Équivalent de create_pending_project, mais pour un déploiement multi-service.

        components attendu, une liste de dicts, ex:
        [
            {"name": "front", "kind": ComponentKind.FRONT, "repo_url": "...", "branch": "main", "replica": 1, "env_vars": {...}},
            {"name": "back", "kind": ComponentKind.BACK, "repo_url": "...", "branch": "main", "replica": 1, "env_vars": {...}},
            {"name": "database", "kind": ComponentKind.DATABASE, "db_image": "postgres:16", "volume_name": "vol-monapp", "env_vars": {...}},
        ]
        """
        existing = ProjectService.get_project_by_slug(db, slug)
        if existing:
            raise ValueError(f"Un projet avec le nom '{slug}' existe déjà")

        # Repo "principal" affiché sur le Project parent : le premier composant
        # applicatif (FRONT ou BACK) de la liste. Purement informatif — la vraie
        # donnée par service vit dans ProjectComponent.
        primary = next((c for c in components if c["kind"] != ComponentKind.DATABASE), None)
        if not primary:
            raise ValueError("Une stack doit contenir au moins un composant applicatif (front ou back)")

        new_project = Project(
            user_id=user.id,
            slug=slug,
            repo_url=primary["repo_url"],
            branch=primary.get("branch", "main"),
            replica=1,          # non significatif au niveau stack, chaque composant a le sien
            env_vars={},        # idem : les vraies env_vars sont sur chaque ProjectComponent
            status=ProjectStatus.BUILDING,
            container_ids=None,
            commit_hash=None,
            created_at=datetime.utcnow()
        )
        db.add(new_project)
        db.commit()
        db.refresh(new_project)

        # Un ProjectComponent par composant déclaré
        for c in components:
            component = ProjectComponent(
                project_id=new_project.id,
                name=c["name"],
                kind=c["kind"],
                status=ProjectStatus.BUILDING,
                repo_url=c.get("repo_url"),
                branch=c.get("branch", "main") if c["kind"] != ComponentKind.DATABASE else None,
                replica=c.get("replica", 1),
                env_vars=c.get("env_vars", {}),
                db_image=c.get("db_image"),
                volume_name=c.get("volume_name"),
                port=c.get("port"),
                created_at=datetime.utcnow()
            )
            db.add(component)

        db.commit()
        db.refresh(new_project)  # recharge new_project.services via la relation

        return new_project
    
    @staticmethod
    def generate_db_credentials(db, component_id, slug: str):
        """
        Génère et persiste des credentials DB aléatoires pour un ProjectComponent
        de type DATABASE. Appelé une seule fois, jamais ressaisi par l'utilisateur.
        """
        component = ProjectService.get_component_by_id(db, component_id)
        if component is None:
            return None

        component.db_user = f"{slug}_user"
        component.db_name = f"{slug}_db"
        component.db_password = secrets.token_urlsafe(24)
        component.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(component)
        return component
    
    
    # project_service.py
    @staticmethod
    def get_user_stacks(db: Session, user_id: int) -> List[Project]:
        """Récupère tous les projets 'stack' (avec au moins un ProjectComponent) d'un utilisateur."""
        # Sous-requête : "existe-t-il au moins un ProjectComponent pour ce projet ?"
        has_components = exists().where(ProjectComponent.project_id == Project.id)
        
        return (
            db.query(Project)
            .filter(Project.user_id == user_id)
            .filter(has_components)  # Plus de JOIN, plus de DISTINCT, plus de problème JSON !
            .all()
        )
        
     
    @staticmethod
    def delete_project_and_containers(db: Session, project_id: int, user_id: int) -> bool:
        """
        Supprime un projet (ou une stack) : 
        1. Nettoie TOUTES les ressources Docker associées (conteneurs, volumes, images, réseaux).
        2. Supprime l'entrée en base de données (cascade vers les composants).
        """
        project = db.query(Project).filter(Project.id == project_id, Project.user_id == user_id).first()
        if not project:
            return False

        # 1. Collecter tous les IDs de conteneurs (projet parent + composants)
        container_ids_to_clean = list(project.container_ids or [])
        components = ProjectService.get_components_by_project(db, project_id)
        for comp in components:
            if comp.container_ids:
                container_ids_to_clean.extend(comp.container_ids)

        # 2. Nettoyer les ressources Docker via le service dédié (conteneurs, volumes, images, réseaux)
        
        cleanup_project_resources(project.slug, container_ids_to_clean)

        # 3. Suppression en base de données (le cascade delete s'occupe des ProjectComponent)
        db.delete(project)
        db.commit()
        return True