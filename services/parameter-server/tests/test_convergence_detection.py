"""
Tests for Convergence Detection Service

Comprehensive tests covering:
- Loss threshold detection
- Metric target detection
- Plateau detection
- Early stopping (patience-based)
- Gradient norm detection
- Training phase management
- Metrics history tracking
"""

import pytest
import numpy as np
from typing import Dict

from app.services.convergence_detection import (
    ConvergenceDetectionService,
    TrainingMetrics,
    ConvergenceConfig,
    TrainingPhase,
    ConvergenceCriterion,
    MetricDirection
)


# ==================== Fixtures ====================

@pytest.fixture
def convergence_service():
    """Create convergence detection service"""
    return ConvergenceDetectionService()


@pytest.fixture
def basic_config():
    """Create basic convergence configuration"""
    return ConvergenceConfig(
        loss_threshold=0.1,
        loss_patience=5,
        max_iterations=100,
        warmup_iterations=2
    )


def create_metrics(
    iteration: int,
    loss: float,
    metrics: Dict[str, float] = None,
    gradient_norm: float = None
) -> TrainingMetrics:
    """Helper to create training metrics"""
    return TrainingMetrics(
        iteration=iteration,
        loss=loss,
        metrics=metrics or {},
        gradient_norm=gradient_norm,
        num_samples=100
    )


# ==================== Test Training Phase Management ====================

class TestTrainingPhases:
    """Test training phase transitions"""
    
    def test_initial_phase(self, convergence_service):
        """Test initial training phase"""
        model_id = "model-phase"
        
        metrics = create_metrics(0, 1.0)
        result = convergence_service.update_metrics(model_id, metrics)
        
        assert result.phase == TrainingPhase.WARMUP
    
    def test_warmup_to_training_transition(self, convergence_service):
        """Test transition from warmup to training"""
        model_id = "model-warmup"
        config = ConvergenceConfig(warmup_iterations=3)
        
        # During warmup
        for i in range(3):
            metrics = create_metrics(i, 1.0 - i * 0.1)
            result = convergence_service.update_metrics(model_id, metrics, config)
            if i < 3:
                assert result.phase == TrainingPhase.WARMUP
        
        # After warmup
        metrics = create_metrics(3, 0.7)
        result = convergence_service.update_metrics(model_id, metrics, config)
        assert result.phase == TrainingPhase.TRAINING
    
    def test_training_to_converged_transition(self, convergence_service):
        """Test transition from training to converged"""
        model_id = "model-converged"
        config = ConvergenceConfig(
            loss_threshold=0.1,
            warmup_iterations=1
        )
        
        # Warmup
        convergence_service.update_metrics(model_id, create_metrics(0, 1.0), config)
        
        # Training
        convergence_service.update_metrics(model_id, create_metrics(1, 0.5), config)
        
        # Converged
        result = convergence_service.update_metrics(
            model_id,
            create_metrics(2, 0.05),
            config
        )
        
        assert result.phase == TrainingPhase.CONVERGED
        assert result.converged is True


# ==================== Test Loss Threshold Detection ====================

class TestLossThreshold:
    """Test loss threshold convergence detection"""
    
    def test_loss_below_threshold(self, convergence_service):
        """Test convergence when loss below threshold"""
        model_id = "model-loss-threshold"
        config = ConvergenceConfig(
            loss_threshold=0.1,
            warmup_iterations=1
        )
        
        # Warmup
        convergence_service.update_metrics(model_id, create_metrics(0, 1.0), config)
        
        # Below threshold
        result = convergence_service.update_metrics(
            model_id,
            create_metrics(1, 0.05),
            config
        )
        
        assert result.converged is True
        assert ConvergenceCriterion.LOSS_THRESHOLD in result.criteria_met
        assert result.should_stop is True
    
    def test_loss_above_threshold(self, convergence_service):
        """Test no convergence when loss above threshold"""
        model_id = "model-loss-above"
        config = ConvergenceConfig(
            loss_threshold=0.1,
            warmup_iterations=1
        )
        
        # Warmup
        convergence_service.update_metrics(model_id, create_metrics(0, 1.0), config)
        
        # Above threshold
        result = convergence_service.update_metrics(
            model_id,
            create_metrics(1, 0.5),
            config
        )
        
        assert result.converged is False
        assert ConvergenceCriterion.LOSS_THRESHOLD not in result.criteria_met


# ==================== Test Metric Target Detection ====================

