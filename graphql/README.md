# GraphQL Schema for Real-time Metrics

This directory contains the GraphQL schema definition for the MeshML Metrics Service, enabling real-time updates and flexible queries for the dashboard.

## 📁 Structure

```
graphql/
├── schema.graphql        # Complete GraphQL schema definition
└── README.md            # This file
```

## 📖 Overview

### Why GraphQL?

GraphQL provides:
- **Real-time updates** via WebSocket subscriptions
- **Flexible queries** - clients request only the data they need
- **Single endpoint** - no need for many REST routes
- **Type safety** - strongly typed schema
- **Introspection** - self-documenting API

### Architecture

```
┌─────────────┐
│  Dashboard  │
│  (React)    │
└──────┬──────┘
       │
       │ GraphQL over WebSocket
       │ (Subscriptions for real-time)
       │
       ↓
┌──────────────────┐
│ Metrics Service  │
│  (Strawberry)    │
└────────┬─────────┘
         │
    ┌────┴────┬──────────┐
    ↓         ↓          ↓
┌────────┐ ┌──────┐ ┌────────┐
│ Redis  │ │PostgreSQL│ Cloud │
│Pub/Sub │ │  (TSDB)  │Storage│
└────────┘ └──────┘ └────────┘
```

## 🚀 Quick Start

### Using GraphQL Playground

```bash
# Start the Metrics Service (when implemented)
python -m meshml.services.metrics

# Open GraphQL Playground
open http://localhost:4000/graphql
```

### Example Queries

#### Get Job Details

```graphql
query GetJob($jobId: ID!) {
  job(id: $jobId) {
    id
    name
    status
    progress
    currentEpoch
    totalEpochs
    currentLoss
    currentAccuracy
    assignedWorkers {
      id
      type
      status
      capabilities {
        hasGpu
        gpuModel
      }
    }
  }
}
```

**Variables:**
```json
{
  "jobId": "job_abc123"
}
```

#### List Active Jobs

```graphql
query ListActiveJobs {
  jobs(status: RUNNING, limit: 10) {
    edges {
      node {
        id
        name
        progress
        currentEpoch
        totalEpochs
        workerCount
        currentLoss
        currentAccuracy
      }
    }
    pageInfo {
      hasNextPage
      endCursor
    }
    totalCount
  }
}
```

#### Get Job Metrics (Time Series)

```graphql
query GetJobMetrics($jobId: ID!, $start: DateTime, $end: DateTime) {
  jobMetrics(
    jobId: $jobId
    startTime: $start
    endTime: $end
    interval: MINUTE
  ) {
    timestamp
    epoch
    loss
    accuracy
    samplesProcessed
    throughput
  }
}
```

**Variables:**
```json
{
  "jobId": "job_abc123",
  "start": "2026-03-04T10:00:00Z",
  "end": "2026-03-04T11:00:00Z"
}
```

#### Get Aggregated Statistics

```graphql
query GetAggregatedStats($jobId: ID!) {
  aggregatedMetrics(jobId: $jobId, metricType: ACCURACY) {
    min
    max
    mean
    median
    stdDev
    p95
    p99
    sampleCount
  }
}
```

#### List Workers

```graphql
query ListWorkers($groupId: ID!) {
  workers(groupId: $groupId, status: IDLE) {
    edges {
      node {
        id
        type
        status
        capabilities {
          cpuCores
          totalMemory
          hasGpu
          gpuModel
          estimatedThroughput
        }
        batchesCompleted
        averageBatchTime
        lastHeartbeat
      }
    }
  }
}
```

---

## 🔔 Subscriptions (Real-time)

### Subscribe to Job Updates

```graphql
subscription JobUpdates($jobId: ID!) {
  jobMetricsUpdated(jobId: $jobId) {
    jobId
    epoch
    batchesCompleted
    latestLoss
    latestAccuracy
    avgLoss
    avgAccuracy
    progress
    estimatedTimeRemaining
    activeWorkers
    avgWorkerThroughput
    timestamp
  }
}
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
```

### Subscribe to Worker Status Changes

```graphql
subscription WorkerStatusChanges {
  workerStatusChanged {
    workerId
    oldStatus
    newStatus
    jobId
    reason
    timestamp
  }
}
```

