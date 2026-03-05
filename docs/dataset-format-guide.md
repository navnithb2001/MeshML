# Dataset Format Guide

This guide shows the expected structure for different dataset formats supported by MeshML.

## Supported Formats

### 1. ImageFolder Format (PyTorch Style)

**Best for:** Image classification tasks

**Structure:**
```
dataset/
├── class1/
│   ├── image001.jpg
│   ├── image002.jpg
│   └── ...
├── class2/
│   ├── image003.jpg
│   ├── image004.jpg
│   └── ...
└── class3/
    ├── image005.jpg
    └── ...
```

**Requirements:**
- Top-level directories represent class names
- Each class directory contains images
- Supported image formats: .jpg, .jpeg, .png, .bmp, .gif, .tiff, .webp
- Minimum 1 sample per class (recommended: 100+)
- Maximum 10,000 classes

**Example:**
```
dogs_vs_cats/
├── dog/
│   ├── dog.1.jpg
│   ├── dog.2.jpg
│   └── dog.3.jpg
└── cat/
    ├── cat.1.jpg
    ├── cat.2.jpg
    └── cat.3.jpg
```

---

### 2. COCO Format

**Best for:** Object detection, segmentation, keypoint detection

**Structure:**
```
dataset/
├── annotations.json  (or instances_train.json, etc.)
└── images/
    ├── image001.jpg
    ├── image002.jpg
    └── ...
```

**Annotations JSON Format:**
```json
{
  "images": [
    {
      "id": 1,
      "file_name": "image001.jpg",
      "width": 640,
      "height": 480
    }
  ],
  "annotations": [
    {
      "id": 1,
      "image_id": 1,
      "category_id": 1,
      "bbox": [x, y, width, height],
      "area": 1234.5,
      "segmentation": [...],
      "iscrowd": 0
    }
  ],
  "categories": [
    {
      "id": 1,
      "name": "person",
      "supercategory": "human"
    }
  ]
}
```

**Requirements:**
- Annotations JSON must contain: `images`, `annotations`, `categories`
- Images directory with corresponding image files
- Valid COCO JSON structure
- Maximum 10,000 categories

**Alternate Image Locations:**
The validator will check these directories for images:
- `images/`
- `train/`
- `val/`
- Root directory

---

### 3. CSV Format

**Best for:** Tabular data, image paths with labels, custom formats

**Structure:**
```
dataset/
└── data.csv
```

**CSV Format:**
```csv
image_path,label,split
images/img001.jpg,cat,train
images/img002.jpg,dog,train
images/img003.jpg,cat,val
```

**Requirements:**
- CSV file with header row
- `label` column (required for classification)
- Optional columns: `image_path`, `split`, custom columns
- Maximum 10,000 unique labels

**Example CSV:**
```csv
filename,category,subset
cat/001.jpg,0,train
cat/002.jpg,0,train
dog/001.jpg,1,train
dog/002.jpg,1,val
```

---

## Validation Limits

| Limit | Value |
|-------|-------|
| Maximum dataset size | 100 GB |
| Maximum files | 1,000,000 |
| Maximum classes | 10,000 |
| Minimum samples per class | 1 (recommended: 100+) |

## Upload to GCS

### Using gsutil:
```bash
# Install gsutil
pip install gsutil

# Upload dataset
gsutil -m cp -r /path/to/dataset gs://meshml-datasets/my-dataset

# Verify upload
gsutil ls gs://meshml-datasets/my-dataset
```

### Using Python SDK:
```python
from google.cloud import storage

# Initialize client
client = storage.Client()
bucket = client.bucket('meshml-datasets')

# Upload directory
import os
for root, dirs, files in os.walk('/path/to/dataset'):
    for file in files:
        local_path = os.path.join(root, file)
        blob_path = os.path.relpath(local_path, '/path/to/dataset')
        blob = bucket.blob(f'my-dataset/{blob_path}')
        blob.upload_from_filename(local_path)
        print(f'Uploaded {blob_path}')
```

## Validation via API

### Validate Dataset:
```bash
POST /api/v1/datasets/validate
Authorization: Bearer <token>

{
  "gcs_path": "gs://meshml-datasets/my-dataset",
  "expected_format": "imagefolder"  # optional, auto-detect if omitted
}

Response (Success):
{
  "is_valid": true,
  "format": "imagefolder",
  "error_message": null,
  "validation_details": {
    "format_valid": true,
    "structure_valid": true,
    "content_valid": true,
    "size_valid": true,
    "num_classes": 2,
    "total_samples": 1000,
    "class_distribution": {
      "cat": 500,
      "dog": 500
    },
    "total_size_bytes": 52428800,
    "errors": [],
    "warnings": []
  }
}

Response (Failure):
{
  "is_valid": false,
  "format": null,
  "error_message": "No class directories found",
  "validation_details": {
    "format_valid": false,
    "errors": ["No class directories found"]
  }
}
```

### Get Supported Formats:
```bash
GET /api/v1/datasets/formats

Response:
{
  "supported_formats": [
    {
      "name": "imagefolder",
      "description": "PyTorch ImageFolder format",
      "structure": "dataset/class1/img1.jpg, ...",
      "requirements": [...]
    },
    ...
  ],
  "limits": {
    "max_dataset_size_gb": 100,
    "max_files_per_dataset": 1000000,
    ...
  }
}
```

## Best Practices

1. **Organize by Format:**
   - Use ImageFolder for simple classification
   - Use COCO for detection/segmentation
   - Use CSV for custom/tabular data

2. **Balance Classes:**
   - Try to have similar number of samples per class
   - If imbalanced, validation will warn you
   - Consider data augmentation for minority classes

3. **Optimize File Size:**
   - Compress images appropriately
   - Remove unused files
   - Keep total size under 100 GB

4. **Test Locally First:**
   - Validate structure before uploading
   - Use small subset for initial testing
   - Upload full dataset after validation passes

5. **Use Clear Naming:**
   - Class names should be descriptive
   - Avoid special characters
   - Use consistent naming convention

## Common Errors

### "No class directories found"
- **Cause:** ImageFolder format expects class subdirectories
- **Fix:** Organize images into class folders

### "Invalid COCO format: missing required keys"
- **Cause:** Annotations JSON missing required fields
- **Fix:** Ensure JSON has `images`, `annotations`, `categories`

### "Dataset too large"
- **Cause:** Dataset exceeds 100 GB limit
- **Fix:** Reduce image resolution, remove duplicates, or split dataset

### "Too many classes"
- **Cause:** More than 10,000 unique classes
- **Fix:** Merge similar classes or use different dataset structure

### "Could not detect dataset format"
- **Cause:** Dataset doesn't match any supported format
- **Fix:** Restructure dataset to match one of the supported formats

## Examples

See `examples/` directory for sample datasets:
- `examples/imagefolder_dataset/` - ImageFolder example
- `examples/coco_dataset/` - COCO example
- `examples/csv_dataset/` - CSV example
