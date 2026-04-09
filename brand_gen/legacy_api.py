"""Deprecated compatibility export surface for older external callers.

Internal brand-gen modules and tests should import from the concrete package
modules directly (for example ``mcp.material_planning`` or ``mcp.runtime``)
rather than routing through this shim. The file remains only as a thin,
external-facing compatibility layer while older consumers migrate.
"""

from __future__ import annotations

from .blackboard import (
    append_blackboard_decision,
    get_workflow_lineage,
)
from .commands.inspection import cmd_compare
from .generation_flow import (
    assemble_generation_scratchpad,
    execute_generation_scratchpad,
)
from .material_planning import (
    NON_INTERFACE_DOCTRINE_CAP,
    NON_INTERFACE_PRELUDE_CAP,
    NON_INTERFACE_REF_ANALYSIS_CAP,
    NON_INTERFACE_TOTAL_PRELUDE_CAP,
    build_effective_prompt,
    build_material_plan_from_args,
    build_plan_critique_payload,
    cap_text_at_sentence,
    classify_workflow_route_smart,
    derive_copy_candidates,
    load_plan_payload,
    resolve_material_prompt_snippet,
    review_prompt_architecture,
)
from .media_board import build_agent_regeneration_prompt
from .runtime import (
    INTERFACE_MATERIAL_KEYS,
    NON_INTERFACE_MATERIAL_KEYS,
    SUPPORTED_IMAGE_EXTS,
    build_iteration_memory_snippet,
    collect_workflow_artifacts,
    get_brand_dir,
    load_blackboard,
    load_brand_memory,
    load_json_file,
    load_manifest,
    load_workflow_router_rules,
    normalize_iteration_memory,
    persist_generation_scratchpad_to_blackboard,
    persist_plan_critique_to_blackboard,
    persist_plan_draft_to_blackboard,
    resolve_workflow_id,
    role_pack_material_key,
    save_blackboard,
    save_iteration_memory,
    save_generation_scratchpad,
    save_plan_critique,
    save_plan_draft,
)
from .vlm_critique import refine_prompt_from_vlm_critique, run_vlm_critique

__all__ = [
    "INTERFACE_MATERIAL_KEYS",
    "NON_INTERFACE_DOCTRINE_CAP",
    "NON_INTERFACE_MATERIAL_KEYS",
    "NON_INTERFACE_PRELUDE_CAP",
    "NON_INTERFACE_REF_ANALYSIS_CAP",
    "NON_INTERFACE_TOTAL_PRELUDE_CAP",
    "SUPPORTED_IMAGE_EXTS",
    "append_blackboard_decision",
    "assemble_generation_scratchpad",
    "build_agent_regeneration_prompt",
    "build_effective_prompt",
    "build_iteration_memory_snippet",
    "build_material_plan_from_args",
    "build_plan_critique_payload",
    "cap_text_at_sentence",
    "classify_workflow_route_smart",
    "cmd_compare",
    "collect_workflow_artifacts",
    "derive_copy_candidates",
    "execute_generation_scratchpad",
    "get_brand_dir",
    "get_workflow_lineage",
    "load_blackboard",
    "load_brand_memory",
    "load_json_file",
    "load_manifest",
    "load_plan_payload",
    "load_workflow_router_rules",
    "normalize_iteration_memory",
    "persist_generation_scratchpad_to_blackboard",
    "persist_plan_critique_to_blackboard",
    "persist_plan_draft_to_blackboard",
    "refine_prompt_from_vlm_critique",
    "resolve_material_prompt_snippet",
    "resolve_workflow_id",
    "review_prompt_architecture",
    "role_pack_material_key",
    "run_vlm_critique",
    "save_blackboard",
    "save_generation_scratchpad",
    "save_iteration_memory",
    "save_plan_critique",
    "save_plan_draft",
]
