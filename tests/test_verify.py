from __future__ import annotations

from c2_edge_lab.verify import FetchResult, VerifyError, run_verify

BASE = "https://d111111abcdef8.cloudfront.net/"
PATH = "/cdn/probe"
HEADER = "X-Lab-Token"
TOKEN = "lab-test-token"
ALLOW_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) LabCallback/1.0"
DECOY = FetchResult(200, "<html>Northline Analytics</html>")
ECHO = FetchResult(200, "teamserver-ok")


def _edge(url: str, *, headers: dict[str, str], timeout: float = 10.0) -> FetchResult:
    del timeout
    path = url[len(BASE.rstrip("/")) :] or "/"
    token = headers.get(HEADER, "")
    agent = headers.get("User-Agent", "")
    gated = path.startswith("/cdn/")
    allowed = token == TOKEN and "LabCallback/1.0" in agent
    if gated and allowed:
        return ECHO
    return DECOY


def test_verify_green_path_on_mock_edge() -> None:
    checks = run_verify(
        base_url=BASE,
        header_name=HEADER,
        header_value=TOKEN,
        callback_path=PATH,
        user_agent=ALLOW_UA,
        expect_proxy_body="teamserver-ok",
        fetch_fn=_edge,
    )
    assert checks == (
        "decoy",
        "callback without token",
        "scanner user-agent",
        "gated callback",
    )


def test_verify_red_decoy_leaks_echo() -> None:
    def leak(url: str, *, headers: dict[str, str], timeout: float = 10.0) -> FetchResult:
        del url, headers, timeout
        return ECHO

    try:
        run_verify(
            base_url=BASE,
            header_name=HEADER,
            header_value=TOKEN,
            callback_path=PATH,
            user_agent=ALLOW_UA,
            expect_proxy_body="teamserver-ok",
            fetch_fn=leak,
        )
    except VerifyError as exc:
        assert "leaked" in str(exc)
    else:
        raise AssertionError("echo on decoy must fail")


def test_verify_red_missing_token_hits_teamserver() -> None:
    def open_gate(url: str, *, headers: dict[str, str], timeout: float = 10.0) -> FetchResult:
        del headers, timeout
        if url.rstrip("/").endswith("cloudfront.net"):
            return DECOY
        return ECHO

    try:
        run_verify(
            base_url=BASE,
            header_name=HEADER,
            header_value=TOKEN,
            callback_path=PATH,
            user_agent=ALLOW_UA,
            expect_proxy_body="teamserver-ok",
            fetch_fn=open_gate,
        )
    except VerifyError as exc:
        assert "without token" in str(exc)
    else:
        raise AssertionError("open callback must fail")


def test_verify_red_scanner_hits_teamserver() -> None:
    def ignore_ua(url: str, *, headers: dict[str, str], timeout: float = 10.0) -> FetchResult:
        del timeout
        path = url[len(BASE.rstrip("/")) :] or "/"
        if path.startswith("/cdn/") and headers.get(HEADER) == TOKEN:
            return ECHO
        return DECOY

    try:
        run_verify(
            base_url=BASE,
            header_name=HEADER,
            header_value=TOKEN,
            callback_path=PATH,
            user_agent=ALLOW_UA,
            expect_proxy_body="teamserver-ok",
            fetch_fn=ignore_ua,
        )
    except VerifyError as exc:
        assert "scanner" in str(exc)
    else:
        raise AssertionError("scanner reaching echo must fail")


def test_verify_red_gated_stays_on_decoy() -> None:
    def never_proxy(url: str, *, headers: dict[str, str], timeout: float = 10.0) -> FetchResult:
        del url, headers, timeout
        return DECOY

    try:
        run_verify(
            base_url=BASE,
            header_name=HEADER,
            header_value=TOKEN,
            callback_path=PATH,
            user_agent=ALLOW_UA,
            expect_proxy_body="teamserver-ok",
            fetch_fn=never_proxy,
        )
    except VerifyError as exc:
        assert "gated callback" in str(exc)
    else:
        raise AssertionError("closed gate must fail")
