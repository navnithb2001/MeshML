# TASK 5.2: Sharding Algorithms - COMPLETED ✅

## Task Description
Implemented comprehensive dataset sharding algorithms with multiple strategies (Random, Stratified, Non-IID, Sequential) to partition datasets across distributed workers while maintaining data quality.

---

## Implementation Summary

### 1. Dataset Sharder Service (`app/services/dataset_sharder.py` - ~630 lines)

**Purpose**: Partition datasets into shards with different distribution strategies

**Key Components**:

#### Enums

**ShardingStrategy**:
- `RANDOM`: Random IID split (shuffled samples)
- `STRATIFIED`: Maintain class distribution (IID with balance)
- `NON_IID`: Skewed distributions using Dirichlet (realistic federated learning)
- `SEQUENTIAL`: Contiguous chunks (for debugging)

**DataDistribution**:
- `IID`: Independent and Identically Distributed
- `NON_IID`: Non-IID (different distributions per worker)

#### Data Classes

**ShardMetadata**:
```python
@dataclass
class ShardMetadata:
    shard_id: int
    total_shards: int
    num_samples: int
    sample_indices: List[int]
    class_distribution: Dict[str, int]
    size_bytes: int
    checksum: Optional[str]
    
    def get_balance_ratio(self) -> float:
        """Returns max_count / min_count (1.0 = perfect balance)"""
```

**ShardingConfig**:
```python
@dataclass
class ShardingConfig:
    num_shards: int
    strategy: ShardingStrategy = STRATIFIED
    batch_size: Optional[int] = None
    min_samples_per_shard: int = 10
    max_samples_per_shard: Optional[int] = None
    seed: int = 42
    
    # Non-IID parameters
    non_iid_alpha: float = 0.5  # Dirichlet α (lower = more skewed)
    non_iid_classes_per_shard: Optional[int] = None
```

---

### 2. Sharding Strategies

#### Strategy 1: Random Sharding (IID)

**Algorithm**:
1. Shuffle all samples randomly
2. Divide into equal-sized chunks
3. Assign chunks to shards

**Characteristics**:
- ✅ Simple and fast
- ✅ IID distribution (similar to centralized training)
- ✅ No class balance guarantee
- ⚠️ May have imbalanced classes per shard

**Use Case**: When dataset is already balanced and IID distribution is desired

```python
config = ShardingConfig(
    num_shards=10,
    strategy=ShardingStrategy.RANDOM,
    seed=42
)
```

**Expected Distribution**:
```
Shard 0: 900 samples (class_a: 450, class_b: 450) ✓ balanced
Shard 1: 900 samples (class_a: 470, class_b: 430) ✓ roughly balanced
Shard 2: 900 samples (class_a: 440, class_b: 460) ✓ roughly balanced
...
```

---

#### Strategy 2: Stratified Sharding (IID + Balanced)

**Algorithm**:
1. Group samples by class
2. Shuffle samples within each class
3. Distribute each class evenly across shards
4. Shuffle samples within each shard

**Characteristics**:
- ✅ Maintains global class distribution in each shard
- ✅ IID distribution
- ✅ Perfect for imbalanced datasets
- ✅ Best for most distributed training scenarios

**Use Case**: Default choice for distributed training (ensures fairness)

```python
config = ShardingConfig(
    num_shards=10,
    strategy=ShardingStrategy.STRATIFIED,
    seed=42
)
```

**Expected Distribution**:
```
Dataset: 1000 samples (class_a: 700, class_b: 300)

Shard 0: 100 samples (class_a: 70, class_b: 30) ✓ 70/30 ratio maintained
Shard 1: 100 samples (class_a: 70, class_b: 30) ✓ 70/30 ratio maintained
Shard 2: 100 samples (class_a: 70, class_b: 30) ✓ 70/30 ratio maintained
...
```

---

#### Strategy 3: Non-IID Sharding (Federated Learning)

**Algorithm**:
1. Use Dirichlet distribution to generate class proportions per shard
2. Distribute samples according to these proportions
3. Creates realistic heterogeneous data partitions

