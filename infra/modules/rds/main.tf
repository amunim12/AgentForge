resource "random_password" "master" {
  length           = 32
  special          = true
  override_special = "!#$%&*()-_=+[]{}<>:?"
}

resource "aws_db_subnet_group" "this" {
  name       = "${var.name}-db-subnets"
  subnet_ids = var.private_subnet_ids

  tags = { Name = "${var.name}-db-subnets" }
}

resource "aws_security_group" "db" {
  name        = "${var.name}-db-sg"
  description = "RDS Postgres ingress from ECS only"
  vpc_id      = var.vpc_id

  ingress {
    description     = "Postgres from ECS tasks"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [var.app_security_group_id]
  }

  egress {
    description = "All egress"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${var.name}-db-sg" }
}

resource "aws_db_instance" "this" {
  identifier              = "${var.name}-db"
  engine                  = "postgres"
  engine_version          = "16.3"
  instance_class          = var.instance_class
  allocated_storage       = var.allocated_storage
  max_allocated_storage   = var.allocated_storage * 4
  storage_type            = "gp3"
  storage_encrypted       = true

  db_name                 = var.database_name
  username                = var.master_username
  password                = random_password.master.result
  port                    = 5432

  db_subnet_group_name    = aws_db_subnet_group.this.name
  vpc_security_group_ids  = [aws_security_group.db.id]
  publicly_accessible     = false
  multi_az                = false

  backup_retention_period   = 7
  delete_automated_backups  = true
  skip_final_snapshot       = true   # portfolio: bump to false in real prod
  deletion_protection       = false  # portfolio: bump to true in real prod

  performance_insights_enabled = false
  auto_minor_version_upgrade   = true

  tags = { Name = "${var.name}-db" }
}

# Stash the password as a Secrets Manager secret so the app can pull it
# at task-launch time without it ever being interpolated into the task
# definition (which would land in CloudTrail).
resource "aws_secretsmanager_secret" "master_password" {
  name                    = "${var.name}/db/master-password"
  recovery_window_in_days = 0
}

resource "aws_secretsmanager_secret_version" "master_password" {
  secret_id     = aws_secretsmanager_secret.master_password.id
  secret_string = random_password.master.result
}

# Compose the SQLAlchemy URL once and store it as a separate secret. ECS
# wires this directly into DATABASE_URL.
resource "aws_secretsmanager_secret" "database_url" {
  name                    = "${var.name}/db/url"
  recovery_window_in_days = 0
}

resource "aws_secretsmanager_secret_version" "database_url" {
  secret_id = aws_secretsmanager_secret.database_url.id
  secret_string = format(
    "postgresql+asyncpg://%s:%s@%s:%d/%s",
    var.master_username,
    random_password.master.result,
    aws_db_instance.this.address,
    aws_db_instance.this.port,
    var.database_name,
  )
}
