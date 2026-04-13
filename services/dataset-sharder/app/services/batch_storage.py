"""Storage management for dataset shards and batches.

This module provides utilities for storing, retrieving, and managing dataset
batches in both local filesystem and cloud storage (GCS/S3).
"""

import hashlib
import json
import logging
import os
import pickle
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import boto3
import numpy as np
from app.core.storage import get_artifact_storage
from app.services.dataset_loader import DataSample
from app.services.dataset_sharder import ShardMetadata
from botocore.config import Config
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)
BATCH_SCOPE_SEPARATOR = "__"


def _sanitize_batch_scope(scope: Optional[str]) -> Optional[str]:
    if not scope:
        return None
    return str(scope).replace("/", "-").replace("\\", "-").strip() or None


def _scoped_batch_id(scope: Optional[str], base_batch_id: str) -> str:
    normalized_scope = _sanitize_batch_scope(scope)
    if not normalized_scope:
        return base_batch_id
    return f"{normalized_scope}{BATCH_SCOPE_SEPARATOR}{base_batch_id}"


def _split_batch_scope(batch_id: str) -> tuple[Optional[str], str]:
    if BATCH_SCOPE_SEPARATOR not in batch_id:
        return None, batch_id
    scope, base_batch_id = batch_id.split(BATCH_SCOPE_SEPARATOR, 1)
    return scope or None, base_batch_id


@dataclass
class BatchMetadata:
    """Metadata for a stored batch."""

    batch_id: str
    shard_id: int
    batch_index: int  # Index within shard
    num_samples: int
    sample_indices: List[int]
    class_distribution: Dict[str, int]
    size_bytes: int
    checksum: str  # SHA256 hash
    storage_path: str
    format: str  # 'pickle', 'numpy', 'tfrecord'
    created_at: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BatchMetadata":
        """Create from dictionary."""
        return cls(**data)


class BatchStorage:
    """Base class for batch storage backends."""

    def save_batch(self, samples: List[DataSample], metadata: BatchMetadata) -> str:
        """
        Save batch to storage.

        Args:
            samples: List of DataSample instances
            metadata: BatchMetadata

        Returns:
            Storage path where batch was saved
        """
        raise NotImplementedError

    def load_batch(self, batch_id: str) -> tuple[List[DataSample], BatchMetadata]:
        """
        Load batch from storage.

        Args:
            batch_id: Batch identifier

        Returns:
            Tuple of (samples, metadata)
        """
        raise NotImplementedError

    def delete_batch(self, batch_id: str) -> bool:
        """
        Delete batch from storage.

        Args:
            batch_id: Batch identifier

        Returns:
            True if deleted successfully
        """
        raise NotImplementedError

    def list_batches(self, shard_id: Optional[int] = None) -> List[BatchMetadata]:
        """
        List available batches.

        Args:
            shard_id: Optional shard ID to filter by

        Returns:
            List of BatchMetadata
        """
        raise NotImplementedError


