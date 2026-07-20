# ExamBrain — Feature Breakdown

## Phase 1: Foundation (features 1–7 can be built in parallel)

| # | Feature | Description |
|---|---------|-------------|
| 1 | [X] **Project Scaffold** | Python project structure, `pyproject.toml`, dependency management, linting/formatting config, CI pipeline (GitHub Actions) |
| 2 | **LiteLLM Bridge** | Async client wrapper for AWS Bedrock via LiteLLM — model selection, retry logic, token tracking |
| 3 | **PostgreSQL + pgvector Schema** | Alembic migrations for users, courses, past papers, exam blueprints, sessions, results |
| 4 | **Redis Session Store** | Async Redis client for session caching, rate-limiting, real-time state |
| 5 | **S3 File Adapter** | Async boto3 client wrapping upload/download/list for raw PDFs/slides/notes |
| 6 | **IAM Credential Manager** | Encrypted local cred store, AWS secret rotation handling, least-privilege key validation |
| 7 | [X] **Async Config & Logging** | Centralized settings (`pydantic-settings`), structured logging (`structlog`), health-check endpoints |

## Phase 2: Agents (sequential — each depends on prior extraction)

| # | Feature | Description |
|---|---------|-------------|
| 8 | **Multi-Format Parsing Agent** | OCR (pytesseract/docling) + pdfplumber for scanned docs → clean text with hierarchy |
| 9 | **Instructor Alignment Agent** | Fuzzy string matching (rapidfuzz) across professor name variants → unified DB identity |
| 10 | **Blueprint Extraction Agent** | Parse historical papers → JSON blueprint: sections, question types, marks, topic weight matrix |
| 11 | **Exam Blueprint Generator** | Combine blueprint JSON + lecture note chunks → prompt Bedrock → original mock exam |
| 12 | **TA Evaluation Agent** | Parse student answers against rubric → point-by-point feedback + weak-topic index update |

## Phase 3: Microservices

| # | Feature | Description |
|---|---------|-------------|
| 13 | **Course Core Service** | FastAPI CRUD for courses, dashboard telemetry, user profiles, performance history |
| 14 | **Ingestion Pipeline Service** | File upload → S3 streaming → chunking → semantic tokenization → DB storage |
| 15 | **Exam Simulation Service** | Real-time session mgmt, countdown timer, auto-save buffer, focus-violation lockout |

## Phase 4: Containerization

| # | Feature | Description |
|---|---------|-------------|
| 16 | [X] **Dockerfiles** | Three lean Dockerfiles for each microservice (python:3.12-slim) |
| 17 | [X] **docker-compose.yml** | Orchestrates all 3 services + PostgreSQL/pgvector + Redis for local dev |

## Phase 5: Frontend

| # | Feature | Description |
|---|---------|-------------|
| 18 | **UI Scaffold** | Fast enough frontend (React/Vite, or HTMX+Jinja) with routing, auth pages |
| 19 | **Dashboard Views** | Course list, upload panel, blueprint viewer, exam launcher, result history |
| 20 | **Exam Player** | Full-screen timed exam UI with auto-save, answer navigation, submit flow |
| 21 | **Focus Tracking** | Page Visibility API + `blur` events → heartbeat → session lockout on violation |

## Phase 6: Production Deployment

| # | Feature | Description |
|---|---------|-------------|
| 22 | **OCI VM Provisioning** | Terraform or manual script for Ampere A1 setup, security groups, SSH hardening |
| 23 | **K3s Cluster Install** | Ansible or shell script for single-node K3s, kubectl, helm |
| 24 | **K8s Manifests** | Deployments, Services, ConfigMaps, Secrets for all 3 services + DB + Redis |
| 25 | **Nginx Edge Proxy** | Ingress controller or standalone Nginx with TLS, rate limiting, reverse proxy |

## Phase 7: Migration Path (future)

| # | Feature | Description |
|---|---------|-------------|
| 26 | **MinIO Self-Hosted S3** | S3-compatible object storage in-cluster, zero-code migration from AWS |
| 27 | **Local LLM Fallback** | LiteLLM config pointing to Ollama/OpenRouter instead of Bedrock |
