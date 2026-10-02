resource "aws_instance" "teamserver" {
  ami                         = data.aws_ssm_parameter.ubuntu_noble.value
  instance_type               = var.instance_type
  subnet_id                   = aws_subnet.private.id
  vpc_security_group_ids      = [aws_security_group.teamserver.id]
  iam_instance_profile        = aws_iam_instance_profile.teamserver.name
  associate_public_ip_address = false
  user_data_replace_on_change = true

  # Gzip keeps the 16 KiB user-data cap off the critical path (raw render is ~13 KiB today).
  user_data_base64 = base64gzip(local.teamserver_user_data)

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
    Name = "${var.name_prefix}-teamserver"
    Role = "teamserver"
  }

  depends_on = [
    aws_vpc_endpoint.ssm,
    aws_vpc_endpoint.s3,
    aws_iam_role_policy_attachment.teamserver_ssm_core,
    aws_iam_role_policy.s3_stage,
  ]
}
