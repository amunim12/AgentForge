# Experiment Log

A record of key architectural and model decisions made during AgentForge development — what was tried, what worked, what didn't, and why.

---

## Experiment 1 — Agent Orchestration Framework

**Hypothesis:** LangGraph provides better control over the Planner→Executor→Critic loop than a hand-rolled dispatcher or a higher-level framework like CrewAI.

**Alternatives evaluated:**

| Option | Result | Why Rejected |
|--------|--------|--------------|
| Hand-rolled async dispatcher | Working prototype | Would have grown into a worse copy of LangGraph; conditional edges and streaming hooks require explicit state management |
| CrewAI | Prototype built | Too opinionated about agent roles; couldn't model the "retry only the Executor, not the Planner" logic cleanly |
| AutoGen | Not prototyped | Multi-turn conversational model doesn't fit a deterministic graph with typed state |
| **LangGraph StateGraph** | **Selected** | Explicit graph topology, typed `AgentState`, conditional edges, streaming-friendly |

**Key learning:** The typed `AgentState` (TypedDict) was the decisive factor — it lets each node return only the fields it changes, and mypy catches missing keys at development time rather than runtime.

---

## Experiment 2 — Planner Model Selection

**Hypothesis:** Gemini 1.5 Flash produces well-structured JSON plans without requiring explicit `response_mime_type` enforcement.

**Alternatives evaluated:**

| Model | JSON reliability | Latency | Cost |
|-------|-----------------|---------|------|
| Gemini 1.5 Pro | Excellent | 8–15 s | Higher |
| **Gemini 1.5 Flash** | **Good (95%+)** | **3–8 s** | **Free tier** |
| GPT-4o-mini | Good | 3–6 s | Requires OpenAI key |
| Llama 3.1 70B (Groq) | Inconsistent on complex schemas | 2–5 s | Free tier |

**Result:** Gemini 1.5 Flash selected. The 5% of cases where it wraps output in ```json fences are handled by `_strip_fences()`, and the remaining JSON schema failures are caught by Pydantic validation and surfaced as `AgentExecutionError`.

---

## Experiment 3 — Executor Model Selection

**Hypothesis:** Groq's Llama 3.1 70B provides the best speed/quality tradeoff for tool-calling execution.

**Alternatives evaluated:**

| Model | Tool-calling quality | Tokens/sec | Rate limit |
|-------|---------------------|------------|------------|
| GPT-4o | Excellent | ~100 | Paid only |
| Claude 3.5 Sonnet | Excellent | ~80 | Paid only |
| Gemini 1.5 Flash | Good | ~120 | Free tier |
| **Llama 3.1 70B (Groq)** | **Good** | **200+** | **Free tier** |
| Llama 3.1 8B (Groq) | Inconsistent tool use | 400+ | Free tier |

**Result:** Groq selected for free-tier accessibility and speed. The 70B over 8B was non-negotiable — 8B showed ~30% tool-call failure rate on multi-step plans.

**Key learning:** Executor speed matters more than marginal accuracy because the Critic provides a correction loop. A fast 70B + retry is better than a slow 7B + retry.

---

## Experiment 4 — Critic Scoring Threshold

**Hypothesis:** A threshold of 0.75 provides the right balance between accepting adequate output and triggering unnecessary retries.

**Thresholds evaluated:**

| Threshold | Acceptance rate | Avg iterations | Observed quality |
|-----------|----------------|----------------|-----------------|
| 0.60 | ~90% | 1.1 | Acceptable but shallow answers frequently accepted |
| **0.75** | **~72%** | **1.4** | **Good balance** |
| 0.85 | ~45% | 2.1 | High quality but high latency and cost |
| 0.90 | ~20% | 2.8 | Often hits iteration cap; frustrating UX |

**Result:** 0.75 selected as default, configurable via `CRITIC_SCORE_THRESHOLD` env var.

---

## Experiment 5 — Event Transport (Redis vs In-Process)

**Hypothesis:** Upstash Redis Streams is the right transport for WebSocket event fan-out vs an in-process pub/sub.

**Alternatives evaluated:**

| Option | Pros | Cons |
|--------|------|------|
| In-process asyncio.Queue | Zero latency, no infra | Single-process only; doesn't work with multiple uvicorn workers |
| Redis Streams (self-hosted) | Persistent, scalable | Operational overhead |
| **Upstash Redis (REST)** | **Serverless, free tier, works from anywhere** | **REST API adds ~5ms per publish** |
| Server-Sent Events (no broker) | Simple | Doesn't cross process boundaries |

**Result:** Upstash selected for serverless convenience and free-tier cost. The 5ms publish overhead is negligible vs LLM inference time.

**Key learning:** Upstash's Python SDK (`upstash-redis`) uses blocking REST calls under the hood. The `publish_task_update` function wraps these in `asyncio.to_thread` to avoid blocking the event loop.

---

## Experiment 6 — Database Choice

**Hypothesis:** SQLModel + SQLAlchemy 2.0 async provides the right abstraction for both development (SQLite) and production (PostgreSQL) without code changes.

**Alternatives evaluated:**

| Option | Dev ergonomics | Production fit |
|--------|---------------|---------------|
| Raw SQL + asyncpg | Full control | No ORM overhead, but lots of boilerplate |
| SQLAlchemy 2.0 (no SQLModel) | Good | Excellent, but verbose Pydantic integration |
| **SQLModel** | **Excellent** | **Good — shares Pydantic models with API schemas** |
| Tortoise ORM | Good | Less mature ecosystem |
| Prisma (Python) | Good | Still alpha |

**Result:** SQLModel selected. The ability to use `class Task(SQLModel, table=True)` as both ORM model and Pydantic schema reduces duplication significantly.

---

## Experiment 7 — Input Validation (Guardrails)

**Hypothesis:** Pattern-based guardrails provide sufficient protection against prompt injection without the latency of an LLM-based moderation call.

**Approach:** Regex patterns block known injection phrases ("ignore all previous instructions", "reveal the system prompt", etc.) and PII patterns (credit card numbers, SSNs). Description length is validated (10–5000 characters).

**Alternative considered:** Use the Moderation API (OpenAI) or a dedicated safety classifier before every task. Rejected: adds 200–500ms latency and an external dependency per request.

**Result:** Pattern-based guardrails catch the clear-cut cases. Edge cases are mitigated by the fact that agent prompts use structured system messages that are harder to override with user content.

---

## Decisions That Were Not Experiments (Made by Design)

| Decision | Rationale |
|----------|-----------|
| `redirect_slashes=False` on FastAPI | Prevents 307 redirects that confuse some HTTP clients; routes are canonical without trailing slashes |
| JWT over sessions | Stateless auth fits the distributed deployment model; no session store needed |
| Pydantic Settings (not dotenv directly) | Validates all env vars at startup; app fails fast with a clear error rather than crashing mid-request on a missing key |
| `StrEnum` for TaskStatus | Python 3.11+ feature that makes enum values directly usable as strings without `.value` in SQL queries |
| structlog over stdlib logging | Structured JSON logs are queryable in CloudWatch/Datadog; key-value context (task_id, user_id) is attached automatically |
