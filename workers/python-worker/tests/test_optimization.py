"""
Tests for device and memory optimization utilities
"""

import time
from unittest.mock import MagicMock, patch

import pytest

from meshml_worker.utils.optimization import (
    MemoryProfiler,
    OptimizedDataLoader,
    PerformanceBenchmark,
    benchmark_device_performance,
    optimize_dataloader_settings,
)

# Check if torch is available
try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

# Decorator to skip tests that require torch
requires_torch = pytest.mark.skipif(not TORCH_AVAILABLE, reason="PyTorch not installed")


class TestMemoryProfiler:
    """Tests for MemoryProfiler"""
    
    def test_init_cpu(self):
        """Test profiler initialization for CPU"""
        profiler = MemoryProfiler(device="cpu")
        assert profiler.device == "cpu"
        assert profiler.device_type == "cpu"
        assert profiler.stats == {}
    
    def test_init_cuda(self):
        """Test profiler initialization for CUDA"""
        profiler = MemoryProfiler(device="cuda:0")
        assert profiler.device == "cuda:0"
        assert profiler.device_type == "cuda"
    
    def test_init_mps(self):
        """Test profiler initialization for MPS"""
        profiler = MemoryProfiler(device="mps")
        assert profiler.device == "mps"
        assert profiler.device_type == "mps"
    
    @requires_torch
    @patch("torch.cuda.is_available", return_value=True)
    @patch("torch.cuda.memory_allocated", return_value=1024 * 1024)
    @patch("torch.cuda.memory_reserved", return_value=2048 * 1024)
    @patch("torch.cuda.max_memory_allocated", return_value=1536 * 1024)
    @patch("torch.cuda.max_memory_reserved", return_value=2560 * 1024)
    def test_get_current_memory_cuda(self, *mocks):
        """Test getting current memory for CUDA"""
        profiler = MemoryProfiler(device="cuda:0")
        memory = profiler.get_current_memory()
        
        assert "allocated" in memory
        assert "reserved" in memory
        assert "max_allocated" in memory
        assert "max_reserved" in memory
        assert memory["allocated"] == 1024 * 1024
    
    def test_get_current_memory_cpu(self):
        """Test getting current memory for CPU"""
        profiler = MemoryProfiler(device="cpu")
        memory = profiler.get_current_memory()
        
        # Should have RSS and VMS if psutil is available
        if memory:
            assert "rss" in memory or "vms" in memory
    
    @requires_torch
    @patch("torch.cuda.is_available", return_value=True)
    @patch("torch.cuda.memory_allocated")
    def test_profile_context(self, mock_allocated, mock_available):
        """Test profiling context manager"""
        # Setup mock to return different values
        mock_allocated.side_effect = [1000, 2000]  # before, after
        
        profiler = MemoryProfiler(device="cuda:0")
        
        with profiler.profile("test_operation"):
            time.sleep(0.01)  # Simulate work
        
        stats = profiler.get_stats("test_operation")
        assert "duration_seconds" in stats
        assert stats["duration_seconds"] > 0
        assert "memory_before" in stats
        assert "memory_after" in stats
    
    def test_profile_disabled(self):
        """Test profiling when disabled"""
        profiler = MemoryProfiler(device="cpu")
        profiler._enabled = False
        
        with profiler.profile("test"):
            pass
        
        # Should not create stats when disabled
        stats = profiler.get_stats("test")
        assert stats == {}
    
    @requires_torch
    @patch("torch.cuda.is_available", return_value=True)
    @patch("torch.cuda.memory_allocated", return_value=1000)
    def test_get_stats(self, *mocks):
        """Test getting statistics"""
        profiler = MemoryProfiler(device="cuda:0")
        
        with profiler.profile("op1"):
            pass
        
        with profiler.profile("op2"):
            pass
        
        # Get all stats
        all_stats = profiler.get_stats()
        assert "op1" in all_stats
        assert "op2" in all_stats
        
        # Get specific stats
        op1_stats = profiler.get_stats("op1")
        assert "duration_seconds" in op1_stats
        
        # Get non-existent stats
        missing = profiler.get_stats("missing")
        assert missing == {}
    
    @requires_torch
    @patch("torch.cuda.is_available", return_value=True)
    @patch("torch.cuda.memory_allocated", return_value=1000)
    @patch("torch.cuda.reset_peak_memory_stats")
    def test_reset(self, mock_reset, *mocks):
        """Test resetting statistics"""
        profiler = MemoryProfiler(device="cuda:0")
        
        with profiler.profile("test"):
            pass
        
        assert len(profiler.stats) > 0
        
        profiler.reset()
        assert len(profiler.stats) == 0
        mock_reset.assert_called_once()
    
    @requires_torch
    @patch("torch.cuda.is_available", return_value=True)
    @patch("torch.cuda.memory_allocated", return_value=1000)
    def test_print_summary(self, mock_allocated, mock_available, caplog):
        """Test printing summary"""
        import logging
        caplog.set_level(logging.INFO)
        
        profiler = MemoryProfiler(device="cuda:0")
        
        with profiler.profile("test_op"):
            time.sleep(0.01)
        
        profiler.print_summary()
        
        # Check that summary was logged
        assert "Memory Profiling Summary" in caplog.text
        assert "test_op" in caplog.text
    
    def test_print_summary_empty(self, caplog):
        """Test printing summary with no data"""
        import logging
        caplog.set_level(logging.INFO)
        
        profiler = MemoryProfiler(device="cpu")
        profiler.print_summary()
        
        assert "No profiling data available" in caplog.text


