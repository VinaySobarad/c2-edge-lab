"""Load and validate redirector.policy.yaml. Unknown keys fail closed."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

ALLOWED_ROOT_KEYS = frozenset({"version", "header", "paths", "user_agents", "backend", "decoy"})
ALLOWED_HEADER_KEYS = frozenset({"name", "value"})
ALLOWED_PATHS_KEYS = frozenset({"prefixes"})
ALLOWED_UA_KEYS = frozenset({"allow_exact", "allow_regex", "scanner_substrings"})
ALLOWED_BACKEND_KEYS = frozenset({"port"})
ALLOWED_DECOY_KEYS = frozenset({"root", "index"})

HTTP_TOKEN = re.compile(r"^[!#$%&'*+\-.^_`|~0-9A-Za-z]+$")
PATH_PREFIX = re.compile(r"^/[A-Za-z0-9._~!$&'()*+,;=:@%/-]*$")
HEADER_VALUE_SAFE = re.compile(r"^[A-Za-z0-9._~+/-]*$")
REGEX_SAFE = re.compile(r"^[A-Za-z0-9._\\*?+\-|\[\]()]+$")
UNIX_DIR = re.compile(r"^/[A-Za-z0-9._/-]+$")
INDEX_FILE = re.compile(r"^[A-Za-z0-9._-]+$")


class PolicyError(ValueError):
    """Policy file is invalid."""


@dataclass(frozen=True)
class Policy:
    header_name: str
    header_value: str
    path_prefixes: tuple[str, ...]
    allow_exact: tuple[str, ...]
    allow_regex: tuple[str, ...]
    scanner_substrings: tuple[str, ...]
    backend_port: int
    decoy_root: str
    decoy_index: str


def _require_mapping(value: Any, where: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise PolicyError(f"{where} must be a mapping")
    return value


def _reject_unknown(mapping: dict[str, Any], allowed: frozenset[str], where: str) -> None:
    extra = sorted(set(mapping) - allowed)
    if extra:
        raise PolicyError(f"{where} has unknown keys: {', '.join(extra)}")


def _string_list(value: Any, where: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        raise PolicyError(f"{where} must be a list of non-empty strings")
    return tuple(value)


def load_policy(path: Path) -> Policy:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise PolicyError(f"invalid YAML: {exc}") from exc
    return parse_policy(raw)


def parse_policy(raw: Any) -> Policy:
    root = _require_mapping(raw, "policy")
    _reject_unknown(root, ALLOWED_ROOT_KEYS, "policy")

    if root.get("version") != 1:
        raise PolicyError("version must be 1")

    header = _require_mapping(root.get("header"), "header")
    _reject_unknown(header, ALLOWED_HEADER_KEYS, "header")
    header_name = header.get("name")
    if not isinstance(header_name, str) or not HTTP_TOKEN.fullmatch(header_name):
        raise PolicyError("header.name must be an HTTP header token (no spaces)")
    header_value = header.get("value", "")
    if header_value is None:
        header_value = ""
    if not isinstance(header_value, str):
        raise PolicyError("header.value must be a string")
    if header_value and not HEADER_VALUE_SAFE.fullmatch(header_value):
        raise PolicyError("header.value contains characters that cannot be placed in nginx maps")

    paths = _require_mapping(root.get("paths"), "paths")
    _reject_unknown(paths, ALLOWED_PATHS_KEYS, "paths")
    prefixes = _string_list(paths.get("prefixes"), "paths.prefixes")
    if not prefixes:
        raise PolicyError("paths.prefixes must be non-empty")
    for prefix in prefixes:
        if not prefix.startswith("/") or not PATH_PREFIX.fullmatch(prefix):
            raise PolicyError(f"invalid path prefix: {prefix}")

    user_agents = _require_mapping(root.get("user_agents"), "user_agents")
    _reject_unknown(user_agents, ALLOWED_UA_KEYS, "user_agents")
    allow_exact = _string_list(user_agents.get("allow_exact"), "user_agents.allow_exact")
    allow_regex = _string_list(user_agents.get("allow_regex"), "user_agents.allow_regex")
    scanners = _string_list(user_agents.get("scanner_substrings"), "user_agents.scanner_substrings")
    for item in (*allow_exact, *scanners):
        if '"' in item or "\n" in item or "\\" in item:
            raise PolicyError("user agent strings cannot contain quotes, backslashes, or newlines")
    if not allow_exact and not allow_regex:
        raise PolicyError("user_agents must include at least one allow_exact or allow_regex")
    for pattern in allow_regex:
        if not REGEX_SAFE.fullmatch(pattern):
            raise PolicyError(f"allow_regex too unsafe for nginx: {pattern}")
        try:
            re.compile(pattern)
        except re.error as exc:
            raise PolicyError(f"invalid allow_regex {pattern}: {exc}") from exc

    backend = _require_mapping(root.get("backend"), "backend")
    _reject_unknown(backend, ALLOWED_BACKEND_KEYS, "backend")
    port = backend.get("port")
    if not isinstance(port, int) or isinstance(port, bool) or not (1 <= port <= 65535):
        raise PolicyError("backend.port must be an integer 1-65535")

    decoy = _require_mapping(root.get("decoy"), "decoy")
    _reject_unknown(decoy, ALLOWED_DECOY_KEYS, "decoy")
    decoy_root = decoy.get("root")
    decoy_index = decoy.get("index")
    if not isinstance(decoy_root, str) or not UNIX_DIR.fullmatch(decoy_root):
        raise PolicyError("decoy.root must be an absolute unix path")
    if not isinstance(decoy_index, str) or not INDEX_FILE.fullmatch(decoy_index):
        raise PolicyError("decoy.index must be a simple file name")

    return Policy(
        header_name=header_name,
        header_value=header_value,
        path_prefixes=prefixes,
        allow_exact=allow_exact,
        allow_regex=allow_regex,
        scanner_substrings=scanners,
        backend_port=port,
        decoy_root=decoy_root,
        decoy_index=decoy_index,
    )


def header_from_mapping(headers: dict[str, str], header_name: str) -> str:
    wanted = header_name.lower()
    for key, value in headers.items():
        if key.lower() == wanted:
            return value
    return ""


def classify_user_agent(policy: Policy, user_agent: str) -> str:
    """Match nginx map order: exact hash first, then scanner regex, then allow_regex."""
    if user_agent in policy.allow_exact:
        return "allow"
    lowered = user_agent.lower()
    for substring in policy.scanner_substrings:
        if substring.lower() in lowered:
            return "scanner"
    for pattern in policy.allow_regex:
        if re.search(pattern, user_agent):
            return "allow"
    return "other"


def path_matches(policy: Policy, path: str) -> bool:
    return any(path.startswith(prefix) for prefix in policy.path_prefixes)


def gate_action(
    policy: Policy,
    path: str,
    headers: dict[str, str],
    user_agent: str,
    *,
    header_value: str | None = None,
) -> str:
    """Return 'proxy' or 'decoy' using the same rules the nginx maps encode."""
    if not path_matches(policy, path):
        return "decoy"
    expected = policy.header_value if header_value is None else header_value
    token_ok = bool(expected) and header_from_mapping(headers, policy.header_name) == expected
    if token_ok and classify_user_agent(policy, user_agent) == "allow":
        return "proxy"
    return "decoy"
