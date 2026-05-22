#!/usr/bin/env python3
"""Synchronize neutral agent markdown files to host mirrors.

Parses `/agents/*.agent.md` files, merges host-specific overrides and
dynamic tool permissions from `brand_gen/agent_specialization.py`,
writes byte-identical prompt bodies to:
  - `.claude/agents/`
  - `.pi/agents/`
  - `skills/brand-gen/claude-agents/`

Also purges retired `brand-*` legacy mirror files.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Add repo root to python path to import brand_gen
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from brand_gen.agent_specialization import AGENT_BY_ID, AGENT_SPECIALIZATIONS


def parse_simple_yaml(text: str) -> dict:
    """A robust, standard-library-only nested YAML parser for agent frontmatter."""
    lines = text.strip().split("\n")
    data: dict = {}
    path: list[tuple[int, str]] = []

    for line in lines:
        if not line.strip() or line.strip().startswith("#"):
            continue
        # Count leading spaces
        indent = len(line) - len(line.lstrip())
        content = line.strip()

        # Check if there is a colon
        if ":" not in content:
            continue

        k, v = content.split(":", 1)
        k = k.strip()
        v = v.strip()

        # Clean quotes
        if v.startswith('"') and v.endswith('"'):
            v = v[1:-1]
        elif v.startswith("'") and v.endswith("'"):
            v = v[1:-1]

        # Determine nesting level based on indentation
        while path and path[-1][0] >= indent:
            path.pop()

        # Place key-value in the nested dictionary
        current_dict = data
        for _, pk in path:
            current_dict = current_dict[pk]

        if v:
            current_dict[k] = v
        else:
            current_dict[k] = {}
            path.append((indent, k))

    return data


def sync_agents() -> None:
    agents_dir = REPO_ROOT / "agents"
    if not agents_dir.exists():
        print(f"Error: agents directory not found at {agents_dir}")
        sys.exit(1)

    # Mirrors setup
    mirrors = {
        "claude": REPO_ROOT / ".claude" / "agents",
        "pi": REPO_ROOT / ".pi" / "agents",
        "skills": REPO_ROOT / "skills" / "brand-gen" / "claude-agents",
    }

    # Ensure all mirror directories exist
    for path in mirrors.values():
        path.mkdir(parents=True, exist_ok=True)

    active_agent_ids = {spec.agent_id for spec in AGENT_SPECIALIZATIONS}
    processed_ids = set()

    agent_files = list(agents_dir.glob("*.agent.md"))
    if not agent_files:
        print("Warning: No *.agent.md files found.")

    for agent_file in agent_files:
        # Extract agent ID (e.g. "art-director" from "art-director.agent.md")
        agent_id = agent_file.name.split(".")[0]
        processed_ids.add(agent_id)

        if agent_id not in AGENT_BY_ID:
            print(f"Warning: Agent '{agent_id}' from file '{agent_file.name}' is not in brand_gen/agent_specialization.py registry. Skipping.")
            continue

        spec = AGENT_BY_ID[agent_id]
        content = agent_file.read_text(encoding="utf-8")

        if not content.startswith("---"):
            print(f"Error: File '{agent_file.name}' does not start with '---'. Skipping.")
            continue

        parts = content.split("---", 2)
        if len(parts) < 3:
            print(f"Error: Could not parse frontmatter in '{agent_file.name}'. Skipping.")
            continue

        frontmatter_text = parts[1]
        body = parts[2]

        frontmatter = parse_simple_yaml(frontmatter_text)
        description = frontmatter.get("description", spec.role)

        hosts_overlay = frontmatter.get("hosts", {})

        # Generate files for each mirror
        for host_name, mirror_dir in mirrors.items():
            overlay_source = "claude" if host_name == "skills" else host_name
            overlay = hosts_overlay.get(overlay_source, {})
            model = overlay.get("model")
            if not model:
                # Fallback to general model or raise error
                model = frontmatter.get("model", "claude-opus-4-7")

            reasoning_effort = overlay.get("reasoning_effort")

            # Build the clean frontmatter block
            yaml_lines = [
                "---",
                f"name: {agent_id}",
                f"description: {description}",
                f"model: {model}",
            ]
            if reasoning_effort:
                yaml_lines.append(f"reasoning_effort: {reasoning_effort}")

            tools_str = ", ".join(spec.canonical_tools)
            yaml_lines.append(f"tools: [{tools_str}]")
            yaml_lines.append("---")

            new_frontmatter = "\n".join(yaml_lines)
            final_content = new_frontmatter + "\n\n" + body.strip() + "\n"

            target_file = mirror_dir / f"{agent_id}.md"
            target_file.write_text(final_content, encoding="utf-8")
            print(f"Synced: {target_file.relative_to(REPO_ROOT)}")

    # Purge legacy or retired files
    for host_name, mirror_dir in mirrors.items():
        for path in mirror_dir.glob("*.md"):
            name = path.stem
            # Do NOT delete the emergency fallback
            if name == "brand-pipeline-executor":
                continue

            # If it is retired (starts with 'brand-' or is not in active agent IDs)
            if name.startswith("brand-") or name not in active_agent_ids:
                path.unlink()
                print(f"Purged: {path.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    sync_agents()
