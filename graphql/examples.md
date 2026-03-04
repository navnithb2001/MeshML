# GraphQL Example Queries and Subscriptions

This file contains ready-to-use GraphQL operations for testing and development.

## 📋 Queries

### Get Job Details with Workers

```graphql
query GetJobDetails($jobId: ID!) {
  job(id: $jobId) {
    id
    name
    description
    status
    progress
    currentEpoch
    totalEpochs
    currentLoss
    currentAccuracy
    bestAccuracy
    bestLoss
    
    config {
      learningRate
      batchSize
      optimizer
      totalEpochs
      mixedPrecision
      earlyStopping
    }
    
    assignedWorkers {
      id
      type
      status
      capabilities {
        cpuCores
        totalMemory
        hasGpu
        gpuModel
        computeType
      }
      batchesCompleted
      averageBatchTime
    }
    
    group {
      name
      memberCount
    }
    
    createdBy {
      username
      fullName
    }
    
    createdAt
    startedAt
    estimatedCompletion
  }
}

# Variables:
# { "jobId": "job_abc123" }
```

### List Active Jobs with Pagination

```graphql
query ListActiveJobs($groupId: ID, $limit: Int = 20, $offset: Int = 0) {
  jobs(groupId: $groupId, status: RUNNING, limit: $limit, offset: $offset) {
    edges {
      node {
        id
        name
        status
        progress
        currentEpoch
        totalEpochs
        currentLoss
        currentAccuracy
        workerCount
        createdAt
        estimatedCompletion
      }
      cursor
    }
    pageInfo {
      hasNextPage
      hasPreviousPage
      endCursor
    }
    totalCount
  }
}

# Variables:
# { "groupId": "group_xyz789", "limit": 10, "offset": 0 }
```

### Get Time-Series Metrics

```graphql
query GetJobMetricsTimeSeries(
  $jobId: ID!
  $startTime: DateTime
  $endTime: DateTime
  $interval: TimeInterval = MINUTE
) {
  jobMetrics(
    jobId: $jobId
    startTime: $startTime
    endTime: $endTime
    interval: $interval
  ) {
    timestamp
    epoch
    loss
    accuracy
    learningRate
    samplesProcessed
    throughput
    gradientNorm
    workerId
  }
}

# Variables:
# {
#   "jobId": "job_abc123",
#   "startTime": "2026-03-04T10:00:00Z",
#   "endTime": "2026-03-04T11:00:00Z",
#   "interval": "MINUTE"
# }
```

### Get Aggregated Statistics

```graphql
query GetAggregatedMetrics($jobId: ID!, $metricType: MetricType!) {
  aggregatedMetrics(jobId: $jobId, metricType: $metricType) {
    metricType
    min
    max
    mean
    median
    stdDev
    p25
    p50
    p75
    p95
    p99
    sampleCount
    startTime
    endTime
  }
}

# Variables:
# { "jobId": "job_abc123", "metricType": "ACCURACY" }
```

### List Workers with Capabilities

```graphql
query ListWorkers(
  $groupId: ID
  $status: WorkerStatus
  $type: WorkerType
  $limit: Int = 50
) {
  workers(groupId: $groupId, status: $status, type: $type, limit: $limit) {
    edges {
      node {
        id
        type
        status
        
        capabilities {
          cpuCores
          cpuModel
          totalMemory
          hasGpu
          gpuCount
          gpuModel
          gpuMemory
          supportsPyTorch
          supportsFp16
          supportsFp32
          computeType
          estimatedThroughput
        }
        
        batchesCompleted
        totalComputeTime
        averageBatchTime
        
        cpuUsage
        memoryUsage
        gpuUsage
        
        lastHeartbeat
        registeredAt
        
        user {
          username
          fullName
        }
      }
    }
    totalCount
  }
}

# Variables:
# { "groupId": "group_xyz789", "status": "IDLE", "type": "PYTHON" }
```

### Get Group Details with Members and Jobs

```graphql
query GetGroupDetails($groupId: ID!) {
  group(id: $groupId) {
    id
    name
    description
    
    owner {
      username
      fullName
      email
    }
    
    members {
      id
      role
      status
      computeContributed
      jobsCreated
      joinedAt
      user {
        username
        fullName
        avatarUrl
      }
    }
    
    memberCount
    
    jobs {
      id
      name
      status
      progress
      createdAt
    }
    
    activeJobsCount
    totalJobsCount
    
    activeWorkers {
      id
      type
      status
      capabilities {
        hasGpu
        gpuModel
      }
    }
    
    activeWorkerCount
    totalComputeHours
    totalJobsCompleted
    
    settings {
      maxMembers
      requireApproval
      computeSharingEnabled
      maxConcurrentJobs
      notifyOnJobComplete
    }
    
    createdAt
  }
}

# Variables:
# { "groupId": "group_xyz789" }
```

