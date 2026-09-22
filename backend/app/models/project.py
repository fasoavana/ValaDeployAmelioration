#app/models/project.py
from sqlalchemy import Column, ForeignKey, Integer, String, DateTime, JSON, Enum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.database import Base
import enum

class ProjectStatus(str, enum.Enum):
    RUNNING = "running"
    STOPPED = "stopped"
    BUILDING = "building"
    FAILED = "failed"
    
class ComponentKind(str, enum.Enum):
    FRONT = "front"
    BACK = "back"
    DATABASE = "database"


class FailReason(str, enum.Enum):
    VULNERABILITY = "vulnerability"
    SECRET_LEAK = "secret_leak"
    BUILD_ERROR = "build_error"
    CLONE_ERROR = "clone_error"
    DEPLOY_ERROR = "deploy_error"
    DETECTION_ERROR = "detection_error"
    SCAN_ERROR = "scan_error"
    OTHER = "other"

class Project(Base):
    __tablename__ = "projects"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True, nullable=False)
    slug = Column(String, unique=True, index=True, nullable=False)
    repo_url = Column(String, nullable=False)
    branch = Column(String, nullable=False, default="main")
    replica = Column(Integer, nullable=False, default=1)
    env_vars = Column(JSON, nullable=False, default=dict)
    port = Column(Integer, nullable=True)
    
    status = Column(Enum(ProjectStatus), nullable=False, default=ProjectStatus.BUILDING)
    pipeline_run_id = Column(String, nullable=True) # pour les threads de suivi du pipeline, on stocke l'ID du run actuel (ou None si pas de pipeline en cours)
    container_ids = Column(JSON, nullable=True)  # liste des container IDs
    commit_hash = Column(String, nullable=True)
    error_message = Column(String, nullable=True)
    fail_reason = Column(Enum(FailReason), nullable=True)
    
    vulnerabilities = Column(JSON, nullable=True, default=list)  # detail des vulns critiques
    critical_vuln_count = Column(Integer, nullable=False, default=0)
    severity_count = Column(JSON, nullable=True, default=dict)
    secret_count = Column(Integer, nullable=False, default=0)
    last_secret = Column(JSON, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    services = relationship("ProjectComponent", back_populates="project", cascade="all, delete-orphan")
    deployment_runs = relationship("DeploymentRun", back_populates="project", cascade="all, delete-orphan")

class ProjectComponent(Base):
    """
    Représente UN composant d'une stack multi-service (front, back ou database).
    Un Project peut avoir plusieurs ProjectService (relation one-to-many).
    Pour un déploiement mono-service classique (existant), cette table n'est pas utilisée :
    Project continue de fonctionner exactement comme avant, seul.
    """
    __tablename__ = "project_services"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)

    name = Column(String, nullable=False)               # ex: "front", "back", "database" (affichage)
    kind = Column(Enum(ComponentKind), nullable=False)     # FRONT / BACK / DATABASE (liste fermée)

    # --- Réutilise ProjectStatus existant (BUILDING, RUNNING, FAILED...) ---
    # Plus élégant : un ProjectService "est" un mini-déploiement, mêmes états possibles.
    status = Column(Enum(ProjectStatus), nullable=False, default=ProjectStatus.BUILDING)

    # --- Champs pour un service applicatif (FRONT / BACK) ---
    repo_url = Column(String, nullable=True)             # null si kind == DATABASE
    branch = Column(String, nullable=True, default="main")
    replica = Column(Integer, nullable=False, default=1)
    container_ids = Column(JSON, nullable=True)          # liste des container IDs (comme sur Project)
    commit_hash = Column(String, nullable=True)
    env_vars = Column(JSON, nullable=False, default=dict)
    port = Column(Integer, nullable=True) 

    # --- Champs pour un service DATABASE uniquement ---
    db_image = Column(String, nullable=True)             # ex: "postgres:16", null si pas une DB
    volume_name = Column(String, nullable=True)           # nom du volume Docker pour la persistance

    db_user = Column(String, nullable=True)
    db_password = Column(String, nullable=True)      # généré, jamais saisi par l'utilisateur
    db_name = Column(String, nullable=True)
    
    # --- Résultats de scan sécurité, copiés depuis Project (mêmes noms, même forme) ---
    # Null pour un service DATABASE (pas de scan Trivy/Gitleaks sur une image officielle).
    vulnerabilities = Column(JSON, nullable=True, default=list)
    critical_vuln_count = Column(Integer, nullable=False, default=0)
    severity_count = Column(JSON, nullable=True, default=dict)
    secret_count = Column(Integer, nullable=False, default=0)
    last_secret = Column(JSON, nullable=True)

    error_message = Column(String, nullable=True)
    fail_reason = Column(Enum(FailReason), nullable=True)  # réutilise l'enum existant aussi

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relation retour vers Project
    project = relationship("Project", back_populates="services")