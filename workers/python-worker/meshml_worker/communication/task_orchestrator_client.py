"""
Task Orchestrator gRPC Client

Handles gRPC communication with the Task Orchestrator service for:
- Worker registration
- Task assignment requests
- Heartbeat monitoring
- Progress reporting
- Failure handling
"""

import logging
import asyncio
import grpc
from typing import Optional, Dict, Any, List
import json
import platform
import psutil
import torch

from meshml_worker.proto import task_orchestrator_pb2, task_orchestrator_pb2_grpc

logger = logging.getLogger(__name__)


class TaskOrchestratorClient:
    """Client for Task Orchestrator gRPC communication"""
    
    def __init__(
        self,
        grpc_url: str,
        user_id: str,
        worker_name: str = "MeshML Python Worker",
        max_retries: int = 3,
        retry_delay: float = 2.0
    ):
        """
        Initialize Task Orchestrator client
        
        Args:
            grpc_url: gRPC server address (host:port)
            user_id: User ID who owns this worker
            worker_name: Human-readable worker name
            max_retries: Maximum number of retry attempts
            retry_delay: Delay between retries in seconds
        """
        self.grpc_url = grpc_url
        self.user_id = user_id
        self.worker_name = worker_name
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        
        self.channel: Optional[grpc.aio.Channel] = None
        self.stub: Optional[task_orchestrator_pb2_grpc.TaskOrchestratorStub] = None
        self.worker_id: Optional[str] = None
        self.heartbeat_interval: int = 30  # seconds
        self._heartbeat_task: Optional[asyncio.Task] = None
        
        logger.info(f"Initialized Task Orchestrator client for {grpc_url}")
    
    async def connect(self) -> None:
        """Establish gRPC connection to Task Orchestrator"""
        try:
            logger.info(f"Connecting to Task Orchestrator at {self.grpc_url}")
            
            # Create async gRPC channel
            self.channel = grpc.aio.insecure_channel(
                self.grpc_url,
                options=[
                    ('grpc.max_send_message_length', 100 * 1024 * 1024),  # 100MB
                    ('grpc.max_receive_message_length', 100 * 1024 * 1024),  # 100MB
                    ('grpc.keepalive_time_ms', 30000),
                    ('grpc.keepalive_timeout_ms', 10000),
                ]
            )
            
            # Create stub
            self.stub = task_orchestrator_pb2_grpc.TaskOrchestratorStub(self.channel)
            
            logger.info("Successfully connected to Task Orchestrator")
            
        except Exception as e:
            logger.error(f"Failed to connect to Task Orchestrator: {e}")
            raise RuntimeError(f"gRPC connection failed: {e}")
    
    async def close(self) -> None:
        """Close gRPC connection"""
        # Stop heartbeat
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
        
        # Close channel
        if self.channel:
            await self.channel.close()
            self.channel = None
            self.stub = None
            logger.info("Task Orchestrator connection closed")
    
    def _get_worker_capabilities(self) -> task_orchestrator_pb2.WorkerCapabilities:
        """
        Gather worker capabilities for registration
        
        Returns:
            WorkerCapabilities protobuf message
        """
        # Get system info
        cpu_count = psutil.cpu_count(logical=False) or 1
        ram_bytes = psutil.virtual_memory().total
        
        # Get GPU info
        gpus = []
        if torch.cuda.is_available():
            for i in range(torch.cuda.device_count()):
                props = torch.cuda.get_device_properties(i)
                gpu = task_orchestrator_pb2.GPU(
                    name=props.name,
                    memory_bytes=props.total_memory,
                    driver_version=torch.version.cuda or "unknown",
                    cuda_available=True,
                    metal_available=False
                )
                gpus.append(gpu)
        elif torch.backends.mps.is_available():
            # Apple Metal
            gpu = task_orchestrator_pb2.GPU(
                name="Apple Metal",
                memory_bytes=ram_bytes,  # Unified memory
                driver_version="metal",
                cuda_available=False,
                metal_available=True
            )
            gpus.append(gpu)
        
        # Get framework versions
        frameworks = {
            "pytorch": torch.__version__,
            "python": platform.python_version(),
        }
        
        # Try to get IP address
        try:
            import socket
            ip_address = socket.gethostbyname(socket.gethostname())
        except:
            ip_address = "unknown"
        
        # Create capabilities message
        capabilities = task_orchestrator_pb2.WorkerCapabilities(
            user_id=self.user_id,
            device_type="python",
            os=platform.system(),
            arch=platform.machine(),
            cpu_cores=cpu_count,
            ram_bytes=ram_bytes,
            gpus=gpus,
            frameworks=frameworks,
            ip_address=ip_address,
            worker_name=self.worker_name
        )
        
        return capabilities
    
    async def register(self) -> Dict[str, Any]:
        """
        Register worker with Task Orchestrator
        
        Returns:
            Registration response with worker_id, groups, heartbeat_interval
            
        Raises:
            RuntimeError: If registration fails
        """
        if not self.stub:
            await self.connect()
        
        logger.info("Registering worker with Task Orchestrator")
        
        try:
            # Get capabilities
            capabilities = self._get_worker_capabilities()
            
            # Make registration RPC call
            response: task_orchestrator_pb2.WorkerRegistration = await self.stub.RegisterWorker(
                capabilities
            )
            
            # Store worker ID and heartbeat interval
            self.worker_id = response.worker_id
            self.heartbeat_interval = response.heartbeat_interval_seconds
            
            logger.info(
                f"Worker registered successfully: {self.worker_id} "
                f"(groups: {list(response.groups)}, "
                f"heartbeat: {self.heartbeat_interval}s)"
            )
            
            # Start heartbeat
            await self.start_heartbeat()
            
            return {
                "worker_id": response.worker_id,
                "groups": list(response.groups),
                "heartbeat_interval": response.heartbeat_interval_seconds,
                "message": response.message
            }
            
        except grpc.RpcError as e:
            logger.error(f"Worker registration failed: {e.code()} - {e.details()}")
            raise RuntimeError(f"Registration failed: {e.details()}")
    
    async def send_heartbeat(
        self,
        status: str = "idle",
        active_tasks: int = 0
    ) -> bool:
        """
        Send heartbeat to Task Orchestrator
        
        Args:
            status: Worker status (online, busy, idle)
            active_tasks: Number of currently active tasks
            
        Returns:
            True if heartbeat was acknowledged, False otherwise
        """
        if not self.stub or not self.worker_id:
            logger.warning("Cannot send heartbeat: worker not registered")
            return False
        
        try:
            # Get current resource usage
            cpu_usage = psutil.cpu_percent(interval=0.1)
            ram_usage = psutil.virtual_memory().percent
            
            # GPU usage (if available)
            gpu_usage = 0.0
            if torch.cuda.is_available() and torch.cuda.device_count() > 0:
                try:
                    # This requires nvidia-ml-py3
                    import pynvml
                    pynvml.nvmlInit()
                    handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                    util = pynvml.nvmlDeviceGetUtilizationRates(handle)
                    gpu_usage = float(util.gpu)
                    pynvml.nvmlShutdown()
                except:
                    gpu_usage = 0.0
            
            # Create heartbeat message
            heartbeat = task_orchestrator_pb2.Heartbeat(
                worker_id=self.worker_id,
                status=status,
                active_tasks=active_tasks,
                cpu_usage_percent=cpu_usage,
                ram_usage_percent=ram_usage,
                gpu_usage_percent=gpu_usage
            )
            
            # Send heartbeat
            response: task_orchestrator_pb2.HeartbeatAck = await self.stub.SendHeartbeat(
                heartbeat
            )
            
            if response.success:
                logger.debug(f"Heartbeat acknowledged: {response.message}")
                return True
            else:
                logger.warning(f"Heartbeat not acknowledged: {response.message}")
                return False
                
        except grpc.RpcError as e:
            logger.error(f"Heartbeat failed: {e.code()} - {e.details()}")
            return False
    
    async def _heartbeat_loop(self) -> None:
        """Background task to send periodic heartbeats"""
        logger.info(f"Starting heartbeat loop (interval: {self.heartbeat_interval}s)")
        
        while True:
            try:
                await asyncio.sleep(self.heartbeat_interval)
                await self.send_heartbeat()
                
            except asyncio.CancelledError:
                logger.info("Heartbeat loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in heartbeat loop: {e}")
                # Continue sending heartbeats despite errors
                await asyncio.sleep(self.heartbeat_interval)
    
    async def start_heartbeat(self) -> None:
        """Start the heartbeat background task"""
        if self._heartbeat_task and not self._heartbeat_task.done():
            logger.warning("Heartbeat already running")
            return
        
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        logger.info("Heartbeat task started")
    
    async def request_task(
        self,
        preferred_job_ids: Optional[List[str]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Request a task assignment from Task Orchestrator
        
        Args:
            preferred_job_ids: Optional list of preferred job IDs
            
        Returns:
            Task assignment dict with job_id, batch_id, paths, etc.
            None if no tasks available
        """
        if not self.stub or not self.worker_id:
            raise RuntimeError("Worker not registered")
        
        logger.info(f"Requesting task assignment for worker {self.worker_id}")
        
        try:
            # Create request
            request = task_orchestrator_pb2.TaskRequest(
                worker_id=self.worker_id,
                preferred_job_ids=preferred_job_ids or []
            )
            
            # Make RPC call
            assignment: task_orchestrator_pb2.TaskAssignment = await self.stub.RequestTask(
                request
            )
            
            if not assignment.has_task:
                logger.info(f"No tasks available: {assignment.message}")
                return None
            
            # Parse hyperparameters
            hyperparameters = {}
            if assignment.hyperparameters:
                try:
                    hyperparameters = json.loads(assignment.hyperparameters.decode('utf-8'))
                except:
                    logger.warning("Failed to parse hyperparameters")
            
            task_info = {
                "job_id": assignment.job_id,
                "batch_id": assignment.batch_id,
                "batch_gcs_path": assignment.batch_gcs_path,
                "model_gcs_path": assignment.model_gcs_path,
                "current_epoch": assignment.current_epoch,
                "hyperparameters": hyperparameters,
                "message": assignment.message
            }
            
            logger.info(
                f"Task assigned: job={task_info['job_id']}, "
                f"batch={task_info['batch_id']}, "
                f"epoch={task_info['current_epoch']}"
            )
            
            return task_info
            
        except grpc.RpcError as e:
            logger.error(f"Task request failed: {e.code()} - {e.details()}")
            raise RuntimeError(f"Task request failed: {e.details()}")
    
    async def report_batch_complete(
        self,
        job_id: str,
        batch_id: int,
        epoch: int,
        loss: float,
        accuracy: float = 0.0,
        processing_time_ms: int = 0,
        metrics: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Report successful batch completion
        
        Args:
            job_id: Job identifier
            batch_id: Batch identifier
            epoch: Epoch number
            loss: Training loss
            accuracy: Training accuracy
            processing_time_ms: Processing time in milliseconds
            metrics: Additional metrics
            
        Returns:
            True if acknowledged, False otherwise
        """
        if not self.stub or not self.worker_id:
            raise RuntimeError("Worker not registered")
        
        logger.info(
            f"Reporting batch completion: job={job_id}, batch={batch_id}, "
            f"loss={loss:.4f}, accuracy={accuracy:.4f}"
        )
        
        try:
            # Serialize metrics
            metrics_bytes = b""
            if metrics:
                try:
                    metrics_bytes = json.dumps(metrics).encode('utf-8')
                except:
                    logger.warning("Failed to serialize metrics")
            
            # Create completion message
            completion = task_orchestrator_pb2.BatchCompletion(
                worker_id=self.worker_id,
                job_id=job_id,
                batch_id=batch_id,
                epoch=epoch,
                loss=loss,
                accuracy=accuracy,
                processing_time_ms=processing_time_ms,
                metrics=metrics_bytes
            )
            
            # Make RPC call
            response: task_orchestrator_pb2.BatchAck = await self.stub.ReportBatchComplete(
                completion
            )
            
            logger.info(f"Batch completion acknowledged: {response.message}")
            return response.success
            
        except grpc.RpcError as e:
            logger.error(f"Batch completion report failed: {e.code()} - {e.details()}")
            return False
    
    async def report_batch_failed(
        self,
        job_id: str,
        batch_id: int,
        epoch: int,
        error_message: str
    ) -> bool:
        """
        Report batch processing failure
        
        Args:
            job_id: Job identifier
            batch_id: Batch identifier
            epoch: Epoch number
            error_message: Error description
            
        Returns:
            True if acknowledged, False otherwise
        """
        if not self.stub or not self.worker_id:
            raise RuntimeError("Worker not registered")
        
        logger.info(
            f"Reporting batch failure: job={job_id}, batch={batch_id}, "
            f"error={error_message}"
        )
        
        try:
            # Create failure message
            failure = task_orchestrator_pb2.BatchFailure(
                worker_id=self.worker_id,
                job_id=job_id,
                batch_id=batch_id,
                epoch=epoch,
                error_message=error_message
            )
            
            # Make RPC call
            response: task_orchestrator_pb2.BatchAck = await self.stub.ReportBatchFailed(
                failure
            )
            
            logger.info(f"Batch failure acknowledged: {response.message}")
            return response.success
            
        except grpc.RpcError as e:
            logger.error(f"Batch failure report failed: {e.code()} - {e.details()}")
            return False
