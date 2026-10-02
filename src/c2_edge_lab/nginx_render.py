"""Render policy YAML to an nginx http-context snippet (maps + server)."""

from __future__ import annotations

import ipaddress
import re
from pathlib import Path

from jinja2 import Environment, PackageLoader, StrictUndefined

from c2_edge_lab.policy import HEADER_VALUE_SAFE, Policy

HOSTNAME = re.compile(
    r"^(?=.{1,253}$)(?!-)[A-Za-z0-9-]{1,63}(?<!-)(\.(?!-)[A-Za-z0-9-]{1,63}(?<!-))*$"
)
NGINX_REGEX_ESCAPE = re.compile(r"([.^$*+?{}\[\]()|\\])")

TEMPLATE_NAME = "redirector.conf.j2"


class RenderError(ValueError):
    """Cannot produce a safe nginx config from this policy."""


def header_to_nginx_variable(header_name: str) -> str:
    return "http_" + header_name.lower().replace("-", "_")


def nginx_regex_escape(text: str) -> str:
    return NGINX_REGEX_ESCAPE.sub(r"\\\1", text)


def validate_backend_host(backend_host: str) -> str:
    host = backend_host.strip()
    if not host:
        raise RenderError("backend host is required")
    try:
        parsed_ip = ipaddress.ip_address(host)
    except ValueError:
        parsed_ip = None
    if parsed_ip is not None:
        if parsed_ip.version == 6:
            return f"[{host}]"
        return host
    if HOSTNAME.fullmatch(host):
        return host
    raise RenderError(f"backend host is not an IP or hostname: {backend_host}")


def validate_header_token(header_value: str) -> str:
    if header_value and not HEADER_VALUE_SAFE.fullmatch(header_value):
        raise RenderError("header value contains characters that cannot be placed in nginx maps")
    return header_value


def resolve_header_value(
    policy: Policy,
    *,
    header_value: str | None,
    env_value: str | None,
    allow_empty_header: bool,
) -> str:
    if header_value:
        return validate_header_token(header_value)
    if env_value:
        return validate_header_token(env_value)
    if policy.header_value:
        return validate_header_token(policy.header_value)
    if allow_empty_header:
        return ""
    raise RenderError(
        "header value is empty; pass --header-value, set C2_EDGE_HEADER_VALUE, "
        "or use --allow-empty-header"
    )


def _environment() -> Environment:
    return Environment(
        loader=PackageLoader("c2_edge_lab", "templates"),
        undefined=StrictUndefined,
        autoescape=False,
        keep_trailing_newline=True,
    )


def render_snippet(
    policy: Policy,
    *,
    backend_host: str,
    header_value: str,
    allow_empty_header: bool = False,
) -> str:
    host = validate_backend_host(backend_host)
    token = validate_header_token(header_value)
    scanner_pattern = "|".join(nginx_regex_escape(item) for item in policy.scanner_substrings)
    template = _environment().get_template(TEMPLATE_NAME)
    return template.render(
        header_nginx_var=header_to_nginx_variable(policy.header_name),
        header_value=token,
        header_open=allow_empty_header and not token,
        path_prefixes=policy.path_prefixes,
        allow_exact=policy.allow_exact,
        allow_regex=policy.allow_regex,
        scanner_pattern=scanner_pattern,
        backend_host=host,
        backend_port=policy.backend_port,
        decoy_root=policy.decoy_root,
        decoy_index=policy.decoy_index,
    )


def wrap_standalone(snippet: str) -> str:
    return (
        "worker_processes 1;\n"
        "error_log /tmp/c2-edge-nginx-error.log;\n"
        "pid /tmp/c2-edge-nginx.pid;\n"
        "events { worker_connections 64; }\n"
        "http {\n"
        "    access_log off;\n"
        f"{_indent(snippet, 4)}"
        "}\n"
    )


def _indent(text: str, spaces: int) -> str:
    pad = " " * spaces
    lines = text.splitlines(keepends=True)
    return "".join(pad + line if line.strip() else line for line in lines)


def write_nginx(
    output: Path,
    snippet: str,
    *,
    standalone: bool,
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    body = wrap_standalone(snippet) if standalone else snippet
    output.write_text(body, encoding="utf-8")
