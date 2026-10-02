"""lab CLI: policy validate / render-nginx / test, plus live verify."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from c2_edge_lab.nginx_render import RenderError, render_snippet, resolve_header_value, write_nginx
from c2_edge_lab.policy import Policy, PolicyError, gate_action, load_policy
from c2_edge_lab.verify import VerifyError, run_verify

EXIT_OK = 0
EXIT_TEST_FAIL = 1
EXIT_USAGE = 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lab",
        description="c2-edge-lab operator CLI (policy, verify; AWS apply is operator-gated).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    policy = sub.add_parser("policy", help="validate, render, or fixture-test redirector policy")
    policy_sub = policy.add_subparsers(dest="policy_command", required=True)

    validate = policy_sub.add_parser(
        "validate",
        help="schema-check a policy file (exit 2 on error)",
    )
    validate.add_argument("-f", "--file", type=Path, required=True)

    render = policy_sub.add_parser("render-nginx", help="write nginx config from policy")
    render.add_argument("-f", "--file", type=Path, required=True)
    render.add_argument("--backend-host", required=True, help="teamserver private IP or hostname")
    render.add_argument("-o", "--output", type=Path, required=True)
    render.add_argument("--header-value", default=None, help="overrides empty YAML value")
    render.add_argument(
        "--allow-empty-header",
        action="store_true",
        help="lab-open: skip header gate (do not use on a real edge)",
    )
    render.add_argument(
        "--standalone",
        action="store_true",
        help="wrap maps+server in a full nginx.conf for nginx -t",
    )

    test = policy_sub.add_parser("test", help="run in-process gate fixtures (no AWS)")
    test.add_argument("-f", "--file", type=Path, required=True)
    test.add_argument(
        "--header-value",
        default=None,
        help="token used for fixtures when YAML value is empty",
    )

    verify = sub.add_parser("verify", help="live HTTP checks against the edge (optional)")
    verify.add_argument(
        "--domain",
        default="",
        help="custom hostname (https://DOMAIN). Do not set --base-url as well.",
    )
    verify.add_argument(
        "--base-url",
        default="",
        help="full URL when using the CloudFront default hostname, e.g. https://dxxxx.cloudfront.net",
    )
    verify.add_argument("--header-name", required=True)
    verify.add_argument("--header-value", required=True)
    verify.add_argument(
        "--path",
        required=True,
        help="callback path (terraform output callback_probe_path)",
    )
    verify.add_argument(
        "--user-agent",
        required=True,
        help="must match policy user_agents.allow_exact (terraform output callback_user_agent)",
    )
    verify.add_argument(
        "--expect-proxy-body",
        required=True,
        help="teamserver echo body (terraform output echo_body)",
    )
    return parser


def _fail(message: str, code: int) -> int:
    print(message, file=sys.stderr)
    return code


def cmd_validate(path: Path) -> int:
    try:
        load_policy(path)
    except (OSError, PolicyError) as exc:
        return _fail(f"policy invalid: {exc}", EXIT_USAGE)
    print(f"policy ok: {path}")
    return EXIT_OK


def cmd_render(args: argparse.Namespace) -> int:
    try:
        policy = load_policy(args.file)
        header_value = resolve_header_value(
            policy,
            header_value=args.header_value,
            env_value=os.environ.get("C2_EDGE_HEADER_VALUE"),
            allow_empty_header=args.allow_empty_header,
        )
        snippet = render_snippet(
            policy,
            backend_host=args.backend_host,
            header_value=header_value,
            allow_empty_header=args.allow_empty_header,
        )
        write_nginx(args.output, snippet, standalone=args.standalone)
    except (OSError, PolicyError, RenderError) as exc:
        return _fail(f"render failed: {exc}", EXIT_USAGE)
    print(f"wrote {args.output}")
    return EXIT_OK


def _fixture_header_value(policy: Policy, override: str | None) -> str:
    if override:
        return override
    if policy.header_value:
        return policy.header_value
    env_value = os.environ.get("C2_EDGE_HEADER_VALUE")
    if env_value:
        return env_value
    raise PolicyError("header value is empty; pass --header-value for policy test")


def cmd_policy_test(path: Path, header_override: str | None) -> int:
    try:
        policy = load_policy(path)
        token = _fixture_header_value(policy, header_override)
    except (OSError, PolicyError) as exc:
        return _fail(f"policy invalid: {exc}", EXIT_USAGE)

    if not policy.allow_exact:
        return _fail("policy test needs user_agents.allow_exact[0]", EXIT_USAGE)
    probe = policy.path_prefixes[0].rstrip("/") + "/probe"
    allow_ua = policy.allow_exact[0]
    scanner_ua = "curl/8.4.0"
    cases = [
        ("no header on callback path", probe, {}, allow_ua, "decoy"),
        (
            "scanner UA with good header",
            probe,
            {policy.header_name: token},
            scanner_ua,
            "decoy",
        ),
        (
            "good header and allow UA",
            probe,
            {policy.header_name: token},
            allow_ua,
            "proxy",
        ),
        ("unrelated path", "/", {policy.header_name: token}, allow_ua, "decoy"),
    ]
    failed = 0
    for name, path_value, headers, user_agent, expected in cases:
        got = gate_action(policy, path_value, headers, user_agent, header_value=token)
        status = "ok" if got == expected else "FAIL"
        if got != expected:
            failed += 1
        print(f"{status:4} {name}: expected {expected}, got {got}")
    if failed:
        return _fail(f"{failed} fixture(s) failed", EXIT_TEST_FAIL)
    print("policy test ok")
    return EXIT_OK


def _verify_base_url(domain: str, base_url: str) -> str:
    domain = domain.strip()
    base_url = base_url.strip()
    if domain and base_url:
        raise VerifyError("use --domain or --base-url, not both")
    if domain:
        host = domain.removeprefix("https://").removeprefix("http://").split("/")[0]
        if not host:
            raise VerifyError("domain is empty")
        return f"https://{host}"
    if base_url:
        return base_url
    raise VerifyError("pass --domain (custom hostname) or --base-url (CloudFront default URL)")


def cmd_verify(args: argparse.Namespace) -> int:
    try:
        checks = run_verify(
            base_url=_verify_base_url(args.domain, args.base_url),
            header_name=args.header_name,
            header_value=args.header_value,
            callback_path=args.path,
            user_agent=args.user_agent,
            expect_proxy_body=args.expect_proxy_body,
        )
    except VerifyError as exc:
        return _fail(f"verify failed: {exc}", EXIT_TEST_FAIL)
    for check in checks:
        print(f"ok  {check}")
    print("verify ok")
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "policy" and args.policy_command == "validate":
        return cmd_validate(args.file)
    if args.command == "policy" and args.policy_command == "render-nginx":
        return cmd_render(args)
    if args.command == "policy" and args.policy_command == "test":
        return cmd_policy_test(args.file, args.header_value)
    if args.command == "verify":
        return cmd_verify(args)
    parser.error("unknown command")
    return EXIT_USAGE


if __name__ == "__main__":
    raise SystemExit(main())