class TestPerformanceBenchmark:
    """Tests for PerformanceBenchmark"""
    
    def test_init(self):
        """Test benchmark initialization"""
        benchmark = PerformanceBenchmark()
        assert benchmark.epoch_start_time is None
        assert benchmark.batch_start_time is None
        assert len(benchmark.epoch_times) == 0
        assert len(benchmark.batch_times) == 0
        assert benchmark.samples_processed == 0
        assert benchmark.batches_processed == 0
    
    def test_epoch_timing(self):
        """Test epoch timing"""
        benchmark = PerformanceBenchmark()
        
        benchmark.start_epoch()
        assert benchmark.epoch_start_time is not None
        
        time.sleep(0.01)
        
        benchmark.end_epoch()
        assert benchmark.epoch_start_time is None
        assert len(benchmark.epoch_times) == 1
        assert benchmark.epoch_times[0] > 0
    
    def test_batch_timing(self):
        """Test batch timing"""
        benchmark = PerformanceBenchmark()
        
        benchmark.start_batch()
        assert benchmark.batch_start_time is not None
        
        time.sleep(0.01)
        
        benchmark.end_batch(batch_size=32)
        assert benchmark.batch_start_time is None
        assert len(benchmark.batch_times) == 1
        assert benchmark.batch_times[0] > 0
        assert benchmark.samples_processed == 32
        assert benchmark.batches_processed == 1
    
    def test_multiple_epochs(self):
        """Test multiple epochs"""
        benchmark = PerformanceBenchmark()
        
        for _ in range(3):
            benchmark.start_epoch()
            time.sleep(0.01)
            benchmark.end_epoch()
        
        assert len(benchmark.epoch_times) == 3
    
    def test_multiple_batches(self):
        """Test multiple batches"""
        benchmark = PerformanceBenchmark()
        
        for i in range(5):
            benchmark.start_batch()
            time.sleep(0.005)
            benchmark.end_batch(batch_size=16)
        
        assert len(benchmark.batch_times) == 5
        assert benchmark.samples_processed == 80  # 5 * 16
        assert benchmark.batches_processed == 5
    
    def test_get_stats_empty(self):
        """Test getting stats with no data"""
        benchmark = PerformanceBenchmark()
        stats = benchmark.get_stats()
        
        assert stats == {"total_samples": 0}
    
    def test_get_stats_epoch_only(self):
        """Test getting stats with epoch data only"""
        benchmark = PerformanceBenchmark()
        
        benchmark.start_epoch()
        time.sleep(0.01)
        benchmark.end_epoch()
        
        stats = benchmark.get_stats()
        assert "avg_epoch_time" in stats
        assert "total_epochs" in stats
        assert stats["total_epochs"] == 1
        assert stats["avg_epoch_time"] > 0
    
    def test_get_stats_batch_only(self):
        """Test getting stats with batch data only"""
        benchmark = PerformanceBenchmark()
        
        for _ in range(3):
            benchmark.start_batch()
            time.sleep(0.01)
            benchmark.end_batch(batch_size=32)
        
        stats = benchmark.get_stats()
        assert "avg_batch_time" in stats
        assert "total_batches" in stats
        assert "samples_per_second" in stats
        assert "batches_per_second" in stats
        assert stats["total_batches"] == 3
        assert stats["total_samples"] == 96
    
    def test_get_stats_complete(self):
        """Test getting complete stats"""
        benchmark = PerformanceBenchmark()
        
        benchmark.start_epoch()
        for _ in range(5):
            benchmark.start_batch()
            time.sleep(0.01)
            benchmark.end_batch(batch_size=16)
        benchmark.end_epoch()
        
        stats = benchmark.get_stats()
        assert "avg_epoch_time" in stats
        assert "avg_batch_time" in stats
        assert "samples_per_second" in stats
        assert stats["total_samples"] == 80
    
    def test_reset(self):
        """Test resetting statistics"""
        benchmark = PerformanceBenchmark()
        
        benchmark.start_epoch()
        benchmark.end_epoch()
        
        benchmark.start_batch()
        benchmark.end_batch(batch_size=32)
        
        assert len(benchmark.epoch_times) > 0
        assert len(benchmark.batch_times) > 0
        assert benchmark.samples_processed > 0
        
        benchmark.reset()
        
        assert len(benchmark.epoch_times) == 0
        assert len(benchmark.batch_times) == 0
        assert benchmark.samples_processed == 0
        assert benchmark.batches_processed == 0
    
    def test_print_summary(self, caplog):
        """Test printing summary"""
        import logging
        caplog.set_level(logging.INFO)
        
        benchmark = PerformanceBenchmark()
        
        benchmark.start_epoch()
        for _ in range(3):
            benchmark.start_batch()
            time.sleep(0.01)
            benchmark.end_batch(batch_size=32)
        benchmark.end_epoch()
        
        benchmark.print_summary()
        
        assert "Performance Benchmark Summary" in caplog.text
        assert "Average epoch time" in caplog.text
        assert "Samples per second" in caplog.text
    
    def test_print_summary_empty(self, caplog):
        """Test printing summary with no data"""
        import logging
        caplog.set_level(logging.INFO)
        
        benchmark = PerformanceBenchmark()
        benchmark.print_summary()
        
        assert "No benchmark data available" in caplog.text


