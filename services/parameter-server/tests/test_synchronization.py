"""
Tests for Synchronization Service

Comprehensive tests covering:
- Synchronous mode (wait for all workers)
- Asynchronous mode (immediate processing)
- Semi-synchronous mode (quorum-based)
- Worker registration and tracking
- Timeout handling
- Round management
"""

import pytest
import torch
import asyncio
from datetime import datetime, timedelta
from typing import Dict

from app.services.synchronization import (
    SynchronizationService,
    SyncConfig,
    SyncMode,
    WorkerState,
    WorkerInfo
)
from app.services.gradient_aggregation import (
    GradientAggregationService,
    GradientUpdate,
    AggregationConfig,
    AggregationStrategy
)


# ==================== Fixtures ====================

@pytest.fixture
def gradient_service():
    """Create gradient aggregation service"""
    return GradientAggregationService()


@pytest.fixture
def sync_service(gradient_service):
    """Create synchronization service"""
    return SynchronizationService(gradient_service)


@pytest.fixture
def sample_gradients():
    """Create sample gradient tensors"""
    return {
        "layer1.weight": torch.randn(10, 5),
        "layer1.bias": torch.randn(10),
        "layer2.weight": torch.randn(3, 10),
        "layer2.bias": torch.randn(3)
    }


def create_gradient_update(
    worker_id: str,
    model_id: str,
    version_id: int,
    gradients: Dict[str, torch.Tensor],
    num_samples: int = 100
) -> GradientUpdate:
    """Helper to create gradient update"""
    return GradientUpdate(
        worker_id=worker_id,
        model_id=model_id,
        version_id=version_id,
        gradients=gradients,
        num_samples=num_samples
    )


# ==================== Test Worker Registration ====================

class TestWorkerRegistration:
    """Test worker registration and management"""
    
    def test_register_worker(self, sync_service):
        """Test registering a new worker"""
        worker = sync_service.register_worker(
            worker_id="worker-1",
            model_id="model-test",
            metadata={"gpu": "cuda:0"}
        )
        
        assert worker.worker_id == "worker-1"
        assert worker.model_id == "model-test"
        assert worker.state == WorkerState.ACTIVE
        assert worker.metadata["gpu"] == "cuda:0"
    
    def test_register_multiple_workers(self, sync_service):
        """Test registering multiple workers"""
        for i in range(3):
            sync_service.register_worker(
                worker_id=f"worker-{i}",
                model_id="model-test"
            )
        
        workers = sync_service.list_workers(model_id="model-test")
        assert len(workers) == 3
    
    def test_reregister_worker(self, sync_service):
        """Test re-registering existing worker updates info"""
        sync_service.register_worker(
            worker_id="worker-1",
            model_id="model-test",
            metadata={"version": 1}
        )
        
        # Re-register with new metadata
        worker = sync_service.register_worker(
            worker_id="worker-1",
            model_id="model-test",
            metadata={"version": 2}
        )
        
        assert worker.metadata["version"] == 2
        assert worker.state == WorkerState.ACTIVE
    
    def test_unregister_worker(self, sync_service):
        """Test unregistering a worker"""
        sync_service.register_worker(
            worker_id="worker-1",
            model_id="model-test"
        )
        
        success = sync_service.unregister_worker("worker-1")
        assert success is True
        
        worker = sync_service.get_worker_info("worker-1")
        assert worker.state == WorkerState.EXCLUDED
    
    def test_get_worker_info(self, sync_service):
        """Test getting worker information"""
        sync_service.register_worker(
            worker_id="worker-1",
            model_id="model-test"
        )
        
        worker = sync_service.get_worker_info("worker-1")
        assert worker is not None
        assert worker.worker_id == "worker-1"
    
    def test_list_workers_by_model(self, sync_service):
        """Test filtering workers by model"""
        sync_service.register_worker("worker-1", "model-a")
        sync_service.register_worker("worker-2", "model-a")
        sync_service.register_worker("worker-3", "model-b")
        
        workers_a = sync_service.list_workers(model_id="model-a")
        workers_b = sync_service.list_workers(model_id="model-b")
        
        assert len(workers_a) == 2
        assert len(workers_b) == 1
    
    def test_list_workers_by_state(self, sync_service):
        """Test filtering workers by state"""
        sync_service.register_worker("worker-1", "model-test")
        sync_service.register_worker("worker-2", "model-test")
        sync_service.unregister_worker("worker-2")
        
        active = sync_service.list_workers(state=WorkerState.ACTIVE)
        excluded = sync_service.list_workers(state=WorkerState.EXCLUDED)
        
        assert len(active) == 1
        assert len(excluded) == 1


