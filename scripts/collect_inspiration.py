#!/usr/bin/env python3
"""Capture inspiration screenshots from logosystem.co or any URL using agent-browser."""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_CANDIDATES = [REPO_ROOT / '.env', Path.home() / '.claude' / '.env']
URLS = {
    'symbol': 'https://logosystem.co/symbol',
    'wordmark': 'https://logosystem.co/wordmark',
    'symbol-text': 'https://logosystem.co/symbol-and-text',
    'brown': 'https://logosystem.co/color/brown',
    'beige': 'https://logosystem.co/color/beige',
    'black': 'https://logosystem.co/color/black',
    'all': 'https://logosystem.co/',
}


def load_env() -> dict[str, str]:
    env = dict(os.environ)
    for path in reversed(ENV_CANDIDATES):
        if not path.exists():
            continue
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, value = line.split('=', 1)
            env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def find_agent_browser(env: dict[str, str]) -> str | None:
    override = env.get('AGENT_BROWSER_BIN')
    if override:
        path = Path(override).expanduser()
        return str(path) if path.exists() else None

    try:
        proc = subprocess.run(['which', '-a', 'agent-browser'], capture_output=True, text=True, check=False)
        candidates = []
        seen = set()
        for line in proc.stdout.splitlines():
            line = line.strip()
            if not line or line in seen:
                continue
            seen.add(line)
            candidates.append(line)
        if not candidates:
            return None
        home = str(Path.home())
        candidates.sort(key=lambda p: (0 if p.startswith(home) else 1, p))
        return candidates[0]
    except Exception:
        return None


def run(cmd: list[str], env: dict[str, str]) -> None:
    proc = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if proc.returncode == 0:
        if proc.stdout.strip():
            print(proc.stdout.strip())
        return
    if proc.stdout.strip():
        print(proc.stdout.strip(), file=sys.stderr)
    if proc.stderr.strip():
        print(proc.stderr.strip(), file=sys.stderr)
    if 'Playwright' in proc.stderr or 'chrome-headless-shell' in proc.stderr:
        print('Hint: install the browser runtime with: npx playwright install', file=sys.stderr)
        print('If you have multiple installs, set AGENT_BROWSER_BIN=/full/path/to/agent-browser', file=sys.stderr)
    raise SystemExit(proc.returncode)


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r'[^a-z0-9]+', '-', value)
    return value.strip('-') or 'inspiration'


def main() -> int:
    parser = argparse.ArgumentParser(description='Capture inspiration with agent-browser')
    parser.add_argument('--category', default='symbol', choices=sorted(URLS.keys()),
                        help='Logo System category to browse when --url is not provided.')
    parser.add_argument('--url',
                        help='Arbitrary URL to capture instead of a predefined Logo System category.')
    parser.add_argument('--label',
                        help='Filename label for screenshots when using a custom URL.')
    parser.add_argument('--out-dir', type=Path)
    parser.add_argument('--count', type=int, default=3, help='Number of full-page screenshots to capture')
    parser.add_argument('--scroll-px', type=int, default=1600)
    parser.add_argument('--session', default=f'loggen-{time.time_ns()}-{os.getpid()}')
    parser.add_argument('--open-folder', action='store_true')
    args = parser.parse_args()

    env = load_env()
    agent_browser = find_agent_browser(env)
    if not agent_browser:
        print('ERROR: agent-browser is not installed. Install with: npm install -g agent-browser', file=sys.stderr)
        return 1

    if args.out_dir:
        out_dir = args.out_dir.expanduser().resolve()
    else:
        brand_gen_root = Path(env.get('BRAND_GEN_DIR')).expanduser() if env.get('BRAND_GEN_DIR') else (REPO_ROOT / '.brand-gen')
        if brand_gen_root.exists():
            config_path = brand_gen_root / 'config.json'
            config = {}
            if config_path.exists():
                try:
                    import json
                    config = json.loads(config_path.read_text())
                except Exception:
                    config = {}
            active = config.get('active')
            if active:
                out_dir = (brand_gen_root / 'brands' / str(active) / 'inspiration').resolve()
            else:
                out_dir = (brand_gen_root / 'inspiration').resolve()
        else:
            out_dir = (REPO_ROOT / 'examples' / 'inspiration').resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    env['AGENT_BROWSER_SESSION'] = args.session
    if args.url:
        url = args.url
        label = slugify(args.label or 'custom-reference')
    else:
        url = URLS[args.category]
        label = f'logosystem-{args.category}'

    run([agent_browser, 'open', url], env)
    run([agent_browser, 'wait', '--load', 'networkidle'], env)

    for idx in range(1, args.count + 1):
        shot = out_dir / f'{label}-{idx:02d}.png'
        run([agent_browser, 'screenshot', '--full', str(shot)], env)
        if idx != args.count:
            run([agent_browser, 'scroll', 'down', str(args.scroll_px)], env)
            run([agent_browser, 'wait', '--load', 'networkidle'], env)

    snapshot = out_dir / f'{label}-snapshot.txt'
    with snapshot.open('w') as fh:
        subprocess.run([agent_browser, 'snapshot', '-i', '-c'], check=True, env=env, stdout=fh)

    print(f'Saved inspiration set to: {out_dir}')
    print(f'Session: {args.session}')
    print(f'Agent browser binary: {agent_browser}')
    if args.open_folder:
        subprocess.run([sys.executable, str(REPO_ROOT / 'scripts' / 'open_folder.py'), str(out_dir)], check=False)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
