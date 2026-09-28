# AI Systems Project — Handoff

_Last updated: 2026-09-28_

## 1. Current source of truth

The flagship personal project is now a **distributed control plane for LLM inference**.

The project is **not** about reimplementing an inference engine from scratch. Mature serving systems such as vLLM already exist and should be used where appropriate.

The goal is to build and understand the infrastructure *around* model serving:

- request routing
- queues and backpressure
- distributed scheduling
- worker registration and health
- retries and failure recovery
- idempotency
- autoscaling
- observability
- CI/CD
- performance regression testing
- Kubernetes deployment
- benchmarking under realistic workloads

The main purpose is to strengthen weak points in Satria's profile:
- infrastructure
- distributed systems
- production reliability
- CI/CD
- observability
- systems-oriented backend engineering

This should complement, not duplicate, prior AI application work.

---

## 2. Core project framing

A good one-sentence description:

> **A distributed control plane for LLM inference that experiments with workload-aware scheduling, failure recovery, autoscaling, observability, and performance-gated CI/CD on Kubernetes.**

A useful central systems question:

> **How should an LLM inference cluster schedule, recover, and scale under bursty, heterogeneous workloads while maintaining latency and reliability targets?**

The inference engine itself is treated as a workload substrate.

Use:
- vLLM or another mature serving runtime for model inference
- Kubernetes for orchestration
- Redis for fast distributed state / queueing
- Prometheus + Grafana + OpenTelemetry for observability

Build the interesting coordination layer yourself:
- gateway
- scheduler
- worker registry
- health / heartbeat logic
- retry semantics
- autoscaling policy
- benchmark harness
- CI/CD pipeline
- performance gates

---

## 3. Why this project matters

Satria already has strong evidence of:
- AI application engineering
- agents / workflows / RAG
- production integrations
- backend/data infrastructure

The missing signal is deeper infrastructure and systems work.

The project should make it possible to credibly discuss:

- distributed scheduling
- partial failures
- queue semantics
- backpressure
- leases
- retries
- idempotency
- horizontal scaling
- health checks
- latency percentiles
- observability
- CI/CD
- performance regression testing
- Kubernetes
- model-serving infrastructure

The ideal resume narrative is:

> I can build AI applications, but I also understand the distributed systems and infrastructure required to operate them reliably.

---

## 4. Target architecture

```text
                              CLIENTS
                                 |
                                 v
                      +----------------------+
                      |     API GATEWAY      |
                      |         Go           |
                      | validation / limits  |
                      +----------+-----------+
                                 |
                                 v
                      +----------------------+
                      |        Redis         |
                      | queue / worker state |
                      | leases / backlog     |
                      +----------+-----------+
                                 |
                                 v
                      +----------------------+
                      |      SCHEDULER       |
                      |         Go           |
                      |                      |
                      | round robin          |
                      | least loaded         |
                      | token-aware          |
                      | batch-aware          |
                      +----+-----------+-----+
                           |           |
                +----------+           +----------+
                v                                 v
        +----------------+                +----------------+
        | vLLM Worker 1  |      ...       | vLLM Worker N  |
        | model server   |                | model server   |
        +----------------+                +----------------+

                        Kubernetes Cluster
                               |
             +-----------------+-----------------+
             |                                   |
             v                                   v
      Prometheus / Grafana                OpenTelemetry
      metrics / dashboards                distributed traces

GitHub
   |
   v
CI/CD
   |- unit tests
   |- integration tests
   |- failure tests
   |- load tests
   |- performance regression tests
   |- Docker image builds
   `- Kubernetes deployment