class LocalBatchStorage(BatchStorage):
    """Local filesystem storage for batches."""

    def __init__(self, base_path: str = "./data/batches"):
        """
        Initialize local storage.

        Args:
            base_path: Base directory for storing batches
        """
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

        self.batches_dir = self.base_path / "batches"
        self.metadata_dir = self.base_path / "metadata"

        self.batches_dir.mkdir(exist_ok=True)
        self.metadata_dir.mkdir(exist_ok=True)

        logger.info(f"Initialized local batch storage at {self.base_path}")

    def save_batch(self, samples: List[DataSample], metadata: BatchMetadata) -> str:
        """Save batch to local filesystem."""
        batch_path, metadata_path = self._paths_for_batch(metadata.batch_id)
        batch_path.parent.mkdir(parents=True, exist_ok=True)
        metadata_path.parent.mkdir(parents=True, exist_ok=True)

        # Serialize samples
        batch_data = {"samples": samples, "num_samples": len(samples)}

        with open(batch_path, "wb") as f:
            pickle.dump(batch_data, f, protocol=pickle.HIGHEST_PROTOCOL)

        # Calculate actual file size and checksum
        file_size = batch_path.stat().st_size
        checksum = self._calculate_checksum(batch_path)

        # Update metadata
        metadata.size_bytes = file_size
        metadata.checksum = checksum
        metadata.storage_path = str(batch_path)

        with open(metadata_path, "w") as f:
            json.dump(metadata.to_dict(), f, indent=2)

        logger.info(
            f"Saved batch {metadata.batch_id}: "
            f"{metadata.num_samples} samples, "
            f"{file_size / 1024:.2f} KB"
        )

        return str(batch_path)

    def load_batch(self, batch_id: str) -> tuple[List[DataSample], BatchMetadata]:
        """Load batch from local filesystem."""
        # Load metadata
        _, metadata_path = self._paths_for_batch(batch_id)

        if not metadata_path.exists():
            raise FileNotFoundError(f"Batch metadata not found: {batch_id}")

        with open(metadata_path, "r") as f:
            metadata_dict = json.load(f)

        metadata = BatchMetadata.from_dict(metadata_dict)

        # Load batch data
        batch_path = Path(metadata.storage_path)

        if not batch_path.exists():
            raise FileNotFoundError(f"Batch data not found: {batch_path}")

        # Verify checksum
        current_checksum = self._calculate_checksum(batch_path)
        if current_checksum != metadata.checksum:
            logger.warning(
                f"Checksum mismatch for batch {batch_id}: "
                f"expected {metadata.checksum}, got {current_checksum}"
            )

        with open(batch_path, "rb") as f:
            batch_data = pickle.load(f)

        samples = batch_data["samples"]

        logger.info(f"Loaded batch {batch_id}: {len(samples)} samples")

        return samples, metadata

    def delete_batch(self, batch_id: str) -> bool:
        """Delete batch from local filesystem."""
        batch_path, metadata_path = self._paths_for_batch(batch_id)

        deleted = False

        if batch_path.exists():
            batch_path.unlink()
            deleted = True

        if metadata_path.exists():
            metadata_path.unlink()
            deleted = True

        if deleted:
            logger.info(f"Deleted batch {batch_id}")

        return deleted

    def list_batches(self, shard_id: Optional[int] = None) -> List[BatchMetadata]:
        """List batches from local filesystem."""
        batches = []

        for metadata_file in self.metadata_dir.rglob("*.json"):
            try:
                with open(metadata_file, "r") as f:
                    metadata_dict = json.load(f)

                metadata = BatchMetadata.from_dict(metadata_dict)

                # Filter by shard_id if provided
                if shard_id is not None and metadata.shard_id != shard_id:
                    continue

                batches.append(metadata)

            except Exception as e:
                logger.warning(f"Failed to load metadata {metadata_file}: {e}")
                continue

        return sorted(batches, key=lambda b: (b.shard_id, b.batch_index))

    def _paths_for_batch(self, batch_id: str) -> tuple[Path, Path]:
        scope, _ = _split_batch_scope(batch_id)
        batch_dir = self.batches_dir / scope if scope else self.batches_dir
        metadata_dir = self.metadata_dir / scope if scope else self.metadata_dir
        return batch_dir / f"{batch_id}.pkl", metadata_dir / f"{batch_id}.json"

    def _calculate_checksum(self, file_path: Path) -> str:
        """Calculate SHA256 checksum of a file."""
        sha256 = hashlib.sha256()

        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256.update(chunk)

        return sha256.hexdigest()

    def get_storage_stats(self) -> Dict[str, Any]:
        """Get storage statistics."""
        total_batches = len(list(self.batches_dir.glob("*.pkl")))
        total_size = sum(f.stat().st_size for f in self.batches_dir.glob("*.pkl"))

        return {
            "total_batches": total_batches,
            "total_size_bytes": total_size,
            "total_size_mb": total_size / (1024**2),
            "storage_path": str(self.base_path),
        }


