# Architecture Decision Records

Decisions that shape AgentForge today and the reasoning that drove each one. New ADRs go at the bottom; existing ones are not edited in place when superseded â a follow-up entry records the reversal so the history reads as a story.

## ADR-001 â LangGraph for agent orchestration

**Status:** Accepted

**Context.** The product needs three specialized agents (Planner, Executor, Critic) with a retry loop driven by a critic score. We need streaming, conditional edges, and the option to add nodes later without rewriting the control flow.

**Decision.** Use LangGraph's `StateGraph` with a typed `AgentState` and explicit conditional edges. Each agent is a plain async function that returns a partial state.

**Alternatives considered.** A hand-rolled async dispatcher; CrewAI; AutoGen. The hand-rolled version would have grown into a worse copy of LangGraph as soon as we added the retry edge. CrewAI and AutoGen are higher-level than we need â we want explicit graph control for streaming and persistence hooks.

**Consequences.** Plus: graph topology is readable in one file; every transition is a single seam to test. Minus: LangGraph is young, breaking changes are possible, so we pin a tested version and keep our integration surface narrow (graph construction + `ainvoke`).

## ADR-002 â FastAPI long-running over serverless functions

**Status:** Accepted

**Context.** The frontend needs a live, multi-minute view of agent execution: token streams, tool calls, critic verdicts. The backend needs to hold WebSocket connections and run a graph that can take 30+ seconds.

**Decision.** Run a single FastAPI process under `uvicorn` on Render. Use `BackgroundTasks` to start the graph after the HTTP response is sent. Stream events to clients via in-process broker fed from Redis Streams.

**Alternatives considered.** AWS Lambda behind API Gateway. Lambda's 15-minute hard cap is workable, but it has no native WebSocket model for streaming intermediate state â you have to use API Gateway WebSockets, which forces a polling/queue rewrite of the frontend. Cloud Run hits the same WebSocket awkwardness with cold starts on top.

**Consequences.** Plus: WebSockets are first-class, the orchestrator is a normal Python program, local dev matches prod. Minus: we manage one always-on process and pay for it even when idle; mitigated by Render's free tier and the small footprint.

## ADR-003 â Postgres / SQLite via SQLModel, not DynamoDB

**Status:** Accepted

**Context.** Tasks have rich relational data (owner, status enum, timestamps, planner/executor/critic JSON outputs, iteration count, score). We query by user, by status, sort by created_at, and want migrations.

**Decision.** SQLModel on async SQLAlchemy 2.0. SQLite locally and in tests; managed Postgres in production.

**Alternatives considered.** DynamoDB â great for the AWS plan's session-scoped chatbot, wrong here. We'd need a GSI per access pattern, JSON blobs become opaque, and migrations are manual. Mongo â solves nothing the relational store doesn't, costs another service.

**Consequences.** Plus: standard SQL, Alembic if needed, easy local stories. Minus: locked into a relational store; hot-path counts could need an index later (acceptable, easy to add).

## ADR-004 â Upstash Redis Streams + in-process broker for fan-out

**Status:** Accepted

**Context.** Multiple WebSocket clients can watch the same task. The orchestrator publishes events from a background task; the connection handler consumes them.

**Decision.** Publish to Upstash Redis Streams via REST (no persistent connection needed â works on serverless platforms). On the consumer side, a single in-process `_Broker` reads the stream and fans events out to all active WebSockets for that task.

