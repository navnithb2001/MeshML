"""Tests for batch storage management."""

import os
import json
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timedelta

import pytest
import numpy as np
from PIL import Image

from app.services.dataset_loader import DataSample
from app.services.dataset_sharder import ShardMetadata
from app.services.batch_storage import (
    BatchMetadata,
    LocalBatchStorage,
    BatchManager,
    create_storage_backend
)


@pytest.fixture
def temp_storage_path():
    """Create temporary storage directory."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def sample_data_samples():
    """Create sample DataSample instances."""
    samples = []
    
    for i in range(10):
        # Create small dummy image
        img = Image.new('RGB', (32, 32), color=(i * 25, 100, 150))
        img_array = np.array(img)
        
        sample = DataSample(
            index=i,
            data=img_array,
            label=i % 3,  # 3 classes
            metadata={"class_name": f"class_{i % 3}"}
        )
        samples.append(sample)
    
    return samples


@pytest.fixture
def sample_batch_metadata():
    """Create sample BatchMetadata."""
    return BatchMetadata(
        batch_id="test_batch_0",
        shard_id=0,
        batch_index=0,
        num_samples=10,
        sample_indices=[0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
        class_distribution={"0": 4, "1": 3, "2": 3},
        size_bytes=0,
        checksum="",
        storage_path="",
        format="pickle",
        created_at=datetime.utcnow().isoformat()
    )


class TestBatchMetadata:
    """Test BatchMetadata dataclass."""
    
    def test_to_dict(self, sample_batch_metadata):
        """Test conversion to dictionary."""
        data = sample_batch_metadata.to_dict()
        
        assert data["batch_id"] == "test_batch_0"
        assert data["shard_id"] == 0
        assert data["num_samples"] == 10
        assert "class_distribution" in data
    
    def test_from_dict(self):
        """Test creation from dictionary."""
        data = {
            "batch_id": "test_batch_1",
            "shard_id": 1,
            "batch_index": 0,
            "num_samples": 5,
            "sample_indices": [0, 1, 2, 3, 4],
            "class_distribution": {"0": 2, "1": 3},
            "size_bytes": 1024,
            "checksum": "abc123",
            "storage_path": "/path/to/batch",
            "format": "pickle",
            "created_at": datetime.utcnow().isoformat()
        }
        
        metadata = BatchMetadata.from_dict(data)
        
        assert metadata.batch_id == "test_batch_1"
        assert metadata.num_samples == 5
        assert metadata.size_bytes == 1024


class TestLocalBatchStorage:
    """Test local filesystem storage."""
    
    def test_initialization(self, temp_storage_path):
        """Test storage initialization."""
        storage = LocalBatchStorage(base_path=temp_storage_path)
        
        assert storage.base_path.exists()
        assert storage.batches_dir.exists()
        assert storage.metadata_dir.exists()
    
    def test_save_and_load_batch(
        self,
        temp_storage_path,
        sample_data_samples,
        sample_batch_metadata
    ):
        """Test saving and loading a batch."""
        storage = LocalBatchStorage(base_path=temp_storage_path)
        
        # Save batch
        storage_path = storage.save_batch(sample_data_samples, sample_batch_metadata)
        
        assert os.path.exists(storage_path)
        assert sample_batch_metadata.size_bytes > 0
        assert sample_batch_metadata.checksum != ""
        
        # Load batch
        loaded_samples, loaded_metadata = storage.load_batch(sample_batch_metadata.batch_id)
        
        assert len(loaded_samples) == len(sample_data_samples)
        assert loaded_metadata.batch_id == sample_batch_metadata.batch_id
        assert loaded_metadata.num_samples == sample_batch_metadata.num_samples
        
        # Verify sample data
        for orig, loaded in zip(sample_data_samples, loaded_samples):
            assert orig.index == loaded.index
            assert orig.label == loaded.label
            np.testing.assert_array_equal(orig.data, loaded.data)
    
    def test_checksum_verification(
        self,
        temp_storage_path,
        sample_data_samples,
        sample_batch_metadata
    ):
        """Test checksum calculation and verification."""
        storage = LocalBatchStorage(base_path=temp_storage_path)
        
        # Save batch
        storage.save_batch(sample_data_samples, sample_batch_metadata)
        
        # Load and verify checksum is calculated
        samples, metadata = storage.load_batch(sample_batch_metadata.batch_id)
        
        assert metadata.checksum != ""
        assert len(metadata.checksum) == 64  # SHA256 hex digest
    
    def test_delete_batch(
        self,
        temp_storage_path,
        sample_data_samples,
        sample_batch_metadata
    ):
        """Test batch deletion."""
        storage = LocalBatchStorage(base_path=temp_storage_path)
        
        # Save batch
        storage.save_batch(sample_data_samples, sample_batch_metadata)
        
        # Delete batch
        deleted = storage.delete_batch(sample_batch_metadata.batch_id)
        
        assert deleted is True
        
        # Verify batch is gone
        with pytest.raises(FileNotFoundError):
            storage.load_batch(sample_batch_metadata.batch_id)
    
    def test_list_batches(
        self,
        temp_storage_path,
        sample_data_samples
    ):
        """Test listing batches."""
        storage = LocalBatchStorage(base_path=temp_storage_path)
        
        # Create multiple batches
        for i in range(5):
            metadata = BatchMetadata(
                batch_id=f"batch_{i}",
                shard_id=i // 2,  # 2 batches per shard
                batch_index=i % 2,
                num_samples=len(sample_data_samples),
                sample_indices=list(range(len(sample_data_samples))),
                class_distribution={"0": 4, "1": 3, "2": 3},
                size_bytes=0,
                checksum="",
                storage_path="",
                format="pickle",
                created_at=datetime.utcnow().isoformat()
            )
            storage.save_batch(sample_data_samples, metadata)
        
        # List all batches
        all_batches = storage.list_batches()
        assert len(all_batches) == 5
        
        # List batches for specific shard
        shard_0_batches = storage.list_batches(shard_id=0)
        assert len(shard_0_batches) == 2
        assert all(b.shard_id == 0 for b in shard_0_batches)
    
    def test_storage_stats(
        self,
        temp_storage_path,
        sample_data_samples,
        sample_batch_metadata
    ):
        """Test storage statistics."""
        storage = LocalBatchStorage(base_path=temp_storage_path)
        
        # Save a batch
        storage.save_batch(sample_data_samples, sample_batch_metadata)
        
        stats = storage.get_storage_stats()
        
        assert stats["total_batches"] == 1
        assert stats["total_size_bytes"] > 0
        assert stats["total_size_mb"] > 0
        assert stats["storage_path"] == str(storage.base_path)


class TestBatchManager:
    """Test BatchManager functionality."""
    
    def test_initialization(self, temp_storage_path):
        """Test manager initialization."""
        storage = LocalBatchStorage(base_path=temp_storage_path)
        manager = BatchManager(storage_backend=storage)
        
        assert manager.storage == storage
        assert manager.auto_cleanup is False
    
    def test_create_batches_from_shard(
        self,
        temp_storage_path,
        sample_data_samples
    ):
        """Test creating batches from a shard."""
        from app.services.dataset_loader import DatasetLoader
        
        # Create mock loader
        class MockLoader(DatasetLoader):
            def __init__(self, samples):
                self.samples = samples
                self._metadata = None
            
            def load_metadata(self):
                return None
            
            def stream_samples(self):
                return iter(self.samples)
            
            def get_sample(self, index):
                return self.samples[index]
        
        loader = MockLoader(sample_data_samples)
        
        # Create shard metadata
        shard = ShardMetadata(
            shard_id=0,
            num_samples=len(sample_data_samples),
            sample_indices=list(range(len(sample_data_samples))),
            class_distribution={"0": 4, "1": 3, "2": 3}
        )
        
        # Create batch manager
        storage = LocalBatchStorage(base_path=temp_storage_path)
        manager = BatchManager(storage_backend=storage)
        
        # Create batches
        batch_size = 3
        batches = manager.create_batches_from_shard(shard, loader, batch_size)
        
        # Verify batches
        expected_num_batches = (len(sample_data_samples) + batch_size - 1) // batch_size
        assert len(batches) == expected_num_batches
        
        # Verify batch metadata
        for i, batch in enumerate(batches):
            assert batch.shard_id == 0
            assert batch.batch_index == i
            assert batch.size_bytes > 0
            assert batch.checksum != ""
            
            # Verify batch can be loaded
            samples, metadata = manager.load_batch(batch.batch_id)
            assert len(samples) <= batch_size
    
    def test_batch_stats(
        self,
        temp_storage_path,
        sample_data_samples
    ):
        """Test batch statistics calculation."""
        storage = LocalBatchStorage(base_path=temp_storage_path)
        manager = BatchManager(storage_backend=storage)
        
        # Create multiple batches for different shards
        for shard_id in range(2):
            for batch_idx in range(2):
                metadata = BatchMetadata(
                    batch_id=f"shard_{shard_id}_batch_{batch_idx}",
                    shard_id=shard_id,
                    batch_index=batch_idx,
                    num_samples=5,
                    sample_indices=list(range(5)),
                    class_distribution={"0": 2, "1": 3},
                    size_bytes=0,
                    checksum="",
                    storage_path="",
                    format="pickle",
                    created_at=datetime.utcnow().isoformat()
                )
                storage.save_batch(sample_data_samples[:5], metadata)
        
        # Get stats
        stats = manager.get_batch_stats()
        
        assert stats["total_batches"] == 4
        assert stats["total_samples"] == 20
        assert stats["num_shards"] == 2
        assert stats["total_size_bytes"] > 0
        
        # Verify per-shard stats
        assert 0 in stats["shard_stats"]
        assert 1 in stats["shard_stats"]
        assert stats["shard_stats"][0]["num_batches"] == 2
        assert stats["shard_stats"][0]["num_samples"] == 10
    
    def test_cleanup_old_batches(
        self,
        temp_storage_path,
        sample_data_samples
    ):
        """Test cleanup of old batches."""
        storage = LocalBatchStorage(base_path=temp_storage_path)
        manager = BatchManager(storage_backend=storage)
        
        # Create old batch
        old_time = (datetime.utcnow() - timedelta(hours=48)).isoformat()
        old_metadata = BatchMetadata(
            batch_id="old_batch",
            shard_id=0,
            batch_index=0,
            num_samples=5,
            sample_indices=list(range(5)),
            class_distribution={"0": 2, "1": 3},
            size_bytes=0,
            checksum="",
            storage_path="",
            format="pickle",
            created_at=old_time
        )
        storage.save_batch(sample_data_samples[:5], old_metadata)
        
        # Create recent batch
        recent_metadata = BatchMetadata(
            batch_id="recent_batch",
            shard_id=0,
            batch_index=1,
            num_samples=5,
            sample_indices=list(range(5)),
            class_distribution={"0": 2, "1": 3},
            size_bytes=0,
            checksum="",
            storage_path="",
            format="pickle",
            created_at=datetime.utcnow().isoformat()
        )
        storage.save_batch(sample_data_samples[:5], recent_metadata)
        
        # Cleanup batches older than 24 hours
        deleted_count = manager.cleanup_old_batches(max_age_hours=24)
        
        assert deleted_count == 1
        
        # Verify old batch is gone
        batches = manager.list_batches()
        assert len(batches) == 1
        assert batches[0].batch_id == "recent_batch"


class TestStorageFactory:
    """Test storage backend factory."""
    
    def test_create_local_storage(self, temp_storage_path):
        """Test creating local storage backend."""
        storage = create_storage_backend(
            storage_type="local",
            base_path=temp_storage_path
        )
        
        assert isinstance(storage, LocalBatchStorage)
        assert storage.base_path == Path(temp_storage_path)
    
    def test_unsupported_storage_type(self):
        """Test error for unsupported storage type."""
        with pytest.raises(ValueError, match="Unsupported storage type"):
            create_storage_backend(storage_type="unsupported")


class TestErrorHandling:
    """Test error handling scenarios."""
    
    def test_load_nonexistent_batch(self, temp_storage_path):
        """Test loading non-existent batch."""
        storage = LocalBatchStorage(base_path=temp_storage_path)
        
        with pytest.raises(FileNotFoundError):
            storage.load_batch("nonexistent_batch")
    
    def test_delete_nonexistent_batch(self, temp_storage_path):
        """Test deleting non-existent batch."""
        storage = LocalBatchStorage(base_path=temp_storage_path)
        
        deleted = storage.delete_batch("nonexistent_batch")
        assert deleted is False
    
    def test_empty_batch_list(self, temp_storage_path):
        """Test listing batches when none exist."""
        storage = LocalBatchStorage(base_path=temp_storage_path)
        manager = BatchManager(storage_backend=storage)
        
        batches = manager.list_batches()
        assert batches == []
        
        stats = manager.get_batch_stats()
        assert stats["total_batches"] == 0
        assert stats["total_samples"] == 0


class TestIntegration:
    """Integration tests with dataset loader and sharder."""
    
    def test_end_to_end_workflow(self, temp_storage_path):
        """Test complete workflow from sharding to storage."""
        from app.services.dataset_loader import DatasetLoader, DataSample
        from app.services.dataset_sharder import (
            DatasetSharder,
            ShardingConfig,
            ShardingStrategy
        )
        
        # Create mock loader
        class MockLoader(DatasetLoader):
            def __init__(self):
                self.samples = []
                for i in range(30):
                    img = Image.new('RGB', (32, 32), color=(i * 8, 100, 150))
                    sample = DataSample(
                        index=i,
                        data=np.array(img),
                        label=i % 3,
                        metadata={"class_name": f"class_{i % 3}"}
                    )
                    self.samples.append(sample)
                self._metadata = None
            
            def load_metadata(self):
                return None
            
            def stream_samples(self):
                return iter(self.samples)
            
            def get_sample(self, index):
                return self.samples[index]
        
        loader = MockLoader()
        
        # Create shards
        sharder = DatasetSharder()
        config = ShardingConfig(
            num_shards=3,
            strategy=ShardingStrategy.STRATIFIED,
            seed=42
        )
        
        shards = sharder.create_shards(loader, config)
        
        # Store batches for each shard
        storage = LocalBatchStorage(base_path=temp_storage_path)
        manager = BatchManager(storage_backend=storage)
        
        all_batches = []
        for shard in shards:
            batches = manager.create_batches_from_shard(shard, loader, batch_size=5)
            all_batches.extend(batches)
        
        # Verify all batches created
        assert len(all_batches) > 0
        
        # Verify we can load all batches
        for batch in all_batches:
            samples, metadata = manager.load_batch(batch.batch_id)
            assert len(samples) == metadata.num_samples
        
        # Get overall stats
        stats = manager.get_batch_stats()
        assert stats["total_samples"] == 30
        assert stats["num_shards"] == 3