```

---

## 5. Main components Satria owns

### 5.1 API gateway
Responsibilities:
- receive client requests
- validate payloads
- assign request IDs
- enforce rate limits
- propagate deadlines / cancellation
- enqueue work
- return results / errors

Recommended language:
- Go

Learning:
- HTTP servers
- middleware
- request contexts
- concurrency
- cancellation
- timeout propagation
- rate limiting

---

### 5.2 Worker registry
Responsibilities:
- track available inference workers
- record last heartbeat
- record current load
- record loaded model
- track active / queued work
- mark workers unhealthy

Possible state:
```text
worker_id
status
last_heartbeat
active_requests
queued_tokens
model
capacity
```

Learning:
- service discovery
- ephemeral distributed state
- heartbeat design
- stale-state handling
- health semantics

---

### 5.3 Scheduler
This is one of the central parts of the project.

Implement multiple scheduling strategies:

1. **Round Robin**
2. **Least Loaded**
3. **Shortest Queue**
4. **Token-Aware Scheduling**
5. **Batch-Aware Scheduling** later

Important insight:

One request is not necessarily equal to another.

Example:
```text
Request A: 100 input/output tokens
Request B: 8,000 tokens
Request C: 300 tokens
```

Round-robin may assign one request per worker but still create severe imbalance.

Possible token-aware workload estimate:

```text
estimated_work =
prompt_tokens
+
expected_output_tokens
```

or later:

```text
estimated_work =
queued_tokens
+
active_tokens
+
new_request_tokens
```

Learning:
- scheduling
- fairness
- load balancing
- queueing
- workload estimation
- latency / throughput tradeoffs

---

### 5.4 Redis
Use Redis for fast ephemeral state.

Possible responsibilities:
- request queue
- worker heartbeat state
- worker load
- leases
- retry state
- backlog statistics

Prefer Redis Streams or another mechanism with useful acknowledgement semantics where practical.

Learning:
- distributed queues
- acknowledgement
- consumer groups
- leases
- retries
- ephemeral state
- contention
- backpressure

---

### 5.5 Inference workers
Do **not** spend large amounts of time reimplementing model inference.

Use:
- vLLM first choice
- Hugging Face / PyTorch if needed for simpler local development

Workers should expose:
- inference endpoint
- health endpoint
- metrics
- heartbeat information

The worker layer is the workload being coordinated.

Learning:
- model-serving APIs
- tokens/sec
- time-to-first-token
- batch behavior
- GPU / CPU utilization
- inference capacity

---

## 6. Core experiments

The project should be benchmark-driven rather than merely feature-driven.

### Experiment 1 — Scheduling policy comparison

Compare:

```text
Round Robin
vs
Least Loaded
vs
Token-Aware
vs
Batch-Aware
```

Under the same workload.

Measure:
- throughput
- p50 latency
- p95 latency
- p99 latency
- queue wait time
- worker utilization
- queued tokens
- fairness / load skew

Use heterogeneous requests:
- short prompts
- long prompts
- short outputs
- long outputs
- bursty arrival patterns

The goal is to determine:
> Which scheduler performs best under which traffic pattern?

Do not assume one policy wins everywhere.

---

### Experiment 2 — Autoscaling policy comparison

Compare signals such as:

1. CPU utilization
2. GPU utilization
3. Redis queue depth
4. queued token backlog
5. p95 queue wait

Possible question:

> Does token-backlog-based autoscaling react better to LLM traffic than simple CPU-based autoscaling?

Measure:
- time to scale
- p95 latency during spikes
- queue growth
- time to recover
- overprovisioning
- worker count over time

---

### Experiment 3 — Failure recovery

Scenario:

```text
request assigned
      |
      v
worker begins inference
      |
      v
worker crashes
```

System should:
- detect missed heartbeats
- mark worker unhealthy
- stop routing new work there
- recover / retry unfinished work where appropriate
- avoid unacceptable duplicate execution
- surface failure if retry budget is exhausted

Measure:
- failure detection time
- recovery time
- lost requests
- duplicate requests
- retry count

---

### Experiment 4 — Burst traffic / backpressure

Generate traffic like:

```text
10 req/s
20 req/s
50 req/s
100 req/s
200 req/s
```

Observe:
- queue growth
- latency growth
- throughput saturation
- worker utilization
- autoscaling behavior

This teaches:
- backpressure
- saturation
- capacity planning
- queueing effects

---

### Experiment 5 — Performance-aware CI

A pull request changes the scheduler.

CI runs:
- correctness tests
- integration tests
- load tests
- baseline comparison

Example gate:

```text
FAIL if:
p95 regression > 20%
or
error rate > threshold
or
throughput regression > threshold
```

This is a major differentiator.

---

## 7. Failure semantics to understand

Important concepts to learn and be able to explain:

### At-most-once
A request is processed zero or one times.

Risk:
- lost work

### At-least-once
A request may be processed more than once.

Risk:
- duplicates

Requires:
- idempotency

### Exactly-once
Usually not truly free or simple in distributed systems.

Important lesson:
- understand why "exactly once" is often implemented through idempotent effects + durable coordination rather than magic guarantees.

### Leases
A worker owns a request for a limited time.

If the worker stops renewing:
- request becomes retryable

### Heartbeats
Workers periodically prove they are alive.

### Retry budget
Do not retry forever.

### Exponential backoff
Avoid hammering unhealthy dependencies.

### Cancellation
If the client disconnects:
- decide whether the inference should continue

These are more important than memorizing infrastructure commands.

---

## 8. Observability

Observability is a first-class part of the project.

Use:
- Prometheus
- Grafana
- OpenTelemetry

Important metrics:

```text
requests_total
requests_failed_total
request_latency_seconds
queue_wait_seconds
queue_depth
queued_tokens
active_workers
worker_utilization
worker_heartbeat_age
retry_count
tokens_generated_total
time_to_first_token
throughput_requests_per_second
throughput_tokens_per_second
```

Example trace:

```text
request abc123