### Subscribe to Batch Completions

```graphql
subscription BatchCompletions($jobId: ID!) {
  batchCompleted(jobId: $jobId) {
    jobId
    batchId
    workerId
    epoch
    loss
    accuracy
    samplesProcessed
    processingTime
    completedBatches
    totalBatches
    progress
    timestamp
  }
}
```

### Subscribe to System Metrics

```graphql
subscription SystemMetricsStream {
  systemMetricsUpdated {
    timestamp
    totalJobs
    activeJobs
    totalWorkers
    activeWorkers
    totalThroughput
    avgBatchTime
    totalCpuUsage
    totalMemoryUsage
    totalGpuUsage
  }
}
```

---

## 🔧 Mutations

### Create Training Job

```graphql
mutation CreateJob($input: CreateJobInput!) {
  createJob(input: $input) {
    id
    name
    status
    config {
      learningRate
      batchSize
      optimizer
      totalEpochs
    }
  }
}
```

**Variables:**
```json
{
  "input": {
    "name": "MNIST CNN Training",
    "description": "Train ResNet-18 on MNIST dataset",
    "groupId": "group_xyz789",
    "modelId": "model_abc123",
    "datasetUrl": "gs://meshml-datasets/mnist",
    "totalEpochs": 100,
    "learningRate": 0.001,
    "batchSize": 32,
    "optimizer": "adam",
    "lossFunction": "cross_entropy",
    "config": {
      "mixedPrecision": true,
      "earlyStopping": true,
      "earlyStoppingPatience": 10,
      "checkpointInterval": 5,
      "saveTopK": 3
    }
  }
}
```

### Control Job

```graphql
mutation StopJob($jobId: ID!) {
  stopJob(jobId: $jobId) {
    id
    status
  }
}

mutation PauseJob($jobId: ID!) {
  pauseJob(jobId: $jobId) {
    id
    status
  }
}

mutation ResumeJob($jobId: ID!) {
  resumeJob(jobId: $jobId) {
    id
    status
  }
}
```

### Register Worker

```graphql
mutation RegisterWorker($input: RegisterWorkerInput!) {
  registerWorker(input: $input) {
    id
    type
    status
    capabilities {
      cpuCores
      totalMemory
      hasGpu
      gpuModel
    }
  }
}
```

**Variables:**
```json
{
  "input": {
    "type": "PYTHON",
    "version": "1.0.0",
    "capabilities": {
      "cpuCores": 8,
      "cpuModel": "Apple M1",
      "totalMemory": 17179869184,
      "hasGpu": true,
      "gpuCount": 1,
      "gpuModel": "Apple M1 GPU",
      "gpuMemory": 8589934592,
      "supportsPyTorch": true,
      "supportsFp16": true,
      "supportsFp32": true,
      "computeType": "Metal",
      "estimatedThroughput": 500.0
    }
  }
}
```

### Create Group

```graphql
mutation CreateGroup($input: CreateGroupInput!) {
  createGroup(input: $input) {
    id
    name
    description
    owner {
      id
      username
    }
    settings {
      maxMembers
      requireApproval
    }
  }
}
```

**Variables:**
```json
{
  "input": {
    "name": "AI Research Lab",
    "description": "Deep learning research group",
    "settings": {
      "maxMembers": 50,
      "requireApproval": true,
      "computeSharingEnabled": true,
      "maxConcurrentJobs": 10
    }
  }
}
```

### Invite Member

```graphql
mutation InviteMember($groupId: ID!, $email: String!, $role: GroupRole) {
  inviteMember(groupId: $groupId, email: $email, role: $role) {
    id
    token
    inviteeEmail
    role
    expiresAt
  }
}
```

---

## 📊 Dashboard Integration (React + Apollo)

### Setup Apollo Client

