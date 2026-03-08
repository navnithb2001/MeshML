"""
Tests for Gradient Aggregation Service

Comprehensive tests covering:
- FedAvg aggregation
- Asynchronous gradient buffering
- Staleness-aware weighting
- Gradient clipping (value and norm)
- Gradient normalization
- Multiple aggregation strategies
- Integration scenarios
"""

import pytest
import torch
import torch.nn as nn
from datetime import datetime, timedelta
from typing import Dict, List

from app.services.gradient_aggregation import (
    GradientAggregationService,
    GradientUpdate,
    AggregationConfig,
    AggregationStrategy,
    ClippingStrategy
)


# ==================== Fixtures ====================

@pytest.fixture
def gradient_service():
    """Create gradient aggregation service"""
    return GradientAggregationService()


@pytest.fixture
def sample_gradients():
    """Create sample gradient tensors"""
    return {
        "layer1.weight": torch.randn(10, 5),
        "layer1.bias": torch.randn(10),
        "layer2.weight": torch.randn(3, 10),
        "layer2.bias": torch.randn(3)
    }


@pytest.fixture
def gradient_updates(sample_gradients):
    """Create sample gradient updates from multiple workers"""
    updates = []
    
    # Worker 1: 100 samples, version 10
    updates.append(GradientUpdate(
        worker_id="worker-1",
        model_id="model-test",
        version_id=10,
        gradients={k: v.clone() for k, v in sample_gradients.items()},
        num_samples=100,
        loss=0.5
    ))
    
    # Worker 2: 200 samples, version 10
    updates.append(GradientUpdate(
        worker_id="worker-2",
        model_id="model-test",
        version_id=10,
        gradients={k: v.clone() * 2.0 for k, v in sample_gradients.items()},
        num_samples=200,
        loss=0.4
    ))
    
    # Worker 3: 150 samples, version 9 (stale)
    updates.append(GradientUpdate(
        worker_id="worker-3",
        model_id="model-test",
        version_id=9,
        gradients={k: v.clone() * 0.5 for k, v in sample_gradients.items()},
        num_samples=150,
        loss=0.6
    ))
    
    return updates


# ==================== Test Gradient Submission ====================

class TestGradientSubmission:
    """Test gradient submission and buffering"""
    
    def test_submit_gradient(self, gradient_service, gradient_updates):
        """Test submitting a single gradient"""
        update = gradient_updates[0]
        gradient_service.submit_gradient(update)
        
        pending = gradient_service.get_pending_gradients("model-test")
        assert len(pending) == 1
        assert pending[0].worker_id == "worker-1"
        assert pending[0].num_samples == 100
    
    def test_submit_multiple_gradients(self, gradient_service, gradient_updates):
        """Test submitting multiple gradients"""
        for update in gradient_updates:
            gradient_service.submit_gradient(update)
        
        pending = gradient_service.get_pending_gradients("model-test")
        assert len(pending) == 3
        
        worker_ids = {u.worker_id for u in pending}
        assert worker_ids == {"worker-1", "worker-2", "worker-3"}
    
    def test_submit_to_different_models(self, gradient_service, gradient_updates):
        """Test gradients for different models are separated"""
        # Submit to model-test
        gradient_service.submit_gradient(gradient_updates[0])
        
        # Submit to different model
        update_other = GradientUpdate(
            worker_id="worker-x",
            model_id="model-other",
            version_id=1,
            gradients=gradient_updates[0].gradients,
            num_samples=50
        )
        gradient_service.submit_gradient(update_other)
        
        pending_test = gradient_service.get_pending_gradients("model-test")
        pending_other = gradient_service.get_pending_gradients("model-other")
        
        assert len(pending_test) == 1
        assert len(pending_other) == 1


# ==================== Test FedAvg Aggregation ====================

