resource "aws_vpc" "nilepay_vpc" {
  cidr_block = "10.0.0.0/16"
}

resource "aws_subnet" "private_a" {
  vpc_id = aws_vpc.nilepay_vpc.id
}
