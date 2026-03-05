"""
Example custom model file for MeshML.

This file demonstrates the required structure for custom PyTorch models.
Users should copy this template and modify it for their specific model.
"""

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, Dataset
from torchvision import transforms, datasets


# REQUIRED: MODEL_METADATA dictionary
# This metadata is used for validation and job configuration
MODEL_METADATA = {
    # Required fields
    "task_type": "classification",           # Options: classification, regression, segmentation, etc.
    "input_shape": [3, 224, 224],           # Expected input tensor shape (channels, height, width)
    "output_shape": [1000],                 # Output tensor shape (e.g., number of classes)
    "framework": "pytorch",                 # ML framework used
    
    # Optional but recommended fields
    "num_classes": 1000,                    # Number of output classes (for classification)
    "loss_function": "CrossEntropyLoss",    # Loss function name
    "optimizer": "Adam",                    # Optimizer name
    "learning_rate": 0.001,                 # Default learning rate
    
    # Additional custom metadata (optional)
    "model_name": "ResNet50-Custom",
    "model_version": "1.0.0",
    "description": "Custom ResNet-50 for ImageNet classification",
    "batch_size": 32,
    "epochs": 10,
}


# REQUIRED: create_model() function
def create_model():
    """
    Create and return the PyTorch model.
    
    This function will be called by workers to instantiate the model.
    The model should be ready for training (untrained weights are fine).
    
    Returns:
        torch.nn.Module: The model instance
    """
    # Example: Simple ResNet-50 from torchvision
    from torchvision.models import resnet50
    
    model = resnet50(pretrained=False)  # Start with random weights
    
    # Optionally modify the model architecture
    # For example, change the final layer for different number of classes
    num_classes = MODEL_METADATA.get("num_classes", 1000)
    model.fc = nn.Linear(model.fc.in_features, num_classes)
    
    return model


# REQUIRED: create_dataloader() function
def create_dataloader(batch_path: str, batch_size: int = 32, is_train: bool = True):
    """
    Create and return a DataLoader for a batch of data.
    
    This function will be called by workers with paths to data batches.
    It should handle loading the data and returning a PyTorch DataLoader.
    
    Args:
        batch_path (str): Path to the data batch directory or file
        batch_size (int): Batch size for the DataLoader
        is_train (bool): Whether this is for training (True) or validation (False)
        
    Returns:
        torch.utils.data.DataLoader: DataLoader for the batch
    """
    # Example: ImageFolder dataset with standard transforms
    
    # Define transforms
    if is_train:
        transform = transforms.Compose([
            transforms.RandomResizedCrop(224),
            transforms.RandomHorizontalFlip(),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406],
                               std=[0.229, 0.224, 0.225])
        ])
    else:
        transform = transforms.Compose([
            transforms.Resize(256),
            transforms.CenterCrop(224),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406],
                               std=[0.229, 0.224, 0.225])
        ])
    
    # Load dataset from batch_path
    # Assuming ImageFolder structure: batch_path/class_name/image.jpg
    dataset = datasets.ImageFolder(root=batch_path, transform=transform)
    
    # Create DataLoader
    dataloader = DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=is_train,
        num_workers=2,
        pin_memory=True
    )
    
    return dataloader


# OPTIONAL: Additional helper functions
def get_optimizer(model, learning_rate=None):
    """
    Create optimizer for the model.
    
    This is optional - workers can use their own optimizer logic.
    But providing a default can be helpful.
    """
    lr = learning_rate or MODEL_METADATA.get("learning_rate", 0.001)
    optimizer_name = MODEL_METADATA.get("optimizer", "Adam")
    
    if optimizer_name == "Adam":
        return optim.Adam(model.parameters(), lr=lr)
    elif optimizer_name == "SGD":
        return optim.SGD(model.parameters(), lr=lr, momentum=0.9)
    else:
        return optim.Adam(model.parameters(), lr=lr)


def get_loss_function():
    """
    Create loss function.
    
    This is optional - workers can use their own loss logic.
    """
    loss_name = MODEL_METADATA.get("loss_function", "CrossEntropyLoss")
    
    if loss_name == "CrossEntropyLoss":
        return nn.CrossEntropyLoss()
    elif loss_name == "MSELoss":
        return nn.MSELoss()
    else:
        return nn.CrossEntropyLoss()


# Example usage (for testing locally)
if __name__ == "__main__":
    print("Testing model creation...")
    
    # Test model creation
    model = create_model()
    print(f"✓ Model created: {model.__class__.__name__}")
    print(f"  Parameters: {sum(p.numel() for p in model.parameters()):,}")
    
    # Test forward pass with dummy data
    dummy_input = torch.randn(1, *MODEL_METADATA["input_shape"])
    output = model(dummy_input)
    print(f"✓ Forward pass successful")
    print(f"  Input shape: {dummy_input.shape}")
    print(f"  Output shape: {output.shape}")
    
    # Verify output shape matches metadata
    expected_output = torch.Size([1] + MODEL_METADATA["output_shape"])
    assert output.shape == expected_output, f"Output shape mismatch: {output.shape} vs {expected_output}"
    print(f"✓ Output shape matches metadata")
    
    print("\nMODEL_METADATA:")
    for key, value in MODEL_METADATA.items():
        print(f"  {key}: {value}")
    
    print("\n✓ All tests passed! Model is ready for upload.")
