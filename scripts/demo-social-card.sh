#!/usr/bin/env bash
set -euo pipefail

python3 mcp/brand_iterate.py pipeline \
  --material-type x-feed \
  --mode hybrid \
  --format json