class TestFedAvgAggregation:
    """Test Federated Averaging implementation"""
    
    def test_fedavg_basic(self, gradient_service, gradient_updates):
        """Test basic FedAvg aggregation"""
        # Submit gradients
        for update in gradient_updates[:2]:  # Only workers 1 and 2
            gradient_service.submit_gradient(update)
        
        # Aggregate
        config = AggregationConfig(
            strategy=AggregationStrategy.FEDAVG,
            staleness_weight_decay=1.0  # No staleness penalty
        )
        result = gradient_service.aggregate_gradients(
            model_id="model-test",
            current_version=10,
            config=config
        )
        
        assert result is not None
        assert result.num_workers == 2
        assert result.total_samples == 300
        assert set(result.worker_ids) == {"worker-1", "worker-2"}
        assert result.strategy == AggregationStrategy.FEDAVG
    
    def test_fedavg_weighted_by_samples(self, gradient_service, sample_gradients):
        """Test FedAvg weights by sample count"""
        # Create two workers with different sample counts
        update1 = GradientUpdate(
            worker_id="worker-1",
            model_id="model-test",
            version_id=1,
            gradients={k: torch.ones_like(v) for k, v in sample_gradients.items()},
            num_samples=100
        )
        
        update2 = GradientUpdate(
            worker_id="worker-2",
            model_id="model-test",
            version_id=1,
            gradients={k: torch.ones_like(v) * 2.0 for k, v in sample_gradients.items()},
            num_samples=200
        )
        
        gradient_service.submit_gradient(update1)
        gradient_service.submit_gradient(update2)
        
        # Aggregate
        config = AggregationConfig(
            strategy=AggregationStrategy.FEDAVG,
            staleness_weight_decay=1.0
        )
        result = gradient_service.aggregate_gradients(
            model_id="model-test",
            current_version=1,
            config=config
        )
        
        # Expected: (100 * 1.0 + 200 * 2.0) / 300 = 500 / 300 = 1.667
        expected_value = (100 * 1.0 + 200 * 2.0) / 300
        
        for name, grad in result.aggregated_gradients.items():
            assert torch.allclose(grad, torch.ones_like(grad) * expected_value, atol=1e-5)
    
    def test_fedavg_no_gradients(self, gradient_service):
        """Test aggregation with no pending gradients"""
        result = gradient_service.aggregate_gradients(
            model_id="model-empty",
            current_version=1
        )
        
        assert result is None


# ==================== Test Staleness-Aware Weighting ====================

class TestStalenessWeighting:
    """Test staleness-aware gradient weighting"""
    
    def test_staleness_calculation(self, gradient_service, sample_gradients):
        """Test staleness weight calculation"""
        # Create updates with different versions
        updates = [
            GradientUpdate(
                worker_id=f"worker-{i}",
                model_id="model-test",
                version_id=10 - i,  # Decreasing versions (increasing staleness)
                gradients={k: torch.ones_like(v) * (i + 1) for k, v in sample_gradients.items()},
                num_samples=100
            )
            for i in range(3)
        ]
        
        for update in updates:
            gradient_service.submit_gradient(update)
        
        # Aggregate with staleness decay = 0.5
        config = AggregationConfig(
            strategy=AggregationStrategy.SIMPLE_AVERAGE,
            staleness_weight_decay=0.5
        )
        result = gradient_service.aggregate_gradients(
            model_id="model-test",
            current_version=10,
            config=config
        )
        
        # Verify staleness weights
        # worker-0: version 10, staleness 0, weight 0.5^0 = 1.0
        # worker-1: version 9, staleness 1, weight 0.5^1 = 0.5
        # worker-2: version 8, staleness 2, weight 0.5^2 = 0.25
        assert result.staleness_weights["worker-0"] == 1.0
        assert result.staleness_weights["worker-1"] == 0.5
        assert result.staleness_weights["worker-2"] == 0.25
    
    def test_max_staleness_filter(self, gradient_service, sample_gradients):
        """Test filtering by max staleness"""
        # Create updates with varying staleness
        updates = [
            GradientUpdate(
                worker_id=f"worker-{i}",
                model_id="model-test",
                version_id=10 - i * 3,  # 10, 7, 4 (staleness 0, 3, 6)
                gradients={k: torch.ones_like(v) for k, v in sample_gradients.items()},
                num_samples=100
            )
            for i in range(3)
        ]
        
        for update in updates:
            gradient_service.submit_gradient(update)
        
        # Set max_staleness = 5 (should filter out worker-2 with staleness 6)
        config = AggregationConfig(
            strategy=AggregationStrategy.SIMPLE_AVERAGE,
            max_staleness=5
        )
        result = gradient_service.aggregate_gradients(
            model_id="model-test",
            current_version=10,
            config=config
        )
        
        assert result.num_workers == 2
        assert "worker-0" in result.worker_ids
        assert "worker-1" in result.worker_ids
        assert "worker-2" not in result.worker_ids
    
    def test_all_stale_gradients(self, gradient_service, sample_gradients):
        """Test when all gradients are too stale"""
        update = GradientUpdate(
            worker_id="worker-1",
            model_id="model-test",
            version_id=1,
            gradients=sample_gradients,
            num_samples=100
        )
        gradient_service.submit_gradient(update)
        
        # Current version is 20, gradient from version 1 (staleness 19)
        # Max staleness is 10
        config = AggregationConfig(max_staleness=10)
        result = gradient_service.aggregate_gradients(
            model_id="model-test",
            current_version=20,
            config=config
        )
        
        assert result is None