class TestOptimizeDataLoaderSettings:
    """Tests for optimize_dataloader_settings"""
    
    def test_cuda_device(self):
        """Test optimization for CUDA device"""
        settings = optimize_dataloader_settings(
            device="cuda:0",
            batch_size=32,
            dataset_size=1000
        )
        
        assert settings["pin_memory"] is True
        assert settings["num_workers"] > 0
        assert settings["persistent_workers"] is True
        assert settings["prefetch_factor"] == 2
    
    def test_mps_device(self):
        """Test optimization for MPS device"""
        settings = optimize_dataloader_settings(
            device="mps",
            batch_size=32,
            dataset_size=1000
        )
        
        assert settings["pin_memory"] is False
        assert settings["num_workers"] > 0
    
    def test_cpu_device(self):
        """Test optimization for CPU device"""
        settings = optimize_dataloader_settings(
            device="cpu",
            batch_size=32,
            dataset_size=1000
        )
        
        assert settings["pin_memory"] is False
        assert settings["num_workers"] >= 0
    
    def test_small_dataset(self):
        """Test optimization for small dataset"""
        settings = optimize_dataloader_settings(
            device="cuda:0",
            batch_size=32,
            dataset_size=100  # Only 3 batches
        )
        
        # Should use 0 workers for small dataset
        assert settings["num_workers"] == 0
        assert settings["persistent_workers"] is False
        assert settings["prefetch_factor"] is None
    
    def test_large_dataset(self):
        """Test optimization for large dataset"""
        settings = optimize_dataloader_settings(
            device="cuda:0",
            batch_size=32,
            dataset_size=10000
        )
        
        # Should use multiple workers
        assert settings["num_workers"] > 0
        assert settings["persistent_workers"] is True


