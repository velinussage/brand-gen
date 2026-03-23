#!/usr/bin/env bash
# brand-gen installer — sets up venv, installs package, checks deps.
set -euo pipefail

# ── Colors ────────────────────────────────────────────────────────────
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
BOLD='\033[1m'
RESET='\033[0m'

ok()   { printf "${GREEN}  ✓${RESET} %s\n" "$*"; }
warn() { printf "${YELLOW}  ⚠${RESET} %s\n" "$*"; }
fail() { printf "${RED}  ✗${RESET} %s\n" "$*"; }
info() { printf "  %s\n" "$*"; }

# ── Resolve repo root ────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

# ── Handle --shell-init flag ─────────────────────────────────────────
if [[ "${1:-}" == "--shell-init" ]]; then
    echo "# Add this line to your shell profile (~/.zshrc, ~/.bashrc, etc.):"
    echo "alias bgen='source ${REPO_ROOT}/.venv/bin/activate && bgen'"
    exit 0
fi

echo ""
printf "${BOLD}brand-gen installer${RESET}\n"
echo "─────────────────────────────────────"
echo ""

# Track summary
installed=()
missing=()

# ── 1. Python version check ──────────────────────────────────────────
PYTHON=""
for candidate in python3.12 python3.11 python3; do
    if command -v "$candidate" &>/dev/null; then
        ver="$("$candidate" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
        major="${ver%%.*}"
        minor="${ver##*.}"
        if (( major == 3 && minor >= 11 )); then
            PYTHON="$candidate"
            break
        fi
    fi
done

if [[ -z "$PYTHON" ]]; then
    fail "Python 3.11+ not found. Please install it first."
    exit 1
fi
ok "Python $("$PYTHON" --version 2>&1 | awk '{print $2}')"

# ── 2. Virtual environment ───────────────────────────────────────────
if [[ -d .venv ]]; then
    ok "Virtual environment exists at .venv/"
else
    info "Creating virtual environment…"
    "$PYTHON" -m venv .venv
    ok "Created .venv/"
fi

# Activate (within this subshell)
# shellcheck disable=SC1091
source .venv/bin/activate

# ── 3. Install in editable mode ──────────────────────────────────────
info "Installing brand-gen in editable mode…"
pip install --upgrade pip --quiet 2>/dev/null
pip install -e . --quiet 2>/dev/null
ok "pip install -e . completed"

# ── 4. Verify bgen CLI ──────────────────────────────────────────────
if .venv/bin/bgen --help &>/dev/null; then
    ok "bgen --help works"
    installed+=("bgen CLI")
else
    fail "bgen --help failed — check pyproject.toml [project.scripts]"
    missing+=("bgen CLI")
fi

# ── 5. .env file ─────────────────────────────────────────────────────
if [[ -f .env ]]; then
    ok ".env file exists"
    # Check if token is still the placeholder
    if grep -q 'r8_your_replicate_token_here' .env 2>/dev/null; then
        warn "REPLICATE_API_TOKEN is still the placeholder — update it in .env"
        missing+=("REPLICATE_API_TOKEN")
    else
        installed+=(".env configured")
    fi
else
    cp .env.example .env
    warn "Created .env from .env.example — add your REPLICATE_API_TOKEN"
    missing+=("REPLICATE_API_TOKEN")
fi

# ── 6. Optional dependencies ─────────────────────────────────────────
echo ""
printf "${BOLD}Optional dependencies${RESET}\n"
echo ""

check_cmd() {
    local name="$1" cmd="$2" hint="${3:-}"
    if command -v "$cmd" &>/dev/null; then
        ok "$name found ($(command -v "$cmd"))"
        installed+=("$name")
    else
        warn "$name not found${hint:+ — $hint}"
        missing+=("$name")
    fi
}

check_cmd "agent-browser" "agent-browser" "needed for browser automation"
check_cmd "ffmpeg"        "ffmpeg"        "brew install ffmpeg"
check_cmd "sips"          "sips"          "ships with macOS"

# ── 7. Summary ───────────────────────────────────────────────────────
echo ""
echo "─────────────────────────────────────"
printf "${BOLD}Summary${RESET}\n"
echo ""

if (( ${#installed[@]} )); then
    printf "${GREEN}Installed / OK:${RESET}\n"
    for item in "${installed[@]}"; do
        printf "  • %s\n" "$item"
    done
fi

if (( ${#missing[@]} )); then
    echo ""
    printf "${YELLOW}Missing / needs attention:${RESET}\n"
    for item in "${missing[@]}"; do
        printf "  • %s\n" "$item"
    done
fi

# ── 8. Activation hint ──────────────────────────────────────────────
echo ""
echo "─────────────────────────────────────"
printf "${BOLD}Next steps${RESET}\n"
echo ""
info "Activate the venv in your current shell:"
echo ""
printf "    ${GREEN}source .venv/bin/activate${RESET}\n"
echo ""
info "Or generate a shell alias with:"
echo ""
printf "    ${GREEN}./scripts/install.sh --shell-init${RESET}\n"
echo ""