class TestMetricTargets:
    """Test metric target convergence detection"""
    
    def test_accuracy_target_maximize(self, convergence_service):
        """Test convergence when accuracy reaches target (maximize)"""
        model_id = "model-accuracy"
        config = ConvergenceConfig(
            target_metrics={"accuracy": (0.95, MetricDirection.MAXIMIZE)},
            warmup_iterations=1
        )
        
        # Warmup
        convergence_service.update_metrics(
            model_id,
            create_metrics(0, 1.0, {"accuracy": 0.5}),
            config
        )
        
        # Reach target
        result = convergence_service.update_metrics(
            model_id,
            create_metrics(1, 0.5, {"accuracy": 0.96}),
            config
        )
        
        assert result.converged is True
        assert ConvergenceCriterion.METRIC_THRESHOLD in result.criteria_met
    
    def test_error_rate_target_minimize(self, convergence_service):
        """Test convergence when error rate below target (minimize)"""
        model_id = "model-error"
        config = ConvergenceConfig(
            target_metrics={"error_rate": (0.05, MetricDirection.MINIMIZE)},
            warmup_iterations=1
        )
        
        # Warmup
        convergence_service.update_metrics(
            model_id,
            create_metrics(0, 1.0, {"error_rate": 0.5}),
            config
        )
        
        # Below target
        result = convergence_service.update_metrics(
            model_id,
            create_metrics(1, 0.5, {"error_rate": 0.03}),
            config
        )
        
        assert result.converged is True
        assert ConvergenceCriterion.METRIC_THRESHOLD in result.criteria_met
    
    def test_metric_not_reached(self, convergence_service):
        """Test no convergence when metric not reached"""
        model_id = "model-not-reached"
        config = ConvergenceConfig(
            target_metrics={"accuracy": (0.95, MetricDirection.MAXIMIZE)},
            warmup_iterations=1
        )
        
        # Warmup
        convergence_service.update_metrics(
            model_id,
            create_metrics(0, 1.0, {"accuracy": 0.5}),
            config
        )
        
        # Not reached
        result = convergence_service.update_metrics(
            model_id,
            create_metrics(1, 0.5, {"accuracy": 0.85}),
            config
        )
        
        assert result.converged is False


# ==================== Test Plateau Detection ====================

class TestPlateauDetection:
    """Test plateau detection"""
    
    def test_plateau_detection(self, convergence_service):
        """Test detecting training plateau"""
        model_id = "model-plateau"
        config = ConvergenceConfig(
            enable_plateau_detection=True,
            plateau_patience=5,
            plateau_threshold=0.001,
            warmup_iterations=2,
            window_size=5
        )
        
        # Warmup
        for i in range(2):
            convergence_service.update_metrics(
                model_id,
                create_metrics(i, 1.0 - i * 0.1),
                config
            )
        
        # Create plateau (same loss for multiple iterations)
        base_loss = 0.5
        for i in range(2, 20):
            # Add tiny noise to simulate plateau
            loss = base_loss + np.random.normal(0, 0.0001)
            result = convergence_service.update_metrics(
                model_id,
                create_metrics(i, loss),
                config
            )
        
        # Should detect plateau
        assert result.phase == TrainingPhase.PLATEAUED or result.should_stop
    
    def test_no_plateau_with_improvement(self, convergence_service):
        """Test no plateau when loss improving"""
        model_id = "model-improving"
        config = ConvergenceConfig(
            enable_plateau_detection=True,
            plateau_patience=5,
            warmup_iterations=1,
            window_size=5
        )
        
        # Warmup
        convergence_service.update_metrics(model_id, create_metrics(0, 1.0), config)
        
        # Continuously improving
        for i in range(1, 10):
            result = convergence_service.update_metrics(
                model_id,
                create_metrics(i, 1.0 - i * 0.1),
                config
            )
        
        assert result.phase != TrainingPhase.PLATEAUED


# ==================== Test Early Stopping (Patience) ====================

class TestEarlyStopping:
    """Test early stopping based on patience"""
    
    def test_early_stop_no_improvement(self, convergence_service):
        """Test early stopping when no improvement"""
        model_id = "model-early-stop"
        config = ConvergenceConfig(
            enable_early_stopping=True,
            early_stop_patience=5,
            loss_min_delta=0.01,
            warmup_iterations=1
        )
        
        # Warmup
        convergence_service.update_metrics(model_id, create_metrics(0, 1.0), config)
        
        # Initial improvement
        convergence_service.update_metrics(model_id, create_metrics(1, 0.5), config)
        
        # No improvement for patience iterations
        for i in range(2, 8):
            result = convergence_service.update_metrics(
                model_id,
                create_metrics(i, 0.5),
                config
            )
        
        assert result.should_stop is True
        assert ConvergenceCriterion.PATIENCE in result.criteria_met
    
    def test_no_early_stop_with_improvement(self, convergence_service):
        """Test no early stopping when consistently improving"""
        model_id = "model-keep-training"
        config = ConvergenceConfig(
            enable_early_stopping=True,
            early_stop_patience=5,
            loss_min_delta=0.01,
            warmup_iterations=1
        )
        
        # Warmup
        convergence_service.update_metrics(model_id, create_metrics(0, 1.0), config)
        
        # Continuous improvement
        for i in range(1, 10):
            result = convergence_service.update_metrics(
                model_id,
                create_metrics(i, 1.0 - i * 0.05),
                config
            )
        
        assert result.should_stop is False


