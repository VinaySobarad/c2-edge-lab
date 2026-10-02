locals {
  common_tags = merge(
    {
      Project   = "c2-edge-lab"
      ManagedBy = "terraform"
      Component = "decoy-edge"
    },
    var.extra_tags,
  )

  decoy_origin_id      = "s3-decoy"
  redirector_origin_id = "redirector-eip"
  decoy_root           = "${path.module}/../decoy"

  # Content types for objects we ship. Keys must exist under decoy/.
  decoy_objects = {
    "index.html"  = "text/html; charset=utf-8"
    "robots.txt"  = "text/plain; charset=utf-8"
    "app.css"     = "text/css; charset=utf-8"
    "app.js"      = "text/javascript; charset=utf-8"
    "favicon.svg" = "image/svg+xml"
  }

  # Single contract for copy-in. IAM, bucket policy, SSM, and s3_pull.py all share this.
  stage_key_prefix = "stage"
  pull_root        = "/opt/c2"
  agent_lib_dir    = "/usr/local/lib/c2-edge-lab"
  echo_body        = "teamserver-ok"

  # CloudFront pattern "/cdn/*" → nginx/verify prefix "/cdn/".
  short_callback_prefix = trimsuffix(var.callback_path_patterns[0], "*")
  long_callback_prefix  = trimsuffix(var.longhaul_path_patterns[0], "*")
  short_probe_path      = "${local.short_callback_prefix}probe"
  long_probe_path       = "${local.long_callback_prefix}probe"

  teamserver_user_data = templatefile("${path.module}/user_data/teamserver.sh.tftpl", {
    listen_port   = var.teamserver_listen_port
    s3_pull_b64   = base64encode(file("${path.module}/../src/c2_edge_lab/s3_pull.py"))
    pull_root     = local.pull_root
    agent_lib_dir = local.agent_lib_dir
    echo_body     = local.echo_body
  })

  policy = yamldecode(file("${path.module}/../policy/redirector.policy.yaml"))

  nginx_in         = file("${path.module}/templates/redirector.conf.in")
  nginx_header_var = "http_${replace(lower(var.callback_header_name), "-", "_")}"

  use_custom_domain = var.domain_name != ""
  edge_hostname     = local.use_custom_domain ? var.domain_name : aws_cloudfront_distribution.edge.domain_name

  # CloudFront rejects a raw IP as origin_domain_name. The EIP still owns the
  # identity: AWS reverse-DNS for that address. Identity burn (new EIP) changes this.
  ec2_public_dns_suffix = (
    data.aws_region.current.name == "us-east-1"
    ? "compute-1.amazonaws.com"
    : "${data.aws_region.current.name}.compute.amazonaws.com"
  )
  redirector_origin_hostname = "ec2-${replace(aws_eip.redirector.public_ip, ".", "-")}.${local.ec2_public_dns_suffix}"
}
