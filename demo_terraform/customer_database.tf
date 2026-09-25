resource "aws_db_instance" "customer_database" {
  engine = "postgres"
}

resource "aws_elasticache_cluster" "session_cache" {
  engine = "redis"
}
