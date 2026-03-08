"""Worker health monitoring and heartbeat management.

This module provides worker registration, heartbeat tracking, and health
monitoring with TTL-based failure detection.
"""

import logging
import time
from typing import Dict, List, Optional, Set, Any
from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta
from enum import Enum
import threading
import asyncio

logger = logging.getLogger(__name__)


class WorkerStatus(Enum):
    """Worker health status."""
    ONLINE = "online"          # Active and healthy
    IDLE = "idle"              # Online but not assigned work
    BUSY = "busy"              # Online and processing tasks
    DEGRADED = "degraded"      # Online but experiencing issues
    OFFLINE = "offline"        # Failed heartbeat, assumed dead
    UNKNOWN = "unknown"        # Never seen or very old


@dataclass
class WorkerCapabilities:
    """Worker hardware and capability information."""
    gpu_count: int = 0
    gpu_memory_gb: float = 0.0
    gpu_type: str = "none"
    cpu_count: int = 1
    ram_gb: float = 4.0
    network_speed_mbps: float = 100.0
    storage_gb: float = 100.0
    supports_cuda: bool = False
    supports_mps: bool = False  # Apple Metal Performance Shaders
    pytorch_version: str = "unknown"
    python_version: str = "unknown"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WorkerCapabilities':
        """Create from dictionary."""
        return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})
    
    def get_compute_score(self) -> float:
        """
        Calculate compute capability score.
        
        Higher score = more powerful worker.
        Score considers GPU, CPU, and RAM.
        """
        gpu_score = self.gpu_count * self.gpu_memory_gb * 10
        cpu_score = self.cpu_count * 0.5
        ram_score = self.ram_gb * 0.2
        
        return gpu_score + cpu_score + ram_score


@dataclass
class WorkerMetrics:
    """Worker runtime metrics."""
    cpu_usage_percent: float = 0.0
    memory_usage_percent: float = 0.0
    gpu_usage_percent: float = 0.0
    gpu_memory_usage_percent: float = 0.0
    network_rx_mbps: float = 0.0
    network_tx_mbps: float = 0.0
    disk_usage_percent: float = 0.0
    active_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WorkerMetrics':
        """Create from dictionary."""
        return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})
    
    def is_healthy(self) -> bool:
        """Check if metrics indicate healthy worker."""
        return (
            self.cpu_usage_percent < 95.0 and
            self.memory_usage_percent < 95.0 and
            self.gpu_memory_usage_percent < 95.0
        )
    
    def is_overloaded(self) -> bool:
        """Check if worker is overloaded."""
        return (
            self.cpu_usage_percent > 90.0 or
            self.memory_usage_percent > 90.0 or
            self.gpu_memory_usage_percent > 90.0
        )


@dataclass
class WorkerInfo:
    """Complete worker information and state."""
    worker_id: str
    hostname: str
    ip_address: str
    port: int
    status: WorkerStatus
    capabilities: WorkerCapabilities
    metrics: WorkerMetrics = field(default_factory=WorkerMetrics)
    
    # Timing information
    registered_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    last_heartbeat: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    last_status_change: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    # Group and task information
    group_id: Optional[str] = None
    assigned_job_id: Optional[str] = None
    assigned_shard_id: Optional[int] = None
    
    # Metadata
    version: str = "unknown"
    tags: Dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data['status'] = self.status.value
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WorkerInfo':
        """Create from dictionary."""
        if isinstance(data.get('status'), str):
            data['status'] = WorkerStatus(data['status'])
        if isinstance(data.get('capabilities'), dict):
            data['capabilities'] = WorkerCapabilities.from_dict(data['capabilities'])
        if isinstance(data.get('metrics'), dict):
            data['metrics'] = WorkerMetrics.from_dict(data['metrics'])
        
        return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})
    
    def is_alive(self, heartbeat_timeout_seconds: int = 30) -> bool:
        """Check if worker is alive based on last heartbeat."""
        if self.status == WorkerStatus.OFFLINE:
            return False
        
        last_heartbeat_time = datetime.fromisoformat(self.last_heartbeat)
        now = datetime.utcnow()
        elapsed = (now - last_heartbeat_time).total_seconds()
        
        return elapsed < heartbeat_timeout_seconds
    
    def get_uptime_seconds(self) -> float:
        """Get worker uptime in seconds."""
        registered_time = datetime.fromisoformat(self.registered_at)
        now = datetime.utcnow()
        return (now - registered_time).total_seconds()
    
    def time_since_last_heartbeat(self) -> float:
        """Get seconds since last heartbeat."""
        last_heartbeat_time = datetime.fromisoformat(self.last_heartbeat)
        now = datetime.utcnow()
        return (now - last_heartbeat_time).total_seconds()


