"""Tests for dataset loading utilities."""

import pytest
import tempfile
import json
import csv
from pathlib import Path
from PIL import Image
import numpy as np

from app.services.dataset_loader import (
    DatasetFormat,
    DatasetMetadata,
    DataSample,
    ImageFolderLoader,
    COCOLoader,
    CSVLoader,
    create_loader
)


@pytest.fixture
def temp_imagefolder_dataset():
    """Create a temporary ImageFolder dataset for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        
        # Create class directories
        (tmppath / "cat").mkdir()
        (tmppath / "dog").mkdir()
        
        # Create dummy images
        for i in range(5):
            img = Image.new('RGB', (64, 64), color=(i*50, 100, 150))
            img.save(tmppath / "cat" / f"cat_{i}.jpg")
        
        for i in range(7):
            img = Image.new('RGB', (64, 64), color=(150, i*30, 100))
            img.save(tmppath / "dog" / f"dog_{i}.jpg")
        
        yield str(tmppath)


@pytest.fixture
def temp_coco_dataset():
    """Create a temporary COCO dataset for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        images_dir = tmppath / "images"
        images_dir.mkdir()
        
        # Create dummy images
        for i in range(3):
            img = Image.new('RGB', (100, 100), color=(i*80, 100, 200))
            img.save(images_dir / f"image_{i}.jpg")
        
        # Create annotations JSON
        coco_data = {
            "images": [
                {"id": 1, "file_name": "image_0.jpg", "height": 100, "width": 100},
                {"id": 2, "file_name": "image_1.jpg", "height": 100, "width": 100},
                {"id": 3, "file_name": "image_2.jpg", "height": 100, "width": 100},
            ],
            "annotations": [
                {"id": 1, "image_id": 1, "category_id": 1, "bbox": [10, 10, 50, 50]},
                {"id": 2, "image_id": 2, "category_id": 2, "bbox": [20, 20, 60, 60]},
                {"id": 3, "image_id": 3, "category_id": 1, "bbox": [15, 15, 55, 55]},
            ],
            "categories": [
                {"id": 1, "name": "person"},
                {"id": 2, "name": "car"},
            ]
        }
        
        with open(tmppath / "annotations.json", 'w') as f:
            json.dump(coco_data, f)
        
        yield str(tmppath)


