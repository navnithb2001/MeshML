"""Background validation task utilities."""

import logging
from sqlalchemy.orm import Session

from app.models.model import ModelStatus
from app.crud.model import update_model_status
from app.services.model_validator import validate_model_file

logger = logging.getLogger(__name__)


async def trigger_model_validation(
    db: Session,
    model_id: int,
    gcs_path: str,
    skip_instantiation: bool = False
) -> None:
    """
    Trigger model validation workflow.
    
    This function should be called after a model file is uploaded to GCS.
    It can be executed synchronously or as a background task.
    
    Args:
        db: Database session
        model_id: Model ID to validate
        gcs_path: GCS path to model.py file
        skip_instantiation: Skip model instantiation test
    """
    logger.info(f"Triggering validation for model {model_id}")
    
    # Update status to VALIDATING
    await update_model_status(
        db=db,
        model_id=model_id,
        status=ModelStatus.VALIDATING,
        validation_error=None
    )
    
    try:
        # Run validation
        is_valid, metadata, error_message, validation_details = await validate_model_file(
            model_id=model_id,
            gcs_path=gcs_path,
            skip_instantiation=skip_instantiation
        )
        
        if is_valid:
            # Validation passed - update to READY
            # Store validation details in metadata
            if metadata:
                metadata["validation"] = validation_details
            
            await update_model_status(
                db=db,
                model_id=model_id,
                status=ModelStatus.READY,
                validation_error=None,
                model_metadata=metadata
            )
            logger.info(f"Model {model_id} validation successful - status set to READY")
        else:
            # Validation failed - update to FAILED
            await update_model_status(
                db=db,
                model_id=model_id,
                status=ModelStatus.FAILED,
                validation_error=error_message,
                model_metadata={"validation": validation_details}
            )
            logger.warning(f"Model {model_id} validation failed: {error_message}")
            
    except Exception as e:
        # Unexpected error during validation
        logger.error(f"Unexpected error validating model {model_id}: {e}")
        await update_model_status(
            db=db,
            model_id=model_id,
            status=ModelStatus.FAILED,
            validation_error=f"Validation error: {str(e)}"
        )