# ==================== Test Gradient Norm Detection ====================

class TestGradientNorm:
    """Test gradient norm convergence detection"""
    
    def test_gradient_norm_below_threshold(self, convergence_service):
        """Test convergence when gradient norm below threshold"""
        model_id = "model-gradient"
        config = ConvergenceConfig(
            gradient_norm_threshold=0.001,
            warmup_iterations=1
        )
        
        # Warmup
        convergence_service.update_metrics(
            model_id,
            create_metrics(0, 1.0, gradient_norm=1.0),
            config
        )
        
        # Small gradient norm
        result = convergence_service.update_metrics(
            model_id,
            create_metrics(1, 0.5, gradient_norm=0.0005),
            config
        )
        
        assert result.converged is True
        assert ConvergenceCriterion.GRADIENT_NORM in result.criteria_met


# ==================== Test Max Iterations ====================

class TestMaxIterations:
    """Test maximum iterations stopping"""
    
    def test_max_iterations_reached(self, convergence_service):
        """Test stopping when max iterations reached"""
        model_id = "model-max-iter"
        config = ConvergenceConfig(
            max_iterations=5,
            warmup_iterations=1
        )
        
        # Warmup
        convergence_service.update_metrics(model_id, create_metrics(0, 1.0), config)
        
        # Train until max iterations
        for i in range(1, 6):
            result = convergence_service.update_metrics(
                model_id,
                create_metrics(i, 0.5),
                config
            )
        
        assert result.should_stop is True
        assert ConvergenceCriterion.MAX_ITERATIONS in result.criteria_met


# ==================== Test Best Metrics Tracking ====================

class TestBestMetrics:
    """Test tracking of best loss and metrics"""
    
    def test_best_loss_tracking(self, convergence_service):
        """Test tracking best loss"""
        model_id = "model-best-loss"
        config = ConvergenceConfig(warmup_iterations=1)
        
        # Warmup
        convergence_service.update_metrics(model_id, create_metrics(0, 1.0), config)
        
        # Varying losses
        convergence_service.update_metrics(model_id, create_metrics(1, 0.5), config)
        convergence_service.update_metrics(model_id, create_metrics(2, 0.3), config)
        convergence_service.update_metrics(model_id, create_metrics(3, 0.4), config)
        result = convergence_service.update_metrics(
            model_id,
            create_metrics(4, 0.2),
            config
        )
        
        assert result.best_loss == 0.2
        assert result.best_iteration == 4
    
    def test_best_metrics_tracking(self, convergence_service):
        """Test tracking best metrics"""
        model_id = "model-best-metrics"
        config = ConvergenceConfig(
            target_metrics={"accuracy": (1.0, MetricDirection.MAXIMIZE)},
            warmup_iterations=1
        )
        
        # Warmup
        convergence_service.update_metrics(
            model_id,
            create_metrics(0, 1.0, {"accuracy": 0.5}),
            config
        )
        
        # Varying accuracy
        convergence_service.update_metrics(
            model_id,
            create_metrics(1, 0.5, {"accuracy": 0.7}),
            config
        )
        convergence_service.update_metrics(
            model_id,
            create_metrics(2, 0.3, {"accuracy": 0.9}),
            config
        )
        convergence_service.update_metrics(
            model_id,
            create_metrics(3, 0.2, {"accuracy": 0.85}),
            config
        )
        result = convergence_service.update_metrics(
            model_id,
            create_metrics(4, 0.1, {"accuracy": 0.95}),
            config
        )
        
        assert result.best_metrics["accuracy"] == 0.95


# ==================== Test Metrics History ====================

