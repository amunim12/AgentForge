variable "name"                  { type = string }
variable "aws_region"            { type = string }
variable "vpc_id"                { type = string }
variable "public_subnet_ids"     { type = list(string) }
variable "private_subnet_ids"    { type = list(string) }
variable "alb_security_group_id" { type = string }
variable "ecs_security_group_id" { type = string }

variable "image_uri"      { type = string }
variable "task_cpu"       { type = number }
variable "task_memory"    { type = number }
variable "desired_count"  { type = number }
variable "container_port" { type = number }

variable "task_execution_role_arn" { type = string }
variable "task_role_arn"           { type = string }

variable "database_url_ssm_secret_arn" { type = string }

variable "app_secret_arns" {
  type = map(string)
}

variable "allowed_origins" {
  type = list(string)
}
