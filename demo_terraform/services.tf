resource "aws_ecs_service" "login_service" {
  task_definition = aws_ecs_task_definition.login_task.arn
}

resource "aws_ecs_task_definition" "login_task" {
  environment = aws_db_instance.customer_database.address
}

resource "aws_ecs_service" "payment_service" {
  task_definition = aws_ecs_task_definition.payment_task.arn
}

resource "aws_ecs_task_definition" "payment_task" {
  environment = aws_db_instance.customer_database.address
}

resource "aws_ecs_service" "profile_service" {
  task_definition = aws_ecs_task_definition.profile_task.arn
}

resource "aws_ecs_task_definition" "profile_task" {
  environment = aws_db_instance.customer_database.address
}
