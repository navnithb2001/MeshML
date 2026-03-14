"""Dataset Sharder DB models."""

from sqlalchemy import Column, String, DateTime
from datetime import datetime

from app.db import Base


class DataBatch(Base):
    __tablename__ = "data_batches"

    id = Column(String(255), primary_key=True)
    job_id = Column(String(255), nullable=False, index=True)
    model_id = Column(String(255), nullable=False, index=True)
    gcs_path = Column(String(1024), nullable=True)
    status = Column(String(50), nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