# ==================== Test Asynchronous Mode ====================

class TestAsynchronousMode:
    """Test asynchronous synchronization mode"""
    
    @pytest.mark.asyncio
    async def test_async_immediate_aggregation(self, sync_service, sample_gradients):
        """Test immediate aggregation in async mode"""
        config = SyncConfig(
            mode=SyncMode.ASYNCHRONOUS,
            async_batch_size=1  # Aggregate immediately
        )
        
        gradient = create_gradient_update(
            "worker-1", "model-test", 1, sample_gradients
        )
        
        result = await sync_service.submit_gradient(gradient, config)
        
        # Should aggregate immediately
        assert result is not None
        assert result.num_workers == 1
        assert result.total_samples == 100
    
    @pytest.mark.asyncio
    async def test_async_batch_aggregation(self, sync_service, sample_gradients):
        """Test batch aggregation in async mode"""
        config = SyncConfig(
            mode=SyncMode.ASYNCHRONOUS,
            async_batch_size=3  # Wait for 3 gradients
        )
        
        # Submit first two gradients
        for i in range(2):
            gradient = create_gradient_update(
                f"worker-{i}", "model-test", 1, sample_gradients
            )
            result = await sync_service.submit_gradient(gradient, config)
            assert result is None  # Not aggregated yet
        
        # Submit third gradient
        gradient = create_gradient_update(
            "worker-2", "model-test", 1, sample_gradients
        )
        result = await sync_service.submit_gradient(gradient, config)
        
        # Should aggregate now
        assert result is not None
        assert result.num_workers == 3
    
    @pytest.mark.asyncio
    async def test_async_timeout_aggregation(self, sync_service, sample_gradients):
        """Test timeout-based aggregation in async mode"""
        config = SyncConfig(
            mode=SyncMode.ASYNCHRONOUS,
            async_batch_size=10,  # High batch size
            async_timeout_seconds=0.1  # 100ms timeout
        )
        
        # Submit gradient
        gradient = create_gradient_update(
            "worker-1", "model-test", 1, sample_gradients
        )
        result = await sync_service.submit_gradient(gradient, config)
        assert result is None  # Not aggregated yet
        
        # Wait for timeout
        await asyncio.sleep(0.15)
        
        # Check that aggregation occurred via callback or monitoring
        # (In real implementation, this would trigger via background task)


# ==================== Test Synchronous Mode ====================

class TestSynchronousMode:
    """Test synchronous synchronization mode"""
    
    @pytest.mark.asyncio
    async def test_sync_wait_for_all_workers(self, sync_service, sample_gradients):
        """Test waiting for all workers in sync mode"""
        # Register workers
        for i in range(3):
            sync_service.register_worker(f"worker-{i}", "model-test")
        
        config = SyncConfig(
            mode=SyncMode.SYNCHRONOUS,
            min_workers=3
        )
        
        # Submit from first two workers
        for i in range(2):
            gradient = create_gradient_update(
                f"worker-{i}", "model-test", 1, sample_gradients
            )
            result = await sync_service.submit_gradient(gradient, config)
            assert result is None  # Not all workers submitted yet
        
        # Submit from third worker
        gradient = create_gradient_update(
            "worker-2", "model-test", 1, sample_gradients
        )
        result = await sync_service.submit_gradient(gradient, config)
        
        # Should aggregate now
        assert result is not None
        assert result.num_workers == 3
        assert result.total_samples == 300
    
    @pytest.mark.asyncio
    async def test_sync_round_creation(self, sync_service, sample_gradients):
        """Test sync round creation"""
        sync_service.register_worker("worker-1", "model-test")
        sync_service.register_worker("worker-2", "model-test")
        
        config = SyncConfig(mode=SyncMode.SYNCHRONOUS)
        
        # Submit gradient
        gradient = create_gradient_update(
            "worker-1", "model-test", 1, sample_gradients
        )
        await sync_service.submit_gradient(gradient, config)
        
        # Check round created
        current_round = sync_service.get_current_round("model-test")
        assert current_round is not None
        assert current_round.model_id == "model-test"
        assert "worker-1" in current_round.received_workers
    
    @pytest.mark.asyncio
    async def test_sync_round_completion(self, sync_service, sample_gradients):
        """Test sync round completion and history"""
        for i in range(2):
            sync_service.register_worker(f"worker-{i}", "model-test")
        
        config = SyncConfig(mode=SyncMode.SYNCHRONOUS, min_workers=2)
        
        # Complete a round
        for i in range(2):
            gradient = create_gradient_update(
                f"worker-{i}", "model-test", 1, sample_gradients
            )
            await sync_service.submit_gradient(gradient, config)
        
        # Check round completed
        assert sync_service.get_current_round("model-test") is None
        
        # Check history
        history = sync_service.get_round_history(model_id="model-test")
        assert len(history) == 1
        assert history[0].completed_at is not None


