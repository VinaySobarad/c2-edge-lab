"""Burn contract: new redirector VM + new EIP; CloudFront origin follows the EIP."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TERRAFORM = ROOT / "terraform"
MAKEFILE = ROOT / "Makefile"


def _resource_block(text: str, resource_type: str, name: str) -> str:
    needle = f'resource "{resource_type}" "{name}"'
    start = text.index(needle)
    rest = text[start + len(needle) :]
    depth = 0
    for index, char in enumerate(rest):
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return rest[: index + 1]
    raise AssertionError(f"unclosed resource {resource_type}.{name}")


def _target_body(makefile: str, name: str) -> str:
    lines = makefile.splitlines()
    start = None
    for index, line in enumerate(lines):
        if line.startswith(f"{name}:"):
            start = index + 1
            break
    if start is None:
        raise AssertionError(f"missing Makefile target {name}")
    body: list[str] = []
    for line in lines[start:]:
        if line and not line[0].isspace() and not line.startswith("#"):
            break
        body.append(line)
    return "\n".join(body)


def test_eip_allocation_is_not_tied_to_the_instance() -> None:
    redirector = (TERRAFORM / "redirector.tf").read_text(encoding="utf-8")
    eip = _resource_block(redirector, "aws_eip", "redirector")
    assert "instance =" not in eip
    assert "instance=" not in eip
    assert "network_interface" not in eip
    association = _resource_block(redirector, "aws_eip_association", "redirector")
    assert "instance_id   = aws_instance.redirector.id" in association
    assert "allocation_id = aws_eip.redirector.id" in association


def test_cloudfront_origin_follows_the_eip() -> None:
    cloudfront = (TERRAFORM / "cloudfront.tf").read_text(encoding="utf-8")
    locals_tf = (TERRAFORM / "locals.tf").read_text(encoding="utf-8")
    assert "redirector_origin_hostname" in cloudfront
    assert "aws_eip.redirector.public_ip" in locals_tf
    assert "aws_instance.redirector.public_ip" not in cloudfront
    assert "aws_instance.redirector.public_dns" not in cloudfront
    assert "aws_eip.redirector.public_ip" not in cloudfront


def test_redirector_resources_are_not_create_before_destroy() -> None:
    redirector = (TERRAFORM / "redirector.tf").read_text(encoding="utf-8")
    instance = _resource_block(redirector, "aws_instance", "redirector")
    eip = _resource_block(redirector, "aws_eip", "redirector")
    assert "create_before_destroy" not in instance
    assert "create_before_destroy" not in eip


def test_burn_makefile_replaces_instance_and_eip() -> None:
    makefile = MAKEFILE.read_text(encoding="utf-8")
    assert "BURN_INSTANCE := aws_instance.redirector" in makefile
    assert "BURN_EIP      := aws_eip.redirector" in makefile
    body = _target_body(makefile, "burn-redirector")
    assert "Refusing to apply" in body
    assert "-replace=$(BURN_INSTANCE)" in body
    assert "-replace=$(BURN_EIP)" in body
    for line in body.splitlines():
        command = line.lstrip().lstrip("@")
        if (
            command.startswith("echo")
            or command.startswith("exit")
            or command.startswith("#")
            or not command
        ):
            continue
        raise AssertionError(f"burn-redirector must not run: {command}")


def test_burn_outputs_name_the_identity_addresses() -> None:
    outputs = (TERRAFORM / "outputs.tf").read_text(encoding="utf-8")
    assert "burn_replace_addresses" in outputs
    assert '"aws_instance.redirector"' in outputs
    assert '"aws_eip.redirector"' in outputs
    assert 'output "burn_replace_address"' not in outputs
    assert "burn_hostname_address" in outputs
    assert "aws_cloudfront_distribution.edge" in outputs


def test_burn_hostname_makefile_replaces_only_short_haul() -> None:
    makefile = MAKEFILE.read_text(encoding="utf-8")
    assert "BURN_HOSTNAME := aws_cloudfront_distribution.edge" in makefile
    body = _target_body(makefile, "burn-hostname")
    assert "Refusing to apply" in body
    assert "-replace=$(BURN_HOSTNAME)" in body
    assert "longhaul" in body.lower() or "Long-haul" in body
    for line in body.splitlines():
        command = line.lstrip().lstrip("@")
        if (
            command.startswith("echo")
            or command.startswith("exit")
            or command.startswith("#")
            or not command
        ):
            continue
        raise AssertionError(f"burn-hostname must not run: {command}")


def test_c2_push_is_not_terraform_apply() -> None:
    makefile = MAKEFILE.read_text(encoding="utf-8")
    body = _target_body(makefile, "c2-push")
    assert "aws s3 cp" in body
    assert "AWS-RunShellScript" in body
    assert "s3_pull.py" in body
    assert "command-executed" in body
    assert "stage_key_prefix" in body
    assert "pull_root" in body
    assert "agent_lib_dir" in body
    assert "terraform apply" not in body


def test_verify_makefile_uses_terraform_probe_paths() -> None:
    makefile = MAKEFILE.read_text(encoding="utf-8")
    assert "callback_probe_path" in makefile
    assert "longhaul_probe_path" in makefile
    assert "callback_user_agent" in makefile
    assert "echo_body" in makefile
    assert "--path /cdn/probe" not in makefile
    assert "--path /lh/probe" not in makefile