**Alternatives considered.** Direct Redis pub/sub (Upstash REST doesn't support pub/sub). RabbitMQ / SQS (too heavy for this scope). In-process only (loses the property of surviving a brief reconnect on the same instance).

**Consequences.** Plus: works on any Render-class host without raw TCP. Minus: a multi-instance deploy needs every instance subscribed â acceptable until we scale out, then we revisit.

## ADR-005 â Pydantic Settings as the only config surface

**Status:** Accepted

**Context.** API keys for Google, Groq, Tavily, E2B, LangSmith, Upstash; signing key for JWT; CORS allow-list; agent thresholds.

**Decision.** Every value flows through `app.core.config.Settings`. App code never reads `os.environ` directly. `SECRET_KEY` and the API keys are required and validated at process start; the app refuses to boot if any are missing.

**Alternatives considered.** Direct env reads (no validation, sprawls). A separate `.config.json` (would have to be parsed and validated anyway).

**Consequences.** Plus: a single typed object; misconfiguration shows up at startup, not on the first user request. Minus: tests have to set env vars before importing the app â handled in `conftest.py`.

## ADR-006 â Sanitized error envelope (`AgentForgeError.public_message`)

**Status:** Accepted

**Context.** LLM tool errors, validation messages, DB exceptions all have rich internal detail. None of it should reach a client.

**Decision.** Custom exception hierarchy where the *class* defines `public_message` and `status_code`. The handler returns the public message; the constructor argument is internal-only. Unhandled `Exception` collapses to a generic 500.

**Alternatives considered.** Returning `str(exc)` (leaks). Per-route try/except (drift, easy to forget).

**Consequences.** Plus: leak-resistant by construction, tested. Minus: callers can't customize the public message per-raise â intentional; if they need to, they add a new subclass.

## ADR-007 â Guardrails layer separate from Pydantic validation

**Status:** Accepted

**Context.** Pydantic enforces shape and length. It doesn't see content patterns: leaked credentials, prompt-injection markers, oversized agent output.

**Decision.** A dedicated `app.core.guardrails` module with `validate_task_input` (raises `GuardrailViolation` â 400) and `sanitize_agent_output` (truncate + redact). Wired into the task-creation route at the boundary.

**Alternatives considered.** Folding patterns into Pydantic validators. Works for input but not for output sanitization, and mixes concerns.

**Consequences.** Plus: one place to extend when we discover new patterns; cheap to test. Minus: pattern lists are inherently incomplete â this is a tripwire, not a complete defense, and that's documented in `SECURITY.md`.

## ADR-008 â Render + Vercel over self-hosted Kubernetes (or AWS)

**Status:** Superseded by ADR-009.

**Context.** Deploy target needed for the portfolio: it has to be live, cheap, and reproducible.

**Decision.** Backend on Render (managed Postgres + container service); frontend on Vercel (Next.js native). Triggered from `.github/workflows/deploy.yml` and gated by repo variables so forks don't auto-deploy.

**Alternatives considered.** AWS (Lambda+API Gateway+RDS) â richer story for an interview but pulls the architecture toward serverless trade-offs (see ADR-002). Self-hosted on a VPS â no managed Postgres, more ops time. Fly.io â good fit, but Render's free Postgres is a deciding factor for the portfolio budget.

**Consequences.** Plus: free for the relevant scale, two deploys, no Terraform. Minus: vendor-locked at the deploy layer â re-platforming would mean rewriting CI and recreating Postgres elsewhere. Acceptable.

## ADR-009 â AWS as the primary deploy target (ECS Fargate + RDS + Amplify)

**Status:** Accepted. Supersedes ADR-008.

**Context.** The Render path stayed cheap but produced a weaker portfolio story: no IaC, no IAM story, cold starts on the free tier, opaque networking. We want the architecture and the deploy story to demonstrate the same engineering discipline.

**Decision.** Move the primary deploy to AWS, fully described in Terraform under `infra/`:

- **ECS Fargate** behind an ALB for the backend. Fargate is the right shape for FastAPI long-running with WebSockets (ADR-002 still applies â Lambda is rejected for the same reason). ALB idle timeout is bumped to 300s and LB stickiness is on so a WebSocket upgrade survives across the fleet.
- **RDS Postgres** in private subnets with the master password generated by Terraform and stored in Secrets Manager. The container reads `DATABASE_URL` from a separate Secrets Manager entry assembled at apply time.
- **ECR** for the image, scan-on-push enabled, lifecycle policy to keep cost flat (10 tagged + 7-day untagged).
- **Secrets Manager** holds every app env var as a separate entry. ECS maps each one into the container via `taskDefinition.containerDefinitions.secrets` so values never appear in CloudTrail or task-definition diffs.
- **Amplify Hosting** for the Next.js frontend â SSR-aware, single Terraform resource, GitHub-tracked, cheaper and simpler than running a second Fargate service for `next start`.
- **GitHub Actions OIDC** for CI auth. The deploy workflow assumes a tightly-scoped role (ECR push + ECS update-service + PassRole on the two task roles) â no long-lived AWS keys live in repo secrets.

Render + Vercel remain wired up via `deploy.yml` for anyone who wants the free path, but `deploy-aws.yml` is what we link from the README.

**Alternatives considered.**
- *AWS Lambda + API Gateway WebSockets.* Rejected for the same reason as ADR-002: forces a queue-based rewrite of the agent stream and complicates local dev.
- *App Runner.* Simpler than Fargate, but it doesn't support WebSockets at the ALB-equivalent layer; this is a hard blocker for the live-execution view.
- *EKS.* Adds a control plane and a kubeconfig story for no benefit at this scale.
- *Fargate for the frontend instead of Amplify.* Doable but adds an ALB rule, a second target group, a second image, and a second deploy step. Amplify is one resource and handles SSR correctly.

**Consequences.**
- **Plus:** the IaC is the architecture diagram. Reviewers can grep `infra/` and see VPC layout, IAM least-privilege, secret handling, deploy gating. Hot-path numbers (image size, cold-start time, ALB latency) become measurable. Multi-AZ is a flip of `availability_zone_count`.
- **Minus:** real money. Fargate + ALB + RDS + NAT is roughly $35â50/month at idle (see `docs/cost-analysis.md`). The state bucket and GitHub OIDC provider are account-wide bootstrap that can't be inside this Terraform. Operators have to remember to flip `deletion_protection` and `skip_final_snapshot` before treating it as a real prod system.
- **Migration.** The Render Postgres dump can be restored into RDS via `pg_restore`. The frontend gets pointed at the new ALB via the Amplify env vars. Old Render service is paused, not deleted, until DNS is cut over.