gateway          6 ms
queue wait     123 ms
scheduler        2 ms
worker wait     17 ms
inference      612 ms
--------------------
total          760 ms
```

Key learning goal:

> Be able to diagnose where latency comes from.

---

## 9. Kubernetes

Kubernetes should be used after the local Docker system works.

Learn:
- Pods
- Deployments
- Services
- ReplicaSets
- ConfigMaps
- Secrets
- liveness probes
- readiness probes
- rolling updates
- resource requests
- resource limits
- Horizontal Pod Autoscaler
- custom metrics later

Kubernetes should solve real problems:

```text
worker dies
   ->
Kubernetes replaces pod

load rises
   ->
worker replicas increase

new deployment
   ->
rolling update

worker not ready
   ->
readiness probe prevents routing
```

Do not learn Kubernetes only as YAML syntax.

---

## 10. CI/CD

CI/CD is now a headline project goal.

Start with GitHub Actions.

Possible pipeline:

```text
git push / PR
      |
      v
Go lint + tests
      |
      v
Python tests
      |
      v
Docker build
      |
      v
integration environment
      |
      v
distributed-system tests
      |
      v
failure injection
      |
      v
load test
      |
      v
performance comparison
      |
      +--> FAIL if regression
      |
      v
deploy
      |
      v
smoke tests
```

### Important CI tests

#### Normal integration
- start Redis
- start scheduler
- start workers
- send N requests
- verify all complete

#### Failure injection
- begin traffic
- kill one worker
- verify detection
- verify rerouting / retry
- verify expected request behavior

#### Performance regression
- run standard workload
- compare against baseline
- reject severe regressions

#### Deployment smoke test
After deploy:
- health endpoints
- small inference request
- metrics endpoint
- worker registration

---

## 11. Jenkins

Jenkins is optional.

Use it only after understanding CI/CD with GitHub Actions.

Goal:
- gain familiarity with a common enterprise CI tool
- not make Jenkins the center of the project

Possible later work:
- reproduce part of the GitHub Actions pipeline in a Jenkinsfile
- use stages / agents / artifacts / credentials
- deploy into a test Kubernetes namespace

Learning priority:
> CI/CD concepts > Jenkins-specific syntax

---

## 12. Recommended tech stack

| Layer | Technology |
|---|---|
| Gateway | Go |
| Scheduler | Go |
| Worker registry | Go + Redis |
| Queue / ephemeral state | Redis |
| Model serving | vLLM |
| Fallback local inference | PyTorch / Hugging Face |
| Durable benchmark data | PostgreSQL |
| Containers | Docker |
| Local orchestration | Docker Compose |
| Production orchestration | Kubernetes |
| Metrics | Prometheus |
| Dashboards | Grafana |
| Tracing | OpenTelemetry |
| Load testing | k6 |
| CI | GitHub Actions |
| Optional CI exposure | Jenkins |
| Cloud | GCP or AWS |
| Optional IaC | Terraform |
| Optional internal RPC later | gRPC |

---

## 13. Repository structure

```text
infergrid/

