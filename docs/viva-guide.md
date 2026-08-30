# ImageVault AI viva guide

Use these as speaking notes, not a script to memorize word-for-word.

## What is cloud computing?

Cloud computing is on-demand access to shared, configurable computing resources—such as compute, storage, databases, networking, and platforms—that can be provisioned and managed through software. A cloud does not have to be a paid public provider.

## Why does ImageVault AI qualify as a Cloud Computing project?

It deploys an application workload on a private platform made of networked services, object storage, a database, an asynchronous worker, a gateway, orchestration, persistent volumes, configuration, health checks, scaling, automation, and monitoring. AI similarity is the workload; the way it is operated is the cloud/DevOps contribution.

## What is a private cloud?

A private cloud provides cloud-style infrastructure for one organization or controlled environment. This project uses local Docker/Minikube resources controlled by the student instead of renting a public-cloud account.

## What is containerization, and why Docker?

Containerization packages an application with its runtime and dependencies while sharing the host kernel. Docker makes the FastAPI, React/Nginx, worker, PostgreSQL, Redis, MinIO, Prometheus, and Grafana environments repeatable. “Works on my machine” differences are reduced because the image definition travels with the code.

## Docker image versus container?

An image is an immutable package/template built from a Dockerfile. A container is a running instance of that image with runtime configuration, networking, and volumes.

## Why Docker Compose?

Compose starts the complete multi-service development platform with one declarative file. It defines dependencies, networks, ports, health checks, environment values, and persistent volumes, making it the easiest live-demo mode.

## What is Kubernetes?

Kubernetes is a container orchestrator. It schedules containers in Pods, maintains desired replica counts, exposes Services, mounts configuration/secrets/volumes, performs health checks, and supports rolling updates and scaling.

## What is Minikube?

Minikube runs a small Kubernetes cluster on a local computer. It demonstrates Kubernetes concepts without EKS, AKS, GKE, a credit card, or a remote cluster.

## What is orchestration?

Orchestration coordinates deployment, networking, recovery, scaling, configuration, and lifecycle of multiple services. Instead of starting each program manually, Kubernetes works toward the declared desired state.

## Deployment, StatefulSet, Service, and Pod?

- A **Pod** is Kubernetes’ smallest deployable unit and contains one or more containers.
- A **Deployment** manages replaceable/stateless Pods such as backend, frontend, worker, Redis, and Nginx.
- A **StatefulSet** gives stable identity/order to stateful services such as PostgreSQL and MinIO.
- A **Service** provides stable network discovery and load distribution in front of changing Pods.

## ConfigMap versus Secret?

A ConfigMap stores non-sensitive settings such as endpoints, thresholds, and Nginx configuration. A Secret stores credentials such as database passwords, MinIO keys, JWT secret, and Grafana password. A Kubernetes Secret improves separation and handling but is not automatically encrypted in every cluster configuration.

## What is a PersistentVolumeClaim?

A PVC requests durable storage from Kubernetes. PostgreSQL, MinIO, model cache, Prometheus, and Grafana use PVCs so their data survives Pod replacement.

## Liveness versus readiness?

Liveness answers “should Kubernetes restart this process?” Readiness answers “should Kubernetes send traffic to this instance?” ImageVault liveness checks that FastAPI is alive; readiness also checks required database and object-storage dependencies.

## What are requests and limits?

Requests help Kubernetes schedule a Pod by reserving expected CPU/memory. Limits cap usage. ImageVault gives the AI worker the largest memory allowance and keeps it at one replica by default for a 16 GB laptop.

## What is horizontal scaling?

Horizontal scaling adds more replicas instead of giving one instance more resources. The stateless FastAPI deployment can scale from one to three replicas. A HorizontalPodAutoscaler can automate this using CPU metrics, but it is optional for the base project.

## What is Infrastructure as Code?

IaC represents infrastructure in versioned declarative files. It improves repeatability, review, change history, and recovery compared with manual clicking or undocumented commands.

## Why Terraform?

Terraform creates a plan from desired configuration and manages resource state. Here it targets only local Kubernetes resources and secrets. No AWS/Azure/GCP provider is configured, so the required path cannot accidentally provision paid public-cloud resources.

## What is CI/CD, and why GitHub Actions?

Continuous Integration automatically validates each change through dependency installation, security audit, lint, tests, build, and infrastructure checks. Continuous Delivery keeps deployable artifacts ready. GitHub Actions provides an understandable pipeline; this project validates local deployment rather than pretending to deploy to a paid production cloud.

## What is object storage?

Object storage stores each binary as an object identified by a key, with metadata, inside a bucket. It differs from database rows and traditional hierarchical filesystems. It suits large immutable images and can scale independently.

