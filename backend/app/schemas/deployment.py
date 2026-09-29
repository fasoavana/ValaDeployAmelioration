from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional
from app.models.deployment import PipelineStatus, DeploymentTrigger

class DeploymentRunResponse(BaseModel):
    id: int
    project_id: int
    trigger: DeploymentTrigger
    status: PipelineStatus
    commit_hash: Optional[str] = None
    started_at: datetime
    finished_at: Optional[datetime] = None
    logs: Optional[str] = None

    # Propriété calculée pour afficher la durée dans le frontend
    @property
    def duration_seconds(self) -> Optional[int]:
        if self.started_at and self.finished_at:
            # Gestion des timezone-aware datetimes
            start = self.started_at.replace(tzinfo=None) if self.started_at.tzinfo else self.started_at
            finish = self.finished_at.replace(tzinfo=None) if self.finished_at.tzinfo else self.finished_at
            return int((finish - start).total_seconds())
        return None

    model_config = ConfigDict(from_attributes=True)