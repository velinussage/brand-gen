#!/usr/bin/env python3
from __future__ import annotations

import os
import platform
import subprocess
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 2:
        print('Usage: python3 scripts/open_folder.py <path>', file=sys.stderr)
        return 1
    path = Path(sys.argv[1]).expanduser().resolve()
    path.mkdir(parents=True, exist_ok=True)
    system = platform.system().lower()
    if system == 'darwin':
        subprocess.run(['open', str(path)], check=False)
    elif system == 'windows':
        os.startfile(str(path))  # type: ignore[attr-defined]
    else:
        subprocess.run(['xdg-open', str(path)], check=False)
    print(path)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