### Get My Groups

```graphql
query GetMyGroups($limit: Int = 20) {
  myGroups(limit: $limit) {
    edges {
      node {
        id
        name
        description
        memberCount
        activeJobsCount
        activeWorkerCount
        totalComputeHours
        createdAt
      }
    }
    totalCount
  }
}
```

### Get System Health

```graphql
query GetSystemHealth {
  systemHealth {
    status
    version
    uptime
    
    services {
      name
      status
      latency
      errorRate
      lastCheck
    }
    
    databaseConnections
    databaseLatency
    cacheHitRate
    cacheMemoryUsage
    queueDepth
    queueLatency
    
    timestamp
  }
}
```

### Get System Overview

```graphql
query GetSystemOverview {
  activeJobs
  activeWorkers
  
  systemHealth {
    status
    uptime
  }
  
  jobs(status: RUNNING, limit: 5) {
    edges {
      node {
        id
        name
        progress
        workerCount
      }
    }
  }
}
```

---

## ✏️ Mutations

### Create Training Job

```graphql
mutation CreateTrainingJob($input: CreateJobInput!) {
  createJob(input: $input) {
    id
    name
    status
    
    config {
      learningRate
      batchSize
      optimizer
      totalEpochs
      mixedPrecision
      earlyStopping
    }
    
    createdAt
  }
}

# Variables:
# {
#   "input": {
#     "name": "MNIST CNN Training",
#     "description": "Train ResNet-18 on MNIST dataset",
#     "groupId": "group_xyz789",
#     "modelId": "model_abc123",
#     "datasetUrl": "gs://meshml-datasets/mnist",
#     "totalEpochs": 100,
#     "learningRate": 0.001,
#     "batchSize": 32,
#     "optimizer": "adam",
#     "lossFunction": "cross_entropy",
#     "config": {
#       "mixedPrecision": true,
#       "earlyStopping": true,
#       "earlyStoppingPatience": 10,
#       "gradientClipping": 1.0,
#       "checkpointInterval": 5,
#       "saveTopK": 3,
#       "staleness": 5,
#       "aggregationMethod": "mean"
#     }
#   }
# }
```

### Stop Job

```graphql
mutation StopTrainingJob($jobId: ID!) {
  stopJob(jobId: $jobId) {
    id
    status
    completedAt
  }
}

# Variables:
# { "jobId": "job_abc123" }
```

### Pause and Resume Job

```graphql
mutation PauseTrainingJob($jobId: ID!) {
  pauseJob(jobId: $jobId) {
    id
    status
  }
}

mutation ResumeTrainingJob($jobId: ID!) {
  resumeJob(jobId: $jobId) {
    id
    status
    startedAt
  }
}

# Variables:
# { "jobId": "job_abc123" }
```

### Register Worker

```graphql
mutation RegisterNewWorker($input: RegisterWorkerInput!) {
  registerWorker(input: $input) {
    id
    type
    status
    
    capabilities {
      cpuCores
      cpuModel
      totalMemory
      hasGpu
      gpuModel
      computeType
    }
    
    registeredAt
  }
}

# Variables (Python Worker on M1 Mac):
# {
#   "input": {
#     "type": "PYTHON",
#     "version": "1.0.0",
#     "capabilities": {
#       "cpuCores": 8,
#       "cpuModel": "Apple M1",
#       "totalMemory": 17179869184,
#       "hasGpu": true,
#       "gpuCount": 1,
#       "gpuModel": "Apple M1 GPU",
#       "gpuMemory": 8589934592,
#       "supportsPyTorch": true,
#       "supportsFp16": true,
#       "supportsFp32": true,
#       "computeType": "Metal",
#       "estimatedThroughput": 500.0
#     }
#   }
# }

# Variables (C++ Worker on NVIDIA GPU):
# {
#   "input": {
#     "type": "CPP",
#     "version": "1.0.0",
#     "capabilities": {
#       "cpuCores": 16,
#       "cpuModel": "AMD Ryzen 9 5950X",
#       "totalMemory": 34359738368,
#       "hasGpu": true,
#       "gpuCount": 2,
#       "gpuModel": "NVIDIA RTX 3090",
#       "gpuMemory": 25769803776,
#       "supportsPyTorch": true,
#       "supportsFp16": true,
#       "supportsFp32": true,
#       "supportsBf16": true,
#       "computeType": "CUDA",
#       "estimatedThroughput": 2000.0
#     }
#   }
# }
```

