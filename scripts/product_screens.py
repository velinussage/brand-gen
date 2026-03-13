#!/usr/bin/env python3
"""Plan and capture product screenshots with agent-browser."""
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
DEFAULT_SURFACES = ['homepage-hero', 'dashboard-overview', 'key-feature', 'detail-state', 'settings', 'mobile-or-narrow']


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
    proc = subprocess.run(['which', '-a', 'agent-browser'], capture_output=True, text=True, check=False)
    seen = set()
    candidates = []
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


def run(cmd: list[str], env: dict[str, str]) -> None:
    proc = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if proc.stdout.strip():
        print(proc.stdout.strip())
    if proc.returncode != 0:
        if proc.stderr.strip():
            print(proc.stderr.strip(), file=sys.stderr)
        if 'Playwright' in proc.stderr or 'chrome-headless-shell' in proc.stderr:
            print('Hint: install the browser runtime with: npx playwright install', file=sys.stderr)
        raise SystemExit(proc.returncode)


def slugify(value: str) -> str:
    value = re.sub(r'[^a-zA-Z0-9]+', '-', value.strip().lower())
    return value.strip('-') or 'shot'


def cmd_plan(args) -> int:
    surfaces = args.surface or DEFAULT_SURFACES
    output = Path(args.output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    product_name = args.product_name or 'Product'
    goal = args.goal or 'marketing screenshots and branded feature visuals'
    lines = [
        f'# {product_name} product screenshot shot list',
        '',
        f'Goal: {goal}',
        '',
        '## Ask before capturing',
        '- Which screens matter most right now?',
        '- Which states should be shown: default, filled, empty, comparison, modal, onboarding?',
        '- Do we need public marketing pages, authenticated product views, or both?',
        '- Do we want literal screenshots, browser-framed illustrations, or both?',
        '- Which outputs are needed from this capture: docs, banners, X cards, LinkedIn cards, feature animations?',
        '',
        '## Recommended shots',
        '| Priority | Surface | Why it matters | Confirmed URL | Notes |',
        '|---|---|---|---|---|',
    ]
    for idx, surface in enumerate(surfaces, start=1):
        lines.append(f'| {idx} | {surface} | Capture the clearest branded view of this surface. |  |  |')
    lines += [
        '',
        '## Framing heuristics',
        '- Favor one clear product story per screenshot.',
        '- Capture one wide contextual shot and one tighter feature-focused shot when possible.',
        '- Prefer filled / realistic data over empty placeholder states unless the empty state is the feature.',
        '- Keep navigation visible when brand framing matters; crop tighter when feature clarity matters more.',
        '- Note which shots should later become browser illustrations, banners, or social cards.',
        '',
    ]
    output.write_text('\n'.join(lines))
    print(f'Shot list: {output}')
    return 0


def parse_shots(args) -> list[tuple[str, str]]:
    shots = []
    for value in args.shot or []:
        if '=' not in value:
            raise SystemExit(f"Invalid --shot '{value}'. Use label=url")
        label, url = value.split('=', 1)
        shots.append((slugify(label), url.strip()))
    if args.url:
        shots.append((slugify(args.label or 'product-view'), args.url))
    if not shots:
        raise SystemExit('Provide at least one --shot label=url or --url')
    return shots


def cmd_capture(args) -> int:
    env = load_env()
    agent_browser = find_agent_browser(env)
    if not agent_browser:
        print('ERROR: agent-browser is not installed. Install with: npm install -g agent-browser', file=sys.stderr)
        return 1

    out_dir = Path(args.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    shots = parse_shots(args)

    for label, url in shots:
        session = args.session or f'brand-product-{slugify(label)}-{time.time_ns()}-{os.getpid()}'
        env['AGENT_BROWSER_SESSION'] = session
        run([agent_browser, 'open', url], env)
        run([agent_browser, 'wait', '--load', 'networkidle'], env)
        for idx in range(1, args.count + 1):
            output = out_dir / f'{label}-{idx:02d}.png'
            run([agent_browser, 'screenshot', '--full', str(output)], env)
            if idx != args.count:
                run([agent_browser, 'scroll', 'down', str(args.scroll_px)], env)
                run([agent_browser, 'wait', '--load', 'networkidle'], env)
        snapshot = out_dir / f'{label}-snapshot.txt'
        with snapshot.open('w') as fh:
            subprocess.run([agent_browser, 'snapshot', '-i', '-c'], env=env, check=False, stdout=fh)
        print(f'Captured {label} -> {url}')

    if args.open_folder:
        subprocess.run([sys.executable, str(REPO_ROOT / 'scripts' / 'open_folder.py'), str(out_dir)], check=False)
    print(f'Product screenshots: {out_dir}')
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description='Plan and capture product screenshots')
    sub = parser.add_subparsers(dest='command', required=True)

    plan = sub.add_parser('plan', help='Create a shot list before capture')
    plan.add_argument('--product-name', help='Product or app name')
    plan.add_argument('--goal', help='What these screenshots are for')
    plan.add_argument('--surface', action='append', help='Preferred shot surface; repeat as needed')
    plan.add_argument('--output', required=True, help='Output markdown path')

    capture = sub.add_parser('capture', help='Capture product screenshots')
    capture.add_argument('--shot', action='append', help='Shot spec as label=url. Repeat for multiple shots')
    capture.add_argument('--url', help='Fallback single URL')
    capture.add_argument('--label', help='Fallback single label when using --url')
    capture.add_argument('--out-dir', required=True, help='Output directory')
    capture.add_argument('--count', type=int, default=1, help='Number of screenshots per shot')
    capture.add_argument('--scroll-px', type=int, default=1200, help='Scroll distance between screenshots')
    capture.add_argument('--session', help='Reuse an existing agent-browser session (for authenticated capture)')
    capture.add_argument('--open-folder', action='store_true', help='Open output folder after capture')

    args = parser.parse_args()
    if args.command == 'plan':
        return cmd_plan(args)
    return cmd_capture(args)


if __name__ == '__main__':
    raise SystemExit(main())
