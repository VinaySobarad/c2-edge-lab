from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

from c2_edge_lab.cli import main
from c2_edge_lab.verify import VerifyError, run_verify

FIXTURES = Path(__file__).parent / "fixtures"
EXAMPLE_POLICY = Path(__file__).resolve().parents[1] / "policy" / "redirector.policy.yaml"


def test_cli_validate_ok() -> None:
    assert main(["policy", "validate", "-f", str(FIXTURES / "policy.valid.yaml")]) == 0


def test_cli_validate_bad_exits_two() -> None:
    assert main(["policy", "validate", "-f", str(FIXTURES / "policy.bad.yaml")]) == 2


def test_cli_render_and_policy_test(tmp_path: Path) -> None:
    output = tmp_path / "redirector.conf"
    assert (
        main(
            [
                "policy",
                "render-nginx",
                "-f",
                str(FIXTURES / "policy.valid.yaml"),
                "--backend-host",
                "10.42.2.10",
                "-o",
                str(output),
            ]
        )
        == 0
    )
    text = output.read_text(encoding="utf-8")
    assert "proxy_pass http://10.42.2.10:8080" in text
    assert "events {" not in text
    assert main(["policy", "test", "-f", str(FIXTURES / "policy.valid.yaml")]) == 0


def test_example_policy_validates_but_render_needs_secret(tmp_path: Path) -> None:
    assert main(["policy", "validate", "-f", str(EXAMPLE_POLICY)]) == 0
    output = tmp_path / "should-not-write.conf"
    assert (
        main(
            [
                "policy",
                "render-nginx",
                "-f",
                str(EXAMPLE_POLICY),
                "--backend-host",
                "10.42.2.10",
                "-o",
                str(output),
            ]
        )
        == 2
    )
    assert not output.exists()


def test_cli_render_standalone(tmp_path: Path) -> None:
    output = tmp_path / "nginx.conf"
    assert (
        main(
            [
                "policy",
                "render-nginx",
                "-f",
                str(FIXTURES / "policy.valid.yaml"),
                "--backend-host",
                "10.42.2.10",
                "-o",
                str(output),
                "--standalone",
            ]
        )
        == 0
    )
    assert "events {" in output.read_text(encoding="utf-8")


class _LabHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        return

    def do_GET(self) -> None:  # noqa: N802
        token = self.headers.get("X-Lab-Token", "")
        agent = self.headers.get("User-Agent", "")
        gated = self.path.startswith("/cdn/")
        allowed = token == "lab-test-token" and "LabCallback/1.0" in agent
        if gated and allowed:
            body = b"teamserver-ok"
        else:
            body = b"<html>Northline Analytics</html>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def test_verify_against_local_server() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _LabHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        base = f"http://{host}:{port}"
        run_verify(
            base_url=base,
            header_name="X-Lab-Token",
            header_value="lab-test-token",
            callback_path="/cdn/probe",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) LabCallback/1.0",
            expect_proxy_body="teamserver-ok",
        )
        assert (
            main(
                [
                    "verify",
                    "--base-url",
                    base,
                    "--header-name",
                    "X-Lab-Token",
                    "--header-value",
                    "lab-test-token",
                    "--path",
                    "/cdn/probe",
                    "--user-agent",
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) LabCallback/1.0",
                    "--expect-proxy-body",
                    "teamserver-ok",
                ]
            )
            == 0
        )
    finally:
        server.shutdown()
        server.server_close()


def test_cli_verify_requires_live_flags() -> None:
    try:
        main(
            [
                "verify",
                "--base-url",
                "https://example.cloudfront.net",
                "--header-name",
                "X-Lab-Token",
                "--header-value",
                "x",
            ]
        )
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("verify must require --path, --user-agent, and --expect-proxy-body")


def test_verify_rejects_non_http() -> None:
    try:
        run_verify(
            base_url="file:///etc/passwd",
            header_name="X-Lab-Token",
            header_value="x",
            callback_path="/cdn/x",
            user_agent="LabCallback/1.0",
            expect_proxy_body="teamserver-ok",
        )
    except VerifyError as exc:
        assert "http" in str(exc)
    else:
        raise AssertionError("file URL must be rejected")


def test_verify_domain_flag_builds_https_url() -> None:
    from c2_edge_lab.cli import _verify_base_url

    assert _verify_base_url("lab.example.com", "") == "https://lab.example.com"
    assert _verify_base_url("https://lab.example.com/", "") == "https://lab.example.com"
    try:
        _verify_base_url("lab.example.com", "https://d111.cloudfront.net")
    except VerifyError as exc:
        assert "not both" in str(exc)
    else:
        raise AssertionError("domain and base-url together must fail")
    try:
        _verify_base_url("", "")
    except VerifyError as exc:
        assert "domain" in str(exc)
    else:
        raise AssertionError("missing hostname must fail")