**Characteristics**:
- ✅ Simulates real-world federated learning scenarios
- ✅ Configurable skewness via `non_iid_alpha`
- ✅ Each shard has different class distribution
- ⚠️ More challenging for training (requires robust algorithms)

**Use Case**: Federated learning research, testing model robustness

```python
config = ShardingConfig(
    num_shards=10,
    strategy=ShardingStrategy.NON_IID,
    non_iid_alpha=0.5,  # Lower = more skewed
    seed=42
)
```

**Alpha Parameter**:
- `α = 0.1`: Highly skewed (each shard dominated by 1-2 classes)
- `α = 0.5`: Moderately skewed (realistic federated setting)
- `α = 10.0`: Almost uniform (close to IID)

**Expected Distribution**:
```
Dataset: 1000 samples (10 classes, 100 samples each)

α = 0.1 (Highly Skewed):
Shard 0: class_0: 90, class_1: 5, class_2: 3, class_3: 2, ...
Shard 1: class_1: 85, class_0: 8, class_4: 4, class_2: 3, ...
Shard 2: class_3: 88, class_5: 7, class_1: 3, class_7: 2, ...

α = 0.5 (Moderate):
Shard 0: class_0: 35, class_1: 25, class_2: 20, class_3: 10, ...
Shard 1: class_2: 30, class_4: 25, class_0: 15, class_1: 20, ...

α = 10.0 (Nearly Uniform):
Shard 0: class_0: 11, class_1: 9, class_2: 10, class_3: 11, ...
Shard 1: class_0: 10, class_1: 10, class_2: 10, class_3: 10, ...
```

---

#### Strategy 4: Sequential Sharding (Debugging)

**Algorithm**:
1. Divide dataset into contiguous chunks
2. No shuffling

**Characteristics**:
- ✅ Deterministic and predictable
- ✅ Easy to debug
- ⚠️ Not recommended for training (biased)

**Use Case**: Testing, debugging, validation

```python
config = ShardingConfig(
    num_shards=10,
    strategy=ShardingStrategy.SEQUENTIAL
)
```

---

### 3. Batch Size Calculation

**Auto-calculate optimal batch size** based on shard size and target batches per epoch:

```python
sharder = DatasetSharder(loader, config)
sharder.create_shards()

# Calculate batch size
batch_size = sharder.calculate_batch_size(
    target_batches_per_epoch=100,  # Desired batches per epoch
    min_batch_size=8,
    max_batch_size=512
)

# Returns power of 2 (e.g., 8, 16, 32, 64, ...)
```

**Algorithm**:
1. Find smallest shard size
2. Calculate: `batch_size = shard_size / target_batches`
3. Clamp to [min_batch_size, max_batch_size]
4. Round to nearest power of 2

**Example**:
```
Smallest shard: 3200 samples
Target batches: 100
Calculated: 3200 / 100 = 32
Power of 2: 32 ✓
Result: batch_size = 32
```

---

### 4. Distribution Quality Analysis

**Analyze shard quality** with comprehensive metrics:

```python
from app.services.dataset_sharder import analyze_distribution_quality

analysis = analyze_distribution_quality(shards)
```

**Returns**:
```python
{
    "num_shards": 10,
    "total_samples": 10000,
    
    # Size distribution
    "size_distribution": {
        "mean": 1000.0,
        "std": 5.2,
        "min": 995,
        "max": 1005,
        "cv": 0.0052  # Coefficient of variation
    },
    
    # Class balance
    "balance_distribution": {
        "mean": 1.05,  # Average balance ratio
        "std": 0.02,
        "min": 1.01,
        "max": 1.08
    },
    
    # Class variance (IID measure)
    "class_variance": {
        "per_class": {
            "class_0": 2.5,
            "class_1": 3.1,
            ...
        },
        "average": 2.8
    },
    
    # Overall quality (0-100, higher is better)
    "quality_score": 92.5
}
```

**Quality Score Components**:
- **Size uniformity** (30%): How evenly samples are distributed
- **Balance quality** (40%): How balanced classes are within shards
- **Class variance** (30%): How similar class distributions are (IID measure)

---

## Usage Examples

### Example 1: Stratified Sharding for Production

