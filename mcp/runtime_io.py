from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import fcntl
import tempfile
from pathlib import Path

from .runtime_paths import ENV_CANDIDATES
from .runtime_support import dedupe_keep_order


def load_env_values() -> dict[str, str]:
    data: dict[str, str] = {}
    for path in reversed(ENV_CANDIDATES):
        if not path.exists():
            continue
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            data[key.strip()] = value.strip().strip('"').strip("'")
    return data


def build_env() -> dict[str, str]:
    env = dict(os.environ)
    env.update(load_env_values())
    return env


def load_json_file(path: Path | None, *, warn_message: str | None = None) -> dict:
    if not path or not path.exists():
        return {}
    try:
        value = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError, UnicodeDecodeError) as exc:
        if warn_message:
            warn(f"{warn_message}: {exc}")
        return {}
    return value if isinstance(value, dict) else {}


def warn(message: str) -> None:
    print(f"WARNING: {message}", file=sys.stderr)


def dedupe_paths(paths: list[Path]) -> list[Path]:
    out: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        resolved = str(Path(path).expanduser().resolve())
        if resolved in seen:
            continue
        seen.add(resolved)
        out.append(Path(resolved))
    return out

def slugify(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "-", str(value or "").strip().lower())
    return value.strip("-") or "plan"


def atomic_json_write(path: Path, data: dict, *, lock: bool = True) -> None:
    """Write JSON to *path* atomically with optional file-level locking.

    1. Acquires an exclusive flock on ``<path>.lock`` (prevents concurrent
       writers from interleaving read-modify-write cycles).
    2. Writes serialised JSON to a temporary file in the same directory.
    3. Calls ``fsync`` + ``os.rename`` (atomic on POSIX) to replace the target.

    The lock file is a no-op advisory lock — it never contains data and is
    safe to delete at any time.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, indent=2) + "\n"

    def _write() -> None:
        fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp", prefix=f".{path.stem}-")
        try:
            os.write(fd, payload.encode())
            os.fsync(fd)
            os.close(fd)
            fd = -1  # mark closed
            os.rename(tmp, path)
        except BaseException:
            if fd >= 0:
                os.close(fd)
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise

    if lock:
        lock_path = path.with_suffix(".lock")
        with open(lock_path, "w") as lf:
            fcntl.flock(lf, fcntl.LOCK_EX)
            try:
                _write()
            finally:
                fcntl.flock(lf, fcntl.LOCK_UN)
    else:
        _write()


def prefix_prompt(prelude: str, body: str, token_block: str | None = None) -> str:
    prelude = (prelude or "").strip()
    token_block = (token_block or "").strip()
    body = (body or "").strip()
    parts = [part for part in [prelude, token_block, body] if part]
    return "\n\n".join(parts)


def run_child_script(script: Path, args: list[str]) -> None:
    env = build_env()
    result = subprocess.run([sys.executable, str(script)] + args, env=env, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout)
    if result.returncode != 0:
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        sys.exit(result.returncode)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
