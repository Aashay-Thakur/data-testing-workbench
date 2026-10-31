"""Manifest stitch tests. Rows are in memory; Snowflake is not contacted."""

import pytest

from app.manifest_stitch import StitchError, stitch_manifest


def test_line_order():
    rows = [
        {"line": 3, "content": "]}"},
        {"line": 1, "content": '{"models":['},
        {"line": 2, "content": '{"name":"a"}'},
    ]
    assert stitch_manifest(rows) == {"models": [{"name": "a"}]}


def test_line_order_is_numeric():
    rows = [
        {"line": 10, "content": "}"},
        {"line": 2, "content": "1"},
        {"line": "1", "content": '{"n":'},
    ]
    assert stitch_manifest(rows) == {"n": 1}


def test_duplicate_line():
    with pytest.raises(StitchError, match="Duplicate manifest line 1"):
        stitch_manifest(
            [
                {"line": 1, "content": "{"},
                {"line": 1, "content": "}"},
            ]
        )


def test_bad_json():
    with pytest.raises(StitchError, match="JSON failed to parse"):
        stitch_manifest([{"line": 1, "content": "{not-json"}])
