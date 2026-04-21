from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from typing import Any

try:
    from .command_registry import COMMAND_SPECS, build_parser
except ImportError:  # pragma: no cover - direct script compatibility
    from command_registry import COMMAND_SPECS, build_parser  # type: ignore


@dataclass(frozen=True)
class McpBridge:
    command: str
    tool_name: str
    description: str
    read_only: bool = False
    mutates_state: bool = True
    primitive: bool = True
    convenience: bool = False
    feature_tags: tuple[str, ...] = ()
    arg_renames: dict[str, str] = field(default_factory=dict)
    schema_overrides: dict[str, dict[str, Any]] = field(default_factory=dict)
    argv_defaults: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class McpBridgeOverride:
    tool_name: str | None = None
    description: str | None = None
    arg_renames: dict[str, str] = field(default_factory=dict)
    schema_overrides: dict[str, dict[str, Any]] = field(default_factory=dict)
    argv_defaults: dict[str, Any] = field(default_factory=dict)
    enabled: bool = True


try:
    COMMAND_SPEC_BY_NAME = {spec.name: spec for spec in COMMAND_SPECS}
except Exception:  # pragma: no cover
    COMMAND_SPEC_BY_NAME = {}


def _default_tool_name(command: str) -> str:
    return f"brand_{command.replace('-', '_')}"