```python
from app.services.dataset_loader import ImageFolderLoader
from app.services.dataset_sharder import DatasetSharder, ShardingConfig, ShardingStrategy

# Load dataset
loader = ImageFolderLoader("gs://bucket/imagenet")
metadata = loader.load_metadata()

print(f"Dataset: {metadata.total_samples} samples, {metadata.num_classes} classes")

# Create stratified shards
config = ShardingConfig(
    num_shards=100,  # 100 workers
    strategy=ShardingStrategy.STRATIFIED,
    seed=42
)

sharder = DatasetSharder(loader, config)
shards = sharder.create_shards()

# Calculate batch size
batch_size = sharder.calculate_batch_size(target_batches_per_epoch=100)

print(f"Created {len(shards)} shards")
print(f"Batch size: {batch_size}")

# Analyze quality
from app.services.dataset_sharder import analyze_distribution_quality
analysis = analyze_distribution_quality(shards)
print(f"Quality score: {analysis['quality_score']}")

# Get specific shard
shard_0 = sharder.get_shard(0)
print(f"Shard 0: {shard_0.num_samples} samples")
print(f"Class distribution: {shard_0.class_distribution}")
print(f"Balance ratio: {shard_0.get_balance_ratio():.2f}")
```

### Example 2: Non-IID for Federated Learning

```python
# Simulate federated learning with heterogeneous data
config = ShardingConfig(
    num_shards=50,  # 50 clients
    strategy=ShardingStrategy.NON_IID,
    non_iid_alpha=0.1,  # Highly skewed
    seed=42
)

sharder = DatasetSharder(loader, config)
shards = sharder.create_shards()

# Each client gets different class distribution
for shard in shards[:5]:  # Show first 5
    print(f"Client {shard.shard_id}:")
    print(f"  Samples: {shard.num_samples}")
    print(f"  Distribution: {shard.class_distribution}")
    print(f"  Dominant class: {max(shard.class_distribution.items(), key=lambda x: x[1])}")
```

### Example 3: Compare Strategies

```python
strategies = [
    ShardingStrategy.RANDOM,
    ShardingStrategy.STRATIFIED,
    ShardingStrategy.NON_IID
]

for strategy in strategies:
    config = ShardingConfig(num_shards=10, strategy=strategy, seed=42)
    sharder = DatasetSharder(loader, config)
    shards = sharder.create_shards()
    
    analysis = analyze_distribution_quality(shards)
    
    print(f"\n{strategy}:")
    print(f"  Quality score: {analysis['quality_score']}")
    print(f"  Avg balance ratio: {analysis['balance_distribution']['mean']:.2f}")
    print(f"  Class variance: {analysis['class_variance']['average']:.2f}")
```

### Example 4: Dynamic Batch Size

```python
# Create shards with varying sizes
config = ShardingConfig(num_shards=20, strategy=ShardingStrategy.STRATIFIED)
sharder = DatasetSharder(loader, config)
shards = sharder.create_shards()

# Auto-calculate batch size
batch_size = sharder.calculate_batch_size(
    target_batches_per_epoch=50,
    min_batch_size=16,
    max_batch_size=256
)

print(f"Batch size: {batch_size}")
print(f"Batches per epoch: {min(s.num_samples for s in shards) // batch_size}")
```

---

## Performance Characteristics

### Time Complexity

| Operation | Complexity | Notes |
|-----------|------------|-------|
| Random sharding | O(n) | Shuffle + split |
| Stratified sharding | O(n) | Scan dataset once |
| Non-IID sharding | O(n) | Scan + Dirichlet sampling |
| Sequential sharding | O(n) | Linear scan only |
| Batch size calculation | O(k) | k = num_shards |
| Distribution analysis | O(k × c) | k = shards, c = classes |

### Space Complexity

| Operation | Space | Notes |
|-----------|-------|-------|
| Shard metadata | O(k × c) | k = shards, c = classes |
| Sample indices | O(n) | n = total samples |

### Scalability

- ✅ **1M+ samples**: Memory-efficient (stores indices only)
- ✅ **1000+ workers**: Linear scaling with num_shards
- ✅ **10K+ classes**: Efficient class mapping

---

## Testing