├── gateway/
│   ├── cmd/
│   ├── internal/
│   │   ├── api/
│   │   ├── middleware/
│   │   └── queue/
│   ├── Dockerfile
│   └── go.mod
│
├── scheduler/
│   ├── cmd/
│   ├── internal/
│   │   ├── scheduling/
│   │   ├── registry/
│   │   ├── health/
│   │   ├── leases/
│   │   └── retries/
│   ├── Dockerfile
│   └── go.mod
│
├── workers/
│   ├── vllm/
│   ├── local-dev/
│   └── health/
│
├── autoscaler/
│   ├── policies/
│   └── metrics/
│
├── database/
│   ├── migrations/
│   └── schema.sql
│
├── benchmarks/
│   ├── workloads/
│   ├── scheduling/
│   ├── autoscaling/
│   ├── failures/
│   └── results/
│
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── failure/
│   └── performance/
│
├── monitoring/
│   ├── prometheus/
│   ├── grafana/
│   └── otel/
│
├── deploy/
│   ├── docker-compose.yml
│   └── kubernetes/
│
├── .github/
│   └── workflows/
│
├── Jenkinsfile
└── README.md
```

---

## 14. Recommended build order

### Phase 1 — Minimal serving substrate
Goal:
```text
client -> gateway -> vLLM worker
```

Build:
- simple Go gateway
- one vLLM or local model worker
- Docker Compose
- health endpoints

Learn:
- Go service
- container networking
- model-server API

---

### Phase 2 — Redis + multiple workers
Goal:
```text
client
  -> gateway
  -> Redis
  -> scheduler
  -> worker 1 / worker 2 / worker 3
```

Build:
- Redis
- worker registry
- 2–3 workers
- round-robin scheduler
- basic request state

Learn:
- queues
- distributed state
- routing

---

### Phase 3 — Heartbeats + health
Build:
- worker heartbeats
- stale worker detection
- health status
- scheduler excludes unhealthy workers

Learn:
- failure detection
- partial failure
- distributed state freshness

---

### Phase 4 — Retry / leases / idempotency
Build:
- request lease
- retry after worker failure
- retry budget
- idempotency keys
- timeout behavior

Learn:
- distributed execution semantics
- duplicate handling
- retries

---

### Phase 5 — Scheduling experiments
Implement:
- round robin
- least loaded
- shortest queue
- token-aware scheduling

Build benchmark workload.

Measure:
- p50 / p95 / p99
- throughput
- queue wait
- worker load skew

This is a major project milestone.

---

### Phase 6 — Observability
Add:
- Prometheus
- Grafana
- OpenTelemetry

Build dashboards and traces.

Learn:
- production debugging
- latency decomposition
- system health

---

### Phase 7 — Load testing
Use k6.

Workloads:
- constant
- ramp
- spike
- heterogeneous token lengths

Find:
- saturation point
- queue growth
- throughput ceiling

---

### Phase 8 — Kubernetes
Move working system from Docker Compose to Kubernetes.

Learn:
- Deployments
- Services
- probes
- replicas
- rolling updates
- resources

---

### Phase 9 — Autoscaling experiments
Implement / compare:
- CPU-based scaling
- queue-depth scaling
- token-backlog scaling

Measure:
- spike latency
- scaling delay
- overprovisioning
- recovery

---

### Phase 10 — CI/CD
Build:
- unit CI
- integration CI
- Docker image build
- Kubernetes test deployment
- smoke test

Then add:
- failure tests
- performance regression tests

This is another major project milestone.

---

### Phase 11 — Performance-gated deployment
Create baseline benchmark.

PR pipeline produces something like:

```text
scheduler change

throughput:
24 -> 29 req/s

p95:
900 -> 880 ms

errors:
0.2% -> 0.2%

RESULT: PASS
```

or:

```text
p95:
900 -> 1800 ms