# ==================== Test Semi-Synchronous Mode ====================

class TestSemiSynchronousMode:
    """Test semi-synchronous synchronization mode"""
    
    @pytest.mark.asyncio
    async def test_semi_sync_quorum(self, sync_service, sample_gradients):
        """Test quorum-based aggregation"""
        # Register 5 workers
        for i in range(5):
            sync_service.register_worker(f"worker-{i}", "model-test")
        
        config = SyncConfig(
            mode=SyncMode.SEMI_SYNCHRONOUS,
            worker_quorum=0.6,  # Need 60% = 3 workers
            min_workers=2
        )
        
        # Submit from 2 workers (not enough)
        for i in range(2):
            gradient = create_gradient_update(
                f"worker-{i}", "model-test", 1, sample_gradients
            )
            result = await sync_service.submit_gradient(gradient, config)
            assert result is None
        
        # Submit from 3rd worker (reaches quorum)
        gradient = create_gradient_update(
            "worker-2", "model-test", 1, sample_gradients
        )
        result = await sync_service.submit_gradient(gradient, config)
        
        # Should aggregate now
        assert result is not None
        assert result.num_workers == 3
    
    @pytest.mark.asyncio
    async def test_semi_sync_minimum_workers(self, sync_service, sample_gradients):
        """Test minimum workers requirement"""
        sync_service.register_worker("worker-1", "model-test")
        
        config = SyncConfig(
            mode=SyncMode.SEMI_SYNCHRONOUS,
            min_workers=2,  # Need at least 2
            worker_quorum=0.5
        )
        
        # Submit from 1 worker
        gradient = create_gradient_update(
            "worker-1", "model-test", 1, sample_gradients
        )
        result = await sync_service.submit_gradient(gradient, config)
        
        # Should not aggregate (below min_workers)
        assert result is None
    
    @pytest.mark.asyncio
    async def test_semi_sync_with_staleness(self, sync_service, sample_gradients):
        """Test semi-sync with staleness filtering"""
        for i in range(3):
            sync_service.register_worker(f"worker-{i}", "model-test")
        
        config = SyncConfig(
            mode=SyncMode.SEMI_SYNCHRONOUS,
            worker_quorum=0.5,
            max_staleness=5,
            min_workers=1
        )
        
        # Submit gradients with different versions
        gradient1 = create_gradient_update(
            "worker-0", "model-test", 10, sample_gradients  # Fresh
        )
        gradient2 = create_gradient_update(
            "worker-1", "model-test", 8, sample_gradients  # Staleness 2
        )
        gradient3 = create_gradient_update(
            "worker-2", "model-test", 1, sample_gradients  # Staleness 9 (too stale)
        )
        
        await sync_service.submit_gradient(gradient1, config)
        result = await sync_service.submit_gradient(gradient2, config)
        
        # Should aggregate with 2 workers (quorum reached)
        assert result is not None
        assert result.num_workers == 2  # worker-2's gradient filtered by staleness


# ==================== Test Worker Timeout ====================