class WorkerRegistry:
    """Registry for managing worker registration and health monitoring."""
    
    def __init__(
        self,
        heartbeat_timeout_seconds: int = 30,
        heartbeat_check_interval: int = 10,
        auto_cleanup: bool = True
    ):
        """
        Initialize worker registry.
        
        Args:
            heartbeat_timeout_seconds: Seconds before worker considered offline
            heartbeat_check_interval: Seconds between health checks
            auto_cleanup: Automatically mark workers offline on timeout
        """
        self.heartbeat_timeout = heartbeat_timeout_seconds
        self.check_interval = heartbeat_check_interval
        self.auto_cleanup = auto_cleanup
        
        # Worker storage
        self.workers: Dict[str, WorkerInfo] = {}  # worker_id -> WorkerInfo
        
        # Status tracking
        self.workers_by_status: Dict[WorkerStatus, Set[str]] = {
            status: set() for status in WorkerStatus
        }
        
        # Group tracking
        self.workers_by_group: Dict[str, Set[str]] = {}  # group_id -> set(worker_ids)
        
        # Synchronization
        self._lock = threading.Lock()
        
        # Background monitoring
        self._monitor_task = None
        self._running = False
        
        logger.info(
            f"Initialized WorkerRegistry: "
            f"heartbeat_timeout={heartbeat_timeout_seconds}s, "
            f"check_interval={heartbeat_check_interval}s"
        )
    
    def register_worker(
        self,
        worker_id: str,
        hostname: str,
        ip_address: str,
        port: int,
        capabilities: WorkerCapabilities,
        group_id: Optional[str] = None,
        version: str = "unknown",
        tags: Optional[Dict[str, str]] = None
    ) -> WorkerInfo:
        """
        Register a new worker or update existing registration.
        
        Args:
            worker_id: Unique worker identifier
            hostname: Worker hostname
            ip_address: Worker IP address
            port: Worker port
            capabilities: Worker capabilities
            group_id: Optional group ID
            version: Worker software version
            tags: Optional metadata tags
            
        Returns:
            WorkerInfo instance
        """
        with self._lock:
            now = datetime.utcnow().isoformat()
            
            # Check if re-registering
            if worker_id in self.workers:
                logger.info(f"Re-registering existing worker: {worker_id}")
                worker = self.workers[worker_id]
                
                # Update registration info
                worker.hostname = hostname
                worker.ip_address = ip_address
                worker.port = port
                worker.capabilities = capabilities
                worker.group_id = group_id
                worker.version = version
                worker.tags = tags or {}
                worker.last_heartbeat = now
                
                # Update status to IDLE if was OFFLINE
                if worker.status == WorkerStatus.OFFLINE:
                    self._change_worker_status(worker_id, WorkerStatus.IDLE)
                
            else:
                # New registration
                worker = WorkerInfo(
                    worker_id=worker_id,
                    hostname=hostname,
                    ip_address=ip_address,
                    port=port,
                    status=WorkerStatus.IDLE,
                    capabilities=capabilities,
                    group_id=group_id,
                    version=version,
                    tags=tags or {},
                    registered_at=now,
                    last_heartbeat=now,
                    last_status_change=now
                )
                
                self.workers[worker_id] = worker
                self.workers_by_status[WorkerStatus.IDLE].add(worker_id)
                
                # Add to group tracking
                if group_id:
                    if group_id not in self.workers_by_group:
                        self.workers_by_group[group_id] = set()
                    self.workers_by_group[group_id].add(worker_id)
                
                logger.info(
                    f"Registered new worker: {worker_id} "
                    f"({hostname}, {capabilities.gpu_count} GPUs, "
                    f"{capabilities.ram_gb:.1f}GB RAM)"
                )
            
            return worker
    
    def update_heartbeat(
        self,
        worker_id: str,
        metrics: Optional[WorkerMetrics] = None,
        status: Optional[WorkerStatus] = None
    ) -> bool:
        """
        Update worker heartbeat.
        
        Args:
            worker_id: Worker ID
            metrics: Optional updated metrics
            status: Optional status update
            
        Returns:
            True if updated successfully
        """
        with self._lock:
            if worker_id not in self.workers:
                logger.warning(f"Heartbeat from unknown worker: {worker_id}")
                return False
            
            worker = self.workers[worker_id]
            worker.last_heartbeat = datetime.utcnow().isoformat()
            
            # Update metrics if provided
            if metrics:
                worker.metrics = metrics
                
                # Auto-detect degraded state
                if metrics.is_overloaded() and worker.status != WorkerStatus.DEGRADED:
                    self._change_worker_status(worker_id, WorkerStatus.DEGRADED)
                elif not metrics.is_overloaded() and worker.status == WorkerStatus.DEGRADED:
                    # Recover from degraded
                    new_status = WorkerStatus.BUSY if worker.assigned_job_id else WorkerStatus.IDLE
                    self._change_worker_status(worker_id, new_status)
            
            # Update status if provided
            if status and status != worker.status:
                self._change_worker_status(worker_id, status)
            
            return True
    
    def get_worker(self, worker_id: str) -> Optional[WorkerInfo]:
        """Get worker information."""
        return self.workers.get(worker_id)
    
    def list_workers(
        self,
        status: Optional[WorkerStatus] = None,
        group_id: Optional[str] = None,
        min_gpu_count: int = 0
    ) -> List[WorkerInfo]:
        """
        List workers with optional filtering.
        
        Args:
            status: Filter by status
            group_id: Filter by group
            min_gpu_count: Filter by minimum GPU count
            
        Returns:
            List of WorkerInfo
        """
        with self._lock:
            workers = list(self.workers.values())
            
            # Filter by status
            if status:
                workers = [w for w in workers if w.status == status]
            
            # Filter by group
            if group_id:
                workers = [w for w in workers if w.group_id == group_id]
            
            # Filter by GPU count
            if min_gpu_count > 0:
                workers = [w for w in workers if w.capabilities.gpu_count >= min_gpu_count]
            
            return workers
    
    def get_available_workers(
        self,
        group_id: Optional[str] = None,
        min_gpu_count: int = 0
    ) -> List[WorkerInfo]:
        """
        Get workers available for assignment (IDLE or ONLINE status).
        
        Args:
            group_id: Optional group filter
            min_gpu_count: Minimum GPU count required
            
        Returns:
            List of available WorkerInfo sorted by compute score
        """
        workers = self.list_workers(group_id=group_id, min_gpu_count=min_gpu_count)
        
        # Filter to available statuses
        available = [
            w for w in workers
            if w.status in {WorkerStatus.IDLE, WorkerStatus.ONLINE}
        ]
        
        # Sort by compute capability (best first)
        available.sort(
            key=lambda w: w.capabilities.get_compute_score(),
            reverse=True
        )
        
        return available
    
    def assign_job(
        self,
        worker_id: str,
        job_id: str,
        shard_id: Optional[int] = None
    ) -> bool:
        """
        Assign job to worker.
        
        Args:
            worker_id: Worker ID
            job_id: Job ID to assign
            shard_id: Optional shard ID
            
        Returns:
            True if assigned successfully
        """
        with self._lock:
            if worker_id not in self.workers:
                return False
            
            worker = self.workers[worker_id]
            
            # Verify worker is available
            if worker.status not in {WorkerStatus.IDLE, WorkerStatus.ONLINE}:
                logger.warning(
                    f"Cannot assign job to worker {worker_id}: "
                    f"status is {worker.status.value}"
                )
                return False
            
            worker.assigned_job_id = job_id
            worker.assigned_shard_id = shard_id
            
            self._change_worker_status(worker_id, WorkerStatus.BUSY)
            
            logger.info(f"Assigned job {job_id} to worker {worker_id}")
            
            return True
    
    def release_job(self, worker_id: str) -> bool:
        """
        Release job assignment from worker.
        
        Args:
            worker_id: Worker ID
            
        Returns:
            True if released successfully
        """
        with self._lock:
            if worker_id not in self.workers:
                return False
            
            worker = self.workers[worker_id]
            old_job_id = worker.assigned_job_id
            
            worker.assigned_job_id = None
            worker.assigned_shard_id = None
            
            if worker.status == WorkerStatus.BUSY:
                self._change_worker_status(worker_id, WorkerStatus.IDLE)
            
            if old_job_id:
                logger.info(f"Released job {old_job_id} from worker {worker_id}")
            
            return True
    
    def mark_offline(self, worker_id: str, reason: str = "Manual") -> bool:
        """Mark worker as offline."""
        with self._lock:
            if worker_id not in self.workers:
                return False
            
            self._change_worker_status(worker_id, WorkerStatus.OFFLINE)
            logger.warning(f"Worker {worker_id} marked OFFLINE: {reason}")
            
            return True
    
    def remove_worker(self, worker_id: str) -> bool:
        """
        Remove worker from registry.
        
        Args:
            worker_id: Worker ID
            
        Returns:
            True if removed successfully
        """
        with self._lock:
            if worker_id not in self.workers:
                return False
            
            worker = self.workers[worker_id]
            
            # Remove from status tracking
            self.workers_by_status[worker.status].discard(worker_id)
            
            # Remove from group tracking
            if worker.group_id and worker.group_id in self.workers_by_group:
                self.workers_by_group[worker.group_id].discard(worker_id)
                if not self.workers_by_group[worker.group_id]:
                    del self.workers_by_group[worker.group_id]
            
            # Remove from main registry
            del self.workers[worker_id]
            
            logger.info(f"Removed worker {worker_id} from registry")
            
            return True
    
    def check_worker_health(self) -> Dict[str, List[str]]:
        """
        Check all worker health and mark offline if needed.
        
        Returns:
            Dictionary with 'offline' and 'degraded' worker lists
        """
        with self._lock:
            offline_workers = []
            degraded_workers = []
            
            for worker_id, worker in self.workers.items():
                if worker.status == WorkerStatus.OFFLINE:
                    continue
                
                # Check heartbeat timeout
                if not worker.is_alive(self.heartbeat_timeout):
                    self._change_worker_status(worker_id, WorkerStatus.OFFLINE)
                    offline_workers.append(worker_id)
                    logger.warning(
                        f"Worker {worker_id} marked OFFLINE: "
                        f"No heartbeat for {worker.time_since_last_heartbeat():.1f}s"
                    )
                
                # Check for degraded performance
                elif worker.metrics.is_overloaded() and worker.status != WorkerStatus.DEGRADED:
                    self._change_worker_status(worker_id, WorkerStatus.DEGRADED)
                    degraded_workers.append(worker_id)
                    logger.warning(
                        f"Worker {worker_id} marked DEGRADED: "
                        f"CPU={worker.metrics.cpu_usage_percent:.1f}%, "
                        f"MEM={worker.metrics.memory_usage_percent:.1f}%"
                    )
            
            return {
                "offline": offline_workers,
                "degraded": degraded_workers
            }
    
    def get_registry_stats(self) -> Dict[str, Any]:
        """Get registry statistics."""
        with self._lock:
            status_counts = {
                status.value: len(worker_ids)
                for status, worker_ids in self.workers_by_status.items()
            }
            
            total_workers = len(self.workers)
            total_gpus = sum(w.capabilities.gpu_count for w in self.workers.values())
            total_ram_gb = sum(w.capabilities.ram_gb for w in self.workers.values())
            
            group_counts = {
                group_id: len(worker_ids)
                for group_id, worker_ids in self.workers_by_group.items()
            }
            
            return {
                "total_workers": total_workers,
                "status_counts": status_counts,
                "total_gpus": total_gpus,
                "total_ram_gb": total_ram_gb,
                "group_counts": group_counts,
                "heartbeat_timeout_seconds": self.heartbeat_timeout
            }
    
    def _change_worker_status(self, worker_id: str, new_status: WorkerStatus):
        """Internal method to change worker status (requires lock)."""
        worker = self.workers[worker_id]
        old_status = worker.status
        
        if old_status == new_status:
            return
        
        # Remove from old status set
        self.workers_by_status[old_status].discard(worker_id)
        
        # Add to new status set
        self.workers_by_status[new_status].add(worker_id)
        
        # Update worker
        worker.status = new_status
        worker.last_status_change = datetime.utcnow().isoformat()
        
        logger.info(f"Worker {worker_id} status: {old_status.value} → {new_status.value}")
    
    async def start_monitoring(self):
        """Start background health monitoring."""
        if self._running:
            logger.warning("Monitoring already running")
            return
        
        self._running = True
        logger.info("Started worker health monitoring")
        
        while self._running:
            try:
                health_report = self.check_worker_health()
                
                if health_report["offline"]:
                    logger.warning(f"Offline workers: {health_report['offline']}")
                
                if health_report["degraded"]:
                    logger.warning(f"Degraded workers: {health_report['degraded']}")
                
                await asyncio.sleep(self.check_interval)
                
            except Exception as e:
                logger.error(f"Error in health monitoring: {e}", exc_info=True)
                await asyncio.sleep(self.check_interval)
    
    def stop_monitoring(self):
        """Stop background health monitoring."""
        self._running = False
        logger.info("Stopped worker health monitoring")
