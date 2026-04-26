variable "name"                   { type = string }
variable "aws_region"             { type = string }
variable "account_id"             { type = string }
variable "github_owner"           { type = string }
variable "github_repo"            { type = string }
variable "ecr_repository_arn"     { type = string }
variable "db_password_secret_arn" { type = string }

variable "app_secret_arns" {
  type        = map(string)
  description = "env-var name â secret ARN."
}
