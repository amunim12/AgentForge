data "aws_caller_identity" "current" {}

locals {
  account_id = data.aws_caller_identity.current.account_id
  name       = "${var.project_name}-${var.environment}"
}

module "network" {
  source = "./modules/network"

  name                    = local.name
  vpc_cidr                = var.vpc_cidr
  availability_zone_count = var.availability_zone_count
}

module "ecr" {
  source = "./modules/ecr"

  name = "${local.name}-backend"
}

module "secrets" {
  source = "./modules/secrets"

  name              = local.name
  app_secret_values = var.app_secret_values
}

module "rds" {
  source = "./modules/rds"

  name                  = local.name
  vpc_id                = module.network.vpc_id
  private_subnet_ids    = module.network.private_subnet_ids
  app_security_group_id = module.network.ecs_security_group_id
  instance_class        = var.db_instance_class
  allocated_storage     = var.db_allocated_storage
  database_name         = var.db_name
  master_username       = var.db_username
}

module "iam" {
  source = "./modules/iam"

  name                  = local.name
  aws_region            = var.aws_region
  account_id            = local.account_id
  github_owner          = var.github_owner
  github_repo           = var.github_repo
  app_secret_arns       = module.secrets.app_secret_arns
  db_password_secret_arn = module.rds.master_password_secret_arn
  ecr_repository_arn    = module.ecr.repository_arn
}

module "ecs" {
  source = "./modules/ecs"

  name                  = local.name
  aws_region            = var.aws_region
  vpc_id                = module.network.vpc_id
  public_subnet_ids     = module.network.public_subnet_ids
  private_subnet_ids    = module.network.private_subnet_ids
  alb_security_group_id = module.network.alb_security_group_id
  ecs_security_group_id = module.network.ecs_security_group_id

  image_uri          = "${module.ecr.repository_url}:${var.backend_image_tag}"
  task_cpu           = var.backend_cpu
  task_memory        = var.backend_memory
  desired_count      = var.backend_desired_count
  container_port     = var.backend_container_port

  task_execution_role_arn = module.iam.task_execution_role_arn
  task_role_arn           = module.iam.task_role_arn

  database_url_ssm_secret_arn = module.rds.database_url_secret_arn
  app_secret_arns             = module.secrets.app_secret_arns
  allowed_origins             = var.allowed_origins
}

module "frontend" {
  count  = var.amplify_repository_url == "" ? 0 : 1
  source = "./modules/frontend"

  name              = "${local.name}-web"
  repository_url    = var.amplify_repository_url
  branch            = var.amplify_branch
  github_token      = var.amplify_github_token
  backend_api_url   = "https://${module.ecs.alb_dns_name}"
  backend_ws_url    = "wss://${module.ecs.alb_dns_name}"
}
