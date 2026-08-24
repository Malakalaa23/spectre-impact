# terraform/risky_db.tf – Risky database configuration
resource "aws_db_instance" "risky_db" {
  engine         = "postgres"
  instance_class = "db.t3.medium"
  name           = "production_db"
  username       = "admin"
  password       = "HardcodedPassword123!"
  publicly_accessible = true
  backup_retention_period = 0
}
