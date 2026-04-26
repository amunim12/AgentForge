# AgentForge AWS Infrastructure

Terraform that provisions AgentForge on AWS:

- **Backend** â ECS Fargate behind an Application Load Balancer (WebSocket-friendly)
- **Database** â RDS Postgres in private subnets, password in Secrets Manager
- **Image registry** â ECR with vulnerability scanning + lifecycle policy
- **Secrets** â one Secrets Manager entry per app env var, mounted into the task definition
- **Frontend** â AWS Amplify Hosting (Next.js SSR), wired to the backend ALB
- **CI/CD trust** â GitHub Actions assumes a scoped role via OIDC; no long-lived AWS keys

## One-time bootstrap

You need the OIDC provider for GitHub and an S3 bucket for remote state. Both are account-wide and live outside this Terraform.

```bash
# 1. Create the state bucket (account-scoped name).
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
aws s3api create-bucket \
  --bucket agentforge-tfstate-$ACCOUNT_ID \
  --region us-east-1
aws s3api put-bucket-versioning \
  --bucket agentforge-tfstate-$ACCOUNT_ID \
  --versioning-configuration Status=Enabled
aws s3api put-bucket-encryption \
  --bucket agentforge-tfstate-$ACCOUNT_ID \
  --server-side-encryption-configuration \
    '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'

# 2. Create the GitHub OIDC provider (idempotent â skip if it already exists).
aws iam create-open-id-connect-provider \
  --url https://token.actions.githubusercontent.com \
  --client-id-list sts.amazonaws.com \
  --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1 || true
```

## Apply

```bash
cd infra
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars â do NOT commit real values.

terraform init -backend-config="bucket=agentforge-tfstate-$ACCOUNT_ID"
terraform plan
terraform apply
```

## Useful outputs

```bash
terraform output backend_url               # http://<alb-dns>
terraform output ecr_repository_url        # for `docker push`
terraform output github_actions_role_arn   # paste into GitHub repo secret AWS_DEPLOY_ROLE_ARN
terraform output amplify_app_url           # frontend URL (if frontend module enabled)
```

After the first apply, push an image so the service has something to run:

```bash
ECR_URL=$(terraform output -raw ecr_repository_url)
aws ecr get-login-password | docker login --username AWS --password-stdin "${ECR_URL%/*}"
docker build -t "$ECR_URL:latest" -f ../backend/Dockerfile ../backend
docker push "$ECR_URL:latest"

# Force the service to pull the new image.
CLUSTER=$(terraform output -raw ecs_cluster_name)
SERVICE=$(terraform output -raw ecs_service_name)
aws ecs update-service --cluster "$CLUSTER" --service "$SERVICE" --force-new-deployment
```

## Tear down

```bash
terraform destroy
```

`recovery_window_in_days = 0` on Secrets Manager entries makes destroy fast at the cost of immediate deletion. Bump for real prod.

## What you still have to do

- Add an ACM certificate + Route53 record + HTTPS listener if you want a real domain (the ALB serves HTTP only by default).
- Set `deletion_protection = true` and `skip_final_snapshot = false` on the RDS instance before going to real prod.
- Move the GitHub PAT used by Amplify into Secrets Manager and reference it via `aws_amplify_app.access_token` from there if you don't want it in `TF_VAR_amplify_github_token`.
