output "decoy_url" {
  description = "HTTPS URL of the S3 decoy via CloudFront (custom domain or dxxxx.cloudfront.net)."
  value       = "https://${local.edge_hostname}/"
}

output "callback_example" {
  description = "Short-haul callback URL on the nginx origin (needs header + allowed UA)."
  value       = "https://${local.edge_hostname}${local.short_callback_prefix}"
}

output "callback_probe_path" {
  description = "Path make lab-verify hits on the short-haul hostname."
  value       = local.short_probe_path
}

output "longhaul_url" {
  description = "Second CloudFront hostname (long-haul). Survives a short-haul hostname burn."
  value       = "https://${aws_cloudfront_distribution.longhaul.domain_name}/"
}

output "longhaul_callback_example" {
  description = "Long-haul callback path on the second hostname."
  value       = "https://${aws_cloudfront_distribution.longhaul.domain_name}${local.long_callback_prefix}"
}

output "longhaul_probe_path" {
  description = "Path make lab-verify-longhaul hits on the long-haul hostname."
  value       = local.long_probe_path
}

output "longhaul_distribution_id" {
  description = "Long-haul distribution. Do not -replace this when burning the short-haul hostname."
  value       = aws_cloudfront_distribution.longhaul.id
}

output "uses_custom_domain" {
  description = "True when ACM + Route 53 alias are enabled."
  value       = local.use_custom_domain
}

output "cloudfront_domain_name" {
  description = "CloudFront domain (dxxxxx.cloudfront.net)."
  value       = aws_cloudfront_distribution.edge.domain_name
}

output "cloudfront_distribution_id" {
  description = "Distribution id."
  value       = aws_cloudfront_distribution.edge.id
}

output "decoy_bucket_name" {
  description = "Private decoy bucket. Not a website endpoint."
  value       = aws_s3_bucket.decoy.id
}

output "decoy_bucket_arn" {
  description = "Decoy bucket ARN."
  value       = aws_s3_bucket.decoy.arn
}

output "acm_certificate_arn" {
  description = "ACM certificate ARN when a custom domain is set; otherwise null."
  value       = local.use_custom_domain ? aws_acm_certificate.edge[0].arn : null
}

output "vpc_id" {
  description = "Lab VPC."
  value       = aws_vpc.lab.id
}

output "public_subnet_id" {
  description = "Public subnet (redirector + EIP)."
  value       = aws_subnet.public.id
}

output "private_subnet_id" {
  description = "Private subnet (teamserver + SSM endpoints)."
  value       = aws_subnet.private.id
}

output "redirector_security_group_id" {
  description = "Redirector SG. Ingress 80 from CloudFront prefix list only."
  value       = aws_security_group.redirector.id
}

output "teamserver_security_group_id" {
  description = "Teamserver SG. No inbound from the internet."
  value       = aws_security_group.teamserver.id
}

output "cloudfront_prefix_list_id" {
  description = "Managed prefix list used on redirector :80."
  value       = data.aws_ec2_managed_prefix_list.cloudfront.id
}

output "redirector_instance_id" {
  description = "Redirector EC2 id (SSM target)."
  value       = aws_instance.redirector.id
}

output "teamserver_instance_id" {
  description = "Teamserver EC2 id (SSM target)."
  value       = aws_instance.teamserver.id
}

output "teamserver_private_ip" {
  description = "nginx proxy_pass target. Not a public address."
  value       = aws_instance.teamserver.private_ip
}

output "redirector_eip" {
  description = "Redirector origin IP (CloudFront → nginx). Changes on identity burn. Implants use CloudFront, not this."
  value       = aws_eip.redirector.public_ip
}

output "redirector_eip_allocation_id" {
  description = "EIP allocation id. Changes when aws_eip.redirector is replaced."
  value       = aws_eip.redirector.id
}

output "burn_replace_addresses" {
  description = "Redirector identity to -replace: new VM + new EIP. CloudFront origin follows. S3 and the CF hostname stay."
  value = [
    "aws_instance.redirector",
    "aws_eip.redirector",
  ]
}

output "burn_hostname_address" {
  description = "Short-haul CloudFront distribution. -replace this for a new dxxxx.cloudfront.net. Long-haul stays."
  value       = "aws_cloudfront_distribution.edge"
}

output "ssm_redirector" {
  description = "Session Manager command for the redirector. No SSH."
  value       = "aws ssm start-session --target ${aws_instance.redirector.id}"
}

output "ssm_teamserver" {
  description = "Session Manager command for the teamserver. No SSH."
  value       = "aws ssm start-session --target ${aws_instance.teamserver.id}"
}

output "ssm_cs_port_forward" {
  description = "Copy-paste: CS client 50050 on localhost. Never open 50050 on the SG."
  value       = "aws ssm start-session --target ${aws_instance.teamserver.id} --document-name AWS-StartPortForwardingSession --parameters '{\"portNumber\":[\"50050\"],\"localPortNumber\":[\"50050\"]}'"
}

output "ssm_sliver_port_forward" {
  description = "Copy-paste: Sliver multiplayer 31337 on localhost. Never open 31337 on the SG."
  value       = "aws ssm start-session --target ${aws_instance.teamserver.id} --document-name AWS-StartPortForwardingSession --parameters '{\"portNumber\":[\"31337\"],\"localPortNumber\":[\"31337\"]}'"
}

output "stage_prefix" {
  description = "S3 URI prefix the teamserver may GetObject. make c2-push writes here."
  value       = "s3://${aws_s3_bucket.decoy.id}/${local.stage_key_prefix}/"
}

output "stage_key_prefix" {
  description = "Object-key prefix inside the decoy bucket for staged binaries."
  value       = local.stage_key_prefix
}

output "pull_root" {
  description = "Directory on the teamserver where s3_pull.py writes. make c2-push uses this."
  value       = local.pull_root
}

output "agent_lib_dir" {
  description = "Directory on the teamserver that holds s3_pull.py. make c2-push uses this."
  value       = local.agent_lib_dir
}

output "callback_user_agent" {
  description = "Exact User-Agent the nginx gate allows. From policy YAML."
  value       = local.policy.user_agents.allow_exact[0]
}

output "echo_body" {
  description = "Body the teamserver echo returns. make lab-verify expects this."
  value       = local.echo_body
}

output "callback_header_name" {
  description = "Header clients must send. Not the secret."
  value       = var.callback_header_name
}

output "lab_header_value" {
  description = "Gate token. Sensitive. Do not print in CI logs."
  value       = random_password.lab_header.result
  sensitive   = true
}
