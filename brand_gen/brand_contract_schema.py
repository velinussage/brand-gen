"""Brand-contract JSON Schema loader and validator.

The schema is `data/schemas/brand_contract.schema.json`. This module loads
it once and exposes `validate_brand_contract()` for use by the loader (PR-1)
and the typed mutation verbs (PR-1, PR-2, PR-6).

Validation is best-effort: if `jsonschema` is not installed, validation is
skipped with a warning. We do not want to add a hard dependency just for
a contract sanity check; the typed verbs already constrain inputs at the
argparse layer.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .runtime_paths import SCRIPT_DIR

_SCHEMA_PATH = SCRIPT_DIR.parent / "data" / "schemas" / "brand_contract.schema.json"
_schema_cache: dict[str, Any] | None = None


def brand_contract_schema_path() -> Path:
    return _SCHEMA_PATH


def load_brand_contract_schema() -> dict[str, Any]:
    global _schema_cache
    if _schema_cache is not None:
        return _schema_cache
    if not _SCHEMA_PATH.exists():
        _schema_cache = {}
        return _schema_cache
    _schema_cache = json.loads(_SCHEMA_PATH.read_text())
    return _schema_cache


def validate_brand_contract(contract: dict[str, Any]) -> tuple[bool, str]:
    """Validate a brand-contract dict against the JSON Schema.

    Returns (ok, message). ok=True with empty message means valid (or that
    `jsonschema` is not installed and validation was skipped). ok=False
    with a non-empty message means a validation error.
    """
    try:
        import jsonschema
    except ImportError:
        return True, "jsonschema not installed; validation skipped"
    schema = load_brand_contract_schema()
    if not schema:
        return True, "schema file missing; validation skipped"
    try:
        jsonschema.validate(contract, schema)
    except jsonschema.ValidationError as err:
        return False, f"{err.message} (at {list(err.absolute_path) or 'root'})"
    return True, ""
