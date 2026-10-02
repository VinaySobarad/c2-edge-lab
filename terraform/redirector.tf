data "aws_ssm_parameter" "ubuntu_noble" {
  name = "/aws/service/canonical/ubuntu/server/24.04/stable/current/amd64/hvm/ebs-gp3/ami-id"
}

resource "random_password" "lab_header" {
  length  = 32
  special = false
}

locals {
  nginx_conf = replace(
    replace(
      local.nginx_in,
      var.nginx_backend_placeholder,
      aws_instance.teamserver.private_ip,
    ),
    var.nginx_header_placeholder,
    random_password.lab_header.result,
  )
}

# Identity burn: terraform apply -replace=aws_instance.redirector -replace=aws_eip.redirector
# CloudFront origin is this public_ip, so replacing the EIP updates the origin.
# Association (not instance =) lets the allocation die without deleting the VM resource graph by accident.
resource "aws_eip" "redirector" {
  domain = "vpc"

  tags = {
    Name = "${var.name_prefix}-redirector"
  }

  depends_on = [aws_internet_gateway.lab]
}

# Do not set create_before_destroy: one EIP cannot bind two instances.
resource "aws_instance" "redirector" {
  ami                         = data.aws_ssm_parameter.ubuntu_noble.value
  instance_type               = var.instance_type
  subnet_id                   = aws_subnet.public.id
  vpc_security_group_ids      = [aws_security_group.redirector.id]
  iam_instance_profile        = aws_iam_instance_profile.ssm.name
  associate_public_ip_address = true
  user_data_replace_on_change = true

  user_data = templatefile("${path.module}/user_data/redirector.sh.tftpl", {
    nginx_conf_base64 = base64encode(local.nginx_conf)
    decoy_html_base64 = base64encode(file("${path.module}/../decoy/index.html"))
  })

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
    instance_metadata_tags      = "disabled"
  }

  root_block_device {
    encrypted   = true
    volume_type = var.root_volume_type
    volume_size = var.root_volume_size
  }

  tags = {
    Name = "${var.name_prefix}-redirector"
    Role = "redirector"
  }

  depends_on = [
    aws_internet_gateway.lab,
    aws_iam_role_policy_attachment.ssm_core,
  ]
}

resource "aws_eip_association" "redirector" {
  instance_id   = aws_instance.redirector.id
  allocation_id = aws_eip.redirector.id
}
