from sqlalchemy import Column, Integer, String, Text, DateTime, Enum, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.database import Base
import enum

class PipelineStatus(str, enum.Enum):
    PENDING = "pending"
    CLONING = "cloning"
    BUILDING = "building"
    SCANNING = "scanning"
    DEPLOYING = "deploying"
    SUCCESS = "success"
    FAILED = "failed"

class DeploymentTrigger(str, enum.Enum):
    MANUAL = "manual"
    WEBHOOK = "webhook"

class DeploymentRun(Base):
    __tablename__ = "deployment_runs"
    
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True) # Null si déclenché par webhook
    
    trigger = Column(Enum(DeploymentTrigger), nullable=False, default=DeploymentTrigger.MANUAL)
    status = Column(Enum(PipelineStatus), nullable=False, default=PipelineStatus.PENDING)
    
    commit_hash = Column(String(40), nullable=True) # Hash du commit déclencheur
    logs = Column(Text, nullable=True, default="")  # Accumulation des logs d'étape
    
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    finished_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relations
    project = relationship("Project", back_populates="deployment_runs")
    user = relationship("User")