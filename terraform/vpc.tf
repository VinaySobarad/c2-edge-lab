data "aws_availability_zones" "available" {
  state = "available"
  filter {
    name   = "opt-in-status"
    values = ["opt-in-not-required"]
  }
}

locals {
  lab_az          = var.availability_zone != "" ? var.availability_zone : data.aws_availability_zones.available.names[0]
  public_newbits  = tonumber(split("/", var.public_subnet_cidr)[1]) - tonumber(split("/", var.vpc_cidr)[1])
  private_newbits = tonumber(split("/", var.private_subnet_cidr)[1]) - tonumber(split("/", var.vpc_cidr)[1])
}

check "subnets_inside_vpc" {
  assert {
    condition = (
      local.public_newbits >= 0 && local.public_newbits <= 12 &&
      local.private_newbits >= 0 && local.private_newbits <= 12 &&
      contains([for i in range(pow(2, local.public_newbits)) : cidrsubnet(var.vpc_cidr, local.public_newbits, i)], var.public_subnet_cidr) &&
      contains([for i in range(pow(2, local.private_newbits)) : cidrsubnet(var.vpc_cidr, local.private_newbits, i)], var.private_subnet_cidr)
    )
    error_message = "public_subnet_cidr and private_subnet_cidr must sit entirely inside vpc_cidr."
  }
}

resource "aws_vpc" "lab" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = {
    Name = "${var.name_prefix}-vpc"
  }
}

# CIS: default SG allows all intra-VPC traffic. Close it; instances use named SGs.
resource "aws_default_security_group" "lab" {
  vpc_id = aws_vpc.lab.id

  tags = {
    Name = "${var.name_prefix}-default-closed"
  }
}

resource "aws_internet_gateway" "lab" {
  vpc_id = aws_vpc.lab.id

  tags = {
    Name = "${var.name_prefix}-igw"
  }
}

resource "aws_subnet" "public" {
  vpc_id                  = aws_vpc.lab.id
  cidr_block              = var.public_subnet_cidr
  availability_zone       = local.lab_az
  map_public_ip_on_launch = true

  tags = {
    Name = "${var.name_prefix}-public"
    Tier = "public"
  }
}

resource "aws_subnet" "private" {
  vpc_id                  = aws_vpc.lab.id
  cidr_block              = var.private_subnet_cidr
  availability_zone       = local.lab_az
  map_public_ip_on_launch = false

  tags = {
    Name = "${var.name_prefix}-private"
    Tier = "private"
  }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.lab.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.lab.id
  }

  tags = {
    Name = "${var.name_prefix}-public"
  }
}

resource "aws_route_table" "private" {
  vpc_id = aws_vpc.lab.id

  tags = {
    Name = "${var.name_prefix}-private"
  }
}

resource "aws_route_table_association" "public" {
  subnet_id      = aws_subnet.public.id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table_association" "private" {
  subnet_id      = aws_subnet.private.id
  route_table_id = aws_route_table.private.id
}

data "aws_iam_policy_document" "s3_endpoint" {
  statement {
    sid    = "TeamserverStageGet"
    effect = "Allow"

    principals {
      type        = "*"
      identifiers = ["*"]
    }

    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.decoy.arn}/${local.stage_key_prefix}/*"]
  }
}

# Private subnet has no NAT. S3 gateway lets the teamserver pull a staged C2 binary.
resource "aws_vpc_endpoint" "s3" {
  vpc_id            = aws_vpc.lab.id
  service_name      = "com.amazonaws.${data.aws_region.current.name}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = [aws_route_table.private.id]
  policy            = data.aws_iam_policy_document.s3_endpoint.json

  tags = {
    Name = "${var.name_prefix}-s3"
  }
}
