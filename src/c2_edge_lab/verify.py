"""HTTP checks for the split-origin edge. CI mocks fetch; live is operator-only."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


class VerifyError(RuntimeError):
    """A verify check failed."""


@dataclass(frozen=True)
class FetchResult:
    status: int
    body: str


FetchFn = Callable[..., FetchResult]

MAX_BODY_BYTES = 1_048_576
VERIFY_CHECKS = (
    "decoy",
    "callback without token",
    "scanner user-agent",
    "gated callback",
)


def _require_http_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise VerifyError("URL must be http or https with a host")
    return url


def _read_limited(stream: object, limit: int = MAX_BODY_BYTES) -> str:
    chunk = stream.read(limit + 1)  # type: ignore[union-attr]
    if not chunk:
        return ""
    if len(chunk) > limit:
        raise VerifyError("response body exceeded 1 MiB")
    return chunk.decode("utf-8", errors="replace")


def fetch(url: str, *, headers: dict[str, str], timeout: float = 10.0) -> FetchResult:
    safe_url = _require_http_url(url)
    request = Request(safe_url, headers=headers, method="GET")
    try:
        with urlopen(request, timeout=timeout) as response:
            body = _read_limited(response)
            return FetchResult(status=response.status, body=body)
    except HTTPError as exc:
        body = _read_limited(exc) if exc.fp else ""
        return FetchResult(status=exc.code, body=body)
    except URLError as exc:
        raise VerifyError(f"request failed {url}: {exc}") from exc


def _join(base_url: str, path: str) -> str:
    return base_url.rstrip("/") + "/" + path.lstrip("/")


def run_verify(
    *,
    base_url: str,
    header_name: str,
    header_value: str,
    callback_path: str,
    user_agent: str,
    expect_proxy_body: str,
    timeout: float = 10.0,
    fetch_fn: FetchFn | None = None,
) -> tuple[str, ...]:
    """Run the four split-origin checks. Raises VerifyError on the first failure."""
    do_fetch = fetch_fn or fetch

    decoy = do_fetch(base_url, headers={"User-Agent": "c2-edge-lab-verify"}, timeout=timeout)
    if decoy.status != 200:
        raise VerifyError(f"decoy URL {base_url} returned {decoy.status}")
    if expect_proxy_body in decoy.body:
        raise VerifyError("decoy page leaked the teamserver echo body")

    gated = _join(base_url, callback_path)
    _require_http_url(gated)
    missing = do_fetch(gated, headers={"User-Agent": user_agent}, timeout=timeout)
    if missing.status != 200:
        raise VerifyError(f"callback without token returned {missing.status}")
    if expect_proxy_body in missing.body:
        raise VerifyError("callback without token reached the teamserver")

    scanner = do_fetch(
        gated,
        headers={header_name: header_value, "User-Agent": "curl/8.4.0"},
        timeout=timeout,
    )
    if scanner.status != 200:
        raise VerifyError(f"scanner User-Agent returned {scanner.status}")
    if expect_proxy_body in scanner.body:
        raise VerifyError("scanner User-Agent reached the teamserver")

    proxied = do_fetch(
        gated,
        headers={header_name: header_value, "User-Agent": user_agent},
        timeout=timeout,
    )
    if expect_proxy_body not in proxied.body:
        raise VerifyError(
            f"gated callback did not return {expect_proxy_body!r} (status {proxied.status})"
        )

    return VERIFY_CHECKS