```typescript
// apollo-client.ts
import { ApolloClient, InMemoryCache, split, HttpLink } from '@apollo/client';
import { GraphQLWsLink } from '@apollo/client/link/subscriptions';
import { getMainDefinition } from '@apollo/client/utilities';
import { createClient } from 'graphql-ws';

const httpLink = new HttpLink({
  uri: 'http://localhost:4000/graphql',
  headers: {
    authorization: `Bearer ${localStorage.getItem('token')}`,
  },
});

const wsLink = new GraphQLWsLink(
  createClient({
    url: 'ws://localhost:4000/graphql',
    connectionParams: {
      authorization: `Bearer ${localStorage.getItem('token')}`,
    },
  })
);

// Split based on operation type
const splitLink = split(
  ({ query }) => {
    const definition = getMainDefinition(query);
    return (
      definition.kind === 'OperationDefinition' &&
      definition.operation === 'subscription'
    );
  },
  wsLink,
  httpLink
);

export const apolloClient = new ApolloClient({
  link: splitLink,
  cache: new InMemoryCache(),
});
```

### React Component with Subscription

```typescript
// JobMonitor.tsx
import { useQuery, useSubscription } from '@apollo/client';
import { gql } from '@apollo/client';

const GET_JOB = gql`
  query GetJob($jobId: ID!) {
    job(id: $jobId) {
      id
      name
      status
      progress
      currentEpoch
      totalEpochs
    }
  }
`;

const JOB_METRICS_SUBSCRIPTION = gql`
  subscription JobMetricsUpdated($jobId: ID!) {
    jobMetricsUpdated(jobId: $jobId) {
      jobId
      latestLoss
      latestAccuracy
      progress
      estimatedTimeRemaining
      activeWorkers
      timestamp
    }
  }
`;

export function JobMonitor({ jobId }: { jobId: string }) {
  // Initial query
  const { data: jobData } = useQuery(GET_JOB, {
    variables: { jobId },
  });

  // Real-time subscription
  const { data: metricsData } = useSubscription(JOB_METRICS_SUBSCRIPTION, {
    variables: { jobId },
  });

  return (
    <div>
      <h1>{jobData?.job.name}</h1>
      <p>Status: {jobData?.job.status}</p>
      <p>Progress: {metricsData?.jobMetricsUpdated.progress.toFixed(1)}%</p>
      <p>Loss: {metricsData?.jobMetricsUpdated.latestLoss.toFixed(4)}</p>
      <p>Accuracy: {metricsData?.jobMetricsUpdated.latestAccuracy.toFixed(2)}%</p>
      <p>Active Workers: {metricsData?.jobMetricsUpdated.activeWorkers}</p>
      <p>ETA: {formatTime(metricsData?.jobMetricsUpdated.estimatedTimeRemaining)}</p>
    </div>
  );
}
```

### Real-time Chart Component

```typescript
// MetricsChart.tsx
import { useSubscription } from '@apollo/client';
import { LineChart, Line, XAxis, YAxis } from 'recharts';
import { useState, useEffect } from 'react';

const BATCH_COMPLETED_SUBSCRIPTION = gql`
  subscription BatchCompleted($jobId: ID!) {
    batchCompleted(jobId: $jobId) {
      timestamp
      loss
      accuracy
      batchId
    }
  }
`;

export function MetricsChart({ jobId }: { jobId: string }) {
  const [dataPoints, setDataPoints] = useState([]);

  const { data } = useSubscription(BATCH_COMPLETED_SUBSCRIPTION, {
    variables: { jobId },
  });

  useEffect(() => {
    if (data?.batchCompleted) {
      setDataPoints((prev) => [
        ...prev,
        {
          time: new Date(data.batchCompleted.timestamp).toLocaleTimeString(),
          loss: data.batchCompleted.loss,
          accuracy: data.batchCompleted.accuracy,
        },
      ]);
    }
  }, [data]);

  return (
    <LineChart width={600} height={300} data={dataPoints}>
      <XAxis dataKey="time" />
      <YAxis />
      <Line type="monotone" dataKey="loss" stroke="#ff7300" />
      <Line type="monotone" dataKey="accuracy" stroke="#387908" />
    </LineChart>
  );
}
```

---

## 🔒 Authentication

All GraphQL operations require JWT authentication (except introspection queries).

### HTTP Header

```http
Authorization: Bearer <jwt_token>
```

### WebSocket Connection Params

```typescript
connectionParams: {
  authorization: `Bearer ${token}`,
}
```

---

## 📚 Schema Documentation

### Core Concepts

#### **Query** - Fetch data (one-time)
- `job(id)` - Get single job
- `jobs(...)` - List jobs with filters
- `worker(id)` - Get single worker
- `workers(...)` - List workers with filters
- `jobMetrics(...)` - Get time-series metrics
- `aggregatedMetrics(...)` - Get statistical summaries

