"""Client example for worker to download batches.

This demonstrates how a worker should interact with the distribution API
to download and process assigned batches.
"""

import requests
import pickle
import time
from typing import List, Dict, Any


class BatchDownloadClient:
    """Client for workers to download assigned batches."""
    
    def __init__(self, base_url: str, worker_id: str):
        """
        Initialize download client.
        
        Args:
            base_url: Base URL of distribution API (e.g., "http://localhost:8000")
            worker_id: Unique worker identifier
        """
        self.base_url = base_url.rstrip('/')
        self.worker_id = worker_id
    
    def get_assigned_batches(self) -> List[str]:
        """
        Get list of batches assigned to this worker.
        
        Returns:
            List of batch IDs
        """
        url = f"{self.base_url}/distribution/workers/{self.worker_id}/batches"
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    
    def get_assignment_info(self) -> Dict[str, Any]:
        """
        Get detailed assignment information.
        
        Returns:
            Assignment details including shard_id, progress, etc.
        """
        url = f"{self.base_url}/distribution/workers/{self.worker_id}/assignment"
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    
    def download_batch(self, batch_id: str, save_path: str) -> Dict[str, Any]:
        """
        Download a specific batch.
        
        Args:
            batch_id: Batch ID to download
            save_path: Local path to save batch
            
        Returns:
            Batch metadata
        """
        # Notify server download is starting
        self.update_status(batch_id, "downloading")
        
        try:
            # Download batch
            url = f"{self.base_url}/distribution/workers/{self.worker_id}/batches/{batch_id}/download"
            response = requests.get(url, stream=True)
            response.raise_for_status()
            
            # Save to file
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=65536):
                    if chunk:
                        f.write(chunk)
            
            # Load and return metadata
            with open(save_path, 'rb') as f:
                batch_data = pickle.load(f)
            
            # Mark as completed
            self.update_status(batch_id, "completed")
            
            return batch_data['metadata']
            
        except Exception as e:
            # Mark as failed
            self.update_status(batch_id, "failed", str(e))
            raise
    
    def update_status(self, batch_id: str, status: str, failure_reason: str = None):
        """
        Update download status for a batch.
        
        Args:
            batch_id: Batch ID
            status: Status ('downloading', 'completed', 'failed')
            failure_reason: Optional failure reason
        """
        url = f"{self.base_url}/distribution/workers/{self.worker_id}/batches/{batch_id}/status"
        data = {"status": status}
        
        if failure_reason:
            data["failure_reason"] = failure_reason
        
        response = requests.post(url, json=data)
        response.raise_for_status()
    
    def download_all_batches(self, save_dir: str = "./batches") -> List[Dict[str, Any]]:
        """
        Download all assigned batches.
        
        Args:
            save_dir: Directory to save batches
            
        Returns:
            List of batch metadata
        """
        import os
        os.makedirs(save_dir, exist_ok=True)
        
        batch_ids = self.get_assigned_batches()
        print(f"Worker {self.worker_id}: Downloading {len(batch_ids)} batches...")
        
        downloaded = []
        
        for i, batch_id in enumerate(batch_ids, 1):
            try:
                save_path = os.path.join(save_dir, f"{batch_id}.pkl")
                print(f"[{i}/{len(batch_ids)}] Downloading {batch_id}...")
                
                metadata = self.download_batch(batch_id, save_path)
                downloaded.append(metadata)
                
                print(f"  ✓ Downloaded {metadata['num_samples']} samples")
                
            except Exception as e:
                print(f"  ✗ Failed: {e}")
        
        print(f"\nCompleted: {len(downloaded)}/{len(batch_ids)} batches")
        
        return downloaded


# Example usage
if __name__ == "__main__":
    # Initialize client
    client = BatchDownloadClient(
        base_url="http://localhost:8000",
        worker_id="worker_001"
    )
    
    # Get assignment info
    info = client.get_assignment_info()
    print(f"Assigned shard: {info['shard_id']}")
    print(f"Total batches: {len(info['assigned_batches'])}")
    print(f"Progress: {info['progress'] * 100:.1f}%")
    
    # Download all batches
    metadata_list = client.download_all_batches(save_dir="./worker_001_batches")
    
    # Use batches for training
    for metadata in metadata_list:
        batch_path = f"./worker_001_batches/{metadata['batch_id']}.pkl"
        
        with open(batch_path, 'rb') as f:
            batch_data = pickle.load(f)
        
        samples = batch_data['samples']
        
        # Train model with samples
        for sample in samples:
            # process sample.data, sample.label
            pass