# ==================== Test Gradient Clipping ====================

class TestGradientClipping:
    """Test gradient clipping strategies"""
    
    def test_value_clipping(self, gradient_service, sample_gradients):
        """Test clipping by value"""
        # Create gradients with large values
        large_gradients = {
            k: v * 10.0 for k, v in sample_gradients.items()
        }
        
        update = GradientUpdate(
            worker_id="worker-1",
            model_id="model-test",
            version_id=1,
            gradients=large_gradients,
            num_samples=100
        )
        gradient_service.submit_gradient(update)
        
        # Clip by value (max absolute value = 1.0)
        config = AggregationConfig(
            strategy=AggregationStrategy.SIMPLE_AVERAGE,
            clipping_strategy=ClippingStrategy.VALUE,
            clip_value=1.0
        )
        result = gradient_service.aggregate_gradients(
            model_id="model-test",
            current_version=1,
            config=config
        )
        
        # All values should be in [-1.0, 1.0]
        for name, grad in result.aggregated_gradients.items():
            assert grad.abs().max() <= 1.0
    
    def test_norm_clipping(self, gradient_service, sample_gradients):
        """Test clipping by L2 norm"""
        # Create gradients with large norm
        large_gradients = {
            k: v * 100.0 for k, v in sample_gradients.items()
        }
        
        update = GradientUpdate(
            worker_id="worker-1",
            model_id="model-test",
            version_id=1,
            gradients=large_gradients,
            num_samples=100
        )
        gradient_service.submit_gradient(update)
        
        # Clip by norm (max L2 norm = 1.0)
        config = AggregationConfig(
            strategy=AggregationStrategy.SIMPLE_AVERAGE,
            clipping_strategy=ClippingStrategy.NORM,
            clip_norm=1.0
        )
        result = gradient_service.aggregate_gradients(
            model_id="model-test",
            current_version=1,
            config=config
        )
        
        # Each gradient tensor should have norm <= 1.0
        for name, grad in result.aggregated_gradients.items():
            norm = torch.norm(grad).item()
            assert norm <= 1.0 + 1e-5  # Small tolerance for floating point
    
    def test_no_clipping(self, gradient_service, sample_gradients):
        """Test no clipping (values preserved)"""
        original_gradients = {k: v.clone() for k, v in sample_gradients.items()}
        
        update = GradientUpdate(
            worker_id="worker-1",
            model_id="model-test",
            version_id=1,
            gradients=original_gradients,
            num_samples=100
        )
        gradient_service.submit_gradient(update)
        
        config = AggregationConfig(
            strategy=AggregationStrategy.SIMPLE_AVERAGE,
            clipping_strategy=ClippingStrategy.NONE
        )
        result = gradient_service.aggregate_gradients(
            model_id="model-test",
            current_version=1,
            config=config
        )
        
        # Gradients should be unchanged
        for name, grad in result.aggregated_gradients.items():
            assert torch.allclose(grad, original_gradients[name])


# ==================== Test Gradient Normalization ====================

class TestGradientNormalization:
    """Test gradient normalization"""
    
    def test_normalize_gradients(self, gradient_service, sample_gradients):
        """Test gradient normalization by L2 norm"""
        update = GradientUpdate(
            worker_id="worker-1",
            model_id="model-test",
            version_id=1,
            gradients=sample_gradients,
            num_samples=100
        )
        gradient_service.submit_gradient(update)
        
        config = AggregationConfig(
            strategy=AggregationStrategy.SIMPLE_AVERAGE,
            normalize_gradients=True
        )
        result = gradient_service.aggregate_gradients(
            model_id="model-test",
            current_version=1,
            config=config
        )
        
        # Each gradient should have unit norm
        for name, grad in result.aggregated_gradients.items():
            norm = torch.norm(grad).item()
            assert abs(norm - 1.0) < 1e-5 or norm == 0.0


# ==================== Test Aggregation Strategies ====================

