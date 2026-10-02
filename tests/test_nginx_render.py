from __future__ import annotations

from pathlib import Path

import pytest

from c2_edge_lab.nginx_render import (
    RenderError,
    render_snippet,
    resolve_header_value,
    wrap_standalone,
)
from c2_edge_lab.policy import load_policy

FIXTURES = Path(__file__).parent / "fixtures"


def _snippet() -> str:
    policy = load_policy(FIXTURES / "policy.valid.yaml")
    return render_snippet(policy, backend_host="10.42.2.10", header_value="lab-test-token")


def test_render_contains_contract_lines() -> None:
    snippet = _snippet()
    expected = (FIXTURES / "expected.conf.fragment").read_text(encoding="utf-8")
    for line in expected.splitlines():
        if line.strip():
            assert line in snippet


def test_render_does_not_proxy_inside_if() -> None:
    snippet = _snippet()
    assert "if ($c2e_gate = proxy) { proxy_pass" not in snippet
    assert "location @proxy" in snippet
    assert "listen 80" in snippet
    assert "listen 443" not in snippet


def test_backend_host_rejects_injection() -> None:
    policy = load_policy(FIXTURES / "policy.valid.yaml")
    with pytest.raises(RenderError, match="backend host"):
        render_snippet(policy, backend_host="10.42.2.10; rm -rf /", header_value="x")


def test_resolve_header_requires_value() -> None:
    policy = load_policy(FIXTURES / "policy.valid.yaml")
    empty = policy.__class__(
        header_name=policy.header_name,
        header_value="",
        path_prefixes=policy.path_prefixes,
        allow_exact=policy.allow_exact,
        allow_regex=policy.allow_regex,
        scanner_substrings=policy.scanner_substrings,
        backend_port=policy.backend_port,
        decoy_root=policy.decoy_root,
        decoy_index=policy.decoy_index,
    )
    with pytest.raises(RenderError, match="header value is empty"):
        resolve_header_value(empty, header_value=None, env_value=None, allow_empty_header=False)
    resolved = resolve_header_value(
        empty,
        header_value=None,
        env_value="from-env",
        allow_empty_header=False,
    )
    assert resolved == "from-env"


def test_ipv6_backend_is_bracketed() -> None:
    policy = load_policy(FIXTURES / "policy.valid.yaml")
    snippet = render_snippet(
        policy,
        backend_host="2001:db8::10",
        header_value="lab-test-token",
    )
    assert "proxy_pass http://[2001:db8::10]:8080" in snippet


def test_render_rejects_unsafe_header_value() -> None:
    policy = load_policy(FIXTURES / "policy.valid.yaml")
    with pytest.raises(RenderError, match="header value"):
        render_snippet(policy, backend_host="10.42.2.10", header_value='evil"; return 200')


def test_standalone_wrap_has_events() -> None:
    wrapped = wrap_standalone(_snippet())
    assert "events {" in wrapped
    assert "http {" in wrapped
    assert "proxy_pass http://10.42.2.10:8080" in wrapped
