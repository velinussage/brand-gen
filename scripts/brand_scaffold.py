#!/usr/bin/env python3
"""Compatibility wrapper for package-owned brand scaffold helpers."""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from brand_gen.brand_scaffold import *  # noqa: F401,F403