class TestAggregationStrategies:
    """Test different aggregation strategies"""
    
    def test_simple_average(self, gradient_service, sample_gradients):
        """Test simple averaging (equal weights)"""
        # Create two workers with different sample counts
        update1 = GradientUpdate(
            worker_id="worker-1",
            model_id="model-test",
            version_id=1,
            gradients={k: torch.ones_like(v) for k, v in sample_gradients.items()},
            num_samples=100
        )
        
        update2 = GradientUpdate(
            worker_id="worker-2",
            model_id="model-test",
            version_id=1,
            gradients={k: torch.ones_like(v) * 3.0 for k, v in sample_gradients.items()},
            num_samples=200  # Different sample count (should be ignored)
        )
        
        gradient_service.submit_gradient(update1)
        gradient_service.submit_gradient(update2)
        
        config = AggregationConfig(
            strategy=AggregationStrategy.SIMPLE_AVERAGE,
            staleness_weight_decay=1.0
        )
        result = gradient_service.aggregate_gradients(
            model_id="model-test",
            current_version=1,
            config=config
        )
        
        # Expected: (1.0 + 3.0) / 2 = 2.0 (sample counts ignored)
        expected_value = 2.0
        
        for name, grad in result.aggregated_gradients.items():
            assert torch.allclose(grad, torch.ones_like(grad) * expected_value)
    
    def test_weighted_average(self, gradient_service, sample_gradients):
        """Test weighted average with custom weights"""
        # Create updates with custom weights in metadata
        update1 = GradientUpdate(
            worker_id="worker-1",
            model_id="model-test",
            version_id=1,
            gradients={k: torch.ones_like(v) for k, v in sample_gradients.items()},
            num_samples=100,
            metadata={"weight": 1.0}
        )
        
        update2 = GradientUpdate(
            worker_id="worker-2",
            model_id="model-test",
            version_id=1,
            gradients={k: torch.ones_like(v) * 4.0 for k, v in sample_gradients.items()},
            num_samples=100,
            metadata={"weight": 3.0}
        )
        
        gradient_service.submit_gradient(update1)
        gradient_service.submit_gradient(update2)
        
        config = AggregationConfig(
            strategy=AggregationStrategy.WEIGHTED_AVERAGE,
            staleness_weight_decay=1.0
        )
        result = gradient_service.aggregate_gradients(
            model_id="model-test",
            current_version=1,
            config=config
        )
        
        # Expected: (1.0 * 1.0 + 4.0 * 3.0) / (1.0 + 3.0) = 13.0 / 4.0 = 3.25
        expected_value = 3.25
        
        for name, grad in result.aggregated_gradients.items():
            assert torch.allclose(grad, torch.ones_like(grad) * expected_value)
    
    def test_momentum_aggregation(self, gradient_service, sample_gradients):
        """Test momentum-based aggregation"""
        # First aggregation
        update1 = GradientUpdate(
            worker_id="worker-1",
            model_id="model-test",
            version_id=1,
            gradients={k: torch.ones_like(v) for k, v in sample_gradients.items()},
            num_samples=100
        )
        gradient_service.submit_gradient(update1)
        
        config = AggregationConfig(
            strategy=AggregationStrategy.MOMENTUM,
            momentum_factor=0.9,
            staleness_weight_decay=1.0
        )
        result1 = gradient_service.aggregate_gradients(
            model_id="model-test",
            current_version=1,
            config=config
        )
        
        # First aggregation: momentum = gradients
        for name, grad in result1.aggregated_gradients.items():
            assert torch.allclose(grad, torch.ones_like(grad))
        
        # Second aggregation with different gradients
        update2 = GradientUpdate(
            worker_id="worker-2",
            model_id="model-test",
            version_id=2,
            gradients={k: torch.zeros_like(v) for k, v in sample_gradients.items()},
            num_samples=100
        )
        gradient_service.submit_gradient(update2)
        
        result2 = gradient_service.aggregate_gradients(
            model_id="model-test",
            current_version=2,
            config=config
        )
        
        # Second aggregation: momentum = 0.9 * old + 0.1 * new = 0.9 * 1.0 + 0.1 * 0.0 = 0.9
        expected_value = 0.9
        
        for name, grad in result2.aggregated_gradients.items():
            assert torch.allclose(grad, torch.ones_like(grad) * expected_value, atol=1e-5)
    
    def test_adaptive_aggregation(self, gradient_service, sample_gradients):
        """Test adaptive aggregation based on loss"""
        # Create workers with different losses
        update1 = GradientUpdate(
            worker_id="worker-1",
            model_id="model-test",
            version_id=1,
            gradients={k: torch.ones_like(v) for k, v in sample_gradients.items()},
            num_samples=100,
            loss=0.1  # Low loss (high quality)
        )
        
        update2 = GradientUpdate(
            worker_id="worker-2",
            model_id="model-test",
            version_id=1,
            gradients={k: torch.ones_like(v) * 2.0 for k, v in sample_gradients.items()},
            num_samples=100,
            loss=0.9  # High loss (low quality)
        )
        
        gradient_service.submit_gradient(update1)
        gradient_service.submit_gradient(update2)
        
        config = AggregationConfig(
            strategy=AggregationStrategy.ADAPTIVE,
            staleness_weight_decay=1.0
        )
        result = gradient_service.aggregate_gradients(
            model_id="model-test",
            current_version=1,
            config=config
        )
        
        # Worker 1 should have higher weight due to lower loss
        # Expected value should be closer to 1.0 than 2.0
        for name, grad in result.aggregated_gradients.items():
            mean_value = grad.mean().item()
            assert mean_value < 1.5  # Closer to worker-1's gradient


