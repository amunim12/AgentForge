# AgentForge

A multi-agent AI orchestration platform that decomposes a natural-language task into a plan, executes it with tools, and self-critiques the result in a closed loop until it passes a quality bar.

Three specialized agents collaborate over a LangGraph state machine:

- **Planner** — Gemini 1.5 Flash. Turns the task into a structured JSON plan.
- **Executor** — Llama 3.1 70B (Groq). Carries out the plan using web search, a sandboxed Python interpreter (E2B), and a working notebook.
- **Critic** — Gemini 1.5 Pro. Scores the executor's output against a five-axis rubric and either accepts it or sends it back with specific feedback.

The full conversation streams to the frontend over a WebSocket — every agent stream chunk, every tool call, every verdict — so you can watch the system reason in real time.

## Tech stack

**Backend** — FastAPI · SQLModel · LangChain · LangGraph · Pydantic v2 · python-jose (JWT) · Upstash Redis Streams · ChromaDB (RAG memory) · structlog
**Frontend** — Next.js 14 (App Router) · React 18 · Tailwind · shadcn/ui · Radix · Framer Motion · TanStack Query · Zustand · react-hook-form + zod
**Infra** — Docker · GitHub Actions · Dependabot · CodeQL · Bandit · pip-audit · Gitleaks

## Architecture

```
┌──────────────┐    WS stream    ┌────────────────────────────────────┐
│  Next.js UI  │ ◄──────────────►│  FastAPI                            │
└──────────────┘                 │   ├─ /api/auth   (JWT access+refresh)│
                                 │   ├─ /api/tasks                     │
                                 │   └─ /ws/tasks/{id}                 │
                                 │                                     │
                                 │   BackgroundTasks                   │
                                 │       │                             │
                                 │       ▼                             │
                                 │   LangGraph: planner → executor →   │
                                 │              critic ─┐              │
                                 │                  ▲   │ score < gate │
                                 │                  └───┘              │
                                 │       │                             │
                                 │       ▼                             │
                                 │   Upstash Redis (event fan-out) ────┼─► WS
                                 │       │                             │
                                 │       ▼                             │
                                 │   Postgres / SQLite (Tasks, Users)  │
                                 │   ChromaDB (vector memory)          │
                                 └────────────────────────────────────┘
```

## Quick start

### Prerequisites

- Python 3.11+
- Node.js 20+ and pnpm 9+
- API keys for: Google AI, Groq, Tavily, E2B, LangSmith, Upstash Redis

### 1. Clone and configure

```bash
git clone https://github.com/your-org/agentforge.git
cd agentforge
cp backend/.env.example backend/.env
# Fill in API keys and generate SECRET_KEY:
#   python -c "import secrets; print(secrets.token_hex(32))"
```

### 2. Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt -r requirements-dev.txt
uvicorn app.main:app --reload
```

API docs: http://localhost:8000/docs

### 3. Frontend

```bash
cd frontend
pnpm install
pnpm dev
```

App: http://localhost:3000

### Docker

```bash
docker-compose up --build
```

## Running tests

```bash
cd backend
pytest --cov=app --cov-report=term-missing
```

```bash
cd frontend
pnpm lint && pnpm type-check && pnpm build
```

## Project layout

```
agentforge/
├─ backend/
│  ├─ app/
│  │  ├─ agents/        planner, executor, critic, orchestrator (LangGraph)
│  │  ├─ api/           routes, deps, middleware (rate limit, logging)
│  │  ├─ core/          config, security, exceptions, logging
│  │  ├─ db/            SQLModel models, async session
│  │  ├─ memory/        ChromaDB RAG store
│  │  ├─ queue/         Upstash Redis client + in-process broker
│  │  ├─ schemas/       Pydantic event/agent schemas
│  │  └─ tools/         web_search (Tavily), code_executor (E2B), file_tool
│  └─ tests/            pytest + pytest-asyncio (LLMs/Redis/Chroma stubbed)
├─ frontend/
│  ├─ app/              Next.js App Router (auth + app shells)
│  ├─ components/       agents/, layout/, shared/, tasks/, ui/ (shadcn)
│  ├─ hooks/            useTasks, useTaskStream (WS), useAgentStatus
│  ├─ stores/           Zustand task-stream store
│  └─ providers/        TanStack Query, theme, toaster
├─ .github/             ci.yml, security.yml, deploy.yml, dependabot.yml
└─ docker-compose.yml
```

## Configuration

All backend settings come through `app.core.config.Settings` (Pydantic). Required env vars are listed in `backend/.env.example`; the app refuses to start without them.

| Knob                       | Default | Purpose                                |
| -------------------------- | ------- | -------------------------------------- |
| `CRITIC_SCORE_THRESHOLD`   | 0.75    | Minimum verdict score to accept output |
| `MAX_CRITIC_ITERATIONS`    | 3       | Hard cap on retry loops                |
| `MAX_TOKENS_PER_AGENT`     | 4096    | Per-agent generation cap               |
| `RATE_LIMIT_TASK_CREATE`   | 10/hour | Throttle on `POST /api/tasks`          |

## Security

See [SECURITY.md](SECURITY.md) for the threat model, supported versions, and how to report vulnerabilities.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT
