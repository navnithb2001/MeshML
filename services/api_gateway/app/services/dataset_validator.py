"""Dataset validation service for common ML dataset formats."""

import os
import json
import csv
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from collections import Counter
import tempfile
import logging
from io import BytesIO

from app.core.storage import get_dataset_storage
from app.services.error_reporting import categorize_dataset_validation_results, ValidationReport

logger = logging.getLogger(__name__)


class DatasetValidationError(Exception):
    """Custom exception for dataset validation errors."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class DatasetValidator:
    """Validator for ML datasets in various formats."""
    
    SUPPORTED_IMAGE_FORMATS = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff', '.webp'}
    SUPPORTED_FORMATS = ['imagefolder', 'coco', 'csv', 'json']
    
    # Size limits
    MAX_DATASET_SIZE_GB = 100  # 100 GB max
    MAX_FILES_PER_DATASET = 1_000_000  # 1 million files max
    MIN_SAMPLES_PER_CLASS = 1
    MAX_CLASSES = 10_000
    
    def __init__(self):
        self.validation_results: Dict[str, Any] = {
            "format_valid": False,
            "structure_valid": False,
            "content_valid": False,
            "size_valid": False,
            "format": None,
            "total_samples": 0,
            "num_classes": 0,
            "class_distribution": {},
            "total_size_bytes": 0,
            "errors": [],
            "warnings": [],
        }
    
    def get_validation_report(self, dataset_path: str) -> ValidationReport:
        """
        Generate a structured ValidationReport from validation results.
        
        Args:
            dataset_path: GCS path to dataset
            
        Returns:
            ValidationReport instance
        """
        return categorize_dataset_validation_results(
            validation_results=self.validation_results,
            gcs_path=dataset_path
        )
    
    def detect_format(self, dataset_path: Path) -> Optional[str]:
        """
        Auto-detect dataset format based on structure.
        
        Args:
            dataset_path: Path to dataset directory
            
        Returns:
            Format name: 'imagefolder', 'coco', 'csv', or None
        """
        if not dataset_path.exists():
            return None
        
        # Check for COCO format (annotations.json or instances_*.json)
        coco_files = list(dataset_path.glob("*annotations*.json")) + list(dataset_path.glob("instances_*.json"))
        if coco_files:
            return "coco"
        
        # Check for CSV format
        csv_files = list(dataset_path.glob("*.csv"))
        if csv_files:
            return "csv"
        
        # Check for ImageFolder format (class subdirectories)
        subdirs = [d for d in dataset_path.iterdir() if d.is_dir()]
        if subdirs:
            # Check if subdirectories contain images
            for subdir in subdirs[:3]:  # Check first 3 subdirs
                image_files = [f for f in subdir.iterdir() if f.suffix.lower() in self.SUPPORTED_IMAGE_FORMATS]
                if image_files:
                    return "imagefolder"
        
        return None
    
    def validate_imagefolder(self, dataset_path: Path) -> bool:
        """
        Validate ImageFolder format dataset.
        
        Expected structure:
        dataset/
          class1/
            img1.jpg
            img2.jpg
          class2/
            img3.jpg
        
        Args:
            dataset_path: Path to dataset root
            
        Returns:
            True if valid
        """
        class_dirs = [d for d in dataset_path.iterdir() if d.is_dir()]
        
        if not class_dirs:
            self.validation_results["errors"].append("No class directories found")
            raise DatasetValidationError(
                "ImageFolder format requires class subdirectories",
                details={"found_dirs": 0}
            )
        
        if len(class_dirs) > self.MAX_CLASSES:
            self.validation_results["errors"].append(f"Too many classes: {len(class_dirs)} (max: {self.MAX_CLASSES})")
            raise DatasetValidationError(
                f"Dataset has too many classes: {len(class_dirs)}",
                details={"num_classes": len(class_dirs), "max_classes": self.MAX_CLASSES}
            )
        
        # Validate each class directory
        class_distribution = {}
        total_samples = 0
        total_size = 0
        invalid_files = []
        
        for class_dir in class_dirs:
            class_name = class_dir.name
            
            # Get all files in class directory
            files = [f for f in class_dir.iterdir() if f.is_file()]
            image_files = [f for f in files if f.suffix.lower() in self.SUPPORTED_IMAGE_FORMATS]
            
            # Track non-image files
            non_image_files = [f for f in files if f.suffix.lower() not in self.SUPPORTED_IMAGE_FORMATS]
            if non_image_files:
                self.validation_results["warnings"].append(
                    f"Class '{class_name}' contains {len(non_image_files)} non-image files"
                )
            
            if not image_files:
                invalid_files.append(class_name)
                continue
            
            if len(image_files) < self.MIN_SAMPLES_PER_CLASS:
                self.validation_results["warnings"].append(
                    f"Class '{class_name}' has only {len(image_files)} samples (min recommended: {self.MIN_SAMPLES_PER_CLASS})"
                )
            
            class_distribution[class_name] = len(image_files)
            total_samples += len(image_files)
            
            # Calculate size
            for img_file in image_files:
                total_size += img_file.stat().st_size
        
        if invalid_files:
            self.validation_results["errors"].append(
                f"Classes with no valid images: {', '.join(invalid_files)}"
            )
        
        # Check class balance
        if class_distribution:
            counts = list(class_distribution.values())
            max_count = max(counts)
            min_count = min(counts)
            imbalance_ratio = max_count / min_count if min_count > 0 else float('inf')
            
            if imbalance_ratio > 10:
                self.validation_results["warnings"].append(
                    f"Dataset is imbalanced (ratio: {imbalance_ratio:.1f}:1)"
                )
        
        # Update results
        self.validation_results["num_classes"] = len(class_distribution)
        self.validation_results["total_samples"] = total_samples
        self.validation_results["class_distribution"] = class_distribution
        self.validation_results["total_size_bytes"] = total_size
        self.validation_results["structure_valid"] = True
        
        logger.info(f"ImageFolder validation: {total_samples} samples, {len(class_distribution)} classes")
        return True
    
    def validate_coco(self, dataset_path: Path) -> bool:
        """
        Validate COCO format dataset.
        
        Expected structure:
        dataset/
          annotations.json (or instances_train.json, etc.)
          images/
            img1.jpg
            img2.jpg
        
        Args:
            dataset_path: Path to dataset root
            
        Returns:
            True if valid
        """
        # Find annotations file
        annotation_files = list(dataset_path.glob("*annotations*.json")) + list(dataset_path.glob("instances_*.json"))
        
        if not annotation_files:
            self.validation_results["errors"].append("No COCO annotations file found")
            raise DatasetValidationError(
                "COCO format requires annotations JSON file",
                details={"searched_patterns": ["*annotations*.json", "instances_*.json"]}
            )
        
        annotation_file = annotation_files[0]
        
        # Load and validate annotations
        try:
            with open(annotation_file, 'r') as f:
                coco_data = json.load(f)
        except json.JSONDecodeError as e:
            self.validation_results["errors"].append(f"Invalid JSON: {str(e)}")
            raise DatasetValidationError(
                "Failed to parse COCO annotations JSON",
                details={"error": str(e)}
            )
        
        # Validate COCO structure
        required_keys = ['images', 'annotations', 'categories']
        missing_keys = [key for key in required_keys if key not in coco_data]
        
        if missing_keys:
            self.validation_results["errors"].append(f"Missing required keys: {', '.join(missing_keys)}")
            raise DatasetValidationError(
                "Invalid COCO format: missing required keys",
                details={"missing_keys": missing_keys, "required_keys": required_keys}
            )
        
        # Extract metadata
        num_images = len(coco_data['images'])
        num_annotations = len(coco_data['annotations'])
        num_categories = len(coco_data['categories'])
        
        if num_categories > self.MAX_CLASSES:
            self.validation_results["errors"].append(f"Too many categories: {num_categories}")
            raise DatasetValidationError(
                f"Dataset has too many categories: {num_categories}",
                details={"num_categories": num_categories, "max_classes": self.MAX_CLASSES}
            )
        
        # Build category distribution
        category_map = {cat['id']: cat['name'] for cat in coco_data['categories']}
        category_counts = Counter(ann['category_id'] for ann in coco_data['annotations'])
        class_distribution = {
            category_map.get(cat_id, f"category_{cat_id}"): count
            for cat_id, count in category_counts.items()
        }
        
        # Check if image files exist
        images_dir = dataset_path / "images"
        if not images_dir.exists():
            # Try alternate locations
            alt_dirs = [dataset_path / "train", dataset_path / "val", dataset_path]
            images_dir = next((d for d in alt_dirs if d.exists() and list(d.glob("*.jpg"))), None)
            
            if images_dir is None:
                self.validation_results["warnings"].append("Could not verify image files existence")
        
        total_size = 0
        if images_dir:
            image_files = list(images_dir.glob("*.jpg")) + list(images_dir.glob("*.png"))
            total_size = sum(f.stat().st_size for f in image_files)
        
        # Update results
        self.validation_results["num_classes"] = num_categories
        self.validation_results["total_samples"] = num_images
        self.validation_results["class_distribution"] = class_distribution
        self.validation_results["total_size_bytes"] = total_size
        self.validation_results["structure_valid"] = True
        
        logger.info(f"COCO validation: {num_images} images, {num_annotations} annotations, {num_categories} categories")
        return True
    
    def validate_csv(self, dataset_path: Path) -> bool:
        """
        Validate CSV format dataset.
        
        Expected: CSV file with 'image_path' and 'label' columns
        
        Args:
            dataset_path: Path to dataset root
            
        Returns:
            True if valid
        """
        csv_files = list(dataset_path.glob("*.csv"))
        
        if not csv_files:
            self.validation_results["errors"].append("No CSV file found")
            raise DatasetValidationError("CSV format requires a CSV file")
        
        csv_file = csv_files[0]
        
        # Read and validate CSV
        try:
            with open(csv_file, 'r') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                
                if not rows:
                    self.validation_results["errors"].append("CSV file is empty")
                    raise DatasetValidationError("CSV file contains no data")
                
                # Check for required columns
                fieldnames = reader.fieldnames or []
                if 'label' not in fieldnames:
                    self.validation_results["warnings"].append(
                        "CSV missing 'label' column - ensure labels are provided"
                    )
                
                # Extract class distribution
                if 'label' in fieldnames:
                    label_counts = Counter(row['label'] for row in rows if 'label' in row)
                    
                    if len(label_counts) > self.MAX_CLASSES:
                        self.validation_results["errors"].append(f"Too many unique labels: {len(label_counts)}")
                        raise DatasetValidationError(
                            f"Dataset has too many classes: {len(label_counts)}",
                            details={"num_classes": len(label_counts), "max_classes": self.MAX_CLASSES}
                        )
                    
                    class_distribution = dict(label_counts)
                else:
                    class_distribution = {}
                
                # Update results
                self.validation_results["num_classes"] = len(class_distribution)
                self.validation_results["total_samples"] = len(rows)
                self.validation_results["class_distribution"] = class_distribution
                self.validation_results["structure_valid"] = True
                
                logger.info(f"CSV validation: {len(rows)} samples, {len(class_distribution)} classes")
                return True
                
        except Exception as e:
            self.validation_results["errors"].append(f"Failed to read CSV: {str(e)}")
            raise DatasetValidationError(
                "Failed to parse CSV file",
                details={"error": str(e)}
            )
    
    def validate_size(self, total_size_bytes: int, total_files: int) -> bool:
        """
        Validate dataset size limits.
        
        Args:
            total_size_bytes: Total dataset size in bytes
            total_files: Total number of files
            
        Returns:
            True if within limits
        """
        max_size_bytes = self.MAX_DATASET_SIZE_GB * 1024 * 1024 * 1024
        
        if total_size_bytes > max_size_bytes:
            size_gb = total_size_bytes / (1024 ** 3)
            self.validation_results["errors"].append(
                f"Dataset too large: {size_gb:.2f}GB (max: {self.MAX_DATASET_SIZE_GB}GB)"
            )
            raise DatasetValidationError(
                f"Dataset exceeds size limit: {size_gb:.2f}GB",
                details={
                    "size_bytes": total_size_bytes,
                    "size_gb": size_gb,
                    "max_gb": self.MAX_DATASET_SIZE_GB
                }
            )
        
        if total_files > self.MAX_FILES_PER_DATASET:
            self.validation_results["errors"].append(
                f"Too many files: {total_files:,} (max: {self.MAX_FILES_PER_DATASET:,})"
            )
            raise DatasetValidationError(
                f"Dataset has too many files: {total_files:,}",
                details={
                    "total_files": total_files,
                    "max_files": self.MAX_FILES_PER_DATASET
                }
            )
        
        self.validation_results["size_valid"] = True
        return True


async def validate_dataset(
    gcs_path: str,
    expected_format: Optional[str] = None
) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str], Dict[str, Any]]:
    """
    Complete dataset validation workflow.
    
    Args:
        gcs_path: GCS path to dataset (gs://bucket/path/to/dataset)
        expected_format: Expected format ('imagefolder', 'coco', 'csv', or None for auto-detect)
        
    Returns:
        Tuple of (is_valid, metadata_dict, error_message, validation_details)
    """
    validator = DatasetValidator()
    temp_dir = None
    
    try:
        # Extract blob path from GCS path
        storage_client = get_dataset_storage()
        blob_prefix = gcs_path.split(f"{storage_client.bucket_name}/", 1)[-1]
        
        # Download dataset to temporary directory
        # Note: For large datasets, we might want to sample or stream instead
        temp_dir = tempfile.mkdtemp(prefix='meshml_dataset_')
        dataset_path = Path(temp_dir)
        
        logger.info(f"Downloading dataset from {gcs_path} for validation...")
        
        # List all blobs with the prefix
        bucket = storage_client.bucket
        blobs = list(bucket.list_blobs(prefix=blob_prefix, max_results=10000))
        
        if not blobs:
            raise DatasetValidationError(
                "Dataset directory is empty",
                details={"gcs_path": gcs_path}
            )
        
        # Download files (limit for validation)
        downloaded_files = 0
        total_size = 0
        
        for blob in blobs[:1000]:  # Limit to 1000 files for validation
            # Skip directory markers
            if blob.name.endswith('/'):
                continue
            
            # Create local path
            relative_path = blob.name[len(blob_prefix):].lstrip('/')
            local_path = dataset_path / relative_path
            local_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Download file
            blob.download_to_filename(str(local_path))
            downloaded_files += 1
            total_size += blob.size
        
        logger.info(f"Downloaded {downloaded_files} files for validation")
        
        # Detect format if not specified
        if expected_format:
            detected_format = expected_format.lower()
        else:
            detected_format = validator.detect_format(dataset_path)
        
        if not detected_format:
            raise DatasetValidationError(
                "Could not detect dataset format",
                details={"supported_formats": validator.SUPPORTED_FORMATS}
            )
        
        validator.validation_results["format"] = detected_format
        validator.validation_results["format_valid"] = True
        
        # Validate based on format
        if detected_format == "imagefolder":
            validator.validate_imagefolder(dataset_path)
        elif detected_format == "coco":
            validator.validate_coco(dataset_path)
        elif detected_format == "csv":
            validator.validate_csv(dataset_path)
        else:
            raise DatasetValidationError(
                f"Unsupported format: {detected_format}",
                details={"supported_formats": validator.SUPPORTED_FORMATS}
            )
        
        # Validate size
        validator.validate_size(
            total_size_bytes=validator.validation_results["total_size_bytes"],
            total_files=downloaded_files
        )
        
        validator.validation_results["content_valid"] = True
        
        # Build metadata
        metadata = {
            "format": detected_format,
            "num_classes": validator.validation_results["num_classes"],
            "total_samples": validator.validation_results["total_samples"],
            "class_distribution": validator.validation_results["class_distribution"],
            "size_bytes": validator.validation_results["total_size_bytes"],
            "size_gb": validator.validation_results["total_size_bytes"] / (1024 ** 3),
        }
        
        logger.info(f"Dataset validation successful: {detected_format} format, {metadata['total_samples']} samples")
        
        return True, metadata, None, validator.validation_results
        
    except DatasetValidationError as e:
        logger.warning(f"Dataset validation failed: {e.message}")
        return False, None, e.message, validator.validation_results
        
    except Exception as e:
        logger.error(f"Unexpected error during dataset validation: {e}")
        error_msg = f"Validation error: {str(e)}"
        validator.validation_results["errors"].append(error_msg)
        return False, None, error_msg, validator.validation_results
        
    finally:
        # Clean up temporary directory
        if temp_dir and Path(temp_dir).exists():
            import shutil
            try:
                shutil.rmtree(temp_dir)
            except Exception as e:
                logger.warning(f"Failed to delete temp directory: {e}")
