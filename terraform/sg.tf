data "aws_region" "current" {}

data "aws_ec2_managed_prefix_list" "cloudfront" {
  name = "com.amazonaws.global.cloudfront.origin-facing"
}

# Gateway endpoints route to S3's public prefix list, not to VPC CIDRs.
data "aws_ec2_managed_prefix_list" "s3" {
  name = "com.amazonaws.${data.aws_region.current.name}.s3"
}

resource "aws_security_group" "endpoints" {
  name        = "${var.name_prefix}-ssm-endpoints"
  description = "HTTPS to SSM interface endpoints. No SSH."
  vpc_id      = aws_vpc.lab.id

  ingress {
    description = "Instances in this VPC to SSM APIs"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = [aws_vpc.lab.cidr_block]
  }

  egress {
    description = "VPC DNS"
    from_port   = 53
    to_port     = 53
    protocol    = "udp"
    cidr_blocks = [aws_vpc.lab.cidr_block]
  }

  egress {
    description = "AWS service prefix (interface endpoint)"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.name_prefix}-ssm-endpoints"
  }
}

# Redirector must not reference the teamserver SG (cycle). Egress to the private
# subnet CIDR is enough: only the teamserver lives there.
resource "aws_security_group" "redirector" {
  name        = "${var.name_prefix}-redirector"
  description = "nginx origin. HTTP from CloudFront prefix list only. No SSH."
  vpc_id      = aws_vpc.lab.id

  ingress {
    description     = "CloudFront origin-facing prefix list"
    from_port       = 80
    to_port         = 80
    protocol        = "tcp"
    prefix_list_ids = [data.aws_ec2_managed_prefix_list.cloudfront.id]
  }

  egress {
    description = "apt over HTTP (Ubuntu archive URIs are http://)"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "SSM agent and apt over HTTPS"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "VPC DNS"
    from_port   = 53
    to_port     = 53
    protocol    = "udp"
    cidr_blocks = [aws_vpc.lab.cidr_block]
  }

  egress {
    description = "VPC DNS TCP"
    from_port   = 53
    to_port     = 53
    protocol    = "tcp"
    cidr_blocks = [aws_vpc.lab.cidr_block]
  }

  egress {
    description = "Proxy to teamserver in the private subnet"
    from_port   = var.teamserver_listen_port
    to_port     = var.teamserver_listen_port
    protocol    = "tcp"
    cidr_blocks = [aws_subnet.private.cidr_block]
  }

  tags = {
    Name = "${var.name_prefix}-redirector"
  }
}

resource "aws_security_group" "teamserver" {
  name        = "${var.name_prefix}-teamserver"
  description = "Private teamserver. Ingress from redirector only. No SSH. No NAT."
  vpc_id      = aws_vpc.lab.id

  ingress {
    description     = "Gated callbacks from the redirector"
    from_port       = var.teamserver_listen_port
    to_port         = var.teamserver_listen_port
    protocol        = "tcp"
    security_groups = [aws_security_group.redirector.id]
  }

  egress {
    description = "HTTPS to SSM VPC endpoints"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = [aws_vpc.lab.cidr_block]
  }

  egress {
    description     = "HTTPS to S3 via the gateway endpoint (public S3 prefix list)"
    from_port       = 443
    to_port         = 443
    protocol        = "tcp"
    prefix_list_ids = [data.aws_ec2_managed_prefix_list.s3.id]
  }

  egress {
    description = "VPC DNS"
    from_port   = 53
    to_port     = 53
    protocol    = "udp"
    cidr_blocks = [aws_vpc.lab.cidr_block]
  }

  egress {
    description = "VPC DNS TCP"
    from_port   = 53
    to_port     = 53
    protocol    = "tcp"
    cidr_blocks = [aws_vpc.lab.cidr_block]
  }

  tags = {
    Name = "${var.name_prefix}-teamserver"
  }
}
