#!/usr/bin/env python3
"""Validate the brand-gen local environment."""
from __future__ import annotations

import os
import platform
import shutil
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_CANDIDATES = [REPO_ROOT / '.env', Path.home() / '.claude' / '.env']
REQUIRED_COMMANDS = {
    'python3': 'Python 3 is required to run the scripts.',
    'agent-browser': 'Used to collect inspiration screenshots from Logo System.',
}
OPTIONAL_COMMANDS = {
    'sips': 'Used on macOS to convert generated WEBP outputs to PNG automatically.',
    'ffmpeg': 'Used to convert generated short videos into GIFs.',
}
REQUIRED_ENV = {
    'REPLICATE_API_TOKEN': 'Required for image generation.',
}
OPTIONAL_ENV = {
    'BROWSERBASE_API_KEY': 'Optional remote browser provider.',
    'BROWSERBASE_PROJECT_ID': 'Optional remote browser provider project id.',
    'SCREENSHOTS_DIR': 'Optional default output base directory.',
    'LOGO_DIR': 'Legacy output directory override.',
    'BRAND_DIR': 'Preferred output directory override for brand materials.',
    'AGENT_BROWSER_BIN': 'Optional override when multiple agent-browser installs exist.',
}


def load_env_file(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    if not path.exists():
        return data
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        data[key.strip()] = value.strip().strip('"').strip("'")
    return data


def merged_env() -> tuple[dict[str, str], list[Path]]:
    env = dict(os.environ)
    used: list[Path] = []
    for path in reversed(ENV_CANDIDATES):
        values = load_env_file(path)
        if values:
            env.update(values)
            used.append(path)
    return env, used


def mask(value: str) -> str:
    if len(value) <= 8:
        return 'set'
    return value[:6] + '...' + value[-4:]


def find_all_agent_browsers() -> list[str]:
    proc = subprocess.run(['which', '-a', 'agent-browser'], capture_output=True, text=True, check=False)
    seen = set()
    paths = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line or line in seen:
            continue
        seen.add(line)
        paths.append(line)
    return paths


def main() -> int:
    env, used_files = merged_env()
    failures = 0

    print('== brand-gen setup validation ==')
    print(f'Repo root: {REPO_ROOT}')
    print(f'Platform: {platform.platform()}')
    if used_files:
        print('Loaded env files (repo .env wins over ~/.claude/.env):')
        for path in used_files:
            print(f'  - {path}')
    else:
        print('Loaded env files: none')
        print('  Hint: copy .env.example to .env in the repo root or use ~/.claude/.env')

    print('\nRequired commands:')
    for name, note in REQUIRED_COMMANDS.items():
        path = shutil.which(name)
        ok = bool(path)
        print(f"  [{'OK' if ok else 'MISSING'}] {name:<14} {path or note}")
        if not ok:
            failures += 1

    agent_browsers = find_all_agent_browsers()
    if agent_browsers:
        print('  Agent-browser candidates:')
        for path in agent_browsers:
            print(f'    - {path}')
        if len(agent_browsers) > 1:
            print('  Note: multiple agent-browser installs found. Use AGENT_BROWSER_BIN in .env if the wrong one is picked.')

    print('\nOptional commands:')
    for name, note in OPTIONAL_COMMANDS.items():
        path = shutil.which(name)
        ok = bool(path)
        print(f"  [{'OK' if ok else 'optional'}] {name:<14} {path or note}")

    print('\nRequired environment:')
    for key, note in REQUIRED_ENV.items():
        value = env.get(key)
        ok = bool(value)
        print(f"  [{'OK' if ok else 'MISSING'}] {key:<22} {mask(value) if value else note}")
        if not ok:
            failures += 1

    print('\nOptional environment:')
    for key, note in OPTIONAL_ENV.items():
        value = env.get(key)
        print(f"  [{'set' if value else 'optional'}] {key:<22} {mask(value) if value else note}")

    print('\nInstall notes:')
    print('  - agent-browser: npm install -g agent-browser')
    print('  - If agent-browser complains about missing Playwright browsers: npx playwright install')
    print('  - Register `mcp/brand_iterate_mcp.py` with your preferred MCP host if you want tool-mode use.')
    print('  - Replicate token: https://replicate.com/account/api-tokens')

    if failures:
        print(f'\nValidation failed: {failures} required item(s) missing.')
        return 1

    print('\nValidation passed. You can start the Ralph loop.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
