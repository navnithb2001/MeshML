"""Database models for Metrics Service."""

from sqlalchemy import Column, String, Integer, Float, DateTime, func

from app.db import Base


class MetricPoint(Base):
    __tablename__ = "metrics"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String, nullable=False, index=True)
    step = Column(Integer, nullable=False, index=True)
    loss = Column(Float, nullable=True)
    accuracy = Column(Float, nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
