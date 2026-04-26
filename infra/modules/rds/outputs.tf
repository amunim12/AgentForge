output "endpoint"                   { value = aws_db_instance.this.endpoint }
output "master_password_secret_arn" { value = aws_secretsmanager_secret.master_password.arn }
output "database_url_secret_arn"    { value = aws_secretsmanager_secret.database_url.arn }