## Why MinIO and what is S3 compatibility?

MinIO is free/open-source object storage exposing an API compatible with common Amazon S3 operations. ImageVault gets bucket/object semantics locally. S3 compatibility means the storage abstraction and concepts can map to other implementations; it does not mean AWS is used.

## Why not store images in PostgreSQL?

Large binaries would grow backups, database I/O, and row storage unnecessarily. MinIO is optimized for objects, while PostgreSQL is used for transactions, ownership, queries, hashes, relationships, states, and embeddings.

## What are PostgreSQL and pgvector?

PostgreSQL is a relational database with transactions, constraints, indexes, and SQL. pgvector is an extension that adds fixed-dimensional vectors and distance operators/indexes. It lets the same database store image metadata and query the closest embeddings.

## What is a vector embedding?

An embedding is a list of numbers learned by a model to represent important content. Images that the model considers visually/semantically related tend to have vectors close to each other. ImageVault normalizes 512-number OpenCLIP embeddings.

## What is cosine similarity?

Cosine similarity measures the angle between vectors: for normalized vectors it is their dot product. A higher value indicates closer direction/content in the embedding space. It is evidence, not proof that two photos are duplicates.

## What is CLIP / OpenCLIP?

CLIP learns a shared representation from images and text. OpenCLIP is an open implementation/model ecosystem. ImageVault uses its image encoder locally to produce vectors. The model is downloaded and cached at runtime, runs on CPU, and optionally uses CUDA.

## SHA-256 versus perceptual hashing?

SHA-256 is cryptographic: any byte change produces a very different digest, so equal digests provide extremely strong evidence of identical bytes. A perceptual hash deliberately stays similar when appearance changes modestly and is compared by Hamming distance. It can make false matches and is not a cryptographic integrity check.

## Why use both pHash and OpenCLIP?

pHash is cheap and useful for resized/recompressed versions. OpenCLIP captures broader visual/semantic relationships and tolerates edits, but costs more CPU/memory. Keeping their results separate makes the evidence explainable.

## Why process images asynchronously?

Model inference can take seconds or longer on CPU. Upload should not keep an HTTP request open for all processing. The API stores the object and PENDING record, then Redis/Celery lets a worker process it independently with retries and visible states.

## Why Redis/Celery instead of Kafka?

The laptop workload needs a small queue, background tasks, and retry support. Redis/Celery is easier to explain and operate. Kafka would add resources and complexity without solving a requirement here.

## Why Nginx?

Nginx gives one browser entry point, routes SPA and API traffic, adds security headers, request-size/rate controls, request IDs, and load distribution across backend replicas.

## Why Prometheus and Grafana?

Prometheus periodically scrapes numeric time-series metrics. Grafana queries Prometheus and visualizes them. Together they show request rate, latency, errors, uploads, processing, duplicate outcomes, inference time, failures, and optional container resources.

## Metrics versus logs?

Metrics are aggregated numeric time series used for trends and alerts. Logs are discrete event records with context such as request ID, image ID, duration, and error. Neither should contain passwords, tokens, object keys with sensitive context, or raw image data.

## How is user isolation enforced?

The JWT identifies one active user. Every resource query includes `user_id`; knowing another image UUID is insufficient. Object keys also include the user UUID, and signed links are produced only after the ownership query.

## Why are signed URLs used?

The bucket remains private. After authorization, MinIO produces a time-limited URL allowing the browser to fetch that object without routing all image bytes through FastAPI. Expiration limits the value of a leaked link.

## Is the system perfectly secure or perfectly accurate?

No. The default local HTTP deployment lacks TLS, accounts lack email recovery/MFA, host compromise remains possible, and similarity can be wrong. The design states these limitations, keeps results advisory, and requires explicit deletion.

## How could it migrate to AWS, Azure, or Google Cloud?

MinIO maps conceptually to S3/Blob/Cloud Storage; PostgreSQL to RDS/Azure Database/Cloud SQL; Minikube to EKS/AKS/GKE; Nginx to a load balancer/API gateway; Prometheus/Grafana to managed monitoring. Migration would still require IAM, networking, TLS, backups, resilience, and cost design.

## Why choose a local open-source private cloud?

It satisfies the ₹0 additional software/cloud constraint, avoids card verification and usage surprises, keeps images local, works offline after dependencies/model are cached, and lets students demonstrate the same architectural concepts on controlled hardware.

## How is the project “completely free”?

The required software, AI inference, database, object storage, orchestration, IaC, CI setup, and monitoring require no additional paid license or cloud service. The statement does not treat the existing laptop, electricity, or internet as literally free.
