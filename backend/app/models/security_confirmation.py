# app/models/security_confirmation.py
import enum
from sqlalchemy import Column, Integer, DateTime, JSON, Enum, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.database import Base


class ConfirmationStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    TIMEOUT = "timeout"


class SecurityConfirmation(Base):
    """
    Table séparée de `projects` : stocke la demande de confirmation quand une
    faille CRITICAL patchable est détectée. On laisse la main à l'utilisateur
    (continuer / annuler) au lieu de bloquer automatiquement.

    Volontairement isolée de Project.vulnerabilities : ça permet de wipe cette
    table indépendamment (ex: après refus) sans toucher aux scans "normaux",
    et sans migration risquée sur `projects`.
    """
    __tablename__ = "security_confirmations"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)

    status = Column(Enum(ConfirmationStatus), nullable=False, default=ConfirmationStatus.PENDING)

    # Snapshot du scan au moment de la détection (pas une référence vivante à
    # Project.vulnerabilities, qui peut être écrasé par un retry entre-temps).
    critical_vulnerabilities = Column(JSON, nullable=False, default=list)
    severity_count = Column(JSON, nullable=True, default=dict)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    project = relationship("Project", back_populates="security_confirmations")