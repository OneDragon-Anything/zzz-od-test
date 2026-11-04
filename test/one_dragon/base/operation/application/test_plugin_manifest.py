import json
from pathlib import Path

from one_dragon.base.operation.application.plugin_manifest import (
    MAX_MANIFEST_BYTES,
    PluginManifestInfo,
    extract_manifest_info,
    parse_manifest,
    read_manifest_file,
)


def test_extract_reads_all_display_fields() -> None:
    manifest = parse_manifest(
        json.dumps(
            {
                "version": "1.2.0",
                "author": {"name": "作者"},
                "homepage": "https://github.com/a/b",
                "summary": "简介",
            }
        )
    )

    assert extract_manifest_info(manifest) == PluginManifestInfo(
        version="1.2.0",
        author="作者",
        homepage="https://github.com/a/b",
        description="简介",
    )


def test_extract_drops_invalid_field_types() -> None:
    manifest = {"version": 3, "author": "not a dict", "homepage": ["x"], "summary": None}

    assert extract_manifest_info(manifest) == PluginManifestInfo()


def test_extract_only_accepts_https_homepage() -> None:
    assert extract_manifest_info({"homepage": "http://a/b"}).homepage == ""
    assert extract_manifest_info({"homepage": "javascript:alert(1)"}).homepage == ""
    assert extract_manifest_info({"homepage": "HTTPS://a/b"}).homepage == "HTTPS://a/b"


def test_extract_limits_length() -> None:
    assert extract_manifest_info({"version": "1" * 33}).version == ""
    assert extract_manifest_info({"version": "1" * 32}).version == "1" * 32
    assert len(extract_manifest_info({"summary": "x" * 900}).description) == 500
    assert len(extract_manifest_info({"author": {"name": "x" * 900}}).author) == 200


def test_extract_rejects_control_characters_but_keeps_newline() -> None:
    assert extract_manifest_info({"version": "1.0\x00"}).version == ""
    assert extract_manifest_info({"summary": "第一行\n第二行"}).description == "第一行\n第二行"


def test_extract_none_returns_empty_info() -> None:
    assert extract_manifest_info(None) == PluginManifestInfo()


def test_parse_accepts_bom() -> None:
    assert parse_manifest(b'\xef\xbb\xbf{"version": "1"}') == {"version": "1"}


def test_parse_rejects_invalid_content() -> None:
    assert parse_manifest(b"[1, 2]") is None
    assert parse_manifest("{not json") is None
    assert parse_manifest(b"\xff\xfe\x00") is None
    assert parse_manifest(b" " * (MAX_MANIFEST_BYTES + 1)) is None


def test_read_manifest_file(tmp_path: Path) -> None:
    manifest_file = tmp_path / "plugin.json"
    assert read_manifest_file(manifest_file) is None

    manifest_file.write_text('{"version": "2"}', encoding="utf-8")
    assert read_manifest_file(manifest_file) == {"version": "2"}

    manifest_file.write_text(" " * (MAX_MANIFEST_BYTES + 1), encoding="utf-8")
    assert read_manifest_file(manifest_file) is None