# ==================== Test Buffer Management ====================

class TestBufferManagement:
    """Test gradient buffer management"""
    
    def test_clear_buffer(self, gradient_service, gradient_updates):
        """Test clearing gradient buffer"""
        for update in gradient_updates:
            gradient_service.submit_gradient(update)
        
        assert len(gradient_service.get_pending_gradients("model-test")) == 3
        
        count = gradient_service.clear_buffer("model-test")
        
        assert count == 3
        assert len(gradient_service.get_pending_gradients("model-test")) == 0
    
    def test_auto_clear_after_aggregation(self, gradient_service, gradient_updates):
        """Test automatic buffer clearing after aggregation"""
        for update in gradient_updates:
            gradient_service.submit_gradient(update)
        
        config = AggregationConfig()
        gradient_service.aggregate_gradients(
            model_id="model-test",
            current_version=10,
            config=config,
            clear_buffer=True
        )
        
        # Buffer should be empty
        assert len(gradient_service.get_pending_gradients("model-test")) == 0
    
    def test_preserve_buffer_after_aggregation(self, gradient_service, gradient_updates):
        """Test preserving buffer after aggregation"""
        for update in gradient_updates:
            gradient_service.submit_gradient(update)
        
        config = AggregationConfig()
        gradient_service.aggregate_gradients(
            model_id="model-test",
            current_version=10,
            config=config,
            clear_buffer=False
        )
        
        # Buffer should still have gradients
        assert len(gradient_service.get_pending_gradients("model-test")) > 0


# ==================== Test History and Statistics ====================

class TestHistoryAndStatistics:
    """Test aggregation history and statistics"""
    
    def test_aggregation_history(self, gradient_service, gradient_updates):
        """Test tracking aggregation history"""
        # First aggregation
        for update in gradient_updates[:2]:
            gradient_service.submit_gradient(update)
        
        gradient_service.aggregate_gradients(
            model_id="model-test",
            current_version=10
        )
        
        # Second aggregation
        gradient_service.submit_gradient(gradient_updates[2])
        gradient_service.aggregate_gradients(
            model_id="model-test",
            current_version=11
        )
        
        history = gradient_service.get_aggregation_history()
        
        assert len(history) == 2
        assert history[0].target_version_id == 11  # Most recent first
        assert history[1].target_version_id == 10
    
    def test_filter_history_by_model(self, gradient_service, gradient_updates):
        """Test filtering history by model"""
        # Aggregation for model-test
        gradient_service.submit_gradient(gradient_updates[0])
        gradient_service.aggregate_gradients(
            model_id="model-test",
            current_version=1
        )
        
        # Aggregation for model-other
        other_update = GradientUpdate(
            worker_id="worker-x",
            model_id="model-other",
            version_id=1,
            gradients=gradient_updates[0].gradients,
            num_samples=50
        )
        gradient_service.submit_gradient(other_update)
        gradient_service.aggregate_gradients(
            model_id="model-other",
            current_version=1
        )
        
        history_test = gradient_service.get_aggregation_history(model_id="model-test")
        history_other = gradient_service.get_aggregation_history(model_id="model-other")
        
        assert len(history_test) == 1
        assert len(history_other) == 1
        assert history_test[0].model_id == "model-test"
        assert history_other[0].model_id == "model-other"
    
    def test_limit_history(self, gradient_service, gradient_updates):
        """Test limiting history results"""
        # Create multiple aggregations
        for i in range(5):
            gradient_service.submit_gradient(gradient_updates[0])
            gradient_service.aggregate_gradients(
                model_id="model-test",
                current_version=i
            )
        
        history = gradient_service.get_aggregation_history(limit=3)
        
        assert len(history) == 3
    
    def test_statistics(self, gradient_service, gradient_updates):
        """Test service statistics"""
        # Submit gradients
        for update in gradient_updates:
            gradient_service.submit_gradient(update)
        
        # Perform aggregations
        gradient_service.aggregate_gradients(
            model_id="model-test",
            current_version=10,
            config=AggregationConfig(strategy=AggregationStrategy.FEDAVG)
        )
        
        gradient_service.submit_gradient(gradient_updates[0])
        gradient_service.aggregate_gradients(
            model_id="model-test",
            current_version=11,
            config=AggregationConfig(strategy=AggregationStrategy.SIMPLE_AVERAGE)
        )
        
        stats = gradient_service.get_statistics()
        
        assert stats["total_aggregations"] == 2
        assert stats["strategy_counts"]["fedavg"] == 1
        assert stats["strategy_counts"]["simple_average"] == 1