COMMAND_OVERRIDES: dict[str, McpBridgeOverride] = {
    "types": McpBridgeOverride(argv_defaults={}),
    "bootstrap": McpBridgeOverride(description="Scan existing brand files into the manifest."),
    "show": McpBridgeOverride(argv_defaults={"format": "json"}),
    "diagnose": McpBridgeOverride(argv_defaults={"format": "json"}),
    "list-brands": McpBridgeOverride(tool_name="brand_list", argv_defaults={"format": "json"}),
    "extract-brand": McpBridgeOverride(tool_name="brand_extract"),
    "build-identity": McpBridgeOverride(tool_name="brand_build_identity"),
    "describe-brand": McpBridgeOverride(tool_name="brand_describe"),
    "append-forbidden-pattern": McpBridgeOverride(argv_defaults={"format": "json"}),
    "append-custom-scratchpad-note": McpBridgeOverride(argv_defaults={"format": "json"}),
    "promote-learning": McpBridgeOverride(argv_defaults={"format": "json"}),
    "promote-style-policy": McpBridgeOverride(argv_defaults={"format": "json"}),
    "set-motion-grammar": McpBridgeOverride(argv_defaults={"format": "json"}),
    "update-palette": McpBridgeOverride(argv_defaults={"format": "json"}),
    "update-typography": McpBridgeOverride(argv_defaults={"format": "json"}),
    "update-devices": McpBridgeOverride(argv_defaults={"format": "json"}),
    "show-identity": McpBridgeOverride(argv_defaults={"format": "json"}),
    "show-blackboard": McpBridgeOverride(argv_defaults={"format": "json"}),
    "prepare-run": McpBridgeOverride(argv_defaults={"format": "json"}),
    "plan-run": McpBridgeOverride(argv_defaults={"format": "json"}),
    "validate-run": McpBridgeOverride(argv_defaults={"format": "json"}),
    "execute-run": McpBridgeOverride(argv_defaults={"format": "json"}),
    "review-run": McpBridgeOverride(argv_defaults={"format": "json"}),
    "evolve-run": McpBridgeOverride(argv_defaults={"format": "json"}),
    "orchestrate-material": McpBridgeOverride(argv_defaults={"format": "json"}),
    "show-session-summary": McpBridgeOverride(argv_defaults={"format": "json"}),
    "context-snapshot": McpBridgeOverride(argv_defaults={"format": "json"}),
    "capabilities": McpBridgeOverride(argv_defaults={"format": "json"}),
    "workspace-status": McpBridgeOverride(argv_defaults={"format": "json"}),
    "improvement-questions": McpBridgeOverride(argv_defaults={"format": "json"}),
    "show-workflow-lineage": McpBridgeOverride(argv_defaults={"format": "json"}),
    "list-runs": McpBridgeOverride(argv_defaults={"format": "json"}),
    "get-run": McpBridgeOverride(argv_defaults={"format": "json"}),
    "get-plan": McpBridgeOverride(argv_defaults={"format": "json"}),
    "get-critique": McpBridgeOverride(argv_defaults={"format": "json"}),
    "get-scratchpad": McpBridgeOverride(argv_defaults={"format": "json"}),
    "get-review-packet": McpBridgeOverride(argv_defaults={"format": "json"}),
    "get-version": McpBridgeOverride(argv_defaults={"format": "json"}),
    "compare-versions": McpBridgeOverride(argv_defaults={"format": "json"}),
    "show-reference-analysis": McpBridgeOverride(argv_defaults={"format": "json"}),
    "prompts-list": McpBridgeOverride(argv_defaults={"format": "json"}),
    "prompts-get": McpBridgeOverride(argv_defaults={"format": "json"}),
    "route-request": McpBridgeOverride(argv_defaults={"format": "json"}),
    "resolve-prompt": McpBridgeOverride(argv_defaults={"format": "json"}),
    "review-prompt": McpBridgeOverride(argv_defaults={"format": "json"}),
    "validate-identity": McpBridgeOverride(argv_defaults={"format": "json"}),
    "parse-design-memory": McpBridgeOverride(argv_defaults={"format": "json"}),
    "extract-css-variables": McpBridgeOverride(argv_defaults={"format": "json"}),
    "diff-design-memory": McpBridgeOverride(argv_defaults={"format": "json"}),
    "create-brand": McpBridgeOverride(
        tool_name="brand_create",
        arg_renames={"value_props": "value_prop"},
    ),
    "extract-inspiration": McpBridgeOverride(
        tool_name="brand_extract_inspiration",
        arg_renames={"sources": "source"},
    ),
    "consolidate-inspiration": McpBridgeOverride(argv_defaults={"format": "json"}),
    "capture-product": McpBridgeOverride(
        tool_name="brand_capture_product",
        arg_renames={"shots": "shot"},
        argv_defaults={"open_folder": True},
    ),
    "explore-brand": McpBridgeOverride(
        tool_name="brand_explore",
        arg_renames={"materials": "material", "sources": "source"},
    ),
    "review-brand": McpBridgeOverride(tool_name="brand_review", argv_defaults={"open": True}),
    "collect-examples": McpBridgeOverride(arg_renames={"sites": "site"}, argv_defaults={"open_folder": True}),
    "build-generation-scratchpad": McpBridgeOverride(
        arg_renames={"reference_assets": "image"},
        argv_defaults={"format": "json"},
    ),
    "critique-plan": McpBridgeOverride(
        arg_renames={"reference_assets": "image"},
        argv_defaults={"format": "json"},
    ),
    "submit-review": McpBridgeOverride(tool_name="brand_submit_review", argv_defaults={"format": "json"}),
    "plan-set": McpBridgeOverride(argv_defaults={"format": "json"}),
    "validate-brand-fit": McpBridgeOverride(argv_defaults={"format": "json"}),
    "validate-set": McpBridgeOverride(argv_defaults={"format": "json"}),
    "ideate-copy": McpBridgeOverride(argv_defaults={"format": "json"}),
    "ideate-messaging": McpBridgeOverride(argv_defaults={"format": "json"}),
    "update-messaging": McpBridgeOverride(argv_defaults={"format": "json"}),
    "show-iteration-memory": McpBridgeOverride(argv_defaults={"format": "json"}),
    "update-iteration-memory": McpBridgeOverride(argv_defaults={"format": "json"}),
    "suggest-role-pack": McpBridgeOverride(argv_defaults={"format": "json"}),
    "plan-material": McpBridgeOverride(argv_defaults={"format": "json"}),
    "plan-draft": McpBridgeOverride(argv_defaults={"format": "json"}),
    "ideate-material": McpBridgeOverride(argv_defaults={"format": "json"}),
    "generate-once": McpBridgeOverride(argv_defaults={"format": "json"}),
    "generate": McpBridgeOverride(
        schema_overrides={
            "max_iterations": {"type": "integer", "minimum": 1, "maximum": 3, "default": 1, "description": "Max generate→critique→refine loops."},
            "internal_vlm_critique": {"type": "boolean", "default": False, "description": "Opt into the legacy internal VLM critique/refine loop after generation."},
            "skip_vlm": {"type": "boolean", "default": False, "description": "Deprecated compatibility flag. Internal VLM critique is off by default unless internal_vlm_critique is true."},
        }
    ),
    "derive-mockup": McpBridgeOverride(argv_defaults={"format": "json"}),
    "derive-video": McpBridgeOverride(argv_defaults={"format": "json"}),
    "feedback": McpBridgeOverride(arg_renames={"lock_fragments": "lock"}),
    "evolve": McpBridgeOverride(description="Analyze prompt patterns across scored brand materials."),
    "pipeline": McpBridgeOverride(enabled=False),
    "inspire": McpBridgeOverride(enabled=False),
}


def _subparser_map() -> dict[str, argparse.ArgumentParser]:
    parser = build_parser()
    subparsers: dict[str, argparse.ArgumentParser] = {}
    for action in parser._actions:  # type: ignore[attr-defined]
        if isinstance(action, argparse._SubParsersAction):
            subparsers.update(action.choices)
    return subparsers


