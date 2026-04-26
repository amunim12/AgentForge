variable "name"                  { type = string }
variable "vpc_id"                { type = string }
variable "private_subnet_ids"    { type = list(string) }
variable "app_security_group_id" { type = string }
variable "instance_class"        { type = string }
variable "allocated_storage"     { type = number }
variable "database_name"         { type = string }
variable "master_username"       { type = string }