class GCSBatchStorage(BatchStorage):
    """Google Cloud Storage backend for batches."""

    def __init__(self, bucket_name: str, base_prefix: str = "batches"):
        """
        Initialize GCS storage.

        Args:
            bucket_name: GCS bucket name
            base_prefix: Base prefix for batch objects
        """
        self.storage_client = get_artifact_storage()
        self.bucket_name = bucket_name
        self.base_prefix = base_prefix
        self._s3 = self._emulator_s3_client()

        logger.info(f"Initialized GCS batch storage: gs://{bucket_name}/{base_prefix}")

    def _emulator_s3_client(self):
        endpoint = os.getenv("STORAGE_EMULATOR_URL")
        if not endpoint:
            return None
        return boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=(
                os.getenv("AWS_ACCESS_KEY_ID") or os.getenv("MINIO_ROOT_USER") or "meshml"
            ),
            aws_secret_access_key=(
                os.getenv("AWS_SECRET_ACCESS_KEY")
                or os.getenv("MINIO_ROOT_PASSWORD")
                or "meshml_minio_password"
            ),
            region_name="us-east-1",
            config=Config(signature_version="s3v4"),
        )

    def save_batch(self, samples: List[DataSample], metadata: BatchMetadata) -> str:
        """Save batch to GCS."""
        # Serialize samples to bytes
        batch_data = {"samples": samples, "num_samples": len(samples)}

        batch_bytes = pickle.dumps(batch_data, protocol=pickle.HIGHEST_PROTOCOL)

        # Calculate checksum
        checksum = hashlib.sha256(batch_bytes).hexdigest()

        blob_name, metadata_blob_name = self._object_names_for_batch(metadata.batch_id)

        # Update metadata before writing metadata object.
        metadata.size_bytes = len(batch_bytes)
        metadata.checksum = checksum
        metadata.storage_path = f"gs://{self.bucket_name}/{blob_name}"

        if self._s3:
            self._s3.put_object(
                Bucket=self.bucket_name,
                Key=blob_name,
                Body=batch_bytes,
                ContentType="application/octet-stream",
            )
            self._s3.put_object(
                Bucket=self.bucket_name,
                Key=metadata_blob_name,
                Body=json.dumps(metadata.to_dict(), indent=2).encode("utf-8"),
                ContentType="application/json",
            )
        else:
            bucket = self.storage_client.bucket
            blob = bucket.blob(blob_name)
            blob.upload_from_string(batch_bytes, content_type="application/octet-stream")
            metadata_blob = bucket.blob(metadata_blob_name)
            metadata_blob.upload_from_string(
                json.dumps(metadata.to_dict(), indent=2), content_type="application/json"
            )

        logger.info(
            f"Saved batch to GCS {metadata.batch_id}: "
            f"{metadata.num_samples} samples, "
            f"{len(batch_bytes) / 1024:.2f} KB"
        )

        return metadata.storage_path

    def load_batch(self, batch_id: str) -> tuple[List[DataSample], BatchMetadata]:
        """Load batch from GCS."""
        batch_blob_name, metadata_blob_name = self._object_names_for_batch(batch_id)
        if self._s3:
            try:
                self._s3.head_object(Bucket=self.bucket_name, Key=metadata_blob_name)
                metadata_obj = self._s3.get_object(Bucket=self.bucket_name, Key=metadata_blob_name)
                metadata_json = metadata_obj["Body"].read().decode("utf-8")
            except ClientError:
                raise FileNotFoundError(f"Batch metadata not found in GCS: {batch_id}")
            try:
                self._s3.head_object(Bucket=self.bucket_name, Key=batch_blob_name)
                batch_obj = self._s3.get_object(Bucket=self.bucket_name, Key=batch_blob_name)
                batch_bytes = batch_obj["Body"].read()
            except ClientError:
                raise FileNotFoundError(f"Batch data not found in GCS: {batch_id}")
        else:
            bucket = self.storage_client.bucket
            metadata_blob = bucket.blob(metadata_blob_name)
            if not metadata_blob.exists():
                raise FileNotFoundError(f"Batch metadata not found in GCS: {batch_id}")
            metadata_json = metadata_blob.download_as_text()
            batch_blob = bucket.blob(batch_blob_name)
            if not batch_blob.exists():
                raise FileNotFoundError(f"Batch data not found in GCS: {batch_id}")
            batch_bytes = batch_blob.download_as_bytes()

        metadata = BatchMetadata.from_dict(json.loads(metadata_json))

        # Verify checksum
        current_checksum = hashlib.sha256(batch_bytes).hexdigest()
        if current_checksum != metadata.checksum:
            logger.warning(
                f"Checksum mismatch for batch {batch_id}: "
                f"expected {metadata.checksum}, got {current_checksum}"
            )

        batch_data = pickle.loads(batch_bytes)
        samples = batch_data["samples"]

        logger.info(f"Loaded batch from GCS {batch_id}: {len(samples)} samples")

        return samples, metadata

    def delete_batch(self, batch_id: str) -> bool:
        """Delete batch from GCS."""
        deleted = False
        batch_blob_name, metadata_blob_name = self._object_names_for_batch(batch_id)
        if self._s3:
            for key in (batch_blob_name, metadata_blob_name):
                try:
                    self._s3.head_object(Bucket=self.bucket_name, Key=key)
                    self._s3.delete_object(Bucket=self.bucket_name, Key=key)
                    deleted = True
                except ClientError:
                    continue
        else:
            bucket = self.storage_client.bucket
            batch_blob = bucket.blob(batch_blob_name)
            metadata_blob = bucket.blob(metadata_blob_name)
            if batch_blob.exists():
                batch_blob.delete()
                deleted = True
            if metadata_blob.exists():
                metadata_blob.delete()
                deleted = True

        if deleted:
            logger.info(f"Deleted batch from GCS {batch_id}")

        return deleted

    def list_batches(self, shard_id: Optional[int] = None) -> List[BatchMetadata]:
        """List batches from GCS."""
        metadata_prefix = f"{self.base_prefix}/"

        batches = []
        if self._s3:
            paginator = self._s3.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=self.bucket_name, Prefix=metadata_prefix):
                for item in page.get("Contents", []):
                    key = item["Key"]
                    if not key.endswith(".json") or "/metadata/" not in key:
                        continue
                    try:
                        data = self._s3.get_object(Bucket=self.bucket_name, Key=key)["Body"].read()
                        metadata = BatchMetadata.from_dict(json.loads(data.decode("utf-8")))
                        if shard_id is not None and metadata.shard_id != shard_id:
                            continue
                        batches.append(metadata)
                    except Exception as e:
                        logger.warning(f"Failed to load metadata {key}: {e}")
                        continue
        else:
            bucket = self.storage_client.bucket
            blobs = bucket.list_blobs(prefix=metadata_prefix)
            for blob in blobs:
                if not blob.name.endswith(".json") or "/metadata/" not in blob.name:
                    continue
                try:
                    metadata_json = blob.download_as_text()
                    metadata = BatchMetadata.from_dict(json.loads(metadata_json))
                    if shard_id is not None and metadata.shard_id != shard_id:
                        continue
                    batches.append(metadata)
                except Exception as e:
                    logger.warning(f"Failed to load metadata {blob.name}: {e}")
                    continue

        return sorted(batches, key=lambda b: (b.shard_id, b.batch_index))

    def _object_names_for_batch(self, batch_id: str) -> tuple[str, str]:
        scope, _ = _split_batch_scope(batch_id)
        if scope:
            prefix = f"{self.base_prefix}/{scope}"
        else:
            prefix = self.base_prefix
        return (
            f"{prefix}/{batch_id}.pkl",
            f"{prefix}/metadata/{batch_id}.json",
        )


