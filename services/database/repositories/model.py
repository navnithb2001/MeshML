"""
Model repository with specific query methods.
"""
from typing import Optional, List
from sqlalchemy.orm import Session
from services.database.models.model import Model, ModelStatus
from .base import BaseRepository


class ModelRepository(BaseRepository[Model]):
    """Repository for Model (custom PyTorch models)."""
    
    def __init__(self, db: Session):
        super().__init__(Model, db)
    
    def get_by_group(self, group_id: int, status: Optional[ModelStatus] = None) -> List[Model]:
        """
        Get all models for a group.
        
        Args:
            group_id: Group identifier
            status: Optional filter by status
            
        Returns:
            List of models
        """
        filters = {'group_id': group_id}
        if status:
            filters['status'] = status
        
        return self.get_all(
            filters=filters,
            order_by='created_at',
            descending=True
        )
    
    def get_ready_models(self, group_id: int) -> List[Model]:
        """Get all ready-to-use models for a group."""
        return self.get_by_group(group_id, ModelStatus.READY)
    
    def get_by_uploader(self, user_id: int) -> List[Model]:
        """Get all models uploaded by a user."""
        return self.get_all(
            filters={'uploaded_by_id': user_id},
            order_by='created_at',
            descending=True
        )
    
    def set_uploading(self, model_id: int) -> Optional[Model]:
        """Set model status to uploading."""
        return self.update(model_id, status=ModelStatus.UPLOADING)
    
    def set_validating(self, model_id: int) -> Optional[Model]:
        """Set model status to validating."""
        return self.update(model_id, status=ModelStatus.VALIDATING)
    
    def set_ready(self, model_id: int, metadata: dict) -> Optional[Model]:
        """Mark model as ready with metadata."""
        return self.update(
            model_id,
            status=ModelStatus.READY,
            model_metadata=metadata,
            validation_error=None
        )
    
    def set_failed(self, model_id: int, error: str) -> Optional[Model]:
        """Mark model as failed with error message."""
        return self.update(
            model_id,
            status=ModelStatus.FAILED,
            validation_error=error
        )
    
    def set_deprecated(self, model_id: int) -> Optional[Model]:
        """Mark model as deprecated."""
        return self.update(model_id, status=ModelStatus.DEPRECATED)
    
    def get_model_versions(self, parent_model_id: int) -> List[Model]:
        """Get all versions of a model."""
        return self.get_all(
            filters={'parent_model_id': parent_model_id},
            order_by='created_at',
            descending=True
        )
    
    def get_latest_version(self, name: str, group_id: int) -> Optional[Model]:
        """Get latest version of a model by name."""
        models = self.db.query(Model).filter(
            Model.name == name,
            Model.group_id == group_id,
            Model.status == ModelStatus.READY
        ).order_by(Model.created_at.desc()).first()
        
        return models
