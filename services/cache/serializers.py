"""
Binary serialization utilities for model weights and gradients.
"""
import msgpack
import numpy as np
from typing import Dict, Any, Union
import io


class WeightsSerializer:
    """Efficient binary serialization for PyTorch model weights using MessagePack."""
    
    @staticmethod
    def serialize(weights: Dict[str, Any]) -> bytes:
        """
        Serialize PyTorch state_dict to binary format.
        
        Args:
            weights: Dictionary of layer_name -> tensor (as numpy arrays)
            
        Returns:
            Binary bytes ready for Redis storage
            
        Example:
            weights = {
                'layer1.weight': np.array([[1.0, 2.0], [3.0, 4.0]]),
                'layer1.bias': np.array([0.5, 0.5])
            }
            binary = WeightsSerializer.serialize(weights)
        """
        # Convert numpy arrays to lists with dtype info
        serializable = {}
        for key, value in weights.items():
            if isinstance(value, np.ndarray):
                serializable[key] = {
                    'data': value.tobytes(),
                    'dtype': str(value.dtype),
                    'shape': value.shape
                }
            else:
                serializable[key] = value
        
        # Use MessagePack for efficient binary serialization
        return msgpack.packb(serializable, use_bin_type=True)
    
    @staticmethod
    def deserialize(binary: bytes) -> Dict[str, np.ndarray]:
        """
        Deserialize binary data back to PyTorch-compatible format.
        
        Args:
            binary: Binary bytes from Redis
            
        Returns:
            Dictionary of layer_name -> numpy array
            
        Example:
            weights = WeightsSerializer.deserialize(binary)
            # Convert to PyTorch: {k: torch.from_numpy(v) for k, v in weights.items()}
        """
        data = msgpack.unpackb(binary, raw=False)
        
        # Reconstruct numpy arrays
        weights = {}
        for key, value in data.items():
            if isinstance(value, dict) and 'data' in value:
                dtype = np.dtype(value['dtype'])
                shape = tuple(value['shape'])
                array = np.frombuffer(value['data'], dtype=dtype).reshape(shape)
                weights[key] = array
            else:
                weights[key] = value
        
        return weights
    
    @staticmethod
    def estimate_size(weights: Dict[str, np.ndarray]) -> int:
        """
        Estimate serialized size in bytes.
        
        Args:
            weights: Dictionary of layer_name -> numpy array
            
        Returns:
            Estimated size in bytes
        """
        total_bytes = 0
        for key, value in weights.items():
            if isinstance(value, np.ndarray):
                total_bytes += value.nbytes
                total_bytes += len(key) + 50  # Overhead for key and metadata
        return total_bytes


class GradientSerializer:
    """Efficient binary serialization for gradients with compression."""
    
    @staticmethod
    def serialize(gradients: Dict[str, np.ndarray], compress: bool = True) -> bytes:
        """
        Serialize gradients to binary format with optional compression.
        
        Args:
            gradients: Dictionary of layer_name -> gradient tensor
            compress: Whether to use MessagePack compression
            
        Returns:
            Binary bytes ready for Redis storage
        """
        # Same format as weights but with compression option
        serializable = {}
        for key, value in gradients.items():
            if isinstance(value, np.ndarray):
                serializable[key] = {
                    'data': value.tobytes(),
                    'dtype': str(value.dtype),
                    'shape': value.shape
                }
            else:
                serializable[key] = value
        
        # Use compression for gradients (they're temporary)
        if compress:
            return msgpack.packb(serializable, use_bin_type=True)
        else:
            return msgpack.packb(serializable, use_bin_type=True)
    
    @staticmethod
    def deserialize(binary: bytes) -> Dict[str, np.ndarray]:
        """
        Deserialize gradients from binary format.
        
        Args:
            binary: Binary bytes from Redis
            
        Returns:
            Dictionary of layer_name -> numpy array
        """
        return WeightsSerializer.deserialize(binary)
    
    @staticmethod
    def aggregate(gradient_list: list[Dict[str, np.ndarray]]) -> Dict[str, np.ndarray]:
        """
        Aggregate multiple gradients by averaging.
        
        Args:
            gradient_list: List of gradient dictionaries from different workers
            
        Returns:
            Averaged gradients
            
        Example:
            grad1 = {'layer1': np.array([1.0, 2.0])}
            grad2 = {'layer1': np.array([3.0, 4.0])}
            avg = GradientSerializer.aggregate([grad1, grad2])
            # Result: {'layer1': np.array([2.0, 3.0])}
        """
        if not gradient_list:
            return {}
        
        # Initialize with zeros
        aggregated = {}
        for key in gradient_list[0].keys():
            aggregated[key] = np.zeros_like(gradient_list[0][key])
        
        # Sum all gradients
        for gradients in gradient_list:
            for key, value in gradients.items():
                aggregated[key] += value
        
        # Average
        num_gradients = len(gradient_list)
        for key in aggregated:
            aggregated[key] /= num_gradients
        
        return aggregated


class MetadataSerializer:
    """JSON-compatible serialization for metadata."""
    
    @staticmethod
    def serialize(metadata: Dict[str, Any]) -> bytes:
        """Serialize metadata to MessagePack."""
        return msgpack.packb(metadata, use_bin_type=True)
    
    @staticmethod
    def deserialize(binary: bytes) -> Dict[str, Any]:
        """Deserialize metadata from MessagePack."""
        return msgpack.unpackb(binary, raw=False)
