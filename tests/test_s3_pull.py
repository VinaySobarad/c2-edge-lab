from __future__ import annotations

from pathlib import Path

import pytest

from c2_edge_lab import s3_pull as s3_pull_mod
from c2_edge_lab.s3_pull import PullError, parse_s3_uri, resolve_dest


def test_parse_s3_uri() -> None:
    assert parse_s3_uri("s3://lab-bucket/stage/sliver") == ("lab-bucket", "stage/sliver")


def test_parse_s3_uri_rejects_https() -> None:
    with pytest.raises(PullError):
        parse_s3_uri("https://example.com/file")


@pytest.mark.parametrize(
    "uri",
    [
        "s3://lab-bucket/index.html",
        "s3://lab-bucket/stage/",
        "s3://lab-bucket/stage/..",
        "s3://lab-bucket/stage/../etc",
        "s3://lab-bucket/stage/nested/path",
        "s3://lab-bucket/stage/name;rm",
        "s3://LabBucket/stage/sliver",
    ],
)
def test_parse_s3_uri_rejects_unsafe_keys(uri: str) -> None:
    with pytest.raises(PullError):
        parse_s3_uri(uri)


def test_resolve_dest_stays_under_root(tmp_path: Path) -> None:
    assert resolve_dest(Path("sliver-server"), root=tmp_path) == tmp_path / "sliver-server"
    with pytest.raises(PullError):
        resolve_dest(tmp_path / ".." / "etc" / "passwd", root=tmp_path)
    with pytest.raises(PullError):
        resolve_dest(tmp_path, root=tmp_path)


def test_parse_s3_uri_honors_stage_prefix_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("C2_EDGE_STAGE_PREFIX", "drop")
    assert parse_s3_uri("s3://lab-bucket/drop/sliver") == ("lab-bucket", "drop/sliver")
    with pytest.raises(PullError):
        parse_s3_uri("s3://lab-bucket/stage/sliver")


def test_s3_pull_stdlib_only() -> None:
    text = Path(s3_pull_mod.__file__ or "").read_text(encoding="utf-8")
    assert "boto3" not in text
    assert "botocore" not in text