### Unregister Worker

```graphql
mutation UnregisterWorker($workerId: ID!) {
  unregisterWorker(workerId: $workerId)
}

# Variables:
# { "workerId": "worker_def456" }
```

### Create Group

```graphql
mutation CreateNewGroup($input: CreateGroupInput!) {
  createGroup(input: $input) {
    id
    name
    description
    
    owner {
      username
      fullName
    }
    
    settings {
      maxMembers
      requireApproval
      computeSharingEnabled
      maxConcurrentJobs
    }
    
    createdAt
  }
}

# Variables:
# {
#   "input": {
#     "name": "AI Research Lab",
#     "description": "Deep learning research group for CS401",
#     "settings": {
#       "maxMembers": 50,
#       "requireApproval": true,
#       "computeSharingEnabled": true,
#       "maxConcurrentJobs": 10,
#       "notifyOnJobComplete": true,
#       "notifyOnJobFailed": true
#     }
#   }
# }
```

### Invite Member to Group

```graphql
mutation InviteMemberToGroup(
  $groupId: ID!
  $email: String!
  $role: GroupRole = MEMBER
) {
  inviteMember(groupId: $groupId, email: $email, role: $role) {
    id
    token
    inviteeEmail
    role
    status
    createdAt
    expiresAt
    
    group {
      name
    }
    
    inviter {
      username
      fullName
    }
  }
}

# Variables:
# {
#   "groupId": "group_xyz789",
#   "email": "newstudent@university.edu",
#   "role": "MEMBER"
# }
```

### Update Member Role

```graphql
mutation UpdateMemberRole($groupId: ID!, $userId: ID!, $role: GroupRole!) {
  updateMemberRole(groupId: $groupId, userId: $userId, role: $role) {
    id
    role
    user {
      username
      fullName
    }
  }
}

# Variables:
# {
#   "groupId": "group_xyz789",
#   "userId": "user_ghi789",
#   "role": "ADMIN"
# }
```

### Remove Member from Group

```graphql
mutation RemoveMemberFromGroup($groupId: ID!, $userId: ID!) {
  removeMember(groupId: $groupId, userId: $userId)
}

# Variables:
# { "groupId": "group_xyz789", "userId": "user_ghi789" }
```

---

## 🔔 Subscriptions (Real-time)

### Subscribe to Job Metrics Updates

```graphql
subscription JobMetricsLive($jobId: ID!) {
  jobMetricsUpdated(jobId: $jobId) {
    jobId
    epoch
    batchesCompleted
    
    # Latest Values
    latestLoss
    latestAccuracy
    
    # Moving Averages
    avgLoss
    avgAccuracy
    
    # Progress
    progress
    estimatedTimeRemaining
    
    # Workers
    activeWorkers
    avgWorkerThroughput
    
    timestamp
  }
}

# Variables:
# { "jobId": "job_abc123" }
```

### Subscribe to Job Status Changes

```graphql
subscription JobStatusChanges($jobId: ID!) {
  jobStatusChanged(jobId: $jobId) {
    jobId
    oldStatus
    newStatus
    reason
    timestamp
  }
}

# Variables:
# { "jobId": "job_abc123" }
```

### Subscribe to Worker Status Changes

```graphql
subscription WorkerStatusChanges($workerId: ID) {
  workerStatusChanged(workerId: $workerId) {
    workerId
    oldStatus
    newStatus
    jobId
    reason
    timestamp
  }
}

# Variables (all workers):
# {}

# Variables (specific worker):
# { "workerId": "worker_def456" }
```

### Subscribe to Batch Completions

```graphql
subscription BatchCompletionEvents($jobId: ID!) {
  batchCompleted(jobId: $jobId) {
    jobId
    batchId
    workerId
    epoch
    
    # Metrics
    loss
    accuracy
    samplesProcessed
    processingTime
    
    # Progress
    completedBatches
    totalBatches
    progress
    
    timestamp
  }
}

# Variables:
# { "jobId": "job_abc123" }
```

### Subscribe to Group Jobs Updates

```graphql
subscription GroupJobsUpdates($groupId: ID!) {
  groupJobsUpdated(groupId: $groupId) {
    id
    name
    status
    progress
    currentEpoch
    totalEpochs
    workerCount
  }
}

# Variables:
# { "groupId": "group_xyz789" }
```

### Subscribe to Workers in Group

