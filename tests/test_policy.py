from __future__ import annotations

from pathlib import Path

import pytest

from c2_edge_lab.policy import PolicyError, gate_action, load_policy, parse_policy

FIXTURES = Path(__file__).parent / "fixtures"


def test_valid_policy_loads() -> None:
    policy = load_policy(FIXTURES / "policy.valid.yaml")
    assert policy.header_name == "X-Lab-Token"
    assert policy.path_prefixes == ("/cdn/",)
    assert policy.backend_port == 8080


def test_unknown_key_fails() -> None:
    with pytest.raises(PolicyError, match="unknown keys"):
        load_policy(FIXTURES / "policy.bad.yaml")


def test_version_must_be_one() -> None:
    with pytest.raises(PolicyError, match="version"):
        parse_policy({"version": 2})


def test_header_name_rejects_spaces() -> None:
    raw = {
        "version": 1,
        "header": {"name": "X Lab", "value": "x"},
        "paths": {"prefixes": ["/cdn/"]},
        "user_agents": {"allow_exact": ["LabCallback/1.0"]},
        "backend": {"port": 8080},
        "decoy": {"root": "/var/www/html", "index": "index.html"},
    }
    with pytest.raises(PolicyError, match="header.name"):
        parse_policy(raw)


def test_empty_prefixes_fail() -> None:
    raw = {
        "version": 1,
        "header": {"name": "X-Lab-Token", "value": "x"},
        "paths": {"prefixes": []},
        "user_agents": {"allow_exact": ["LabCallback/1.0"]},
        "backend": {"port": 8080},
        "decoy": {"root": "/var/www/html", "index": "index.html"},
    }
    with pytest.raises(PolicyError, match="prefixes"):
        parse_policy(raw)


def test_port_bounds() -> None:
    raw = {
        "version": 1,
        "header": {"name": "X-Lab-Token", "value": "x"},
        "paths": {"prefixes": ["/cdn/"]},
        "user_agents": {"allow_exact": ["LabCallback/1.0"]},
        "backend": {"port": 0},
        "decoy": {"root": "/var/www/html", "index": "index.html"},
    }
    with pytest.raises(PolicyError, match="backend.port"):
        parse_policy(raw)


def test_decoy_root_rejects_injection() -> None:
    raw = {
        "version": 1,
        "header": {"name": "X-Lab-Token", "value": "x"},
        "paths": {"prefixes": ["/cdn/"]},
        "user_agents": {"allow_exact": ["LabCallback/1.0"]},
        "backend": {"port": 8080},
        "decoy": {"root": "/var/www/html; include /tmp/x", "index": "index.html"},
    }
    with pytest.raises(PolicyError, match="decoy.root"):
        parse_policy(raw)


def test_gate_matrix() -> None:
    policy = load_policy(FIXTURES / "policy.valid.yaml")
    token = "lab-test-token"
    allow = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) LabCallback/1.0"
    headers = {"X-Lab-Token": token}
    assert gate_action(policy, "/cdn/x", {}, allow, header_value=token) == "decoy"
    assert gate_action(policy, "/cdn/x", headers, "curl/8.4.0", header_value=token) == "decoy"
    assert gate_action(policy, "/cdn/x", headers, allow, header_value=token) == "proxy"
    assert gate_action(policy, "/", headers, allow, header_value=token) == "decoy"