# ==================== Integration Tests ====================

class TestIntegration:
    """Integration tests for complete workflows"""
    
    def test_complete_aggregation_workflow(self, gradient_service, sample_gradients):
        """Test complete gradient aggregation workflow"""
        model_id = "model-workflow"
        
        # 1. Submit gradients from multiple workers
        for i in range(3):
            update = GradientUpdate(
                worker_id=f"worker-{i}",
                model_id=model_id,
                version_id=10,
                gradients={k: v.clone() * (i + 1) for k, v in sample_gradients.items()},
                num_samples=100 * (i + 1),
                loss=0.5 - i * 0.1
            )
            gradient_service.submit_gradient(update)
        
        # 2. Check pending gradients
        pending = gradient_service.get_pending_gradients(model_id)
        assert len(pending) == 3
        
        # 3. Aggregate with FedAvg
        config = AggregationConfig(
            strategy=AggregationStrategy.FEDAVG,
            clipping_strategy=ClippingStrategy.NORM,
            clip_norm=10.0,
            staleness_weight_decay=0.8
        )
        result = gradient_service.aggregate_gradients(
            model_id=model_id,
            current_version=10,
            config=config
        )
        
        # 4. Verify result
        assert result is not None
        assert result.num_workers == 3
        assert result.total_samples == 600
        assert len(result.aggregated_gradients) == len(sample_gradients)
        
        # 5. Check history
        history = gradient_service.get_aggregation_history(model_id=model_id)
        assert len(history) == 1
        assert history[0].model_id == model_id
        
        # 6. Verify buffer cleared
        pending_after = gradient_service.get_pending_gradients(model_id)
        assert len(pending_after) == 0
    
    def test_staleness_and_clipping_combined(self, gradient_service, sample_gradients):
        """Test combining staleness weighting and gradient clipping"""
        model_id = "model-combined"
        
        # Create gradients with varying staleness and large values
        updates = [
            GradientUpdate(
                worker_id=f"worker-{i}",
                model_id=model_id,
                version_id=10 - i,
                gradients={k: v.clone() * 10.0 for k, v in sample_gradients.items()},
                num_samples=100
            )
            for i in range(3)
        ]
        
        for update in updates:
            gradient_service.submit_gradient(update)
        
        # Aggregate with staleness weighting and norm clipping
        config = AggregationConfig(
            strategy=AggregationStrategy.FEDAVG,
            staleness_weight_decay=0.5,
            clipping_strategy=ClippingStrategy.NORM,
            clip_norm=1.0
        )
        result = gradient_service.aggregate_gradients(
            model_id=model_id,
            current_version=10,
            config=config
        )
        
        # Verify staleness weights applied
        assert result.staleness_weights["worker-0"] == 1.0
        assert result.staleness_weights["worker-1"] == 0.5
        assert result.staleness_weights["worker-2"] == 0.25
        
        # Verify clipping applied (norm <= 1.0)
        for name, grad in result.aggregated_gradients.items():
            norm = torch.norm(grad).item()
            assert norm <= 1.0 + 1e-5
