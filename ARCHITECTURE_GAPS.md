# Architecture Gap Analysis

**Date:** March 1, 2026  
**Status:** Pre-Implementation Review

This document identifies gaps in the MeshML architecture that should be addressed during implementation.

---

## Critical Gaps (High Priority)

### Gap 1: Model Validation Service ⚠️

**Problem:** No dedicated service to validate uploaded models before deployment  
**Risk:** Invalid models could crash workers, waste compute  
**Impact:** High  

**Solution:**
```
Add Model Validator microservice:
- Runs uploaded model in sandboxed Docker container
- Tests with sample data (1 batch)
- Checks memory requirements against worker capabilities
- Validates output shapes match config
- Estimates training time
- Rejects models that fail validation

Implementation:
- New service: services/model-validator/
- Python sandbox using multiprocessing + resource limits
- Timeout: 60 seconds per validation
- Store validation results in PostgreSQL
```

**Estimated Effort:** 3-5 days

---

### Gap 2: Worker Resource Limits ⚠️

**Problem:** No mechanism to limit worker resource usage  
**Risk:** Workers consume all device resources, poor user experience  
**Impact:** High  

**Solution:**
```python
# Add to worker config
WORKER_LIMITS = {
    "max_cpu_percent": 80,      # Leave 20% for system
    "max_ram_gb": 8,             # Configurable by user
    "max_gpu_percent": 90,       # Leave 10% buffer
    "max_disk_temp_gb": 10,      # Temporary batch storage
    "throttle_when_battery": True  # Reduce usage on battery
}

# Implementation using psutil
import psutil

def check_resource_usage():
    cpu = psutil.cpu_percent(interval=1)
    ram = psutil.virtual_memory().percent
    
    if cpu > WORKER_LIMITS["max_cpu_percent"]:
        reduce_batch_size()  # Adaptive batch sizing
    
    if ram > WORKER_LIMITS["max_ram_gb"]:
        pause_training()
```

**Estimated Effort:** 2-3 days

---

### Gap 3: Notification System ⚠️

**Problem:** No comprehensive notification service  
**Risk:** Users miss important events (job completion, failures)  
**Impact:** Medium-High  

**Solution:**
```
Add Notification Service:
- Email notifications (SendGrid)
- Push notifications (Firebase Cloud Messaging)
- In-app notifications (WebSocket)
- SMS for critical alerts (Twilio)
- User preference management

Events to notify:
- Job complete
- Job failed
- Worker offline
- Invited to group
- Low credits/quota
- Security alerts

Implementation:
- New service: services/notification-service/
- Template engine (Jinja2)
- Celery tasks for async delivery
- PostgreSQL table: notifications, notification_preferences
```

**Estimated Effort:** 5-7 days

---

## Important Gaps (Medium Priority)

### Gap 4: Cost Tracking & Billing 💰

**Problem:** No system to track compute costs per group/user  
**Risk:** Can't bill students or manage budgets  
**Impact:** Medium (critical for monetization)  

**Solution:**
```sql
CREATE TABLE compute_costs (
    id UUID PRIMARY KEY,
    group_id UUID REFERENCES groups(id),
    user_id UUID REFERENCES users(id),
    job_id UUID REFERENCES jobs(id),
    worker_id VARCHAR(255),
    compute_hours DECIMAL NOT NULL,
    cost_usd DECIMAL NOT NULL,
    date DATE NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_costs_user_date ON compute_costs(user_id, date);
CREATE INDEX idx_costs_group_date ON compute_costs(group_id, date);

-- Track in real-time
UPDATE compute_costs
SET compute_hours = compute_hours + {delta},
    cost_usd = cost_usd + {delta} * {rate_per_hour}
WHERE user_id = ? AND date = CURRENT_DATE;

-- Pricing tiers
FREE_TIER = 10 hours/month
STUDENT_TIER = $0.10/hour (unlimited)
PREMIUM_TIER = $0.05/hour (bulk discount)
```

**Features:**
- Dashboard showing usage per user/group
- Budget limits with alerts
- Monthly invoicing
- Export to CSV for accounting

**Estimated Effort:** 3-4 days

---

### Gap 5: Job Prioritization 📋

**Problem:** No queue system for jobs when workers are scarce  
**Risk:** First-come-first-served may not be fair  
**Impact:** Medium  

**Solution:**
```python
# Priority queue in Task Orchestrator
from queue import PriorityQueue

class JobQueue:
    def __init__(self):
        self.queue = PriorityQueue()
    
    def add_job(self, job_id, priority):
        # Priority score calculation:
        # - Group tier (paid > free): +50
        # - User contribution: +contribution_hours
        # - Job size (smaller first): -batch_count/10
        # - Wait time: +wait_minutes
        
        score = calculate_priority(job_id)
        self.queue.put((-score, job_id))  # Negative for max heap
    
    def get_next_job(self):
        return self.queue.get()[1]

# PostgreSQL schema
ALTER TABLE jobs ADD COLUMN priority_score INT DEFAULT 0;
ALTER TABLE jobs ADD COLUMN queue_position INT;

CREATE INDEX idx_jobs_priority ON jobs(priority_score DESC, created_at ASC)
WHERE status = 'pending';
```

**Estimated Effort:** 2-3 days

---

### Gap 6: Model Versioning 🔄

**Problem:** No tracking of model versions and lineage  
**Risk:** Can't compare experiments or reproduce results  
**Impact:** Medium  

