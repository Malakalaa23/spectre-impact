"""
make_demo_terraform.py — Write the 4 demo .tf files for the parser demo.

Run once:
    python make_demo_terraform.py

Safe to re-run — it overwrites the files with the same content.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent / "demo_terraform"
ROOT.mkdir(exist_ok=True)


NETWORK_TF = '''# Networking layer. Everything else sits on top of these resources.
# They have no dependencies of their own, so they show up as roots
# in the parsed graph.

resource "aws_vpc" "nilepay_vpc" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = {
    Name  = "nilepay-vpc"
    Owner = "platform-team"
  }
}

resource "aws_subnet" "private_a" {
  vpc_id            = aws_vpc.nilepay_vpc.id
  cidr_block        = "10.0.1.0/24"
  availability_zone = "eu-west-2a"
}

resource "aws_security_group" "app_sg" {
  name        = "nilepay-app"
  description = "Application security group"
  vpc_id      = aws_vpc.nilepay_vpc.id
}
'''


CUSTOMER_DATABASE_TF = '''# Primary customer data store. Everything customer-facing sits on top
# of this. Changes here have the widest blast radius in the stack.

resource "aws_db_instance" "customer_database" {
  engine               = "postgres"
  engine_version       = "15.4"
  instance_class       = "db.r6g.xlarge"
  allocated_storage    = 500
  storage_encrypted    = true
  db_subnet_group_name = "nilepay-private"

  tags = {
    Name     = "customer-database"
    Owner    = "backend-team"
    Critical = "true"
  }
}

resource "aws_elasticache_cluster" "session_cache" {
  engine            = "redis"
  engine_version    = "7.0"
  node_type         = "cache.r6g.large"
  num_cache_nodes   = 1
  subnet_group_name = "nilepay-cache"

  tags = {
    Name  = "session-cache"
    Owner = "backend-team"
  }
}
'''


SERVICES_TF = '''# Application services. Each one references the database or the cache
# through implicit attribute lookups (inside container_definitions),
# which the parser resolves into graph edges.

resource "aws_ecs_service" "login_service" {
  name            = "login-service"
  desired_count   = 4
  task_definition = aws_ecs_task_definition.login_task.arn

  tags = {
    Name  = "login-service"
    Owner = "identity-team"
  }
}

resource "aws_ecs_task_definition" "login_task" {
  family = "login-service"
  cpu    = "1024"
  memory = "2048"

  container_definitions = jsonencode([
    {
      name  = "login"
      image = "nilepay/login:latest"
      environment = [
        {
          name  = "DB_HOST"
          value = aws_db_instance.customer_database.address
        },
        {
          name  = "CACHE_URL"
          value = aws_elasticache_cluster.session_cache.cache_nodes[0].address
        }
      ]
    }
  ])
}

resource "aws_ecs_service" "payment_service" {
  name            = "payment-service"
  desired_count   = 6
  task_definition = aws_ecs_task_definition.payment_task.arn

  tags = {
    Name  = "payment-service"
    Owner = "payments-team"
  }
}

resource "aws_ecs_task_definition" "payment_task" {
  family = "payment-service"
  cpu    = "2048"
  memory = "4096"

  container_definitions = jsonencode([
    {
      name  = "payment"
      image = "nilepay/payment:latest"
      environment = [
        {
          name  = "DB_HOST"
          value = aws_db_instance.customer_database.address
        },
        {
          name  = "CACHE_URL"
          value = aws_elasticache_cluster.session_cache.cache_nodes[0].address
        }
      ]
    }
  ])
}

resource "aws_ecs_service" "profile_service" {
  name            = "profile-service"
  desired_count   = 3
  task_definition = aws_ecs_task_definition.profile_task.arn
}

resource "aws_ecs_task_definition" "profile_task" {
  family = "profile-service"
  cpu    = "512"
  memory = "1024"

  container_definitions = jsonencode([
    {
      name  = "profile"
      image = "nilepay/profile:latest"
      environment = [
        {
          name  = "DB_HOST"
          value = aws_db_instance.customer_database.address
        }
      ]
    }
  ])
}
'''


FRONTEND_TF = '''# Customer-facing edge. Depends on the services below it, which depend
# on the database. This is the full chain judges will see when they ask
# "what breaks if customer_database changes?"

resource "aws_lb" "api_gateway" {
  name               = "nilepay-api"
  internal           = false
  load_balancer_type = "application"

  # The load balancer sits in front of these services. Declared
  # explicitly because target-group wiring lives elsewhere.
  depends_on = [
    aws_ecs_service.login_service,
    aws_ecs_service.payment_service,
  ]

  tags = {
    Name  = "api-gateway"
    Owner = "platform-team"
  }
}

resource "aws_cloudfront_distribution" "web_frontend" {
  enabled = true

  origin {
    domain_name = aws_lb.api_gateway.dns_name
    origin_id   = "api-gateway"
  }

  tags = {
    Name           = "web-frontend"
    CustomerFacing = "true"
  }
}
'''


FILES = {
    "network.tf": NETWORK_TF,
    "customer_database.tf": CUSTOMER_DATABASE_TF,
    "services.tf": SERVICES_TF,
    "frontend.tf": FRONTEND_TF,
}


def main() -> None:
    for name, content in FILES.items():
        path = ROOT / name
        # encoding="utf-8" with no BOM — Path.write_text uses the
        # default platform encoding, so we pass it explicitly.
        path.write_text(content, encoding="utf-8", newline="\n")
        size = path.stat().st_size
        print(f"  wrote {name:<24} {size:>5} bytes")

    print()
    print(f"Directory: {ROOT}")
    print(f"Files written: {len(FILES)}")


if __name__ == "__main__":
    main()