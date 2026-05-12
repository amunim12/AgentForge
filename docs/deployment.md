# Deployment Guide

This guide covers deploying AgentForge to AWS using the Terraform modules in `infra/`. For local development setup, see the [README](../README.md#6-how-to-run).

---

## Architecture Overview

```
Internet
   │
   ▼
ALB (HTTPS, cert from ACM)
   │
   ├── /api/* ──► ECS Fargate (FastAPI)
   │                    │
   │              Private subnets
   │                    ├── RDS PostgreSQL
   │                    └── (Upstash Redis — external SaaS)
   │
   └── frontend ──► AWS Amplify (Next.js SSR)
```

All AWS secrets are stored in Secrets Manager and injected into ECS task definitions at runtime — no plaintext in CloudTrail or environment variable exposure.

---

## Prerequisites

| Tool | Version |
|------|---------|
| Terraform | >= 1.5 |
| AWS CLI | >= 2.0 |
| Docker | >= 24 |
| GitHub CLI (`gh`) | any |

AWS account with admin access (or the specific IAM permissions listed in `infra/modules/iam/`).

---

## One-Time Bootstrap

These steps are performed once per AWS account and region.

### 1. Create the Terraform state bucket

```bash
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REGION=us-east-1

aws s3 mb s3://agentforge-tfstate-${ACCOUNT_ID} --region ${REGION}
aws s3api put-bucket-versioning \
  --bucket agentforge-tfstate-${ACCOUNT_ID} \
  --versioning-configuration Status=Enabled
aws s3api put-bucket-encryption \
  --bucket agentforge-tfstate-${ACCOUNT_ID} \
  --server-side-encryption-configuration \
  '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'
```

### 2. Create GitHub OIDC provider (enables keyless CI/CD)

```bash
aws iam create-open-id-connect-provider \
  --url https://token.actions.githubusercontent.com \
  --client-id-list sts.amazonaws.com \
  --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1
```

This only needs to be done once per account. The Terraform IAM module then creates a role that GitHub Actions can assume via OIDC.

---

## First Deployment

### 1. Configure variables

```bash
cd infra
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars`:

```hcl
aws_region         = "us-east-1"
project_name       = "agentforge"
environment        = "prod"
github_org         = "your-github-username"
github_repo        = "agentforge"
db_password        = "generate-a-strong-password"
allowed_origins    = ["https://your-amplify-domain.amplifyapp.com"]
```

Do **not** commit `terraform.tfvars` — it's in `.gitignore`.

### 2. Initialize and apply

```bash
terraform init \
  -backend-config="bucket=agentforge-tfstate-${ACCOUNT_ID}" \
  -backend-config="key=agentforge/terraform.tfstate" \
  -backend-config="region=us-east-1"

terraform plan   # review what will be created
terraform apply  # confirm with 'yes'
```

First apply takes approximately 10–15 minutes (RDS provisioning is the bottleneck).

### 3. Capture outputs for GitHub

```bash
terraform output
```

Copy these values into GitHub → Settings → Secrets and Variables → Actions:

| GitHub Secret/Variable | Terraform Output |
|----------------------|-----------------|
| `AWS_ROLE_ARN` | `github_actions_role_arn` |
| `ECR_BACKEND_REPO` | `ecr_backend_repository_url` |
| `ECR_FRONTEND_REPO` | `ecr_frontend_repository_url` |
| `ECS_CLUSTER` | `ecs_cluster_name` |
| `ECS_SERVICE` | `ecs_service_name` |
| `AMPLIFY_APP_ID` | `amplify_app_id` |

### 4. Store application secrets

Store all API keys in Secrets Manager. The ECS task definition is configured to read from these paths:

```bash
aws secretsmanager create-secret \
  --name agentforge/prod/app \
  --secret-string '{
    "SECRET_KEY": "your-generated-key",
    "GOOGLE_API_KEY": "...",
    "GROQ_API_KEY": "...",
    "TAVILY_API_KEY": "...",
    "E2B_API_KEY": "...",
    "LANGCHAIN_API_KEY": "...",
    "UPSTASH_REDIS_REST_URL": "...",
    "UPSTASH_REDIS_REST_TOKEN": "..."
  }'
```

### 5. Trigger first deployment

Push to `main`:

```bash
git push origin main
```

GitHub Actions runs `.github/workflows/deploy-aws.yml`:
1. Builds Docker image for the backend
2. Pushes to ECR
3. Updates the ECS service with the new image
4. Triggers Amplify rebuild for the frontend

---

## Subsequent Deployments

Every push to `main` triggers the CI/CD pipeline automatically. No manual steps required.

To deploy a specific commit:

```bash
git push origin <sha>:main --force   # only if you know what you're doing
```

---

## Environment Variables in Production

The ECS task definition reads environment variables from two sources:

1. **Secrets Manager** — sensitive values (API keys, SECRET_KEY, database password)
2. **ECS task definition environment** — non-sensitive config (DEBUG=false, DATABASE_URL, ALLOWED_ORIGINS)

To update a non-sensitive env var, update the task definition via the ECS console or re-run `terraform apply` with an updated variable.

To rotate a secret:

```bash
aws secretsmanager update-secret \
  --secret-id agentforge/prod/app \
  --secret-string '{"GROQ_API_KEY": "new-value", ...all-other-keys...}'

# Force a new ECS deployment to pick up the rotated secret
aws ecs update-service \
  --cluster agentforge-prod \
  --service agentforge-api \
  --force-new-deployment
```

---

## Database Migrations

AgentForge uses SQLModel's `create_all` on startup (development-friendly). For production schema changes:

1. Add new columns as nullable or with defaults to avoid locking
2. Deploy the new code (ECS rolling update keeps the old tasks alive during migration)
3. For destructive changes (drop column, rename), use a two-phase deployment:
   - Phase 1: deploy code that handles both old and new schema
   - Phase 2: run the migration, then deploy code that uses only the new schema

---

## Scaling

### Horizontal scaling (ECS)

Increase the ECS desired count:

```hcl
# infra/modules/ecs/variables.tf
desired_count = 2
```

The WebSocket architecture supports multiple instances because events are fanned out through Upstash Redis — any instance can serve any client.

### Vertical scaling (ECS task size)

Increase CPU/memory in the task definition. LLM inference is CPU-light (the model runs remotely); memory matters for connection pooling and in-memory Python objects.

### Database scaling

For > 100 concurrent users, increase `DB_POOL_SIZE` and upgrade the RDS instance class. Read replicas are not needed unless you have a heavy reporting workload (agent outputs are write-heavy, read-light).

---

## Monitoring

### Application logs

Logs are sent to CloudWatch Logs via the `awslogs` driver in the ECS task definition. Log group: `/ecs/agentforge-prod`.

Filter by task_id:
```
{ $.task_id = "3fa85f64-..." }
```

### Health checks

The ALB health check hits `GET /health/ready` every 30 seconds. If the check fails 2 consecutive times, the task is replaced.

### Alerts to set up

| Alert | Metric | Threshold |
|-------|--------|-----------|
| API errors | `5xx` responses | > 5 in 5 minutes |
| High latency | ALB `TargetResponseTime` p99 | > 2 seconds |
| ECS task failures | `RunningTaskCount < DesiredCount` | Any |
| RDS CPU | `CPUUtilization` | > 80% |

---

## Rollback

To roll back to the previous task definition:

```bash
# List recent task definition revisions
aws ecs list-task-definitions --family-prefix agentforge-api --sort DESC

# Roll back to a specific revision
aws ecs update-service \
  --cluster agentforge-prod \
  --service agentforge-api \
  --task-definition agentforge-api:42   # previous revision number
```

---

## Troubleshooting

### ECS tasks keep stopping

1. Check CloudWatch Logs for the task — the error is almost always a missing env var or failed health check
2. Confirm `GET /health/ready` responds 200 locally with the same env vars
3. Verify Secrets Manager path matches what's in the task definition

### WebSocket connections drop immediately

1. Confirm ALB idle timeout is ≥ 300 seconds (agent pipelines can take 60–120 seconds)
2. Check that the ALB target group has stickiness enabled for WebSocket connections
3. Verify CORS `ALLOWED_ORIGINS` includes the frontend domain

### Database connection exhausted

Increase `DB_POOL_SIZE` (default 5) or `DB_MAX_OVERFLOW` (default 10) in the ECS environment variables. At 2 ECS tasks × 15 pool connections each, you need a db instance class that supports ≥ 30 connections.

### Upstash rate limiting

The free Upstash tier allows 10,000 commands/day. Each task publish is ~3 commands (xadd + xread). At 1,000 tasks/day × 10 events/task = 10,000 events = 30,000 commands — upgrade to the pay-as-you-go tier if you exceed the free tier.