@pytest.fixture
def temp_csv_dataset():
    """Create a temporary CSV dataset for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        csv_file = tmppath / "data.csv"
        
        # Create CSV data
        with open(csv_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['feature1', 'feature2', 'feature3', 'label'])
            
            for i in range(10):
                writer.writerow([i*1.5, i*2.0, i*0.5, 'class_a' if i % 2 == 0 else 'class_b'])
        
        yield str(csv_file)


class TestImageFolderLoader:
    """Tests for ImageFolderLoader."""
    
    def test_load_metadata_local(self, temp_imagefolder_dataset):
        """Test loading metadata from local ImageFolder dataset."""
        loader = ImageFolderLoader(temp_imagefolder_dataset)
        metadata = loader.load_metadata()
        
        assert metadata.format == DatasetFormat.IMAGEFOLDER
        assert metadata.total_samples == 12  # 5 cats + 7 dogs
        assert metadata.num_classes == 2
        assert set(metadata.class_names) == {"cat", "dog"}
        assert metadata.class_distribution["cat"] == 5
        assert metadata.class_distribution["dog"] == 7
        assert metadata.total_size_bytes > 0
    
    def test_stream_samples(self, temp_imagefolder_dataset):
        """Test streaming samples in batches."""
        loader = ImageFolderLoader(temp_imagefolder_dataset)
        loader.load_metadata()
        
        all_samples = []
        for batch in loader.stream_samples(batch_size=4):
            assert isinstance(batch, list)
            assert len(batch) <= 4
            
            for sample in batch:
                assert isinstance(sample, DataSample)
                assert isinstance(sample.data, np.ndarray)
                assert sample.label in [0, 1]  # cat or dog
                assert "filepath" in sample.metadata
                assert "class_name" in sample.metadata
                
            all_samples.extend(batch)
        
        assert len(all_samples) == 12
    
    def test_get_sample(self, temp_imagefolder_dataset):
        """Test getting individual samples."""
        loader = ImageFolderLoader(temp_imagefolder_dataset)
        loader.load_metadata()
        
        sample = loader.get_sample(0)
        assert isinstance(sample, DataSample)
        assert isinstance(sample.data, np.ndarray)
        assert sample.data.shape == (64, 64, 3)
        assert sample.label in [0, 1]
    
    def test_get_sample_out_of_range(self, temp_imagefolder_dataset):
        """Test getting sample with invalid index."""
        loader = ImageFolderLoader(temp_imagefolder_dataset)
        loader.load_metadata()
        
        with pytest.raises(IndexError):
            loader.get_sample(999)


class TestCOCOLoader:
    """Tests for COCOLoader."""
    
    def test_load_metadata(self, temp_coco_dataset):
        """Test loading COCO metadata."""
        loader = COCOLoader(temp_coco_dataset)
        metadata = loader.load_metadata()
        
        assert metadata.format == DatasetFormat.COCO
        assert metadata.total_samples == 3
        assert metadata.num_classes == 2
        assert set(metadata.class_names) == {"person", "car"}
        assert metadata.class_distribution["person"] == 2
        assert metadata.class_distribution["car"] == 1
    
    def test_stream_samples(self, temp_coco_dataset):
        """Test streaming COCO samples."""
        loader = COCOLoader(temp_coco_dataset)
        loader.load_metadata()
        
        all_samples = []
        for batch in loader.stream_samples(batch_size=2):
            for sample in batch:
                assert isinstance(sample, DataSample)
                assert isinstance(sample.data, np.ndarray)
                assert "annotations" in sample.metadata
                assert "image_id" in sample.metadata
                
            all_samples.extend(batch)
        
        assert len(all_samples) == 3
    
    def test_get_sample(self, temp_coco_dataset):
        """Test getting individual COCO sample."""
        loader = COCOLoader(temp_coco_dataset)
        loader.load_metadata()
        
        sample = loader.get_sample(0)
        assert isinstance(sample, DataSample)
        assert isinstance(sample.data, np.ndarray)
        assert sample.data.shape == (100, 100, 3)
        assert len(sample.metadata["annotations"]) > 0


class TestCSVLoader:
    """Tests for CSVLoader."""
    
    def test_load_metadata(self, temp_csv_dataset):
        """Test loading CSV metadata."""
        loader = CSVLoader(temp_csv_dataset, label_column="label")
        metadata = loader.load_metadata()
        
        assert metadata.format == DatasetFormat.CSV
        assert metadata.total_samples == 10
        assert metadata.num_classes == 2
        assert set(metadata.class_names) == {"class_a", "class_b"}
        assert metadata.class_distribution["class_a"] == 5
        assert metadata.class_distribution["class_b"] == 5
        assert len(metadata.features) == 3  # feature1, feature2, feature3
    
    def test_stream_samples(self, temp_csv_dataset):
        """Test streaming CSV samples."""
        loader = CSVLoader(temp_csv_dataset, label_column="label")
        loader.load_metadata()
        
        all_samples = []
        for batch in loader.stream_samples(batch_size=3):
            for sample in batch:
                assert isinstance(sample, DataSample)
                assert isinstance(sample.data, dict)
                assert "feature1" in sample.data
                assert "feature2" in sample.data
                assert "feature3" in sample.data
                assert sample.label in ["class_a", "class_b"]
                
            all_samples.extend(batch)
        
        assert len(all_samples) == 10
    
    def test_get_sample(self, temp_csv_dataset):
        """Test getting individual CSV sample."""
        loader = CSVLoader(temp_csv_dataset, label_column="label")
        loader.load_metadata()
        
        sample = loader.get_sample(0)
        assert isinstance(sample, DataSample)
        assert isinstance(sample.data, dict)
        assert sample.label in ["class_a", "class_b"]


class TestCreateLoader:
    """Tests for create_loader factory function."""
    
    def test_create_imagefolder_loader(self, temp_imagefolder_dataset):
        """Test creating ImageFolder loader."""
        loader = create_loader(temp_imagefolder_dataset)
        assert isinstance(loader, ImageFolderLoader)
    
    def test_create_coco_loader(self, temp_coco_dataset):
        """Test creating COCO loader."""
        loader = create_loader(temp_coco_dataset, format=DatasetFormat.COCO)
        assert isinstance(loader, COCOLoader)
    
    def test_create_csv_loader(self, temp_csv_dataset):
        """Test creating CSV loader."""
        loader = create_loader(temp_csv_dataset)
        assert isinstance(loader, CSVLoader)
    
    def test_auto_detect_csv(self, temp_csv_dataset):
        """Test auto-detection of CSV format."""
        loader = create_loader(temp_csv_dataset)
        assert isinstance(loader, CSVLoader)
    
    def test_unsupported_format(self):
        """Test error on unsupported format."""
        with pytest.raises(ValueError):
            create_loader("/path/to/dataset", format=DatasetFormat.TFRECORD)
