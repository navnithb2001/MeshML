"""
Redis client wrapper with connection pooling and helper methods.
"""
import redis
from redis.connection import ConnectionPool
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from .config import settings
from .keys import RedisKeys, RedisTTL
from .serializers import WeightsSerializer, GradientSerializer, MetadataSerializer
import json


class RedisClient:
    """Thread-safe Redis client with connection pooling."""
    
    _instance: Optional['RedisClient'] = None
    _pool: Optional[ConnectionPool] = None
    
    def __new__(cls):
        """Singleton pattern to reuse connection pool."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize Redis connection pool."""
        if self._pool is None:
            self._pool = ConnectionPool(
                host=settings.redis_host,
                port=settings.redis_port,
                password=settings.redis_password,
                db=settings.redis_db,
                max_connections=settings.redis_max_connections,
                socket_timeout=settings.redis_socket_timeout,
                socket_connect_timeout=settings.redis_socket_connect_timeout,
                decode_responses=False,  # We handle binary data
            )
    
    @property
    def client(self) -> redis.Redis:
        """Get Redis client from pool."""
        return redis.Redis(connection_pool=self._pool)
    
    def ping(self) -> bool:
        """Check if Redis connection is alive."""
        try:
            return self.client.ping()
        except redis.ConnectionError:
            return False
    
    # ============= Heartbeat Operations =============
    
    def set_heartbeat(self, worker_id: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Set worker heartbeat with TTL.
        
        Args:
            worker_id: Unique worker identifier
            metadata: Optional worker metadata (status, current_task, etc.)
            
        Returns:
            True if successful
        """
        key = RedisKeys.heartbeat(worker_id)
        value = json.dumps(metadata or {'timestamp': datetime.utcnow().isoformat()})
        return self.client.setex(key, settings.heartbeat_ttl, value)
    
    def get_heartbeat(self, worker_id: str) -> Optional[Dict[str, Any]]:
        """
        Get worker heartbeat data.
        
        Args:
            worker_id: Unique worker identifier
            
        Returns:
            Heartbeat metadata or None if expired
        """
        key = RedisKeys.heartbeat(worker_id)
        data = self.client.get(key)
        if data:
            return json.loads(data.decode('utf-8'))
        return None
    
    def is_worker_alive(self, worker_id: str) -> bool:
        """
        Check if worker is alive (heartbeat exists).
        
        Args:
            worker_id: Unique worker identifier
            
        Returns:
            True if heartbeat exists
        """
        key = RedisKeys.heartbeat(worker_id)
        return self.client.exists(key) > 0
    
    def get_all_active_workers(self, job_id: int) -> List[str]:
        """
        Get all active worker IDs for a job.
        
        Args:
            job_id: Job identifier
            
        Returns:
            List of active worker IDs
        """
        key = RedisKeys.active_workers(job_id)
        members = self.client.smembers(key)
        return [m.decode('utf-8') for m in members]
    
    def add_active_worker(self, job_id: int, worker_id: str) -> bool:
        """Add worker to active workers set."""
        key = RedisKeys.active_workers(job_id)
        return self.client.sadd(key, worker_id) > 0
    
    def remove_active_worker(self, job_id: int, worker_id: str) -> bool:
        """Remove worker from active workers set."""
        key = RedisKeys.active_workers(job_id)
        return self.client.srem(key, worker_id) > 0
    
    # ============= Global Weights Operations =============
    
    def set_global_weights(
        self,
        job_id: int,
        version: int,
        weights: Dict[str, Any],
        ttl: Optional[int] = None
    ) -> bool:
        """
        Store global model weights for a specific version.
        
        Args:
            job_id: Job identifier
            version: Weight version number
            weights: Dictionary of layer_name -> numpy array
            ttl: Time-to-live in seconds (default: settings.global_weights_ttl)
            
        Returns:
            True if successful
        """
        key = RedisKeys.global_weights(job_id, version)
        binary = WeightsSerializer.serialize(weights)
        ttl = ttl or settings.global_weights_ttl
        return self.client.setex(key, ttl, binary)
    
    def get_global_weights(self, job_id: int, version: int) -> Optional[Dict[str, Any]]:
        """
        Retrieve global model weights for a specific version.
        
        Args:
            job_id: Job identifier
            version: Weight version number
            
        Returns:
            Dictionary of layer_name -> numpy array or None
        """
        key = RedisKeys.global_weights(job_id, version)
        binary = self.client.get(key)
        if binary:
            return WeightsSerializer.deserialize(binary)
        return None
    
    def set_latest_weights_version(self, job_id: int, version: int) -> bool:
        """
        Update pointer to latest weights version.
        
        Args:
            job_id: Job identifier
            version: Latest version number
            
        Returns:
            True if successful
        """
        key = RedisKeys.latest_weights(job_id)
        return self.client.set(key, str(version))
    
    def get_latest_weights_version(self, job_id: int) -> Optional[int]:
        """
        Get latest weights version number.
        
        Args:
            job_id: Job identifier
            
        Returns:
            Latest version number or None
        """
        key = RedisKeys.latest_weights(job_id)
        version = self.client.get(key)
        return int(version.decode('utf-8')) if version else None
    
    def get_latest_weights(self, job_id: int) -> Optional[Dict[str, Any]]:
        """
        Get latest global weights (convenience method).
        
        Args:
            job_id: Job identifier
            
        Returns:
            Latest weights or None
        """
        version = self.get_latest_weights_version(job_id)
        if version is not None:
            return self.get_global_weights(job_id, version)
        return None
    
    # ============= Version Map Operations =============
    
    def add_version(
        self,
        job_id: int,
        version: int,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Add version to version map (sorted set by timestamp).
        
        Args:
            job_id: Job identifier
            version: Version number
            metadata: Optional metadata (epoch, metrics, etc.)
            
        Returns:
            True if successful
        """
        key = RedisKeys.version_map(job_id)
        timestamp = datetime.utcnow().timestamp()
        
        # Store version as sorted set member (score = timestamp)
        self.client.zadd(key, {str(version): timestamp})
        
        # Store metadata separately if provided
        if metadata:
            meta_key = f"{key}:meta:{version}"
            self.client.setex(
                meta_key,
                settings.version_map_ttl,
                MetadataSerializer.serialize(metadata)
            )
        
        # Set TTL on version map
        self.client.expire(key, settings.version_map_ttl)
        return True
    
    def get_version_history(self, job_id: int, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get version history (newest first).
        
        Args:
            job_id: Job identifier
            limit: Maximum number of versions to return
            
        Returns:
            List of version dictionaries with timestamp and metadata
        """
        key = RedisKeys.version_map(job_id)
        
        # Get versions from sorted set (highest score first)
        versions = self.client.zrevrange(key, 0, limit - 1, withscores=True)
        
        history = []
        for version_bytes, timestamp in versions:
            version = int(version_bytes.decode('utf-8'))
            meta_key = f"{key}:meta:{version}"
            metadata_binary = self.client.get(meta_key)
            
            version_info = {
                'version': version,
                'timestamp': datetime.fromtimestamp(timestamp).isoformat(),
            }
            
            if metadata_binary:
                version_info['metadata'] = MetadataSerializer.deserialize(metadata_binary)
            
            history.append(version_info)
        
        return history
    
    def get_version_count(self, job_id: int) -> int:
        """Get total number of versions."""
        key = RedisKeys.version_map(job_id)
        return self.client.zcard(key)
    
    # ============= Gradient Buffer Operations =============
    
    def set_gradient(
        self,
        job_id: int,
        worker_id: str,
        gradients: Dict[str, Any],
        ttl: int = RedisTTL.GRADIENT_BUFFER
    ) -> bool:
        """
        Store worker gradients in buffer.
        
        Args:
            job_id: Job identifier
            worker_id: Worker identifier
            gradients: Dictionary of layer_name -> numpy array
            ttl: Time-to-live in seconds
            
        Returns:
            True if successful
        """
        key = RedisKeys.gradient_buffer(job_id, worker_id)
        binary = GradientSerializer.serialize(gradients)
        return self.client.setex(key, ttl, binary)
    
    def get_gradient(self, job_id: int, worker_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve worker gradients from buffer.
        
        Args:
            job_id: Job identifier
            worker_id: Worker identifier
            
        Returns:
            Gradients or None
        """
        key = RedisKeys.gradient_buffer(job_id, worker_id)
        binary = self.client.get(key)
        if binary:
            return GradientSerializer.deserialize(binary)
        return None
    
    def delete_gradient(self, job_id: int, worker_id: str) -> bool:
        """Delete gradient buffer after aggregation."""
        key = RedisKeys.gradient_buffer(job_id, worker_id)
        return self.client.delete(key) > 0
    
    # ============= Job Status Cache =============
    
    def cache_job_status(
        self,
        job_id: int,
        status: str,
        progress: float,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Cache job status for fast retrieval.
        
        Args:
            job_id: Job identifier
            status: Job status string
            progress: Progress percentage (0-100)
            metadata: Optional metadata (current_epoch, metrics, etc.)
            
        Returns:
            True if successful
        """
        key = RedisKeys.job_status(job_id)
        data = {
            'status': status,
            'progress': progress,
            'updated_at': datetime.utcnow().isoformat(),
        }
        if metadata:
            data['metadata'] = metadata
        
        return self.client.setex(key, RedisTTL.JOB_STATUS, json.dumps(data))
    
    def get_job_status(self, job_id: int) -> Optional[Dict[str, Any]]:
        """Get cached job status."""
        key = RedisKeys.job_status(job_id)
        data = self.client.get(key)
        if data:
            return json.loads(data.decode('utf-8'))
        return None
    
    # ============= Distributed Lock Operations =============
    
    def acquire_lock(
        self,
        resource: str,
        resource_id: str,
        timeout: int = RedisTTL.LOCK
    ) -> bool:
        """
        Acquire distributed lock.
        
        Args:
            resource: Resource type (e.g., 'job', 'weights')
            resource_id: Resource identifier
            timeout: Lock timeout in seconds
            
        Returns:
            True if lock acquired
        """
        key = RedisKeys.lock(resource, resource_id)
        return self.client.set(key, '1', nx=True, ex=timeout)
    
    def release_lock(self, resource: str, resource_id: str) -> bool:
        """Release distributed lock."""
        key = RedisKeys.lock(resource, resource_id)
        return self.client.delete(key) > 0
    
    # ============= Utility Methods =============
    
    def delete_pattern(self, pattern: str) -> int:
        """
        Delete all keys matching pattern.
        
        Args:
            pattern: Redis key pattern (e.g., 'heartbeat:worker:*')
            
        Returns:
            Number of keys deleted
        """
        keys = self.client.keys(pattern)
        if keys:
            return self.client.delete(*keys)
        return 0
    
    def flush_db(self) -> bool:
        """Flush current database (USE WITH CAUTION!)."""
        return self.client.flushdb()
    
    def get_info(self) -> Dict[str, Any]:
        """Get Redis server info."""
        return self.client.info()


# Singleton instance
redis_client = RedisClient()