```graphql
subscription WorkersInGroup($groupId: ID!) {
  workersInGroup(groupId: $groupId) {
    id
    type
    status
    currentJobId
    capabilities {
      hasGpu
      gpuModel
      estimatedThroughput
    }
    lastHeartbeat
  }
}

# Variables:
# { "groupId": "group_xyz789" }
```

### Subscribe to System Metrics

```graphql
subscription SystemMetricsStream {
  systemMetricsUpdated {
    timestamp
    
    # Jobs
    totalJobs
    activeJobs
    queuedJobs
    completedJobs
    failedJobs
    
    # Workers
    totalWorkers
    activeWorkers
    idleWorkers
    offlineWorkers
    
    # Performance
    totalThroughput
    avgBatchTime
    
    # Resources
    totalCpuUsage
    totalMemoryUsage
    totalGpuUsage
    
    # Network
    totalBandwidthUsed
  }
}
```

---

## 🧪 Combined Operations

### Dashboard Overview Query

```graphql
query DashboardOverview($groupId: ID!) {
  # Group Info
  group(id: $groupId) {
    name
    memberCount
    activeWorkerCount
    totalComputeHours
  }
  
  # Active Jobs
  jobs(groupId: $groupId, status: RUNNING, limit: 5) {
    edges {
      node {
        id
        name
        progress
        currentEpoch
        totalEpochs
        currentLoss
        currentAccuracy
        workerCount
      }
    }
  }
  
  # Available Workers
  workers(groupId: $groupId, status: IDLE, limit: 10) {
    edges {
      node {
        id
        type
        capabilities {
          hasGpu
          gpuModel
          estimatedThroughput
        }
      }
    }
  }
  
  # System Status
  systemHealth {
    status
    uptime
  }
}

# Variables:
# { "groupId": "group_xyz789" }
```

### Complete Job Lifecycle

```graphql
# 1. Create Job
mutation CreateJob($input: CreateJobInput!) {
  createJob(input: $input) {
    id
    name
    status
  }
}

# 2. Subscribe to Updates
subscription WatchJob($jobId: ID!) {
  jobMetricsUpdated(jobId: $jobId) {
    progress
    latestLoss
    latestAccuracy
    activeWorkers
  }
}

# 3. Monitor Status
subscription WatchStatus($jobId: ID!) {
  jobStatusChanged(jobId: $jobId) {
    newStatus
    reason
    timestamp
  }
}

# 4. Stop Job (if needed)
mutation StopJob($jobId: ID!) {
  stopJob(jobId: $jobId) {
    id
    status
    finalAccuracy
  }
}
```

---

## 🎯 Dashboard Use Cases

### Training Monitor Page

```graphql
# Initial Load
query TrainingMonitorInit($jobId: ID!) {
  job(id: $jobId) {
    id
    name
    status
    config { totalEpochs }
    assignedWorkers { id type status }
  }
  
  jobMetrics(jobId: $jobId, interval: MINUTE) {
    timestamp
    loss
    accuracy
  }
}

# Real-time Updates
subscription TrainingMonitorLive($jobId: ID!) {
  jobMetricsUpdated(jobId: $jobId) {
    progress
    latestLoss
    latestAccuracy
    estimatedTimeRemaining
  }
  
  batchCompleted(jobId: $jobId) {
    loss
    accuracy
    timestamp
  }
}
```

### Worker Management Page

```graphql
# Initial Load
query WorkerManagementInit($groupId: ID!) {
  workers(groupId: $groupId, limit: 100) {
    edges {
      node {
        id
        type
        status
        capabilities { hasGpu gpuModel }
        batchesCompleted
        lastHeartbeat
      }
    }
  }
}

# Real-time Updates
subscription WorkerManagementLive {
  workerStatusChanged {
    workerId
    newStatus
    timestamp
  }
}
```

---

## 📝 Notes

- All timestamps are in ISO 8601 format: `2026-03-04T10:30:00Z`
- Memory/storage values are in bytes
- Percentages are 0-100 (not 0-1)
- Throughput is in samples/second
- Duration/time is in seconds unless specified

---

## 🚀 Quick Copy-Paste for Testing

### Most Common Operations

```graphql
# Get job status
query { job(id: "job_abc123") { status progress currentLoss currentAccuracy } }

# List running jobs
query { jobs(status: RUNNING) { edges { node { name progress } } } }

# Subscribe to job updates
subscription { jobMetricsUpdated(jobId: "job_abc123") { progress latestLoss latestAccuracy } }

# Stop job
mutation { stopJob(jobId: "job_abc123") { status } }

# System health
query { systemHealth { status uptime services { name status } } }
```
