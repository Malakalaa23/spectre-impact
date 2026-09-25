resource "aws_lb" "api_gateway" {
  depends_on = [aws_ecs_service.login_service]
}

resource "aws_cloudfront_distribution" "web_frontend" {
  origin { domain_name = aws_lb.api_gateway.dns_name }
}
