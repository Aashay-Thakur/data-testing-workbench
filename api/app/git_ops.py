"""Read-only git clone and diff. No push, and the clone URL never includes a token."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

from app.config import DATA_DIR
from app.errors import UserError
from app.redact import scrub

_REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_BRANCH = re.compile(r"^[A-Za-z0-9._/-]+$")


def clone_readonly(repo: str, branch: str, token: str) -> Path:
    if not _REPO.match(repo or ""):
        raise UserError("GITHUB_REPO must look like owner/name.", 400)
    if not branch or not _BRANCH.match(branch) or branch.startswith("-") or ".." in branch.split("/"):
        raise UserError("GITHUB_BRANCH contains characters that are not allowed.", 400)
    if not token:
        raise UserError("GITHUB_TOKEN is not set.", 400)

    safe_branch = branch.replace("/", "-")
    dest = DATA_DIR / "clones" / f"{repo.replace('/', '__')}__{safe_branch}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    if (dest / ".git").is_dir():
        _disable_push(dest)
        return dest
    if dest.exists():
        shutil.rmtree(dest)

    url = f"https://github.com/{repo}.git"
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_CONFIG_COUNT"] = "1"
    env["GIT_CONFIG_KEY_0"] = "http.extraHeader"
    env["GIT_CONFIG_VALUE_0"] = f"Authorization: Bearer {token}"
    command = [
        "git",
        "clone",
        "--depth",
        "1",
        "--single-branch",
        "--branch",
        branch,
        url,
        str(dest),
    ]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=120,
            env=env,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise UserError("The read-only clone timed out.", 408) from exc
    output = scrub(f"{completed.stdout}\n{completed.stderr}").replace(token, "[redacted]")
    if completed.returncode != 0:
        raise UserError(f"Read-only clone failed. {output[-1500:]}", 400)
    _disable_push(dest)
    return dest


def rev_parse(repo: Path) -> str | None:
    if not (repo / ".git").exists():
        return None
    completed = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    if completed.returncode != 0:
        return None
    sha = completed.stdout.strip()
    return sha or None


def git_diff(repo: Path, relative_path: str) -> str:
    if not (repo / ".git").exists():
        return ""
    _relative_file(relative_path)
    completed = subprocess.run(
        ["git", "-C", str(repo), "diff", "--no-color", "--", relative_path],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    return scrub(completed.stdout)


def _disable_push(repo: Path) -> None:
    subprocess.run(
        ["git", "-C", str(repo), "remote", "set-url", "--push", "origin", "DISABLED"],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    subprocess.run(
        ["git", "-C", str(repo), "config", "--unset-all", "http.extraheader"],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )


def _relative_file(relative_path: str) -> None:
    path = Path(relative_path)
    if path.is_absolute() or ".." in path.parts:
        raise UserError("The model path is not inside the project.", 400)
