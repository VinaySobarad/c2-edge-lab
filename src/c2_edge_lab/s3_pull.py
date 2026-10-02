"""GET an s3://stage/ object using IMDSv2 (or env) credentials. Stdlib only.

The private teamserver has an S3 gateway endpoint. Operators stage a binary with
`make c2-push`; this script pulls it onto the box. It will not fetch keys outside
`stage/` or write outside the pull root (default `/opt/c2`).
"""

from __future__ import annotations

import datetime
import hashlib
import hmac
import json
import os
import re
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping
from pathlib import Path

IMDS = "http://169.254.169.254"
UNSIGNED = "UNSIGNED-PAYLOAD"
STAGE_PREFIX = "stage/"
DEFAULT_PULL_ROOT = "/opt/c2"
MAX_BYTES = 256 * 1024 * 1024
SAFE_NAME = re.compile(r"^[A-Za-z0-9._-]+$")
BUCKET_NAME = re.compile(r"^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$")


class PullError(RuntimeError):
    """Could not pull the object."""


def configured_stage_prefix() -> str:
    name = os.environ.get("C2_EDGE_STAGE_PREFIX", STAGE_PREFIX.strip("/")).strip("/")
    if not name or not SAFE_NAME.fullmatch(name):
        raise PullError("invalid stage prefix")
    return f"{name}/"


def parse_s3_uri(uri: str) -> tuple[str, str]:
    parsed = urllib.parse.urlparse(uri)
    if parsed.scheme != "s3" or not parsed.netloc or parsed.username or parsed.password:
        raise PullError("expected s3://bucket/stage/name")
    bucket = parsed.netloc
    key = parsed.path.lstrip("/")
    if not _safe_bucket(bucket):
        raise PullError("invalid S3 bucket name")
    prefix = configured_stage_prefix()
    if not key.startswith(prefix) or key == prefix:
        raise PullError(f"key must be under {prefix}")
    name = key[len(prefix) :]
    if name in {".", ".."} or "/" in name or not SAFE_NAME.fullmatch(name):
        raise PullError("stage object name must be a simple filename")
    return bucket, key


def _safe_bucket(bucket: str) -> bool:
    if not BUCKET_NAME.fullmatch(bucket):
        return False
    if ".." in bucket or bucket.startswith("-") or bucket.endswith("-"):
        return False
    return True


def resolve_dest(dest: Path, *, root: Path | None = None) -> Path:
    pull_root = (root or Path(os.environ.get("C2_EDGE_PULL_ROOT", DEFAULT_PULL_ROOT))).resolve()
    candidate = dest if dest.is_absolute() else pull_root / dest
    resolved = candidate.resolve()
    try:
        resolved.relative_to(pull_root)
    except ValueError as exc:
        raise PullError(f"destination must be under {pull_root}") from exc
    if resolved == pull_root:
        raise PullError("destination must be a file, not the pull root")
    if resolved.parent != pull_root:
        raise PullError("destination must be a single filename under the pull root")
    if not SAFE_NAME.fullmatch(resolved.name):
        raise PullError("destination filename is not allowed")
    return resolved


def _imds_get(path: str, headers: Mapping[str, str]) -> str:
    request = urllib.request.Request(f"{IMDS}{path}", headers=dict(headers), method="GET")
    try:
        with urllib.request.urlopen(request, timeout=4) as response:
            return response.read().decode("utf-8")
    except urllib.error.URLError as exc:
        raise PullError(f"IMDS failed for {path}: {exc}") from exc


def _imds_token() -> str:
    request = urllib.request.Request(
        f"{IMDS}/latest/api/token",
        data=b"",
        headers={"X-aws-ec2-metadata-token-ttl-seconds": "21600"},
        method="PUT",
    )
    try:
        with urllib.request.urlopen(request, timeout=4) as response:
            return response.read().decode("utf-8")
    except urllib.error.URLError as exc:
        raise PullError(f"IMDS token failed: {exc}") from exc


def credentials_from_imds() -> tuple[str, str, str, str]:
    token = _imds_token()
    meta = {"X-aws-ec2-metadata-token": token}
    region = _imds_get("/latest/meta-data/placement/region", meta).strip()
    role = _imds_get("/latest/meta-data/iam/security-credentials/", meta).splitlines()[0].strip()
    if not role:
        raise PullError("IMDS returned no instance-profile role")
    try:
        blob = json.loads(_imds_get(f"/latest/meta-data/iam/security-credentials/{role}", meta))
        return region, blob["AccessKeyId"], blob["SecretAccessKey"], blob.get("Token", "")
    except (json.JSONDecodeError, KeyError) as exc:
        raise PullError("IMDS credentials document was not usable") from exc


