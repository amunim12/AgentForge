variable "aws_region" {
  description = "AWS region for all resources."
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Lowercase, hyphenated project name â used for resource naming."
  type        = string
  default     = "agentforge"
}

variable "environment" {
  description = "Deployment environment (dev, staging, prod)."
  type        = string
  default     = "prod"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment must be one of dev, staging, prod."
  }
}

# ---------------------------------------------------------------------------
# Networking
# ---------------------------------------------------------------------------
variable "vpc_cidr" {
  description = "CIDR block for the VPC."
  type        = string
  default     = "10.40.0.0/16"
}

variable "availability_zone_count" {
  description = "Number of AZs to span. Two is the cheapest HA configuration."
  type        = number
  default     = 2
}

# ---------------------------------------------------------------------------
# Backend (ECS)
# ---------------------------------------------------------------------------
variable "backend_image_tag" {
  description = "Tag of the backend image in ECR to deploy. CI overrides this on each deploy."
  type        = string
  default     = "latest"
}

variable "backend_cpu" {
  description = "Fargate CPU units for the backend task (256 = 0.25 vCPU)."
  type        = number
  default     = 512
}

variable "backend_memory" {
  description = "Fargate memory (MiB) for the backend task."
  type        = number
  default     = 1024
}

variable "backend_desired_count" {
  description = "Number of backend tasks to run."
  type        = number
  default     = 1
}

variable "backend_container_port" {
  description = "Port the backend container listens on."
  type        = number
  default     = 8000
}

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
variable "db_instance_class" {
  description = "RDS instance class. db.t4g.micro is free-tier eligible for the first year."
  type        = string
  default     = "db.t4g.micro"
}

variable "db_allocated_storage" {
  description = "RDS allocated storage in GB."
  type        = number
  default     = 20
}

variable "db_name" {
  description = "RDS database name."
  type        = string
  default     = "agentforge"
}

variable "db_username" {
  description = "RDS master username."
  type        = string
  default     = "agentforge"
}

# ---------------------------------------------------------------------------
# Application secrets (passed to ECS via Secrets Manager).
# Default values are placeholders â CI / operator overrides them.
# Never commit real values to terraform.tfvars.
# ---------------------------------------------------------------------------
variable "app_secret_values" {
  description = "Map of application secret values stored in Secrets Manager."
  type = object({
    SECRET_KEY              = string
    GOOGLE_API_KEY          = string
    GROQ_API_KEY            = string
    TAVILY_API_KEY          = string
    LANGCHAIN_API_KEY       = string
    E2B_API_KEY             = string
    UPSTASH_REDIS_REST_URL  = string
    UPSTASH_REDIS_REST_TOKEN = string
  })
  sensitive = true
}

variable "allowed_origins" {
  description = "CORS allow-list passed to the backend as ALLOWED_ORIGINS."
  type        = list(string)
  default     = []
}

# ---------------------------------------------------------------------------
# CI/CD (GitHub OIDC trust)
# ---------------------------------------------------------------------------
variable "github_owner" {
  description = "GitHub org/user that owns the repo (for OIDC trust)."
  type        = string
}

variable "github_repo" {
  description = "GitHub repo name (without owner)."
  type        = string
  default     = "agentforge"
}

# ---------------------------------------------------------------------------
# Frontend (Amplify)
# ---------------------------------------------------------------------------
variable "amplify_repository_url" {
  description = "https://github.com/<owner>/<repo> URL for Amplify to track. Empty disables the frontend module."
  type        = string
  default     = ""
}

variable "amplify_branch" {
  description = "Branch Amplify should deploy from."
  type        = string
  default     = "main"
}

variable "amplify_github_token" {
  description = "GitHub personal access token with repo:read scope. Used by Amplify to clone the repo. Pass via TF_VAR_amplify_github_token, never commit."
  type        = string
  default     = ""
  sensitive   = true
}