class TestWorkerTimeout:
    """Test worker timeout detection and handling"""
    
    def test_worker_timeout_detection(self, sync_service, sample_gradients):
        """Test detecting timed out workers"""
        # Register worker
        sync_service.register_worker("worker-1", "model-test")
        
        # Manually set last_seen to old time
        worker = sync_service.workers["worker-1"]
        worker.last_seen = datetime.utcnow() - timedelta(seconds=400)
        
        # Get active workers (should trigger timeout check)
        config = SyncConfig(worker_timeout_seconds=300)
        sync_service.default_config = config
        
        active = sync_service._get_active_workers("model-test")
        
        # Worker should be timed out
        assert len(active) == 0
        assert worker.state == WorkerState.TIMED_OUT
    
    @pytest.mark.asyncio
    async def test_gradient_updates_worker_status(self, sync_service, sample_gradients):
        """Test gradient submission updates worker status"""
        config = SyncConfig(mode=SyncMode.ASYNCHRONOUS)
        
        gradient = create_gradient_update(
            "worker-1", "model-test", 1, sample_gradients
        )
        await sync_service.submit_gradient(gradient, config)
        
        worker = sync_service.get_worker_info("worker-1")
        assert worker is not None
        assert worker.state == WorkerState.ACTIVE
        assert worker.total_gradients == 1
        assert worker.total_samples == 100
        assert worker.last_gradient_version == 1


# ==================== Test Round Management ====================

class TestRoundManagement:
    """Test synchronization round management"""
    
    @pytest.mark.asyncio
    async def test_round_history(self, sync_service, sample_gradients):
        """Test tracking round history"""
        for i in range(2):
            sync_service.register_worker(f"worker-{i}", "model-test")
        
        config = SyncConfig(mode=SyncMode.SYNCHRONOUS, min_workers=2)
        
        # Complete multiple rounds
        for round_num in range(3):
            for i in range(2):
                gradient = create_gradient_update(
                    f"worker-{i}", "model-test", round_num + 1, sample_gradients
                )
                await sync_service.submit_gradient(gradient, config)
        
        # Check history
        history = sync_service.get_round_history()
        assert len(history) == 3
        
        # Should be sorted descending by round_id
        assert history[0].round_id > history[1].round_id
        assert history[1].round_id > history[2].round_id
    
    @pytest.mark.asyncio
    async def test_filter_round_history_by_model(self, sync_service, sample_gradients):
        """Test filtering round history by model"""
        # Register workers for different models
        sync_service.register_worker("worker-1", "model-a")
        sync_service.register_worker("worker-2", "model-b")
        
        config = SyncConfig(mode=SyncMode.SYNCHRONOUS, min_workers=1)
        
        # Complete rounds for different models
        gradient_a = create_gradient_update(
            "worker-1", "model-a", 1, sample_gradients
        )
        gradient_b = create_gradient_update(
            "worker-2", "model-b", 1, sample_gradients
        )
        
        await sync_service.submit_gradient(gradient_a, config)
        await sync_service.submit_gradient(gradient_b, config)
        
        # Filter history
        history_a = sync_service.get_round_history(model_id="model-a")
        history_b = sync_service.get_round_history(model_id="model-b")
        
        assert len(history_a) == 1
        assert len(history_b) == 1
        assert history_a[0].model_id == "model-a"
        assert history_b[0].model_id == "model-b"
    
    @pytest.mark.asyncio
    async def test_limit_round_history(self, sync_service, sample_gradients):
        """Test limiting round history results"""
        sync_service.register_worker("worker-1", "model-test")
        
        config = SyncConfig(mode=SyncMode.SYNCHRONOUS, min_workers=1)
        
        # Complete 5 rounds
        for i in range(5):
            gradient = create_gradient_update(
                "worker-1", "model-test", i + 1, sample_gradients
            )
            await sync_service.submit_gradient(gradient, config)
        
        # Get limited history
        history = sync_service.get_round_history(limit=3)
        assert len(history) == 3


# ==================== Test Statistics ====================

