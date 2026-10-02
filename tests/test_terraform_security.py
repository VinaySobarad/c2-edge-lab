from __future__ import annotations

from pathlib import Path

TERRAFORM = Path(__file__).resolve().parents[1] / "terraform"


def _read(name: str) -> str:
    return (TERRAFORM / name).read_text(encoding="utf-8")


def test_no_ssh_port_in_security_groups() -> None:
    terraform_text = "".join(path.read_text(encoding="utf-8") for path in TERRAFORM.glob("*.tf"))
    assert "from_port       = 22" not in terraform_text
    assert "from_port   = 22" not in terraform_text
    assert "to_port         = 22" not in terraform_text
    assert "to_port     = 22" not in terraform_text


def test_redirector_uses_cloudfront_prefix_list() -> None:
    security_groups = _read("sg.tf")
    assert "com.amazonaws.global.cloudfront.origin-facing" in security_groups
    assert "prefix_list_ids" in security_groups
    assert "from_port       = 80" in security_groups or "from_port   = 80" in security_groups


def test_ssm_interface_endpoints_are_declared() -> None:
    endpoints = _read("endpoints.tf")
    for service in ("ssm", "ssmmessages", "ec2messages"):
        assert service in endpoints
    assert "private_dns_enabled = true" in endpoints


def test_instances_require_imdsv2_and_have_no_ssh_key() -> None:
    combined = _read("redirector.tf") + _read("teamserver.tf")
    assert "http_tokens" in combined
    assert '"required"' in combined
    assert "key_name" not in combined
    assert "associate_public_ip_address = false" in _read("teamserver.tf")


def test_iam_stage_get_is_teamserver_only() -> None:
    iam = _read("iam.tf")
    assert "AmazonSSMManagedInstanceCore" in iam
    assert "AdministratorAccess" not in iam
    assert "s3:GetObject" in iam
    assert "local.stage_key_prefix" in iam
    assert "aws_iam_role.teamserver.id" in iam
    assert 'resource "aws_iam_instance_profile" "teamserver"' in iam
    assert "aws_iam_instance_profile.teamserver.name" in _read("teamserver.tf")
    assert "aws_iam_instance_profile.ssm.name" in _read("redirector.tf")


def test_placeholder_nginx_matches_renderer() -> None:
    from c2_edge_lab.nginx_render import render_snippet
    from c2_edge_lab.policy import load_policy

    policy = load_policy(TERRAFORM.parent / "policy" / "redirector.policy.yaml")
    expected = render_snippet(
        policy,
        backend_host="192.0.2.1",
        header_value="PLACEHOLDERHEADER",
    )
    committed = (TERRAFORM / "templates" / "redirector.conf.in").read_text(encoding="utf-8")
    assert committed == expected


def test_remote_state_bucket_is_not_in_git() -> None:
    backend = _read("backend.tf")
    assert 'backend "s3"' in backend
    assert "encrypt" in backend
    assert "use_lockfile" in backend
    example = (TERRAFORM / "config.s3.tfbackend.example").read_text(encoding="utf-8")
    assert "YOUR-TERRAFORM-STATE-BUCKET" in example
    root = TERRAFORM.parent
    leak = "my-terraform-state-bucket-" + "2026-lol-vinay"
    skip_dirs = {".venv", ".terraform", ".git", ".ruff_cache", ".pytest_cache"}
    skip_local = {".tfvars", ".tfbackend", ".tfplan"}
    for path in root.rglob("*"):
        if not path.is_file() or any(part in skip_dirs for part in path.parts):
            continue
        if path.name in {"backend.hcl", "terraform.rc"} or path.name.endswith(".tfvars.json"):
            continue
        if path.suffix in skip_local:
            continue
        if path.suffix in {".pyc", ".png", ".svg"}:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        assert leak not in text, f"state bucket leaked in {path.relative_to(root)}"


