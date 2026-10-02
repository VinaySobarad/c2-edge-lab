locals {
  ssm_interface_services = toset(["ssm", "ssmmessages", "ec2messages"])
}

resource "aws_vpc_endpoint" "ssm" {
  for_each = local.ssm_interface_services

  vpc_id              = aws_vpc.lab.id
  service_name        = "com.amazonaws.${data.aws_region.current.name}.${each.value}"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = [aws_subnet.private.id]
  security_group_ids  = [aws_security_group.endpoints.id]
  private_dns_enabled = true

  tags = {
    Name = "${var.name_prefix}-${each.value}"
  }
}