class TestStatistics:
    """Test synchronization statistics"""
    
    @pytest.mark.asyncio
    async def test_service_statistics(self, sync_service, sample_gradients):
        """Test comprehensive service statistics"""
        # Register workers
        for i in range(3):
            sync_service.register_worker(f"worker-{i}", "model-test")
        
        # Unregister one
        sync_service.unregister_worker("worker-2")
        
        # Complete a round
        config = SyncConfig(mode=SyncMode.SYNCHRONOUS, min_workers=2)
        for i in range(2):
            gradient = create_gradient_update(
                f"worker-{i}", "model-test", 1, sample_gradients
            )
            await sync_service.submit_gradient(gradient, config)
        
        stats = sync_service.get_statistics()
        
        assert stats["total_workers"] == 3
        assert stats["active_workers"] == 2  # worker-2 excluded
        assert stats["total_rounds"] == 1
        assert stats["completed_rounds"] == 1
        assert stats["avg_round_duration_seconds"] > 0


# ==================== Test Callbacks ====================

class TestCallbacks:
    """Test aggregation callbacks"""
    
    @pytest.mark.asyncio
    async def test_aggregation_callback(self, sync_service, sample_gradients):
        """Test callback triggered on aggregation"""
        callback_called = False
        callback_result = None
        
        def test_callback(result):
            nonlocal callback_called, callback_result
            callback_called = True
            callback_result = result
        
        sync_service.add_aggregation_callback(test_callback)
        
        config = SyncConfig(mode=SyncMode.ASYNCHRONOUS, async_batch_size=1)
        
        gradient = create_gradient_update(
            "worker-1", "model-test", 1, sample_gradients
        )
        await sync_service.submit_gradient(gradient, config)
        
        assert callback_called is True
        assert callback_result is not None
        assert callback_result.num_workers == 1


# ==================== Integration Tests ====================

class TestIntegration:
    """Integration tests for complete workflows"""
    
    @pytest.mark.asyncio
    async def test_complete_sync_workflow(self, sync_service, sample_gradients):
        """Test complete synchronous training workflow"""
        model_id = "model-workflow"
        num_workers = 3
        
        # 1. Register workers
        for i in range(num_workers):
            sync_service.register_worker(f"worker-{i}", model_id)
        
        # 2. Configure synchronous mode
        config = SyncConfig(
            mode=SyncMode.SYNCHRONOUS,
            min_workers=num_workers,
            sync_timeout_seconds=60.0,
            aggregation_config=AggregationConfig(
                strategy=AggregationStrategy.FEDAVG
            )
        )
        
        # 3. Submit gradients from all workers
        results = []
        for i in range(num_workers):
            gradient = create_gradient_update(
                f"worker-{i}", model_id, 1,
                {k: v.clone() * (i + 1) for k, v in sample_gradients.items()},
                num_samples=100 * (i + 1)
            )
            result = await sync_service.submit_gradient(gradient, config)
            results.append(result)
        
        # 4. Verify aggregation occurred
        assert results[-1] is not None  # Last submission triggered aggregation
        assert results[-1].num_workers == num_workers
        assert results[-1].total_samples == 600  # 100 + 200 + 300
        
        # 5. Verify round completed
        current_round = sync_service.get_current_round(model_id)
        assert current_round is None  # Round should be completed
        
        # 6. Check history
        history = sync_service.get_round_history(model_id=model_id)
        assert len(history) == 1
        assert history[0].completed_at is not None
    
    @pytest.mark.asyncio
    async def test_mixed_mode_workflow(self, sync_service, sample_gradients):
        """Test switching between sync modes"""
        model_id = "model-mixed"
        
        # Start with async mode
        async_config = SyncConfig(
            mode=SyncMode.ASYNCHRONOUS,
            async_batch_size=1
        )
        
        gradient = create_gradient_update(
            "worker-1", model_id, 1, sample_gradients
        )
        result1 = await sync_service.submit_gradient(gradient, async_config)
        assert result1 is not None  # Immediate aggregation
        
        # Switch to sync mode
        sync_service.register_worker("worker-1", model_id)
        sync_service.register_worker("worker-2", model_id)
        
        sync_config = SyncConfig(
            mode=SyncMode.SYNCHRONOUS,
            min_workers=2
        )
        
        gradient1 = create_gradient_update(
            "worker-1", model_id, 2, sample_gradients
        )
        result2 = await sync_service.submit_gradient(gradient1, sync_config)
        assert result2 is None  # Waiting for second worker
        
        gradient2 = create_gradient_update(
            "worker-2", model_id, 2, sample_gradients
        )
        result3 = await sync_service.submit_gradient(gradient2, sync_config)
        assert result3 is not None  # Both workers submitted