#### **Mutation** - Modify data
- `createJob(...)` - Start new training job
- `stopJob(...)` / `pauseJob(...)` / `resumeJob(...)` - Control job
- `registerWorker(...)` - Register new worker
- `createGroup(...)` - Create collaboration group
- `inviteMember(...)` - Invite user to group

#### **Subscription** - Real-time updates
- `jobMetricsUpdated(...)` - Live training metrics
- `jobStatusChanged(...)` - Job state changes
- `workerStatusChanged(...)` - Worker state changes
- `batchCompleted(...)` - Batch completion events
- `systemMetricsUpdated` - System-wide metrics

### Key Types

| Type | Description |
|------|-------------|
| `Job` | Training job with configuration, status, metrics |
| `Worker` | Student device with capabilities and status |
| `Group` | Collaboration unit with members and jobs |
| `MetricPoint` | Time-series training metric (loss, accuracy) |
| `SystemMetricPoint` | Time-series system metric (CPU, GPU, memory) |
| `AggregatedMetrics` | Statistical summary (min, max, mean, percentiles) |

### Enums

| Enum | Values |
|------|--------|
| `JobStatus` | PENDING, SHARDING, READY, RUNNING, PAUSED, COMPLETED, FAILED, CANCELLED |
| `WorkerStatus` | IDLE, BUSY, OFFLINE, FAILED, DRAINING |
| `WorkerType` | PYTHON, CPP, JAVASCRIPT, MOBILE |
| `GroupRole` | OWNER, ADMIN, MEMBER |
| `MetricType` | LOSS, ACCURACY, LEARNING_RATE, BATCH_TIME, THROUGHPUT, etc. |

---

## 🧪 Testing

### Using `curl` with GraphQL

```bash
# Query
curl -X POST http://localhost:4000/graphql \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "query": "query { systemHealth { status uptime } }"
  }'

# Mutation
curl -X POST http://localhost:4000/graphql \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "query": "mutation($id: ID!) { stopJob(jobId: $id) { id status } }",
    "variables": { "id": "job_123" }
  }'
```

### Using GraphQL Playground

1. Open `http://localhost:4000/graphql`
2. Set HTTP headers:
   ```json
   {
     "Authorization": "Bearer <your_token>"
   }
   ```
3. Write query/mutation/subscription
4. Click play button

### WebSocket Testing (wscat)

```bash
# Install wscat
npm install -g wscat

# Connect
wscat -c ws://localhost:4000/graphql \
  -H "Authorization: Bearer <token>"

# Send subscription
{
  "type": "start",
  "payload": {
    "query": "subscription { systemMetricsUpdated { totalJobs activeWorkers } }"
  }
}
```

---

## 🎯 Use Cases

### 1. Training Dashboard
- **Query**: Initial job list
- **Subscription**: Real-time progress updates
- **Mutation**: Start/stop/pause jobs

### 2. Worker Monitoring
- **Query**: List all workers with capabilities
- **Subscription**: Worker status changes (online/offline)

### 3. Performance Analytics
- **Query**: Historical metrics with time range
- **Query**: Aggregated statistics (min, max, p95, p99)

### 4. System Admin Panel
- **Query**: System health and service status
- **Subscription**: System-wide metrics (CPU, memory, throughput)

### 5. Group Collaboration
- **Query**: Group members and their contributions
- **Mutation**: Invite members, update roles
- **Subscription**: Group activity updates

---

## 🚀 Next Steps

- **TASK-2.3 Complete** ✅
- **Phase 3**: Implement Metrics Service with Strawberry GraphQL
- **Phase 4**: Build React dashboard with Apollo Client
- **Phase 5**: Deploy to GKE with WebSocket support

---

## 📖 References

- [GraphQL Official Docs](https://graphql.org/)
- [Strawberry GraphQL](https://strawberry.rocks/)
- [Apollo Client](https://www.apollographql.com/docs/react/)
- [GraphQL Subscriptions](https://www.apollographql.com/docs/react/data/subscriptions/)
- [WebSocket Protocol](https://developer.mozilla.org/en-US/docs/Web/API/WebSockets_API)
