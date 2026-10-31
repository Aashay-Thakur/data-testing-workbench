"""Keep passwords, keys, tokens, and tokenized clone URLs out of logs."""

from __future__ import annotations

import logging
import re
import traceback

_TOKEN_URL = re.compile(r"https://[^\s/]+@[^\s]+", re.IGNORECASE)
_GH_TOKEN = re.compile(r"\b(?:ghp_|gho_|ghu_|ghs_|ghr_|github_pat_)[A-Za-z0-9_]+\b")
_BEARER = re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._\-+/=]+")
_KV = re.compile(
    r"(?i)(password|private_key|token|secret|api_key)(['\"]?\s*[:=]\s*['\"]?)([^\s,'\"}]+)"
)

_secrets: list[str] = []


def register_secret(value: str | None) -> None:
    if not value:
        return
    text = value.strip()
    if len(text) >= 8 and text not in _secrets:
        _secrets.append(text)


def scrub(text: str) -> str:
    if not text:
        return text
    cleaned = text
    for secret in _secrets:
        if secret in cleaned:
            cleaned = cleaned.replace(secret, "[redacted]")
    cleaned = _TOKEN_URL.sub("https://[redacted]@redacted", cleaned)
    cleaned = _GH_TOKEN.sub("[redacted]", cleaned)
    cleaned = _BEARER.sub(r"\1[redacted]", cleaned)
    cleaned = _KV.sub(r"\1\2[redacted]", cleaned)
    return cleaned


class RedactFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:
            message = str(record.msg)
        record.msg = scrub(message)
        record.args = ()
        if record.exc_info:
            record.exc_text = scrub("".join(traceback.format_exception(*record.exc_info)))
            record.exc_info = None
        elif record.exc_text:
            record.exc_text = scrub(record.exc_text)
        return True


def install_redaction() -> None:
    redact_filter = RedactFilter()
    root = logging.getLogger()
    root.addFilter(redact_filter)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "snowflake", "snowflake.connector"):
        logger = logging.getLogger(name)
        logger.addFilter(redact_filter)
    logging.getLogger("snowflake.connector").setLevel(logging.WARNING)