class TestOptimizedDataLoader:
    """Tests for OptimizedDataLoader"""
    
    @pytest.fixture
    def mock_dataset(self):
        """Create mock dataset"""
        dataset = MagicMock()
        dataset.__len__ = MagicMock(return_value=1000)
        return dataset
    
    @requires_torch
    def test_init_cuda(self, mock_dataset):
        """Test initialization for CUDA"""
        loader = OptimizedDataLoader(
            dataset=mock_dataset,
            batch_size=32,
            device="cuda:0",
            num_workers=0  # Avoid pickling issues with mock in tests
        )
        
        assert loader.device == "cuda:0"
        assert loader.batch_size == 32
        assert loader.dataloader is not None
    
    @requires_torch
    def test_init_cpu(self, mock_dataset):
        """Test initialization for CPU"""
        loader = OptimizedDataLoader(
            dataset=mock_dataset,
            batch_size=32,
            device="cpu",
            num_workers=0  # Avoid pickling issues with mock in tests
        )
        
        assert loader.device == "cpu"
    
    @requires_torch
    def test_custom_kwargs(self, mock_dataset):
        """Test that custom kwargs override optimizations"""
        loader = OptimizedDataLoader(
            dataset=mock_dataset,
            batch_size=32,
            device="cuda:0",
            num_workers=8,  # Override
            pin_memory=False  # Override
        )
        
        # Custom values should be used
        assert loader.dataloader.num_workers == 8
        assert loader.dataloader.pin_memory is False
    
    @requires_torch
    def test_shuffle(self, mock_dataset):
        """Test shuffle parameter"""
        loader = OptimizedDataLoader(
            dataset=mock_dataset,
            batch_size=32,
            device="cpu",
            shuffle=False,
            num_workers=0  # Avoid pickling issues with mock in tests
        )
        
        # Note: DataLoader doesn't expose shuffle directly,
        # but we can verify it was created
        assert loader.dataloader is not None
    
    @requires_torch
    def test_len(self, mock_dataset):
        """Test __len__"""
        loader = OptimizedDataLoader(
            dataset=mock_dataset,
            batch_size=32,
            device="cpu",
            num_workers=0  # Avoid pickling issues with mock in tests
        )
        
        # 1000 samples / 32 batch_size = 32 batches (rounded up)
        expected_len = (1000 + 31) // 32
        assert len(loader) == expected_len
    
    @requires_torch
    def test_iter(self, mock_dataset):
        """Test __iter__"""
        loader = OptimizedDataLoader(
            dataset=mock_dataset,
            batch_size=32,
            device="cpu",
            num_workers=0  # Avoid pickling issues with mock in tests
        )
        
        # Should be iterable
        iterator = iter(loader)
        assert iterator is not None
    
    @requires_torch
    def test_small_dataset(self, mock_dataset):
        """Test with small dataset"""
        mock_dataset.__len__ = MagicMock(return_value=50)
        
        loader = OptimizedDataLoader(
            dataset=mock_dataset,
            batch_size=32,
            device="cuda:0"
        )
        
        # Small dataset should use 0 workers
        assert loader.dataloader.num_workers == 0


class TestBenchmarkDevicePerformance:
    """Tests for benchmark_device_performance"""
    
    @pytest.fixture
    def mock_model(self):
        """Create mock model"""
        model = MagicMock()
        model.to = MagicMock(return_value=model)
        model.eval = MagicMock()
        model.__call__ = MagicMock(return_value=MagicMock())
        return model
    
    @requires_torch
    @patch("torch.randn")
    @patch("torch.no_grad")
    def test_benchmark_cpu(self, mock_no_grad, mock_randn, mock_model):
        """Test benchmarking on CPU"""
        mock_randn.return_value = MagicMock()
        
        results = benchmark_device_performance(
            device="cpu",
            model=mock_model,
            input_shape=(32, 3, 224, 224)
        )
        
        assert "samples_per_second" in results
        assert "ms_per_batch" in results
        assert "total_iterations" in results
        assert results["total_iterations"] == 100
    
    @requires_torch
    @patch("torch.cuda.is_available", return_value=True)
    @patch("torch.cuda.synchronize")
    @patch("torch.randn")
    @patch("torch.no_grad")
    def test_benchmark_cuda(self, mock_no_grad, mock_randn, mock_sync, mock_available, mock_model):
        """Test benchmarking on CUDA"""
        mock_randn.return_value = MagicMock()
        
        results = benchmark_device_performance(
            device="cuda:0",
            model=mock_model,
            input_shape=(32, 3, 224, 224)
        )
        
        assert "samples_per_second" in results
        assert "ms_per_batch" in results
        
        # Should synchronize for CUDA
        assert mock_sync.call_count > 0
    
    @requires_torch
    @patch("torch.randn")
    @patch("torch.no_grad")
    def test_benchmark_model_called(self, mock_no_grad, mock_randn, mock_model):
        """Test that model is called during benchmark"""
        mock_randn.return_value = MagicMock()
        
        benchmark_device_performance(
            device="cpu",
            model=mock_model,
            input_shape=(16, 3, 32, 32)
        )
        
        # Model should be called for warmup (10) + benchmark (100)
        assert mock_model.call_count >= 100
    
    def test_benchmark_no_torch(self, mock_model):
        """Test benchmark when PyTorch is available"""
        # Since we now require torch to be installed, just verify it works
        if TORCH_AVAILABLE:
            results = benchmark_device_performance(
                device="cpu",
                model=mock_model,
                input_shape=(32, 3, 224, 224)
            )
            
            # Should return results when torch is available
            assert isinstance(results, dict)
            assert "samples_per_second" in results
        else:
            # If torch not available, should return empty dict
            results = benchmark_device_performance(
                device="cpu",
                model=mock_model,
                input_shape=(32, 3, 224, 224)
            )
            assert results == {}



