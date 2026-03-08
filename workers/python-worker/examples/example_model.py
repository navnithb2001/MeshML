"""
Example custom model definition for MeshML

This file demonstrates the required structure for custom models.
Workers will dynamically import this file and use create_model() and create_dataloader().
"""

import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset
from typing import Optional, Tuple


# ==================== REQUIRED: MODEL_METADATA ====================

MODEL_METADATA = {
    # Required fields
    "name": "SimpleCNN",
    "version": "1.0.0",
    "framework": "pytorch",
    "input_shape": [1, 28, 28],  # MNIST images
    "output_shape": [10],  # 10 classes
    
    # Optional fields
    "description": "Simple CNN for MNIST digit classification",
    "author": "MeshML Team",
    "tags": ["vision", "classification", "mnist"],
    "hyperparameters": {
        "learning_rate": 0.001,
        "batch_size": 32,
        "num_epochs": 10
    },
    "requirements": [
        "torch>=2.0.0",
        "torchvision>=0.15.0"
    ]
}


# ==================== REQUIRED: create_model() ====================

def create_model(device: str = "cpu", **kwargs) -> nn.Module:
    """Create and initialize the model
    
    This function will be called by the worker to instantiate the model.
    
    Args:
        device: Device to place model on ("cuda", "cpu", "mps")
        **kwargs: Additional model parameters
        
    Returns:
        Initialized PyTorch model
    """
    model = SimpleCNN(
        num_classes=kwargs.get("num_classes", 10),
        dropout=kwargs.get("dropout", 0.5)
    )
    model = model.to(device)
    
    return model


# ==================== OPTIONAL: create_dataloader() ====================

def create_dataloader(
    data_path: str,
    batch_size: int = 32,
    is_train: bool = True,
    num_workers: int = 4,
    **kwargs
) -> DataLoader:
    """Create data loader for training/validation
    
    This function will be called by the worker to load data.
    
    Args:
        data_path: Path to data files
        batch_size: Batch size
        is_train: Whether this is training data (affects shuffling)
        num_workers: Number of data loading workers
        **kwargs: Additional dataloader parameters
        
    Returns:
        PyTorch DataLoader
    """
    # Note: In production, this would load actual data from data_path
    # For this example, we'll create a dummy dataset
    dataset = DummyMNISTDataset(size=1000)
    
    dataloader = DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=is_train,
        num_workers=num_workers,
        pin_memory=True,
        drop_last=is_train
    )
    
    return dataloader


# ==================== Model Definition ====================

class SimpleCNN(nn.Module):
    """Simple CNN for image classification"""
    
    def __init__(self, num_classes: int = 10, dropout: float = 0.5):
        """Initialize model
        
        Args:
            num_classes: Number of output classes
            dropout: Dropout probability
        """
        super(SimpleCNN, self).__init__()
        
        # Convolutional layers
        self.conv1 = nn.Conv2d(1, 32, kernel_size=3, padding=1)
        self.conv2 = nn.Conv2d(32, 64, kernel_size=3, padding=1)
        self.conv3 = nn.Conv2d(64, 64, kernel_size=3, padding=1)
        
        # Pooling
        self.pool = nn.MaxPool2d(2, 2)
        
        # Fully connected layers
        self.fc1 = nn.Linear(64 * 3 * 3, 128)
        self.fc2 = nn.Linear(128, num_classes)
        
        # Dropout
        self.dropout = nn.Dropout(dropout)
        
        # Activation
        self.relu = nn.ReLU()
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Forward pass
        
        Args:
            x: Input tensor [batch, 1, 28, 28]
            
        Returns:
            Output logits [batch, num_classes]
        """
        # Conv block 1
        x = self.relu(self.conv1(x))
        x = self.pool(x)  # [batch, 32, 14, 14]
        
        # Conv block 2
        x = self.relu(self.conv2(x))
        x = self.pool(x)  # [batch, 64, 7, 7]
        
        # Conv block 3
        x = self.relu(self.conv3(x))
        x = self.pool(x)  # [batch, 64, 3, 3]
        
        # Flatten
        x = x.view(x.size(0), -1)
        
        # FC layers
        x = self.relu(self.fc1(x))
        x = self.dropout(x)
        x = self.fc2(x)
        
        return x


# ==================== Dummy Dataset for Testing ====================

class DummyMNISTDataset(Dataset):
    """Dummy dataset for testing (replace with real data loader)"""
    
    def __init__(self, size: int = 1000):
        """Initialize dataset
        
        Args:
            size: Number of samples
        """
        self.size = size
    
    def __len__(self) -> int:
        return self.size
    
    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor]:
        """Get item
        
        Args:
            idx: Index
            
        Returns:
            Tuple of (image, label)
        """
        # Generate random MNIST-like image
        image = torch.randn(1, 28, 28)
        
        # Random label
        label = torch.randint(0, 10, (1,)).squeeze()
        
        return image, label
