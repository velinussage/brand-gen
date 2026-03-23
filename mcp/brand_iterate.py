#!/usr/bin/env python3
"""Compatibility shim for the brand-gen CLI.

Preferred execution:
  python -m mcp.brand_iterate ...
  brand-iterate ...

Legacy execution still works:
  python3 mcp/brand_iterate.py ...
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _reexec_package_mode() -> "NoReturn":
    repo_root = Path(__file__).resolve().parent.parent
    os.chdir(repo_root)
    os.execv(sys.executable, [sys.executable, "-m", "mcp.brand_iterate", *sys.argv[1:]])

if __name__ == "__main__":
    if __package__ in {None, ""}:
        _reexec_package_mode()
    else:
        from .cli import main

        raise SystemExit(main())
