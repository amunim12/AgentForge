output "backend_url" {
  description = "Public URL of the backend ALB."
  value       = "http://${module.ecs.alb_dns_name}"
}

output "backend_ws_url" {
  description = "WebSocket URL of the backend ALB."
  value       = "ws://${module.ecs.alb_dns_name}"
}

output "ecr_repository_url" {
  description = "ECR repository URL for the backend image."
  value       = module.ecr.repository_url
}

output "ecs_cluster_name" {
  description = "ECS cluster name (used by deploy workflow to force new deployment)."
  value       = module.ecs.cluster_name
}

output "ecs_service_name" {
  description = "ECS service name."
  value       = module.ecs.service_name
}

output "github_actions_role_arn" {
  description = "IAM role ARN that GitHub Actions assumes via OIDC."
  value       = module.iam.github_actions_role_arn
}

output "rds_endpoint" {
  description = "RDS Postgres endpoint (host:port)."
  value       = module.rds.endpoint
  sensitive   = true
}

output "amplify_app_url" {
  description = "Default Amplify-hosted frontend URL (empty if frontend module disabled)."
  value       = try(module.frontend[0].default_domain, "")
}