def _build_cli_bridges() -> tuple[McpBridge, ...]:
    bridges: list[McpBridge] = []
    for spec in COMMAND_SPECS:
        override = COMMAND_OVERRIDES.get(spec.name, McpBridgeOverride())
        if not override.enabled:
            continue
        bridges.append(
            McpBridge(
                command=spec.name,
                tool_name=override.tool_name or _default_tool_name(spec.name),
                description=override.description or spec.help,
                read_only=spec.read_only,
                mutates_state=spec.mutates_state,
                primitive=spec.primitive,
                convenience=spec.convenience,
                feature_tags=tuple(spec.feature_tags),
                arg_renames=dict(override.arg_renames),
                schema_overrides=dict(override.schema_overrides),
                argv_defaults=dict(override.argv_defaults),
            )
        )
    return tuple(bridges)


CLI_BRIDGES: tuple[McpBridge, ...] = _build_cli_bridges()
READ_ONLY_BRIDGES: tuple[McpBridge, ...] = tuple(bridge for bridge in CLI_BRIDGES if bridge.read_only)
SUBPARSER_MAP = _subparser_map()
BRIDGE_BY_TOOL = {bridge.tool_name: bridge for bridge in CLI_BRIDGES}
BRIDGED_TOOL_NAMES = set(BRIDGE_BY_TOOL)


def _json_type_for_action(action: argparse.Action) -> str:
    if isinstance(action, (argparse._StoreTrueAction, argparse._StoreFalseAction)):
        return "boolean"
    if getattr(action, "type", None) is int:
        return "integer"
    if getattr(action, "type", None) is json.loads:
        return "object"
    if action.nargs in ("+", "*") or isinstance(action, argparse._AppendAction):
        return "array"
    return "string"


def _json_property_for_action(action: argparse.Action, override: dict[str, Any] | None = None) -> dict[str, Any]:
    if override:
        return dict(override)
    prop_type = _json_type_for_action(action)
    if prop_type == "array":
        return {"type": "array", "items": {"type": "string"}}
    if prop_type == "object":
        prop: dict[str, Any] = {"type": "object"}
    else:
        prop = {"type": prop_type}
    if action.choices:
        prop["enum"] = list(action.choices)
    if isinstance(action, (argparse._StoreTrueAction, argparse._StoreFalseAction)):
        prop["default"] = bool(action.default)
    elif action.default not in (None, argparse.SUPPRESS):
        prop["default"] = action.default
    if action.help:
        prop["description"] = action.help
    return prop


def _mcp_arg_name_for_dest(bridge: McpBridge, dest: str) -> str:
    for mcp_name, cli_dest in bridge.arg_renames.items():
        if cli_dest == dest:
            return mcp_name
    return dest


def build_tool_schema(bridge: McpBridge) -> dict[str, Any]:
    parser = SUBPARSER_MAP[bridge.command]
    properties: dict[str, Any] = {}
    required: list[str] = []
    for action in parser._actions:
        if action.dest == "help":
            continue
        prop_name = _mcp_arg_name_for_dest(bridge, action.dest)
        override = bridge.schema_overrides.get(prop_name)
        properties[prop_name] = _json_property_for_action(action, override)
        if getattr(action, "required", False):
            required.append(prop_name)
    schema: dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required
    return schema


def build_bridge_tools() -> list[dict[str, Any]]:
    return [
        {
            "name": bridge.tool_name,
            "description": bridge.description,
            "inputSchema": build_tool_schema(bridge),
        }
        for bridge in CLI_BRIDGES
    ]


def argv_from_mcp_args(bridge: McpBridge, arguments: dict[str, Any]) -> list[str]:
    parser = SUBPARSER_MAP[bridge.command]
    argv: list[str] = [bridge.command]
    values: dict[str, Any] = dict(bridge.argv_defaults)
    for key, value in (arguments or {}).items():
        values[bridge.arg_renames.get(key, key)] = value
    for action in parser._actions:
        if action.dest == "help":
            continue
        if action.dest not in values:
            continue
        value = values[action.dest]
        if value is None:
            continue
        if getattr(action, "type", None) is json.loads and not isinstance(value, str):
            value = json.dumps(value)
        if not action.option_strings:
            if isinstance(value, list):
                argv.extend(str(item) for item in value)
            else:
                argv.append(str(value))
            continue
        if isinstance(action, argparse._StoreTrueAction):
            if value:
                argv.append(action.option_strings[0])
            continue
        if isinstance(action, argparse._StoreFalseAction):
            if value is False:
                argv.append(action.option_strings[0])
            continue
        if isinstance(action, argparse._AppendAction):
            items = value if isinstance(value, list) else [value]
            for item in items:
                argv.extend([action.option_strings[0], str(item)])
            continue
        if action.nargs in ("+", "*") and isinstance(value, list):
            argv.append(action.option_strings[0])
            argv.extend(str(item) for item in value)
            continue
        argv.extend([action.option_strings[0], str(value)])
    return argv