**Solution:**
```sql
-- Add to jobs table
ALTER TABLE jobs ADD COLUMN parent_job_id UUID REFERENCES jobs(id);
ALTER TABLE jobs ADD COLUMN version INT DEFAULT 1;
ALTER TABLE jobs ADD COLUMN experiment_name VARCHAR(255);
ALTER TABLE jobs ADD COLUMN tags JSONB DEFAULT '[]';

-- Example usage
INSERT INTO jobs (id, parent_job_id, version, experiment_name, tags, ...)
VALUES (
    'job_v2',
    'job_v1',  -- Parent job
    2,         -- Version 2
    'mnist-cnn',
    '["baseline", "increased-lr"]'
);

-- Query all versions of an experiment
SELECT * FROM jobs
WHERE experiment_name = 'mnist-cnn'
ORDER BY version DESC;
```

**Features:**
- Compare metrics across versions
- Visual experiment tree
- Export experiment results
- Tag-based filtering

**Estimated Effort:** 2-3 days

---

## Nice-to-Have Gaps (Low Priority)

### Gap 7: Worker Reputation System ⭐

**Problem:** No tracking of worker reliability  
**Risk:** Can't identify and deprioritize flaky workers  
**Impact:** Low  

**Solution:**
```sql
CREATE TABLE worker_stats (
    worker_id VARCHAR(255) PRIMARY KEY,
    jobs_completed INT DEFAULT 0,
    jobs_failed INT DEFAULT 0,
    batches_completed INT DEFAULT 0,
    batches_failed INT DEFAULT 0,
    avg_speed_samples_per_sec DECIMAL,
    total_compute_hours DECIMAL DEFAULT 0,
    reliability_score DECIMAL DEFAULT 1.0,  -- 0.0 to 1.0
    last_failure_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Calculate reliability score
reliability_score = (
    0.6 * (jobs_completed / (jobs_completed + jobs_failed)) +
    0.3 * (batches_completed / (batches_completed + batches_failed)) +
    0.1 * min(1.0, avg_speed / target_speed)
)

-- Use in task assignment
SELECT * FROM workers
WHERE status = 'idle'
  AND reliability_score > 0.7
ORDER BY reliability_score DESC, avg_speed DESC
LIMIT 10;
```

**Estimated Effort:** 2 days

---

### Gap 8: Data Privacy / Federated Learning Option 🔒

**Problem:** No true federated learning where data never leaves device  
**Risk:** Some users may want data to stay on device (privacy)  
**Impact:** Low (niche use case)  

**Solution:**
```
Add "federated" mode:
- No dataset upload to server
- Workers use local data only
- Only gradients shared (differential privacy optional)
- Model distributed to all workers
- Each worker trains on full local dataset

Changes needed:
1. Job creation: Skip dataset upload if mode=federated
2. Workers: Load data from local path instead of GCS
3. Parameter Server: Same (gradients only)

Privacy enhancements:
- Differential privacy (add noise to gradients)
- Secure aggregation (encrypted gradients)
- Homomorphic encryption (future)
```

**Estimated Effort:** 5-7 days (if needed)

---

## Summary Table

| Gap # | Name | Priority | Impact | Effort | Status |
|-------|------|----------|--------|--------|--------|
| 1 | Model Validation Service | Critical | High | 3-5 days | 🔴 Not Started |
| 2 | Worker Resource Limits | Critical | High | 2-3 days | 🔴 Not Started |
| 3 | Notification System | Critical | Med-High | 5-7 days | 🔴 Not Started |
| 4 | Cost Tracking & Billing | Important | Medium | 3-4 days | 🔴 Not Started |
| 5 | Job Prioritization | Important | Medium | 2-3 days | 🔴 Not Started |
| 6 | Model Versioning | Important | Medium | 2-3 days | 🔴 Not Started |
| 7 | Worker Reputation | Nice-to-Have | Low | 2 days | 🔴 Not Started |
| 8 | Federated Learning | Nice-to-Have | Low | 5-7 days | 🔴 Not Started |

**Total Estimated Effort:**
- **Critical gaps:** 10-15 days
- **Important gaps:** 7-10 days
- **Nice-to-have gaps:** 7-9 days
- **Grand Total:** 24-34 days (4-7 weeks)

---

## Recommended Implementation Order

### Phase 1 (Weeks 1-2) - Core Infrastructure
1. ✅ Database schema (groups, workers, jobs, batches)
2. ✅ API Gateway basics
3. **Gap 2:** Worker resource limits (integrate early)

### Phase 2 (Weeks 3-4) - Core Services
4. Dataset Sharder
5. Task Orchestrator
6. Parameter Server
7. **Gap 1:** Model validation (before job execution)

### Phase 3 (Weeks 5-6) - Monitoring & UX
8. Metrics Service
9. Dashboard
10. **Gap 3:** Notification system (critical for UX)

### Phase 4 (Weeks 7-8) - Optimization
11. **Gap 4:** Cost tracking (for production)
12. **Gap 5:** Job prioritization (fairness)
13. **Gap 6:** Model versioning (experimentation)

### Phase 5 (Future) - Enhancements
14. **Gap 7:** Worker reputation (nice to have)
15. **Gap 8:** Federated learning (if needed)

---

## Decision: Proceed or Address?

**Recommendation:** Proceed with Phase 1 implementation. Address critical gaps (1-3) during their respective phases:
- **Gap 2** in Phase 1 (worker implementation)
- **Gap 1** in Phase 2 (before job execution)
- **Gap 3** in Phase 3 (with dashboard)

The architecture is **solid enough to start implementation**. These gaps are enhancements, not blockers.

---

**Status:** ✅ Ready for Phase 1 Implementation

