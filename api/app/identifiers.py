"""Quote Snowflake identifiers. Reject anything that is not a plain name."""

from __future__ import annotations

import re

_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")


class IdentifierError(ValueError):
    pass


def quote_ident(name: str) -> str:
    if name is None:
        raise IdentifierError("missing identifier")
    text = str(name).strip()
    if not _IDENT.match(text):
        raise IdentifierError(f"invalid identifier: {text!r}")
    return '"' + text + '"'


def quote_relation(database: str, schema: str, relation: str) -> str:
    return f"{quote_ident(database)}.{quote_ident(schema)}.{quote_ident(relation)}"


def quote_literal(value: str) -> str:
    return "'" + str(value).replace("'", "''") + "'"
