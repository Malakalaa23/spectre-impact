resource "aws_db_instance" "risky" {
  engine         = "mysql"
  instance_class = "db.t3.micro"
  name           = "risky_db"
  username       = "admin"
  password       = "hardcoded_password"
  publicly_accessible = true
  backup_retention_period = 0
  storage_encrypted = false
}