def test_cloudfront_split_origin_uses_managed_policies() -> None:
    cloudfront = _read("cloudfront.tf")
    terraform_text = "".join(path.read_text(encoding="utf-8") for path in TERRAFORM.glob("*.tf"))
    assert "redirector_origin_hostname" in cloudfront
    assert "aws_eip.redirector.public_ip" in _read("locals.tf")
    assert "origin_protocol_policy" in cloudfront
    assert "http-only" in cloudfront
    assert "origin_read_timeout" in cloudfront
    assert 'name = "Managed-CachingOptimized"' in cloudfront
    assert 'name = "Managed-CachingDisabled"' in cloudfront
    assert 'name = "Managed-AllViewer"' in cloudfront
    assert 'name = "Managed-SecurityHeadersPolicy"' in cloudfront
    assert "Managed-CORS-CustomOrigin" not in terraform_text
    assert "AllViewerExceptHostHeader" not in terraform_text
    assert "forwarded_values" not in cloudfront
    assert "ordered_cache_behavior" in cloudfront
    assert "aws_eip_association.redirector" in cloudfront
    assert "callback_path_patterns" in _read("variables.tf")
    assert "longhaul_path_patterns" in _read("variables.tf")
    assert 'resource "aws_cloudfront_distribution" "longhaul"' in cloudfront
    assert "aws_cloudfront_distribution.longhaul.arn" in _read("s3.tf")
    s3 = _read("s3.tf")
    assert "DenyCloudFrontStage" in s3
    assert 'for key in keys(local.decoy_objects)' in s3
    allow = s3.split("AllowCloudFrontReadViaOAC")[1].split("statement")[0]
    assert '"${aws_s3_bucket.decoy.arn}/*"' not in allow
    for uuid in (
        "59781a5b-3903-41f3-afcb-af62929ccde1",
        "216adef6-5c7f-47e4-b989-5492eafa07d3",
        "4135ea2d-6df8-44a3-9df3-4b5a84be39ad",
        "658327ea-f89d-4fab-a63d-7e88639e58f6",
        "67f7725c-6f97-4210-82d7-5512b31e9d03",
    ):
        assert uuid not in terraform_text


def test_s3_pull_is_copied_into_teamserver_user_data() -> None:
    teamserver = _read("teamserver.tf")
    locals_tf = _read("locals.tf")
    assert "s3_pull.py" in locals_tf
    assert "base64gzip" in teamserver
    assert "aws_vpc_endpoint.s3" in teamserver
    assert "stage_key_prefix" in locals_tf
    assert '"stage"' in locals_tf
    assert "pull_root" in locals_tf
    assert "agent_lib_dir" in locals_tf
    assert "echo_body" in locals_tf


def test_operator_knobs_are_variables() -> None:
    variables = _read("variables.tf")
    for name in (
        "acm_region",
        "vpc_cidr",
        "instance_type",
        "root_volume_type",
        "cloudfront_minimum_protocol_version",
        "nginx_backend_placeholder",
    ):
        assert f'variable "{name}"' in variables
    redirector = _read("redirector.tf")
    assert "var.root_volume_type" in redirector
    assert "var.nginx_backend_placeholder" in redirector
    assert "var.acm_region" in _read("providers.tf")
    assert "var.cloudfront_minimum_protocol_version" in _read("cloudfront.tf")


def test_custom_domain_is_optional() -> None:
    terraform_text = "".join(path.read_text(encoding="utf-8") for path in TERRAFORM.glob("*.tf"))
    assert "use_custom_domain" in terraform_text
    assert "cloudfront_default_certificate" in terraform_text
    assert "count = local.use_custom_domain ? 1 : 0" in _read("acm.tf")
    assert "count = local.use_custom_domain ? 1 : 0" in _read("dns.tf")
    assert 'default     = ""' in _read("variables.tf")


def test_private_route_table_has_no_nat() -> None:
    vpc = _read("vpc.tf")
    private_block = vpc.split('resource "aws_route_table" "private"')[1].split("resource ")[0]
    assert "nat_gateway" not in private_block
    assert "0.0.0.0/0" not in private_block
    assert "map_public_ip_on_launch = false" in vpc


def test_private_subnet_has_s3_gateway_not_nat() -> None:
    vpc = _read("vpc.tf")
    assert 'resource "aws_vpc_endpoint" "s3"' in vpc
    assert 'vpc_endpoint_type = "Gateway"' in vpc
    assert "nat_gateway" not in vpc
    assert "s3_endpoint" in vpc
    assert "local.stage_key_prefix" in vpc
    teamserver_sg = _read("sg.tf").split('resource "aws_security_group" "teamserver"')[1]
    assert "aws_ec2_managed_prefix_list.s3.id" in teamserver_sg
