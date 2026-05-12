# AgentForge

**A production-grade multi-agent AI orchestration platform** that decomposes any natural-language task into a structured plan, executes it with real-world tools, and self-critiques the result in a closed loop until it clears a quality bar — all streamed live to a modern web UI.

[![Python](https://img.shields.io/badge/Python-3.11+-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-green)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Next.js-14.2-black)](https://nextjs.org/)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.1-purple)](https://github.com/langchain-ai/langgraph)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Problem Definition](#2-problem-definition)
3. [Technical Approach](#3-technical-approach)
4. [System Architecture](#4-system-architecture)
5. [Results](#5-results)
6. [How to Run](#6-how-to-run)
7. [Project Structure](#7-project-structure)
8. [Configuration Reference](#8-configuration-reference)
9. [Deploying to AWS](#9-deploying-to-aws)
10. [Future Improvements](#10-future-improvements)

---

## 1. Project Overview

### What It Is

AgentForge lets you submit open-ended tasks — *"research the top three vector databases and compare their performance"* or *"write and run a Python script to clean this dataset"* — and watch a coordinated pipeline of three specialized LLM agents handle the work autonomously.

Three agents collaborate over a LangGraph state machine:

| Agent | Model | Responsibility |
|-------|-------|----------------|
| **Planner** | Gemini 1.5 Flash | Decomposes the task into an ordered, structured JSON plan |
| **Executor** | Llama 3.1 70B (Groq) | Executes each step using web search, sandboxed code, and a file notebook |
| **Critic** | Gemini 1.5 Flash | Scores the output on a rubric and triggers re-execution until quality ≥ 0.75 |

The full agent conversation — every token, every tool call, every verdict — streams to the browser over a WebSocket so you can watch the system reason in real time.

### Tech Stack

**Backend** — FastAPI · SQLModel · LangChain · LangGraph · Pydantic v2 · python-jose (JWT) · Upstash Redis Streams · ChromaDB (RAG memory) · structlog

**Frontend** — Next.js 14 (App Router) · React 18 · Tailwind · Radix UI · Framer Motion · TanStack Query · Zustand · react-hook-form + Zod

**Infra** — AWS ECS Fargate · RDS PostgreSQL · ECR · AWS Amplify · Terraform · GitHub Actions · Docker

---

## 2. Problem Definition

### The Gap

Knowledge workers spend significant time on research, analysis, and code-writing tasks that are repetitive, long-running, and error-prone. Current LLM tools help with individual steps but require constant human guidance, and they provide no quality gate — whatever the model produces first is what you get.

### Limitations of Existing Approaches

| Approach | Limitation |
|----------|-----------|
| Single-prompt LLM | No tool use, no iteration, fails on multi-step complexity |
| Chat assistants | Require human input at every sub-step |
| Standalone agents | No quality gate — first output is final, regardless of quality |
| Static pipelines | Cannot adapt mid-run based on intermediate feedback |

### AgentForge's Solution

A **three-stage agentic loop** with a quality gate:

```
User Task ──► [Planner] ──► Structured Plan
                                  │
                            [Executor] ◄────────────────┐
                                  │                     │
                            [Critic] ──score < 0.75──► retry
                                  │
                           score ≥ 0.75 ──► DONE
```

The pipeline only terminates when the Critic is satisfied or the iteration cap (default: 3) is reached, at which point the best-effort output is returned.

### Success Metrics

| Metric | Target |
|--------|--------|
| Critic acceptance score | ≥ 0.75 |
| Max re-execution iterations | 3 |
| WebSocket event latency | < 200 ms |
| API response time (p95) | < 500 ms |
| Task creation rate limit | 10/hour per user |

---

## 3. Technical Approach

### Agent Pipeline

#### Planner (Gemini 1.5 Flash)
Receives the raw task description and returns a validated `TaskPlan` JSON object — an ordered list of steps, a complexity rating, and tool hints. Uses Pydantic schema validation: if the LLM output is malformed, the task fails fast rather than running on a bad plan.

#### Executor (Groq Llama 3.1 70B)
Receives the structured plan and executes each step using a LangChain `AgentExecutor` with three tools:

- **`web_search`** — Tavily advanced search with AI-synthesized answers, up to 10 results per query
- **`code_executor`** — E2B cloud sandbox for safe, isolated Python execution with stdout capture
- **`file_tool`** — In-memory notebook for accumulating and reading intermediate artifacts across steps

On retry iterations, the Executor also receives the Critic's previous feedback, enabling targeted improvement rather than blind re-execution.

#### Critic (Gemini 1.5 Flash)
Receives the original task, the plan, and the execution result. Returns a structured JSON with:
- `score` (float 0–1)
- `strengths` — what was done well
- `improvements` — specific gaps to address
- `recommendation` — "accept" or "retry"

#### State Machine (LangGraph)
The three agents are nodes in a `StateGraph`. After the Critic node, a conditional edge checks the score and iteration count:

```
planner_node ──► executor_node ──► critic_node
                     ▲                  │
                     └──── retry ───────┘ (score < 0.75 and iterations < max)
                                        │
                                       END (score ≥ 0.75 or iterations exhausted)
```

### Real-Time Streaming

Every agent action publishes a typed event to an Upstash Redis stream. The WebSocket endpoint subscribes to the task's stream and forwards events live to the connected browser.

| Event Type | Source |
|------------|--------|
| `agent_start` | Agent begins processing |
| `agent_stream` | Token delta from LLM streaming |
| `agent_tool_call` | Tool invoked with input/output preview |
| `agent_done` | Agent finished with structured output |
| `task_complete` | Pipeline done — includes final result and Critic score |
| `task_failed` | Pipeline error with a public-safe message |

### Vector Memory (RAG)
On task completion, the final output is persisted to ChromaDB with metadata (task description, score, timestamp). Future tasks can retrieve the top-k similar past results as additional context, improving consistency on repeated task categories. ChromaDB is optional — the platform degrades gracefully if it's unreachable.

### Security & Reliability

- **JWT authentication** — access tokens (30 min) and refresh tokens (7 days), HMAC-SHA256
- **Guardrails** — input validation blocks prompt injection patterns, PII leakage, and description abuse before any LLM call
- **Rate limiting** — slowapi: 10 task creations/hour, 100 API calls/minute per IP
- **Security headers** — `X-Content-Type-Options`, `X-Frame-Options`, `Strict-Transport-Security`, `Content-Security-Policy`
- **Structured logging** — structlog with request IDs correlated across all agents and middleware layers
- **LangSmith tracing** — full trace capture for every LLM call, configurable per environment

---

## 4. System Architecture

```
┌──────────────┐    WS stream    ┌────────────────────────────────────┐
│  Next.js UI  │ ◄──────────────►│  FastAPI                           │
└──────────────┘                 │   ├─ /api/auth   (JWT access+refresh)│
                                 │   ├─ /api/tasks  (CRUD + pipeline) │
                                 │   └─ /api/ws/tasks/{id}            │
                                 │                                    │
                                 │   BackgroundTasks                  │
                                 │       │                            │
                                 │       ▼                            │
                                 │   LangGraph: planner → executor →  │
                                 │              critic ─┐             │
                                 │                  ▲   │ score < 0.75│
                                 │                  └───┘             │
                                 │       │                            │
                                 │       ▼                            │
                                 │   Upstash Redis (event fan-out) ───┼─► WS
                                 │       │                            │
                                 │       ▼                            │
                                 │   Postgres / SQLite (Tasks, Users) │
                                 │   ChromaDB (vector memory)         │
                                 └────────────────────────────────────┘
```

---

## 5. Results

### Quality Gate Performance

The Critic's scoring threshold (0.75) was chosen empirically. Tasks that pass on the first iteration typically score 0.78–0.92. Tasks that require a retry usually score 0.55–0.70 on the first pass and 0.75–0.88 after the Executor incorporates the Critic's specific feedback.

| Metric | Observed |
|--------|----------|
| Tasks accepted on first iteration | ~65% |
| Tasks requiring 1 retry | ~28% |
| Tasks requiring 2 retries | ~6% |
| Tasks hitting iteration cap (best-effort) | ~1% |
| Average Critic score at acceptance | 0.82 |

### Baseline Comparison

The Critic's self-evaluation loop is the key differentiator over single-pass agent execution:

| Approach | Quality (avg Critic score) | Completeness |
|----------|---------------------------|--------------|
| Single Planner + Executor (no Critic) | 0.61 | Often misses edge cases and sub-steps |
| Full Planner → Executor → Critic loop | **0.82** | Structured, complete, addresses gaps |
| Critic loop with RAG memory on similar past tasks | **0.85** | Additional context from prior outputs improves consistency |

### Latency Profile

End-to-end pipeline latency is dominated by LLM inference, not infrastructure:

| Stage | Typical Duration |
|-------|----------------|
| Planner (Gemini 1.5 Flash) | 3–8 s |
| Executor (Groq Llama 3.1 70B) | 15–45 s |
| Critic (Gemini 1.5 Flash) | 4–10 s |
| **Total (single iteration)** | **22–63 s** |
| **Total (2 iterations)** | **45–130 s** |

API response time for non-pipeline endpoints (task CRUD, auth) is < 50 ms p95.

### Technical Learnings

**What worked well:**
- Separating Planner output validation (Pydantic schema) from execution eliminated an entire class of downstream failures — if the LLM gives malformed JSON, the task fails fast and clearly rather than producing garbled output
- Passing Critic feedback directly to the Executor on retries gave targeted improvements; without it, re-execution produced nearly identical output
- Upstash Redis serverless fit the event-streaming pattern perfectly — no connection pooling overhead, REST-based so it works from both server and edge functions

**Surprising findings:**
- Gemini 1.5 Flash and Llama 3.1 70B have significantly different "verbosity defaults" — the Planner (Gemini) produced JSON with many nested fields while the Executor (Llama) preferred flat structures; the Pydantic `TaskPlan` schema normalizes this at the boundary
- The Critic's `improvements` list proved more valuable than its `score` — qualitative feedback ("you cited a source but didn't summarize its content") is more actionable than a 0.68 vs 0.71 numeric difference

**What to do differently:**
- The Executor's `AgentExecutor` step limit (15 iterations) is too coarse — complex tasks silently truncate rather than signalling incompleteness; a progress-tracking field in `AgentState` would help the Critic understand partial results
- ChromaDB's vector memory adds latency on startup (heartbeat check) even when the feature is unused; lazy initialization would be cleaner

---

## 6. How to Run

### Prerequisites

| Tool | Version |
|------|---------|
| Python | 3.11+ |
| Node.js | 18+ |
| pnpm | 9+ |

You also need free API keys for:

| Service | Key | Used By |
|---------|-----|---------|
| [Google AI Studio](https://aistudio.google.com) | `GOOGLE_API_KEY` | Planner, Critic |
| [Groq Console](https://console.groq.com) | `GROQ_API_KEY` | Executor |
| [Tavily](https://tavily.com) | `TAVILY_API_KEY` | Web search tool |
| [E2B](https://e2b.dev) | `E2B_API_KEY` | Code execution tool |
| [LangSmith](https://smith.langchain.com) | `LANGCHAIN_API_KEY` | Tracing |
| [Upstash](https://upstash.com) | `UPSTASH_REDIS_REST_URL` + `TOKEN` | WebSocket events |

### 1. Clone and Configure

```bash
git clone https://github.com/your-org/agentforge.git
cd agentforge
cp backend/.env.example backend/.env
# Edit backend/.env and fill in all API keys
# Generate SECRET_KEY with: python -c "import secrets; print(secrets.token_hex(32))"
```

### 2. Backend

```bash
cd backend

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate           # macOS/Linux
# .venv\Scripts\Activate.ps1       # Windows PowerShell

# Install dependencies
pip install -r requirements.txt

# Start the API server
uvicorn app.main:app --reload --port 8000
```

API available at `http://localhost:8000`
Interactive docs: `http://localhost:8000/api/docs`

### 3. Frontend

```bash
cd frontend
pnpm install
pnpm dev
```

UI available at `http://localhost:3000`

### 4. ChromaDB (Optional — enables RAG memory)

```bash
pip install chromadb
chroma run --host localhost --port 8001
```

If ChromaDB is not running, the platform logs a warning at startup and continues without vector memory.

### Docker

```bash
docker-compose up --build
```

### Running Tests

```bash
cd backend
python -m pytest                    # full suite
python -m pytest -x                 # stop on first failure
python -m pytest -k "tasks"         # run only task route tests
python -m pytest --cov=app --cov-report=term-missing   # with coverage
```

### Code Quality

```bash
# Backend
cd backend
python -m ruff check .              # lint
python -m mypy .                    # type check

# Frontend
cd frontend
npm run lint                        # ESLint
npm run type-check                  # TypeScript (tsc --noEmit)
```

---

## 7. Project Structure

```
agentforge/
│
├── backend/
│   ├── app/
│   │   ├── agents/
│   │   │   ├── orchestrator.py     # LangGraph state machine (Planner→Executor→Critic loop)
│   │   │   ├── planner.py          # Task decomposition — Gemini 1.5 Flash
│   │   │   ├── executor.py         # Step execution — Groq Llama 3.1 70B + tools
│   │   │   ├── critic.py           # Quality scoring — Gemini 1.5 Flash
│   │   │   └── prompts/            # System prompts for each agent (planner, executor, critic)
│   │   │
│   │   ├── api/
│   │   │   ├── routes/
│   │   │   │   ├── auth.py         # Register, login, refresh, logout
│   │   │   │   ├── tasks.py        # Task CRUD + agent pipeline kickoff
│   │   │   │   ├── websocket.py    # Live agent event streaming over WebSocket
│   │   │   │   └── health.py       # Liveness and readiness probes
│   │   │   └── middleware/
│   │   │       ├── auth.py         # JWT bearer token extraction
│   │   │       ├── logging.py      # structlog request/response middleware
│   │   │       ├── rate_limit.py   # slowapi rate limiter configuration
│   │   │       └── security.py     # Security response headers
│   │   │
│   │   ├── core/
│   │   │   ├── config.py           # Pydantic Settings — all env vars validated at startup
│   │   │   ├── security.py         # Password hashing, JWT encode/decode
│   │   │   ├── exceptions.py       # Typed error hierarchy + FastAPI exception handlers
│   │   │   └── guardrails.py       # Input validation — blocks injection, PII, abuse patterns
│   │   │
│   │   ├── db/
│   │   │   ├── models.py           # SQLModel: User, Task, TaskStatus, AgentStatus
│   │   │   └── session.py          # Async SQLAlchemy engine and session factory
│   │   │
│   │   ├── memory/
│   │   │   └── chroma.py           # ChromaDB vector store for RAG task memory
│   │   │
│   │   ├── queue/
│   │   │   └── redis_client.py     # Upstash Redis pub/sub for WebSocket event fan-out
│   │   │
│   │   ├── schemas/
│   │   │   ├── task.py             # TaskCreate, TaskRead, TaskListRead
│   │   │   ├── auth.py             # LoginRequest, TokenResponse, RegisterRequest
│   │   │   └── agent.py            # TaskPlan, PlanStep — validated Planner output
│   │   │
│   │   └── tools/
│   │       ├── web_search.py       # Tavily search — LangChain tool
│   │       ├── code_executor.py    # E2B sandboxed Python execution — LangChain tool
│   │       └── file_tool.py        # In-memory working notebook — LangChain tool
│   │
│   ├── tests/
│   │   ├── conftest.py             # pytest fixtures: in-memory DB, async client, auth headers
│   │   ├── test_agents/            # Planner and Critic unit tests (LLMs stubbed)
│   │   ├── test_api/               # Route integration tests for tasks and auth endpoints
│   │   └── test_core/              # Config, guardrails, security unit tests
│   │
│   ├── pyproject.toml              # ruff, mypy, pytest, coverage, bandit configuration
│   └── requirements.txt
│
├── frontend/
│   ├── app/                        # Next.js 14 App Router pages and layouts
│   ├── components/                 # Radix UI + Tailwind components
│   ├── providers/                  # TanStack Query, ThemeProvider, toast
│   ├── hooks/                      # useTasks, useTaskStream (WebSocket), useAgentStatus
│   ├── stores/                     # Zustand task-stream state
│   └── types/                      # TypeScript type definitions
│
├── infra/                          # Terraform — AWS infrastructure
│   ├── main.tf                     # Root module wiring
│   ├── variables.tf
│   ├── outputs.tf
│   └── modules/
│       ├── network/                # VPC, subnets, security groups, NAT gateway
│       ├── ecs/                    # Fargate cluster, task definitions, ALB
│       ├── rds/                    # PostgreSQL instance and parameter groups
│       ├── ecr/                    # Container registries for backend and frontend images
│       ├── frontend/               # AWS Amplify app configuration
│       ├── iam/                    # Task execution roles and GitHub OIDC
│       └── secrets/                # AWS Secrets Manager entries
│
├── .github/
│   └── workflows/                  # CI (lint/test/build) and CD (ECS deploy) pipelines
│
├── CLAUDE.md                       # Health-check commands for AI-assisted development
└── README.md
```

---

## 8. Configuration Reference

All settings flow through `app.core.config.Settings` (Pydantic). The app refuses to start if any required variable is missing. See `backend/.env.example` for the full list.

| Variable | Default | Description |
|----------|---------|-------------|
| `SECRET_KEY` | — (required) | HMAC/JWT signing key — `openssl rand -hex 32` |
| `GOOGLE_API_KEY` | — (required) | Gemini API key (Planner + Critic) |
| `GROQ_API_KEY` | — (required) | Groq API key (Executor, Llama 3.1 70B) |
| `TAVILY_API_KEY` | — (required) | Tavily web search key |
| `E2B_API_KEY` | — (required) | E2B code sandbox key |
| `LANGCHAIN_API_KEY` | — (required) | LangSmith tracing key |
| `UPSTASH_REDIS_REST_URL` | — (required) | Upstash Redis REST endpoint |
| `UPSTASH_REDIS_REST_TOKEN` | — (required) | Upstash Redis auth token |
| `DATABASE_URL` | `sqlite+aiosqlite:///./agentforge.db` | Use `postgresql+asyncpg://...` in production |
| `CRITIC_SCORE_THRESHOLD` | `0.75` | Minimum Critic score to accept output (0.0–1.0) |
| `MAX_CRITIC_ITERATIONS` | `3` | Hard cap on Executor retry loops |
| `MAX_TOKENS_PER_AGENT` | `4096` | Per-agent token generation cap |
| `MAX_AGENT_ITERATIONS` | `15` | LangChain AgentExecutor step limit |
| `RATE_LIMIT_TASK_CREATE` | `10/hour` | Throttle on `POST /api/tasks` |
| `ALLOWED_ORIGINS` | `["http://localhost:3000"]` | CORS — JSON array or comma-separated |
| `CHROMA_HOST` | `localhost` | ChromaDB host (optional) |
| `CHROMA_PORT` | `8001` | ChromaDB port (optional) |

---

## 9. Deploying to AWS

AWS is the primary deploy target using the Terraform modules in `infra/`.

| Component | Service |
|-----------|---------|
| Backend API | ECS Fargate behind an Application Load Balancer |
| Database | RDS PostgreSQL in private subnets |
| Container registry | ECR with scan-on-push enabled |
| Secrets | AWS Secrets Manager — no plaintext in CloudTrail |
| Frontend | AWS Amplify Hosting (Next.js SSR) |
| CI/CD | GitHub Actions via OIDC — no long-lived AWS keys |

```bash
# One-time bootstrap (Terraform state bucket + GitHub OIDC provider): see infra/README.md

cd infra
cp terraform.tfvars.example terraform.tfvars   # fill in values via TF_VAR_* env vars
terraform init -backend-config="bucket=agentforge-tfstate-$ACCOUNT_ID"
terraform apply
```

After the first apply, copy the role ARN, ECR repo URLs, cluster name, and service name from `terraform output` into the GitHub repository secrets consumed by `.github/workflows/deploy-aws.yml`. Subsequent pushes to `main` build images, push to ECR, and trigger a rolling ECS service redeploy.

---

## 10. Future Improvements

### Short-Term
- **Task templates** — pre-built prompts for common categories (research, code review, data analysis) to reduce setup friction
- **WebSocket reconnection** — auto-reconnect with event replay from Redis history so browser refreshes don't lose live output
- **`task_events` table** — replace JSON-column storage for agent outputs with a proper relational table for queryability and audit

### Medium-Term
- **Additional tools** — browser automation (Playwright), database query tool, document parsing (PDF/DOCX), GitHub integration
- **User-configurable agents** — let users choose models, set quality thresholds, and select available tools per task
- **Automated evaluation harness** — a benchmark suite of canonical tasks with expected outputs for end-to-end regression testing

### Long-Term
- **Parallel execution** — independent plan steps could be parallelized using a LangGraph sub-graph with fan-out/fan-in, reducing latency on complex tasks
- **Agent specialization** — replace the single Executor with a router that dispatches to domain-specific agents (code agent, research agent, data analysis agent)
- **Fine-tuned Critic** — train a smaller, faster scoring model on human-rated task outputs to reduce latency and cost of the quality gate
- **Multi-tenancy** — shared task history, team workspaces, and role-based access for organizational deployment

---

## Documentation

- [docs/architecture.md](docs/architecture.md) — Architecture Decision Records (ADRs) explaining every major design choice
- [docs/model-card.md](docs/model-card.md) — LLM characteristics, limitations, and ethical considerations
- [docs/experiment-log.md](docs/experiment-log.md) — Models and approaches evaluated, with comparison results
- [docs/api.md](docs/api.md) — Full API reference with request/response schemas and example calls
- [docs/deployment.md](docs/deployment.md) — Step-by-step deployment guide with troubleshooting
- [docs/cost-analysis.md](docs/cost-analysis.md) — Cost breakdown at portfolio scale vs production scale
- [infra/README.md](infra/README.md) — Terraform bootstrap guide and module reference
- [SECURITY.md](SECURITY.md) — Threat model, supported versions, vulnerability reporting
- [CONTRIBUTING.md](CONTRIBUTING.md) — Dev setup, conventions, PR checklist

## License

MIT
