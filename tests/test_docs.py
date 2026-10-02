"""Step 8 docs exist and teach adopt without BUILD.md."""

from __future__ import annotations

from pathlib import Path

DOCS = Path(__file__).resolve().parents[1] / "docs"


def test_required_human_docs_exist() -> None:
    for name in (
        "adopt.md",
        "architecture.md",
        "detection.md",
        "compare.md",
        "byo-c2.md",
        "categorization.md",
    ):
        path = DOCS / name
        assert path.is_file(), name
        assert path.read_text(encoding="utf-8").strip()


def test_adopt_covers_apply_path() -> None:
    adopt = (DOCS / "adopt.md").read_text(encoding="utf-8")
    for needle in (
        "lab.tfvars.example",
        "config.s3.tfbackend",
        "terraform apply",
        "make lab-verify",
        "callback_probe_path",
        "callback_user_agent",
        "echo_body",
        "ssm start-session",
        "No port 22",
        "domain_name",
        "-replace=aws_eip.redirector",
        "-replace=aws_cloudfront_distribution.edge",
        "longhaul_url",
        "CloudFront",
        "Cloudflare",
    ):
        assert needle in adopt, needle


def test_detection_names_cf_headers_and_prefix_list() -> None:
    detection = (DOCS / "detection.md").read_text(encoding="utf-8")
    for needle in ("via", "x-amz-cf-id", "x-amz-cf-pop", "origin-facing", "nginx"):
        assert needle in detection, needle


def test_byo_c2_names_ports_and_hauls() -> None:
    byo = (DOCS / "byo-c2.md").read_text(encoding="utf-8")
    for needle in (
        "50050",
        "31337",
        "8080",
        "443",
        "No NAT",
        "short-haul",
        "X-Lab-Token",
        "/cdn/",
        "/lh/",
        "AWS-StartPortForwardingSession",
        "c2-push",
    ):
        assert needle in byo, needle


def test_compare_names_borrowed_projects() -> None:
    compare = (DOCS / "compare.md").read_text(encoding="utf-8")
    for needle in ("Lorenzo", "Optiv", "redStack", "C2structor", "S3 OAC"):
        assert needle in compare, needle


def test_categorization_is_a_checklist_not_terraform() -> None:
    text = (DOCS / "categorization.md").read_text(encoding="utf-8")
    for needle in ("PAN", "Blue Coat", "favicon", "not Terraform"):
        assert needle in text, needle