class TestIntegration:
    """Integration tests for optimization utilities"""
    
    @pytest.fixture
    def mock_dataset(self):
        """Create mock dataset"""
        dataset = MagicMock()
        dataset.__len__ = MagicMock(return_value=1000)
        return dataset
    
    def test_profiler_and_benchmark_together(self, mock_dataset):
        """Test using profiler and benchmark together"""
        profiler = MemoryProfiler(device="cpu")
        benchmark = PerformanceBenchmark()
        
        # Simulate training loop
        benchmark.start_epoch()
        
        for i in range(5):
            with profiler.profile(f"batch_{i}"):
                benchmark.start_batch()
                time.sleep(0.01)
                benchmark.end_batch(batch_size=32)
        
        benchmark.end_epoch()
        
        # Check profiler stats
        profiler_stats = profiler.get_stats()
        assert len(profiler_stats) == 5
        
        # Check benchmark stats
        benchmark_stats = benchmark.get_stats()
        assert benchmark_stats["total_batches"] == 5
        assert benchmark_stats["total_samples"] == 160
    
    @requires_torch
    def test_optimized_dataloader_with_profiler(self, mock_dataset):
        """Test OptimizedDataLoader with memory profiling"""
        loader = OptimizedDataLoader(
            dataset=mock_dataset,
            batch_size=32,
            device="cpu",
            num_workers=0  # Avoid pickling issues with mock in tests
        )
        
        profiler = MemoryProfiler(device="cpu")
        
        # Profile creating an iterator
        with profiler.profile("create_iterator"):
            iterator = iter(loader)
        
        stats = profiler.get_stats("create_iterator")
        assert "duration_seconds" in stats
    
    @requires_torch
    def test_full_training_simulation(self, mock_dataset):
        """Test full training simulation with all tools"""
        # Setup
        loader = OptimizedDataLoader(
            dataset=mock_dataset,
            batch_size=32,
            device="cpu",
            shuffle=True,
            num_workers=0  # Avoid pickling issues with mock in tests
        )
        
        profiler = MemoryProfiler(device="cpu")
        benchmark = PerformanceBenchmark()
        
        # Simulate 2 epochs
        for epoch in range(2):
            benchmark.start_epoch()
            
            with profiler.profile(f"epoch_{epoch}"):
                # Simulate batches (just 3 for testing)
                for batch_idx in range(3):
                    benchmark.start_batch()
                    time.sleep(0.005)
                    benchmark.end_batch(batch_size=32)
            
            benchmark.end_epoch()
        
        # Verify results
        profiler_stats = profiler.get_stats()
        assert len(profiler_stats) == 2  # 2 epochs
        
        benchmark_stats = benchmark.get_stats()
        assert benchmark_stats["total_epochs"] == 2
        assert benchmark_stats["total_batches"] == 6  # 2 epochs * 3 batches
        assert benchmark_stats["total_samples"] == 192  # 6 * 32
