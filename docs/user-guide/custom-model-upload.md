# Custom Model Upload System

**Last Updated:** March 1, 2026

Complete guide for students to upload custom PyTorch models and train them using distributed compute from their classmates.

---

## Table of Contents

1. [Overview](#overview)
2. [Student Workflow](#student-workflow)
3. [Model File Structure](#model-file-structure)
4. [Dataset Handling](#dataset-handling)
5. [Examples](#examples)
6. [Validation & Error Handling](#validation--error-handling)

---

## Overview

MeshML supports **custom model uploads** via Python files, allowing students to use any PyTorch architecture for their assignments.

### Key Benefits

✅ **Familiar Python** - Write normal PyTorch code  
✅ **Maximum Flexibility** - Any model, dataset, preprocessing  
✅ **Easy Testing** - Test locally before uploading  
✅ **Collaborative** - Leverage classmates' compute power  
✅ **Version Control** - Standard .py files work with Git

---

## Student Workflow

### Step 1: Write Model File

Create a Python file with three required components:

1. **Model class** (your architecture)
2. **`create_model()` function**
3. **`create_dataloader()` function**
4. **`MODEL_METADATA` dict**

```python
# my_model.py - Example template

import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from torchvision import datasets, transforms
from typing import Dict, Any

# 1. YOUR MODEL ARCHITECTURE
class MyModel(nn.Module):
    def __init__(self, num_classes=10):
        super().__init__()
        # Your layers here
        self.conv1 = nn.Conv2d(3, 64, 3)
        self.fc = nn.Linear(64 * 30 * 30, num_classes)
    
    def forward(self, x):
        # Your forward pass
        x = self.conv1(x)
        x = x.view(x.size(0), -1)
        return self.fc(x)

# 2. REQUIRED: How to create your model
def create_model(config: Dict[str, Any]) -> nn.Module:
    """
    MeshML calls this to instantiate your model.
    
    Args:
        config: Configuration dict from job creation
                e.g., {'num_classes': 10, 'learning_rate': 0.001}
    
    Returns:
        Your model instance
    """
    return MyModel(num_classes=config.get('num_classes', 10))

# 3. REQUIRED: How to load your data
def create_dataloader(batch_path: str, config: Dict[str, Any]):
    """
    MeshML calls this for each data batch on each worker.
    
    Args:
        batch_path: Path where MeshML downloaded the data batch
        config: Same config dict as create_model
    
    Returns:
        PyTorch DataLoader instance
    """
    transform = transforms.Compose([
        transforms.Resize(224),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
    ])
    
    dataset = datasets.ImageFolder(batch_path, transform=transform)
    
    return DataLoader(
        dataset,
        batch_size=config.get('batch_size', 32),
        shuffle=True,
        num_workers=2
    )

# 4. REQUIRED: Metadata about your model
MODEL_METADATA = {
    "name": "MyCustomCNN",
    "description": "Custom CNN for image classification",
    "input_type": "image",  # "image", "text", "tabular", "audio"
    "output_type": "classification",  # "classification", "regression", "detection"
    "dataset_format": "imagefolder",  # Expected dataset structure
    "requirements": [
        # List any extra Python packages (optional)
        # "transformers>=4.30.0",
        # "opencv-python>=4.8.0"
    ]
}

# OPTIONAL: Custom loss function (default: CrossEntropyLoss)
def create_loss_fn(config: Dict[str, Any]):
    return nn.CrossEntropyLoss()

# OPTIONAL: Custom optimizer (default: Adam)
def create_optimizer(model: nn.Module, config: Dict[str, Any]):
    return torch.optim.Adam(
        model.parameters(),
        lr=config.get('learning_rate', 0.001)
    )
```

### Step 2: Test Locally (Recommended)

```bash
# Test your model file before uploading
python my_model.py

# Or create a test script
python -c "
from my_model import create_model, create_dataloader

# Test model creation
config = {'num_classes': 10, 'batch_size': 32}
model = create_model(config)
print(f'Model created: {model}')

# Test dataloader (use local test data)
loader = create_dataloader('./test_data/', config)
print(f'DataLoader created with {len(loader)} batches')
"
```

### Step 3: Upload via Dashboard

1. Open MeshML Dashboard: `https://meshml.yourschool.edu`
2. Click **"Create Training Job"**
3. Select **"Custom Python File"** as model source
4. Upload your `my_model.py` file
5. Upload dataset or select built-in dataset
6. Configure training parameters
7. Click **"Start Training"**

### Step 4: Monitor Training

Watch real-time metrics in the dashboard:
- Training loss and accuracy
- Worker status (which classmates are helping)
- Estimated completion time

### Step 5: Download Results

When training completes:
- Download trained model (.pt file)
- Download training report (PDF)
- Download metrics (CSV for analysis)

---

## Model File Structure

### Required Functions

#### `create_model(config: Dict[str, Any]) -> nn.Module`

**Purpose:** Instantiate your model  
**Called:** Once per worker at the start of training  
**Arguments:**
- `config`: Dict with your training configuration

**Example:**
```python
def create_model(config):
    num_classes = config.get('num_classes', 10)
    dropout = config.get('dropout', 0.5)
    return MyModel(num_classes=num_classes, dropout=dropout)
```

---

#### `create_dataloader(batch_path: str, config: Dict[str, Any]) -> DataLoader`

**Purpose:** Create DataLoader for a data batch  
**Called:** For each batch assigned to each worker  
**Arguments:**
- `batch_path`: Path to downloaded and extracted batch
- `config`: Same dict as `create_model`

**Example:**
```python
def create_dataloader(batch_path, config):
    # Your custom dataset class
    dataset = MyCustomDataset(
        batch_path,
        transform=get_transforms(config)
    )
    
    return DataLoader(
        dataset,
        batch_size=config['batch_size'],
        shuffle=True,
        num_workers=config.get('num_workers', 2),
        pin_memory=True
    )
```

---

### Required Metadata

#### `MODEL_METADATA: Dict[str, Any]`

**Purpose:** Describe your model to the system

**Required fields:**
```python
MODEL_METADATA = {
    "name": str,              # Your model name
    "description": str,       # Brief description
    "input_type": str,        # "image" | "text" | "tabular" | "audio"
    "output_type": str,       # "classification" | "regression" | "detection" | "segmentation"
    "dataset_format": str,    # "imagefolder" | "coco" | "csv" | "json" | "custom"
    "requirements": List[str] # Extra pip packages (optional)
}
```

**Example:**
```python
MODEL_METADATA = {
    "name": "StudentResNet",
    "description": "ResNet-18 variant for CS 4375 Assignment 2",
    "input_type": "image",
    "output_type": "classification",
    "dataset_format": "imagefolder",
    "requirements": []
}
```

---

### Optional Functions

#### `create_loss_fn(config: Dict[str, Any]) -> nn.Module`

**Default:** `nn.CrossEntropyLoss()` for classification  
**Override when:** Using custom loss (e.g., YOLO loss, focal loss)

```python
def create_loss_fn(config):
    alpha = config.get('focal_alpha', 0.25)
    gamma = config.get('focal_gamma', 2.0)
    return FocalLoss(alpha=alpha, gamma=gamma)
```

---

#### `create_optimizer(model: nn.Module, config: Dict[str, Any]) -> Optimizer`

**Default:** `torch.optim.Adam(model.parameters(), lr=config['learning_rate'])`  
**Override when:** Using SGD, AdamW, or custom optimizer

```python
def create_optimizer(model, config):
    return torch.optim.SGD(
        model.parameters(),
        lr=config['learning_rate'],
        momentum=config.get('momentum', 0.9),
        weight_decay=config.get('weight_decay', 1e-4)
    )
```

---

## Dataset Handling

### Supported Dataset Formats

#### 1. ImageFolder (Image Classification)

**Structure:**
```
dataset/
  ├── class1/
  │   ├── img1.jpg
  │   ├── img2.jpg
  │   └── ...
  ├── class2/
  │   ├── img3.jpg
  │   └── ...
  └── class3/
      └── ...
```

**DataLoader:**
```python
def create_dataloader(batch_path, config):
    from torchvision import datasets, transforms
    
    transform = transforms.Compose([
        transforms.Resize(224),
        transforms.ToTensor()
    ])
    
    dataset = datasets.ImageFolder(batch_path, transform=transform)
    return DataLoader(dataset, batch_size=config['batch_size'])
```

---

#### 2. COCO (Object Detection)

**Structure:**
```
dataset/
  ├── images/
  │   ├── img1.jpg
  │   └── img2.jpg
  └── annotations.json
```

**DataLoader:**
```python
def create_dataloader(batch_path, config):
    from pycocotools.coco import COCO
    
    class COCODataset(Dataset):
        def __init__(self, batch_path):
            self.coco = COCO(f"{batch_path}/annotations.json")
            self.img_dir = f"{batch_path}/images"
            self.ids = list(self.coco.imgs.keys())
        
        def __getitem__(self, idx):
            img_id = self.ids[idx]
            ann_ids = self.coco.getAnnIds(imgIds=img_id)
            anns = self.coco.loadAnns(ann_ids)
            # Load image and process annotations
            ...
    
    dataset = COCODataset(batch_path)
    return DataLoader(dataset, batch_size=config['batch_size'])
```

---

#### 3. CSV (Tabular Data)

**Structure:**
```
batch/
  └── data.csv  # Columns: features + labels
```

**DataLoader:**
```python
def create_dataloader(batch_path, config):
    import pandas as pd
    
    class TabularDataset(Dataset):
        def __init__(self, csv_path):
            self.df = pd.read_csv(csv_path)
            self.features = self.df.drop('label', axis=1).values
            self.labels = self.df['label'].values
        
        def __getitem__(self, idx):
            return (
                torch.tensor(self.features[idx], dtype=torch.float32),
                torch.tensor(self.labels[idx], dtype=torch.long)
            )
        
        def __len__(self):
            return len(self.df)
    
    dataset = TabularDataset(f"{batch_path}/data.csv")
    return DataLoader(dataset, batch_size=config['batch_size'])
```

---

#### 4. Text (JSON Lines)

**Structure:**
```
batch/
  └── data.jsonl  # Each line: {"text": "...", "label": 0}
```

**DataLoader:**
```python
def create_dataloader(batch_path, config):
    from transformers import BertTokenizer
    import json
    
    class TextDataset(Dataset):
        def __init__(self, jsonl_path, tokenizer, max_length):
            with open(jsonl_path) as f:
                self.data = [json.loads(line) for line in f]
            self.tokenizer = tokenizer
            self.max_length = max_length
        
        def __getitem__(self, idx):
            item = self.data[idx]
            encoding = self.tokenizer(
                item['text'],
                max_length=self.max_length,
                padding='max_length',
                truncation=True,
                return_tensors='pt'
            )
            return {
                'input_ids': encoding['input_ids'].squeeze(),
                'attention_mask': encoding['attention_mask'].squeeze(),
                'label': torch.tensor(item['label'])
            }
        
        def __len__(self):
            return len(self.data)
    
    tokenizer = BertTokenizer.from_pretrained('bert-base-uncased')
    dataset = TextDataset(
        f"{batch_path}/data.jsonl",
        tokenizer,
        config.get('max_length', 128)
    )
    return DataLoader(dataset, batch_size=config['batch_size'])
```

---

## Examples

### Example 1: Simple CNN for MNIST

```python
# mnist_cnn.py

import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from torchvision import datasets, transforms
from typing import Dict, Any

class SimpleCNN(nn.Module):
    def __init__(self, num_classes=10):
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv2d(1, 32, 3, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(2),
            nn.Conv2d(32, 64, 3, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(2)
        )
        self.classifier = nn.Sequential(
            nn.Linear(64 * 7 * 7, 128),
            nn.ReLU(),
            nn.Dropout(0.5),
            nn.Linear(128, num_classes)
        )
    
    def forward(self, x):
        x = self.features(x)
        x = x.view(x.size(0), -1)
        return self.classifier(x)

def create_model(config: Dict[str, Any]) -> nn.Module:
    return SimpleCNN(num_classes=config.get('num_classes', 10))

def create_dataloader(batch_path: str, config: Dict[str, Any]):
    transform = transforms.Compose([
        transforms.ToTensor(),
        transforms.Normalize((0.1307,), (0.3081,))
    ])
    
    dataset = datasets.ImageFolder(batch_path, transform=transform)
    return DataLoader(
        dataset,
        batch_size=config.get('batch_size', 64),
        shuffle=True
    )

MODEL_METADATA = {
    "name": "SimpleMNISTCNN",
    "description": "3-layer CNN for MNIST digit classification",
    "input_type": "image",
    "output_type": "classification",
    "dataset_format": "imagefolder",
    "requirements": []
}
```

---

### Example 2: BERT for Sentiment Analysis

```python
# bert_sentiment.py

import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from transformers import BertModel, BertTokenizer
import pandas as pd
from typing import Dict, Any

class BERTClassifier(nn.Module):
    def __init__(self, num_classes=2, dropout=0.3):
        super().__init__()
        self.bert = BertModel.from_pretrained('bert-base-uncased')
        self.dropout = nn.Dropout(dropout)
        self.classifier = nn.Linear(768, num_classes)
    
    def forward(self, input_ids, attention_mask):
        outputs = self.bert(
            input_ids=input_ids,
            attention_mask=attention_mask
        )
        pooled = outputs.pooler_output
        dropped = self.dropout(pooled)
        return self.classifier(dropped)

def create_model(config: Dict[str, Any]) -> nn.Module:
    return BERTClassifier(
        num_classes=config.get('num_classes', 2),
        dropout=config.get('dropout', 0.3)
    )

class SentimentDataset(Dataset):
    def __init__(self, csv_path, tokenizer, max_length=128):
        self.df = pd.read_csv(csv_path)
        self.tokenizer = tokenizer
        self.max_length = max_length
    
    def __len__(self):
        return len(self.df)
    
    def __getitem__(self, idx):
        text = self.df.iloc[idx]['text']
        label = self.df.iloc[idx]['label']
        
        encoding = self.tokenizer(
            text,
            max_length=self.max_length,
            padding='max_length',
            truncation=True,
            return_tensors='pt'
        )
        
        return {
            'input_ids': encoding['input_ids'].squeeze(),
            'attention_mask': encoding['attention_mask'].squeeze(),
            'label': torch.tensor(label, dtype=torch.long)
        }

def create_dataloader(batch_path: str, config: Dict[str, Any]):
    tokenizer = BertTokenizer.from_pretrained('bert-base-uncased')
    dataset = SentimentDataset(
        f"{batch_path}/data.csv",
        tokenizer,
        max_length=config.get('max_length', 128)
    )
    
    return DataLoader(
        dataset,
        batch_size=config.get('batch_size', 16),
        shuffle=True
    )

MODEL_METADATA = {
    "name": "BERTSentiment",
    "description": "BERT fine-tuned for sentiment classification",
    "input_type": "text",
    "output_type": "classification",
    "dataset_format": "csv",
    "requirements": [
        "transformers>=4.30.0",
        "pandas>=2.0.0"
    ]
}
```

---

### Example 3: Custom ResNet Variant

```python
# custom_resnet.py

import torch
import torch.nn as nn
from torchvision import transforms, datasets
from torch.utils.data import DataLoader
from typing import Dict, Any

class ResidualBlock(nn.Module):
    def __init__(self, in_channels, out_channels, stride=1):
        super().__init__()
        self.conv1 = nn.Conv2d(in_channels, out_channels, 3, stride, padding=1)
        self.bn1 = nn.BatchNorm2d(out_channels)
        self.conv2 = nn.Conv2d(out_channels, out_channels, 3, 1, padding=1)
        self.bn2 = nn.BatchNorm2d(out_channels)
        
        self.shortcut = nn.Sequential()
        if stride != 1 or in_channels != out_channels:
            self.shortcut = nn.Sequential(
                nn.Conv2d(in_channels, out_channels, 1, stride),
                nn.BatchNorm2d(out_channels)
            )
    
    def forward(self, x):
        out = torch.relu(self.bn1(self.conv1(x)))
        out = self.bn2(self.conv2(out))
        out += self.shortcut(x)
        return torch.relu(out)

class CustomResNet(nn.Module):
    def __init__(self, num_classes=10, num_blocks=[2, 2, 2, 2]):
        super().__init__()
        self.conv1 = nn.Conv2d(3, 64, 7, 2, padding=3)
        self.bn1 = nn.BatchNorm2d(64)
        self.maxpool = nn.MaxPool2d(3, 2, padding=1)
        
        self.layer1 = self._make_layer(64, 64, num_blocks[0], stride=1)
        self.layer2 = self._make_layer(64, 128, num_blocks[1], stride=2)
        self.layer3 = self._make_layer(128, 256, num_blocks[2], stride=2)
        self.layer4 = self._make_layer(256, 512, num_blocks[3], stride=2)
        
        self.avgpool = nn.AdaptiveAvgPool2d((1, 1))
        self.fc = nn.Linear(512, num_classes)
    
    def _make_layer(self, in_channels, out_channels, num_blocks, stride):
        layers = [ResidualBlock(in_channels, out_channels, stride)]
        for _ in range(1, num_blocks):
            layers.append(ResidualBlock(out_channels, out_channels))
        return nn.Sequential(*layers)
    
    def forward(self, x):
        x = self.maxpool(torch.relu(self.bn1(self.conv1(x))))
        x = self.layer1(x)
        x = self.layer2(x)
        x = self.layer3(x)
        x = self.layer4(x)
        x = self.avgpool(x)
        x = x.view(x.size(0), -1)
        return self.fc(x)

def create_model(config: Dict[str, Any]) -> nn.Module:
    return CustomResNet(
        num_classes=config.get('num_classes', 10),
        num_blocks=config.get('num_blocks', [2, 2, 2, 2])
    )

def create_dataloader(batch_path: str, config: Dict[str, Any]):
    # ImageNet-style preprocessing
    transform = transforms.Compose([
        transforms.Resize(256),
        transforms.CenterCrop(224),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
    ])
    
    dataset = datasets.ImageFolder(batch_path, transform=transform)
    return DataLoader(
        dataset,
        batch_size=config.get('batch_size', 32),
        shuffle=True,
        num_workers=4,
        pin_memory=True
    )

def create_optimizer(model: nn.Module, config: Dict[str, Any]):
    return torch.optim.SGD(
        model.parameters(),
        lr=config.get('learning_rate', 0.1),
        momentum=config.get('momentum', 0.9),
        weight_decay=config.get('weight_decay', 1e-4)
    )

MODEL_METADATA = {
    "name": "CustomResNet18",
    "description": "Custom ResNet-18 variant with configurable blocks",
    "input_type": "image",
    "output_type": "classification",
    "dataset_format": "imagefolder",
    "requirements": []
}
```

---

## Validation & Error Handling

### System Validation

When you upload a model file, MeshML validates:

1. ✅ **Syntax:** Python file is syntactically valid
2. ✅ **Required functions:** Has `create_model()` and `create_dataloader()`
3. ✅ **Metadata:** Has `MODEL_METADATA` dict with required fields
4. ✅ **Imports:** All imports are available or in `requirements`
5. ✅ **Test instantiation:** Can create model with default config

### Common Errors

#### Error: Missing Required Function

```
❌ ValidationError: Model file missing required function 'create_model'

Solution: Add the create_model() function to your file
```

#### Error: Invalid Metadata

```
❌ ValidationError: MODEL_METADATA missing required field 'input_type'

Solution: Add 'input_type' to MODEL_METADATA dict
```

#### Error: Import Failed

```
❌ ImportError: No module named 'some_package'

Solution: Add 'some_package>=version' to MODEL_METADATA['requirements']
```

#### Error: Model Instantiation Failed

```
❌ RuntimeError: create_model() failed with: __init__() missing 1 required positional argument

Solution: Make sure your model's __init__ has default values for all parameters
```

### Best Practices

✅ **Test locally first** - Run your model file before uploading  
✅ **Use default arguments** - Make all config parameters optional with defaults  
✅ **Document your code** - Add comments explaining custom logic  
✅ **Minimal requirements** - Only add packages you actually need  
✅ **Standard preprocessing** - Use common transforms when possible  
✅ **Error handling** - Add try/except in custom data loading code

---

## Summary

### What You Need

1. **Model file** (.py) with:
   - Your model class
   - `create_model()` function
   - `create_dataloader()` function
   - `MODEL_METADATA` dict

2. **Dataset** in supported format (ImageFolder, COCO, CSV, etc.)

3. **Configuration** (batch size, learning rate, etc.)

### What MeshML Does

1. ✅ Validates your model file
2. ✅ Distributes it to all workers
3. ✅ Shards your dataset into batches
4. ✅ Assigns batches to workers
5. ✅ Runs distributed training
6. ✅ Aggregates results
7. ✅ Returns trained model

### Getting Help

- 📚 Examples: See `/examples` directory
- 💬 Discord: Join student support channel
- 📧 Email: meshml-support@yourschool.edu
- 📖 Docs: https://docs.meshml.yourschool.edu

---

**Ready to train? Upload your model and start collaborating!** 🚀