class BatchManager:
    """High-level batch management with automatic storage selection."""

    def __init__(self, storage_backend: Optional[BatchStorage] = None, auto_cleanup: bool = False):
        """
        Initialize batch manager.

        Args:
            storage_backend: BatchStorage instance (defaults to LocalBatchStorage)
            auto_cleanup: Whether to automatically cleanup old batches
        """
        self.storage = storage_backend or LocalBatchStorage()
        self.auto_cleanup = auto_cleanup

    def create_batches_from_shard(
        self,
        shard: ShardMetadata,
        loader,
        batch_size: int,
        batch_scope: Optional[str] = None,  # DatasetLoader
    ) -> List[BatchMetadata]:
        """
        Create and store batches from a shard.

        Args:
            shard: ShardMetadata
            loader: DatasetLoader instance
            batch_size: Number of samples per batch

        Returns:
            List of BatchMetadata for created batches
        """
        batches_metadata = []
        sample_indices = shard.sample_indices
        num_batches = (len(sample_indices) + batch_size - 1) // batch_size

        logger.info(
            f"Creating {num_batches} batches from shard {shard.shard_id} "
            f"({len(sample_indices)} samples, batch_size={batch_size})"
        )

        import concurrent.futures
        from datetime import datetime

        def _process_single_batch(batch_idx):
            start_idx = batch_idx * batch_size
            end_idx = min(start_idx + batch_size, len(sample_indices))
            batch_sample_indices = sample_indices[start_idx:end_idx]

            # Let the outer thread pool handle parallelism. Fetch samples directly to avoid thread explosion.
            samples = [loader.get_sample(i) for i in batch_sample_indices]

            # Calculate class distribution
            class_dist = {}
            for sample in samples:
                label = str(sample.label)
                class_dist[label] = class_dist.get(label, 0) + 1

            # Create batch metadata
            batch_id = _scoped_batch_id(
                batch_scope,
                f"shard_{shard.shard_id}_batch_{batch_idx}",
            )

            metadata = BatchMetadata(
                batch_id=batch_id,
                shard_id=shard.shard_id,
                batch_index=batch_idx,
                num_samples=len(samples),
                sample_indices=batch_sample_indices,
                class_distribution=class_dist,
                size_bytes=0,
                checksum="",
                storage_path="",
                format="pickle",
                created_at=datetime.utcnow().isoformat(),
            )

            # Save batch
            self.storage.save_batch(samples, metadata)
            return metadata

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(_process_single_batch, i) for i in range(num_batches)]
            completed = 0
            for future in concurrent.futures.as_completed(futures):
                metadata = future.result()
                batches_metadata.append(metadata)
                completed += 1
                progress_pct = (completed / num_batches) * 100
                logger.info(f"Shard {shard.shard_id} sharding progress: {progress_pct:.2f}% ({completed}/{num_batches} batches completed)")

        logger.info(f"Created {len(batches_metadata)} batches for shard {shard.shard_id}")

        return batches_metadata

    def load_batch(self, batch_id: str) -> tuple[List[DataSample], BatchMetadata]:
        """Load batch by ID."""
        return self.storage.load_batch(batch_id)

    def delete_batch(self, batch_id: str) -> bool:
        """Delete batch by ID."""
        return self.storage.delete_batch(batch_id)

    def list_batches(self, shard_id: Optional[int] = None) -> List[BatchMetadata]:
        """List available batches."""
        return self.storage.list_batches(shard_id=shard_id)

    def get_batch_stats(self) -> Dict[str, Any]:
        """Get batch statistics."""
        batches = self.storage.list_batches()

        if not batches:
            return {"total_batches": 0, "total_samples": 0, "total_size_bytes": 0, "num_shards": 0}

        total_samples = sum(b.num_samples for b in batches)
        total_size = sum(b.size_bytes for b in batches)
        num_shards = len(set(b.shard_id for b in batches))

        # Per-shard stats
        shard_stats = {}
        for batch in batches:
            shard_id = batch.shard_id
            if shard_id not in shard_stats:
                shard_stats[shard_id] = {"num_batches": 0, "num_samples": 0, "size_bytes": 0}

            shard_stats[shard_id]["num_batches"] += 1
            shard_stats[shard_id]["num_samples"] += batch.num_samples
            shard_stats[shard_id]["size_bytes"] += batch.size_bytes

        return {
            "total_batches": len(batches),
            "total_samples": total_samples,
            "total_size_bytes": total_size,
            "total_size_mb": total_size / (1024**2),
            "num_shards": num_shards,
            "shard_stats": shard_stats,
        }

    def cleanup_old_batches(self, max_age_hours: int = 24) -> int:
        """
        Clean up batches older than specified age.

        Args:
            max_age_hours: Maximum age in hours

        Returns:
            Number of batches deleted
        """
        batches = self.storage.list_batches()
        deleted_count = 0

        cutoff_time = datetime.utcnow().timestamp() - (max_age_hours * 3600)

        for batch in batches:
            created_at = datetime.fromisoformat(batch.created_at).timestamp()

            if created_at < cutoff_time:
                if self.storage.delete_batch(batch.batch_id):
                    deleted_count += 1

        if deleted_count > 0:
            logger.info(f"Cleaned up {deleted_count} old batches")

        return deleted_count


def create_storage_backend(storage_type: str = "local", **kwargs) -> BatchStorage:
    """
    Factory function to create storage backend.

    Args:
        storage_type: 'local' or 'gcs'
        **kwargs: Backend-specific arguments

    Returns:
        BatchStorage instance
    """
    if storage_type == "local":
        base_path = kwargs.get("base_path", "./data/batches")
        return LocalBatchStorage(base_path=base_path)

    elif storage_type == "gcs":
        bucket_name = kwargs.get("bucket_name")
        if not bucket_name:
            raise ValueError("bucket_name required for GCS storage")

        base_prefix = kwargs.get("base_prefix", "batches")
        return GCSBatchStorage(bucket_name=bucket_name, base_prefix=base_prefix)

    else:
        raise ValueError(f"Unsupported storage type: {storage_type}")