### Test Coverage (`tests/test_dataset_sharder.py` - ~420 lines)

**Test Classes**:
1. **TestShardingConfig** (2 tests)
   - Default configuration
   - Custom configuration

2. **TestRandomSharding** (3 tests)
   - Shard creation
   - Size distribution
   - Reproducibility with seed

3. **TestStratifiedSharding** (3 tests)
   - Shard creation
   - Class distribution maintenance
   - Imbalanced dataset handling

4. **TestNonIIDSharding** (3 tests)
   - Shard creation
   - Skewed distribution verification
   - Alpha parameter effect

5. **TestSequentialSharding** (1 test)
   - Sequential chunk creation

6. **TestBatchSizeCalculation** (2 tests)
   - Auto-calculation
   - Min/max limits

7. **TestDistributionAnalysis** (2 tests)
   - Quality analysis
   - Strategy comparison

8. **TestErrorHandling** (3 tests)
   - Invalid num_shards
   - Too many shards
   - Non-existent shard access

**Total**: 19 tests with comprehensive coverage

**Run Tests**:
```bash
pytest tests/test_dataset_sharder.py -v
```

---

## Integration with TASK-5.1

Seamless integration with dataset loaders:

```python
from app.services.dataset_loader import create_loader
from app.services.dataset_sharder import DatasetSharder, ShardingConfig

# Load dataset (any format)
loader = create_loader("gs://bucket/dataset")
metadata = loader.load_metadata()

# Create shards
config = ShardingConfig(num_shards=50, strategy=ShardingStrategy.STRATIFIED)
sharder = DatasetSharder(loader, config)
shards = sharder.create_shards()

# Access specific samples from a shard
shard = sharder.get_shard(0)
for idx in shard.sample_indices[:10]:  # First 10 samples
    sample = loader.get_sample(idx)
    process(sample)
```

---

## Comparison of Strategies

| Strategy | IID | Balanced | Use Case | Quality Score* |
|----------|-----|----------|----------|----------------|
| **Random** | ✅ Yes | ⚠️ Maybe | Simple split, balanced datasets | 75-85 |
| **Stratified** | ✅ Yes | ✅ Yes | Production (default), imbalanced datasets | 85-95 |
| **Non-IID** | ❌ No | ❌ No | Federated learning, robustness testing | 40-60 |
| **Sequential** | ❌ No | ❌ No | Debugging, testing | 30-50 |

*Quality score depends on dataset characteristics

---

## Files Created

**New Files**:
1. `app/services/dataset_sharder.py` (~630 lines)
   - ShardingStrategy enum
   - DataDistribution enum
   - ShardMetadata dataclass
   - ShardingConfig dataclass
   - DatasetSharder class (4 sharding algorithms)
   - analyze_distribution_quality() function
   - Batch size calculation

2. `tests/test_dataset_sharder.py` (~420 lines)
   - Config tests (2)
   - Random sharding tests (3)
   - Stratified sharding tests (3)
   - Non-IID sharding tests (3)
   - Sequential sharding tests (1)
   - Batch size tests (2)
   - Analysis tests (2)
   - Error handling tests (3)

**Total**: 2 files, ~1,050 lines

---

## Next Steps (TASK-5.3)

- Implement storage management:
  - Local filesystem batch storage
  - S3/GCS integration for cloud storage
  - Batch metadata generation
  - Checksum calculation

---

## Benefits

✅ **Multiple Strategies**: Random, Stratified, Non-IID, Sequential  
✅ **IID & Non-IID**: Support for both data distributions  
✅ **Class Balance**: Stratified maintains distribution  
✅ **Federated Learning**: Realistic Non-IID with Dirichlet  
✅ **Quality Analysis**: Comprehensive metrics and scoring  
✅ **Auto Batch Size**: Smart calculation based on shard size  
✅ **Reproducible**: Seed-based deterministic sharding  
✅ **Well Tested**: 19 comprehensive tests  

---

**Task Status**: ✅ COMPLETE  
**Implementation Date**: March 2026  
**Lines of Code**: ~1,050 (implementation + tests)  
**Sharding Strategies**: 4 (Random, Stratified, Non-IID, Sequential)
