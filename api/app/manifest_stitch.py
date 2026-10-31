"""Stitch manifest.json from ordered line/content rows. No warehouse access."""

from __future__ import annotations

import json
from decimal import Decimal


class StitchError(ValueError):
    """The manifest table rows cannot be turned into one JSON document."""


def stitch_manifest(rows: list[dict]) -> dict:
    """Concatenate ``content`` by numeric ``line`` and parse one JSON object.

    Duplicate line numbers and invalid JSON raise StitchError. Line order is
    numeric, so line 10 stays after line 2. Nothing is inserted between chunks.
    """
    if not rows:
        raise StitchError("Manifest table returned no rows. Expected columns line and content.")

    chunks: dict[int, str] = {}
    for row in rows:
        if "line" not in row or "content" not in row:
            raise StitchError("Manifest rows need line and content columns.")
        line = _line_number(row["line"])
        if line in chunks:
            raise StitchError(f"Duplicate manifest line {line}. Each line number must appear once.")
        content = row["content"]
        if content is None:
            raise StitchError(f"Manifest line {line} has empty content.")
        if isinstance(content, bytes):
            content = content.decode("utf-8")
        elif not isinstance(content, str):
            content = str(content)
        chunks[line] = content

    text = "".join(chunks[line] for line in sorted(chunks))
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise StitchError(f"Manifest JSON failed to parse: {exc.msg}") from exc
    if not isinstance(parsed, dict):
        raise StitchError("Manifest JSON failed to parse: the top-level value must be an object.")
    return parsed


def _line_number(value: object) -> int:
    if isinstance(value, bool) or value is None:
        raise StitchError(f"Manifest line is not an integer: {value!r}")
    if isinstance(value, int):
        return value
    if isinstance(value, Decimal):
        if value == int(value):
            return int(value)
        raise StitchError(f"Manifest line is not an integer: {value!r}")
    if isinstance(value, float):
        if value.is_integer():
            return int(value)
        raise StitchError(f"Manifest line is not an integer: {value!r}")
    if isinstance(value, str):
        text = value.strip()
        sign = text[1:] if text.startswith("-") else text
        if text and sign.isdigit():
            return int(text)
    raise StitchError(f"Manifest line is not an integer: {value!r}")