class TestMetricsHistory:
    """Test metrics history tracking"""
    
    def test_history_storage(self, convergence_service):
        """Test storing metrics history"""
        model_id = "model-history"
        
        # Add multiple iterations
        for i in range(10):
            convergence_service.update_metrics(
                model_id,
                create_metrics(i, 1.0 - i * 0.1)
            )
        
        history = convergence_service.get_metrics_history(model_id)
        
        assert len(history) == 10
        # Newest first
        assert history[0].iteration == 9
        assert history[-1].iteration == 0
    
    def test_history_limit(self, convergence_service):
        """Test limiting history results"""
        model_id = "model-history-limit"
        
        # Add many iterations
        for i in range(20):
            convergence_service.update_metrics(
                model_id,
                create_metrics(i, 1.0 - i * 0.01)
            )
        
        history = convergence_service.get_metrics_history(model_id, limit=5)
        
        assert len(history) == 5
        # Should get most recent 5
        assert history[0].iteration == 19


# ==================== Test Convergence Summary ====================

class TestConvergenceSummary:
    """Test convergence summary"""
    
    def test_summary_generation(self, convergence_service):
        """Test generating convergence summary"""
        model_id = "model-summary"
        config = ConvergenceConfig(warmup_iterations=1)
        
        # Warmup
        convergence_service.update_metrics(model_id, create_metrics(0, 1.0), config)
        
        # Training
        for i in range(1, 10):
            convergence_service.update_metrics(
                model_id,
                create_metrics(i, 1.0 - i * 0.1, {"accuracy": 0.5 + i * 0.05}),
                config
            )
        
        summary = convergence_service.get_convergence_summary(model_id)
        
        assert summary["model_id"] == model_id
        assert summary["current_iteration"] == 9
        assert summary["total_iterations"] == 10
        assert "improvement_rate" in summary


# ==================== Test Reset Training ====================

class TestResetTraining:
    """Test resetting training state"""
    
    def test_reset_training(self, convergence_service):
        """Test resetting training state"""
        model_id = "model-reset"
        
        # Add some metrics
        for i in range(5):
            convergence_service.update_metrics(
                model_id,
                create_metrics(i, 1.0 - i * 0.1)
            )
        
        # Reset
        success = convergence_service.reset_training(model_id)
        assert success is True
        
        # State should be cleared
        state = convergence_service.get_training_state(model_id)
        assert state is None
    
    def test_reset_nonexistent(self, convergence_service):
        """Test resetting non-existent model"""
        success = convergence_service.reset_training("model-nonexistent")
        assert success is False


# ==================== Test Statistics ====================

class TestStatistics:
    """Test convergence statistics"""
    
    def test_service_statistics(self, convergence_service):
        """Test service statistics"""
        # Track multiple models
        for i in range(3):
            model_id = f"model-{i}"
            for j in range(5):
                convergence_service.update_metrics(
                    model_id,
                    create_metrics(j, 1.0 - j * 0.1)
                )
        
        stats = convergence_service.get_statistics()
        
        assert stats["total_models_tracked"] == 3
        assert stats["total_convergence_checks"] > 0


# ==================== Integration Tests ====================

class TestIntegration:
    """Integration tests for complete workflows"""
    
    def test_complete_training_workflow(self, convergence_service):
        """Test complete training workflow with convergence"""
        model_id = "model-workflow"
        config = ConvergenceConfig(
            loss_threshold=0.1,
            target_metrics={"accuracy": (0.9, MetricDirection.MAXIMIZE)},
            warmup_iterations=2,
            early_stop_patience=10
        )
        
        # Simulate training
        converged = False
        for i in range(50):
            # Simulate improving loss and accuracy
            loss = 1.0 * np.exp(-i * 0.1)
            accuracy = 1.0 - loss
            
            result = convergence_service.update_metrics(
                model_id,
                create_metrics(i, loss, {"accuracy": accuracy}),
                config
            )
            
            if result.should_stop:
                converged = result.converged
                break
        
        # Should converge
        assert converged is True
        
        # Check summary
        summary = convergence_service.get_convergence_summary(model_id)
        assert summary["phase"] in [
            TrainingPhase.CONVERGED.value,
            TrainingPhase.STOPPED.value
        ]
    
    def test_early_stopping_workflow(self, convergence_service):
        """Test early stopping workflow"""
        model_id = "model-early"
        config = ConvergenceConfig(
            enable_early_stopping=True,
            early_stop_patience=5,
            loss_min_delta=0.01,
            warmup_iterations=2
        )
        
        # Warmup
        for i in range(2):
            convergence_service.update_metrics(
                model_id,
                create_metrics(i, 1.0 - i * 0.2),
                config
            )
        
        # No improvement
        stopped = False
        for i in range(2, 20):
            result = convergence_service.update_metrics(
                model_id,
                create_metrics(i, 0.6),  # Constant loss
                config
            )
            
            if result.should_stop:
                stopped = True
                break
        
        # Should stop early
        assert stopped is True
        assert result.converged is False  # Not converged, just stopped
