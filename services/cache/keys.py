"""
Redis key naming conventions and constants.
"""

class RedisKeys:
    """Centralized Redis key naming conventions."""
    
    # Heartbeat keys: heartbeat:worker:{worker_id}
    @staticmethod
    def heartbeat(worker_id: str) -> str:
        """Worker heartbeat key with TTL."""
        return f"heartbeat:worker:{worker_id}"
    
    # Global weights keys: weights:global:{job_id}:{version}
    @staticmethod
    def global_weights(job_id: int, version: int) -> str:
        """Global model weights for a specific job and version."""
        return f"weights:global:{job_id}:{version}"
    
    # Latest weights pointer: weights:latest:{job_id}
    @staticmethod
    def latest_weights(job_id: int) -> str:
        """Pointer to latest weights version."""
        return f"weights:latest:{job_id}"
    
    # Version map: version:map:{job_id}
    @staticmethod
    def version_map(job_id: int) -> str:
        """Version history map (sorted set with timestamps)."""
        return f"version:map:{job_id}"
    
    # Worker assignment: assignment:worker:{worker_id}
    @staticmethod
    def worker_assignment(worker_id: str) -> str:
        """Current batch assignment for worker."""
        return f"assignment:worker:{worker_id}"
    
    # Job status cache: job:status:{job_id}
    @staticmethod
    def job_status(job_id: int) -> str:
        """Cached job status and progress."""
        return f"job:status:{job_id}"
    
    # Active workers set: workers:active:{job_id}
    @staticmethod
    def active_workers(job_id: int) -> str:
        """Set of active worker IDs for a job."""
        return f"workers:active:{job_id}"
    
    # Gradient accumulation buffer: gradients:buffer:{job_id}:{worker_id}
    @staticmethod
    def gradient_buffer(job_id: int, worker_id: str) -> str:
        """Temporary gradient storage before aggregation."""
        return f"gradients:buffer:{job_id}:{worker_id}"
    
    # Model metadata cache: model:meta:{model_id}
    @staticmethod
    def model_metadata(model_id: int) -> str:
        """Cached model metadata from database."""
        return f"model:meta:{model_id}"
    
    # Lock keys: lock:{resource}:{id}
    @staticmethod
    def lock(resource: str, resource_id: str) -> str:
        """Distributed lock for resource coordination."""
        return f"lock:{resource}:{resource_id}"


class RedisTTL:
    """TTL constants (in seconds)."""
    
    HEARTBEAT = 30  # 30 seconds
    GLOBAL_WEIGHTS = 3600  # 1 hour
    VERSION_MAP = 86400  # 24 hours
    JOB_STATUS = 60  # 1 minute
    GRADIENT_BUFFER = 300  # 5 minutes
    MODEL_METADATA = 3600  # 1 hour
    LOCK = 30  # 30 seconds