RESULT: FAIL
performance regression
```

---

### Phase 12 — Optional extensions
Only after the core system is strong.

Possible:
- Jenkins
- Terraform
- gRPC
- multiple models
- model-aware routing
- GPU-specific scheduling
- KV-cache-aware routing
- multi-node GPU workers
- canary deployments
- chaos testing

---

## 15. Minimum resume-worthy version

A strong minimum version is:

```text
Go gateway
+
Redis
+
worker registry
+
scheduler
+
3 workers
+
heartbeats
+
retries
+
token-aware scheduling
+
Prometheus
+
k6 benchmarks
+
CI integration tests
```

This already demonstrates:
- backend infrastructure
- distributed systems
- reliability
- observability
- CI

Do not wait for Kubernetes to consider the project useful.

---

## 16. Strong flagship version

Add:

- Kubernetes
- autoscaling
- Grafana dashboards
- OpenTelemetry traces
- performance-aware CI
- cloud deployment
- vLLM GPU benchmarks
- optional Jenkins
- optional Terraform

The strongest version should be benchmark-heavy, not feature-heavy.

---

## 17. What not to build

Avoid:
- chat UI
- RAG
- agents
- tool calling
- user accounts
- elaborate frontend
- custom transformer inference engine
- custom CUDA kernels
- multiple model providers early
- multi-region deployment
- Kubernetes before local architecture works
- Jenkins before CI concepts are understood
- Terraform before deployment architecture stabilizes

These distract from the project's purpose.

---

## 18. README goals

README should emphasize:

1. problem statement
2. architecture
3. why existing tools are used
4. what control-plane logic is custom
5. benchmark methodology
6. scheduling results
7. failure recovery
8. autoscaling results
9. CI/CD design
10. limitations

Strong introduction:

> InferGrid is a distributed control plane for LLM inference designed to explore workload-aware scheduling, failure recovery, autoscaling, and performance-aware deployment under bursty heterogeneous traffic.

Important:
- use real benchmark numbers only
- no invented performance claims
- explain tradeoffs, not just successes

---

## 19. Interview questions this project should prepare Satria to answer

### Why Redis?
Explain:
- fast shared state
- worker registry
- queueing / acknowledgement semantics
- ephemeral state

### Why Kubernetes?
Explain:
- replica management
- health checks
- service discovery
- deployment
- autoscaling

### Why not just use vLLM directly?
Answer:
> vLLM handles inference. The project focuses on the distributed control plane around multiple serving workers: scheduling, health, recovery, scaling, observability, and deployment.

### What happens if a worker dies?
Explain:
- heartbeat timeout
- unhealthy status
- lease expiry
- retry
- idempotency

### Why token-aware scheduling?
Explain:
- LLM requests have heterogeneous workloads
- request count is a poor proxy for work
- token backlog may better approximate load

### How do you know your scheduler is better?
Explain:
- controlled workloads
- identical request sets
- multiple policies
- p50/p95/p99
- throughput
- queue wait
- utilization

### How do you stop a bad deployment?
Explain:
- CI tests
- integration tests
- failure injection
- performance gate
- smoke tests / rollback path

---

## 20. Resume direction

Possible eventual bullet:

> Built a distributed LLM inference control plane in Go with Redis-backed scheduling, worker health/recovery, Kubernetes orchestration, and Prometheus observability; benchmarked workload-aware routing under bursty heterogeneous traffic.

Possible second bullet:

> Designed performance-gated CI/CD with integration, failure-injection, and load tests that automatically rejected scheduler changes causing latency or throughput regressions.

Replace with real measured outcomes when available.

---

## 21. Time management

During the semester:

Target:
- **4–5 focused hours/week**

Suggested:
- one ~3-hour weekend block
- one ~2-hour continuation block

Research remains the higher-priority technical commitment.

The project should be reduced first during:
- prelim weeks
- heavy pset weeks
- research deadlines
- recruiting / OA spikes

The goal is consistency, not sprinting every week.

---

## 22. Scope rule

When deciding whether to add something, ask:

> Does this teach infrastructure, distributed systems, reliability, observability, CI/CD, or ML systems?

If no:
- probably do not add it.

If yes, ask:

> Is it more valuable than improving the benchmark, failure model, scheduler, or CI pipeline?

If no:
- defer it.

---

## 23. Immediate next action

Start with the smallest real system:

```text
client
  ->
Go gateway
  ->
one vLLM / local inference worker
```

Then add Docker Compose.

Definition of done:

- Go gateway runs
- inference worker runs
- both are containerized
- one request goes through the gateway
- the gateway forwards it to the model server
- response returns successfully
- health endpoint exists
- basic latency is logged

Only after this works:

```text
add Redis
add scheduler
add multiple workers
```

Do **not** start with Kubernetes.

---

## 24. New source-of-truth summary

The project is now:

> **Infrastructure/control-plane engineering for distributed LLM serving.**

Priority order:

1. distributed systems
2. infrastructure
3. CI/CD
4. observability
5. performance engineering
6. ML-serving context

Inference-engine internals are secondary.

The main goal is to add strong systems/infrastructure signal to Satria's profile while staying relevant to both:
- backend / infrastructure SWE roles
- AI infrastructure / ML systems roles