def credentials_from_env() -> tuple[str, str, str, str] | None:
    access = os.environ.get("AWS_ACCESS_KEY_ID", "")
    secret = os.environ.get("AWS_SECRET_ACCESS_KEY", "")
    region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or ""
    token = os.environ.get("AWS_SESSION_TOKEN", "")
    if access and secret and region:
        return region, access, secret, token
    return None


def _sign(key: bytes, message: str) -> bytes:
    return hmac.new(key, message.encode("utf-8"), hashlib.sha256).digest()


def _signing_key(secret: str, datestamp: str, region: str) -> bytes:
    date_key = _sign(f"AWS4{secret}".encode(), datestamp)
    region_key = hmac.new(date_key, region.encode("utf-8"), hashlib.sha256).digest()
    service_key = hmac.new(region_key, b"s3", hashlib.sha256).digest()
    return hmac.new(service_key, b"aws4_request", hashlib.sha256).digest()


def signed_headers(
    *,
    host: str,
    amz_date: str,
    datestamp: str,
    region: str,
    access_key: str,
    secret_key: str,
    session_token: str,
    canonical_uri: str,
) -> dict[str, str]:
    headers = {
        "host": host,
        "x-amz-content-sha256": UNSIGNED,
        "x-amz-date": amz_date,
    }
    if session_token:
        headers["x-amz-security-token"] = session_token
    signed_names = ";".join(sorted(headers))
    canonical_headers = "".join(f"{name}:{headers[name]}\n" for name in sorted(headers))
    canonical_request = "\n".join(
        [
            "GET",
            canonical_uri,
            "",
            canonical_headers,
            signed_names,
            UNSIGNED,
        ]
    )
    credential_scope = f"{datestamp}/{region}/s3/aws4_request"
    string_to_sign = "\n".join(
        [
            "AWS4-HMAC-SHA256",
            amz_date,
            credential_scope,
            hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
        ]
    )
    signature = hmac.new(
        _signing_key(secret_key, datestamp, region),
        string_to_sign.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    headers["Authorization"] = (
        f"AWS4-HMAC-SHA256 Credential={access_key}/{credential_scope}, "
        f"SignedHeaders={signed_names}, Signature={signature}"
    )
    return headers


def pull(uri: str, dest: Path, *, root: Path | None = None) -> Path:
    bucket, key = parse_s3_uri(uri)
    target = resolve_dest(dest, root=root)
    creds = credentials_from_env()
    if creds is None:
        creds = credentials_from_imds()
    region, access_key, secret_key, session_token = creds
    host = f"{bucket}.s3.{region}.amazonaws.com"
    canonical_uri = "/" + urllib.parse.quote(key, safe="/")
    now = datetime.datetime.now(datetime.UTC)
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    datestamp = now.strftime("%Y%m%d")
    headers = signed_headers(
        host=host,
        amz_date=amz_date,
        datestamp=datestamp,
        region=region,
        access_key=access_key,
        secret_key=secret_key,
        session_token=session_token,
        canonical_uri=canonical_uri,
    )
    url = f"https://{host}{canonical_uri}"
    request = urllib.request.Request(url, headers=headers, method="GET")
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(target.name + ".part")
    written = 0
    try:
        with urllib.request.urlopen(
            request, timeout=60, context=ssl.create_default_context()
        ) as response, tmp.open("wb") as handle:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                written += len(chunk)
                if written > MAX_BYTES:
                    raise PullError(f"object exceeds {MAX_BYTES} bytes")
                handle.write(chunk)
    except urllib.error.HTTPError as exc:
        body = exc.read()[:2048] if exc.fp else b""
        tmp.unlink(missing_ok=True)
        raise PullError(f"S3 GET {uri} failed: {exc.code} {body!r}") from exc
    except urllib.error.URLError as exc:
        tmp.unlink(missing_ok=True)
        raise PullError(f"S3 GET {uri} failed: {exc}") from exc
    except PullError:
        tmp.unlink(missing_ok=True)
        raise
    tmp.replace(target)
    target.chmod(0o750)
    return target


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if len(args) != 2:
        print(
            f"usage: s3_pull.py s3://bucket/{STAGE_PREFIX}<name> {DEFAULT_PULL_ROOT}/<name>",
            file=sys.stderr,
        )
        return 2
    try:
        written = pull(args[0], Path(args[1]))
    except PullError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(written)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
