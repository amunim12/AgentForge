# Cost Analysis

What it costs to run AgentForge as a portfolio project, and what changes if you scaled it. Numbers below are list prices as of 2026-04 â check each provider before relying on them.

## Portfolio scale (single demo user, ~50 tasks/month)

| Component | Provider | Plan | Monthly cost |
| --- | --- | --- | --- |
| Backend container | Render | Free web service (sleeps when idle) | $0 |
| Postgres | Render | Free 1 GB instance | $0 |
| Frontend | Vercel | Hobby | $0 |
| Redis Streams | Upstash | Free 10k commands/day | $0 |
| Vector store | ChromaDB (in-process) | Bundled with backend | $0 |
| Code sandbox | E2B | Free tier (limited minutes) | $0 |
| Web search | Tavily | Free 1k queries/month | $0 |
| Planner LLM | Google Gemini 1.5 Flash | Free tier (RPD limit) | $0 |
| Critic LLM | Google Gemini 1.5 Pro | Free tier (RPD limit) | $0 |
| Executor LLM | Groq Llama 3.1 70B | Free tier (RPM/TPM limits) | $0 |
| Tracing | LangSmith | Hobby (5k traces/month) | $0 |
| **Total** | | | **$0** |

The catch: free Render web services sleep after inactivity, so the first request after a long idle waits ~30s for a cold start. Acceptable for a portfolio link, not for paying users.

## Light production (~50 active users, 5k tasks/month, avg 2 critic iterations)

Token math drives this tier. Assume a 5k-token round trip per task per agent (planner small, executor and critic larger):

- Planner (Gemini 1.5 Flash): ~5k tokens Ã 5,000 tasks Ã $0.075/M in + $0.30/M out â **~$2**
- Executor (Groq Llama 3.1 70B): ~12k tokens Ã 10,000 invocations (2 iterations) Ã $0.59/M in + $0.79/M out â **~$80**
- Critic (Gemini 1.5 Pro): ~8k tokens Ã 10,000 Ã $1.25/M in + $5.00/M out â **~$200**

| Component | Plan | Monthly cost |
| --- | --- | --- |
| Render web service (always-on, 0.5 CPU / 512 MB) | Starter | ~$7 |
| Render Postgres 256 MB | Starter | ~$7 |
| Vercel Pro (if past Hobby limits) | Pro | $20 |
| Upstash Redis pay-as-you-go | â | ~$5 |
| Tavily Standard (10k/month) | Standard | ~$30 |
| E2B sandbox usage | Pay-as-you-go | ~$25 |
| LangSmith Plus | Plus | $39 |
| LLM tokens (sum above) | â | ~$280 |
| **Total** | | **~$420 / month** |

The Critic dominates because Gemini Pro output tokens are expensive. If cost matters, swap the Critic to Gemini Flash and accept a quality drop, or run the Critic only every Nth iteration.

## Same scale on AWS (the primary deploy target)

Same usage pattern, but on the ECS Fargate + RDS architecture in `infra/`. Numbers are us-east-1 list price, single-AZ where the module allows it.

| Component | Configuration | Monthly cost |
| --- | --- | --- |
| ECS Fargate task (backend) | 0.5 vCPU + 1 GB, 1 task always-on | ~$13 |
| Application Load Balancer | 1 ALB, light traffic | ~$17 |
| NAT Gateway | 1 NAT, mostly idle (egress for ECS â external LLM/Redis) | ~$33 + data |
| RDS Postgres | db.t4g.micro, 20 GB gp3, single-AZ | $0 first year (free tier) â then ~$13 |
| ECR | <500 MB stored | <$1 |
| Secrets Manager | ~10 secrets | ~$4 |
| CloudWatch Logs | 14-day retention, low volume | ~$1 |
| Amplify Hosting (frontend) | Build minutes + low traffic | ~$5 |
| LLM tokens (same as production scale above) | â | ~$280 |
| **Total (year 1, free RDS)** | | **~$355 / month** |
| **Total (after free tier)** | | **~$370 / month** |

Things that move this number:

- The **NAT Gateway** is the single biggest infra line. It exists so private-subnet ECS tasks can reach Google/Groq/Tavily/E2B/Upstash. Replacing it with VPC endpoints helps for AWS-internal services (Secrets Manager, ECR, CloudWatch) but the LLM calls still need NAT egress. A small NAT instance is ~$5/month and an option for non-prod.
- **Multi-AZ RDS** doubles the DB line. Off by default in this Terraform.
- **Fargate Spot** for non-critical environments cuts compute by ~70%. The cluster is wired for Spot; flip the strategy weight to use it.

## Levers that move the bill

- `MAX_CRITIC_ITERATIONS` â each retry roughly doubles token spend on that task. Default is 3.
- `CRITIC_SCORE_THRESHOLD` â lower = fewer reruns = less spend, at the cost of letting weaker outputs through.
- `MAX_TOKENS_PER_AGENT` â hard cap; we set 4096 because it's the point where Llama 3.1 70B starts repeating itself.
- Output truncation in tools (`_truncate` in `code_executor`, formatter cap in `web_search`) keeps Critic context bounded.

## What we deliberately don't pay for

- A managed vector DB. ChromaDB runs in-process and persists to disk. If we ever serve recall queries at scale, this is the next thing to graduate to a managed service.
- A queue. Upstash Streams is the queue.
- An auth provider. JWT + bcrypt is enough for the user model we have. If SSO becomes a requirement, that's a real cost line.
- Observability beyond LangSmith + structlog + Render's built-in logs. A real platform would add Grafana / Datadog; we don't.
