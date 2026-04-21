from __future__ import annotations

import argparse
from dataclasses import dataclass
import inspect
from typing import Callable

from .cli_builders import CliBuilder, build_cli_parser, get_cli_builder
from .runtime import INSPIRE_URLS, RuntimeContext, list_material_types
from .commands.generation import cmd_create_video, cmd_derive_mockup, cmd_derive_video, cmd_generate, cmd_generate_set, cmd_pipeline
from .commands.generation import cmd_generate_once
from .commands.identity import (
    cmd_build_identity,
    cmd_describe_brand,
    cmd_export_design_tokens,
    cmd_extract_brand,
    cmd_extract_css_variables,
    cmd_diff_design_memory,
    cmd_parse_design_memory,
    cmd_show_identity,
    cmd_validate_identity,
)
from .commands.inspection import (
    cmd_capabilities,
    cmd_context_snapshot,
    cmd_compare,
    cmd_diagnose,
    cmd_inspiration_status,
    cmd_prompts_get,
    cmd_prompts_list,
    cmd_show,
    cmd_show_blackboard,
    cmd_show_iteration_memory,
    cmd_show_reference_analysis,
    cmd_show_rubric,
    cmd_show_session_summary,
    cmd_workspace_status,
    cmd_show_workflow_lineage,
    cmd_update_iteration_memory,
)
from .commands.planning import (
    cmd_build_generation_scratchpad,
    cmd_critique_plan,
    cmd_ideate_copy,
    cmd_ideate_material,
    cmd_ideate_messaging,
    cmd_improvement_questions,
    cmd_plan_material,
    cmd_plan_draft,
    cmd_plan_set,
    cmd_promote_messaging,
    cmd_reference_rubric,
    cmd_resolve_prompt,
    cmd_review_prompt,
    cmd_route_request,
    cmd_submit_reference_analysis,
    cmd_suggest_role_pack,
    cmd_suggest_layout,
    cmd_update_messaging,
    cmd_validate_brand_fit,
)
from .commands.references import (
    cmd_capture_product,
    cmd_collect_examples,
    cmd_consolidate_inspiration,
    cmd_inspiration_capture,
    cmd_inspiration_clear,
    cmd_inspiration_configure,
    cmd_inspiration_list,
    cmd_configure_inspiration,
    cmd_example_sources,
    cmd_explore_brand,
    cmd_extract_inspiration,
    cmd_inspiration_mode,
    cmd_inspire,
    cmd_shotlist,
    cmd_social_specs,
)
from .commands.review import (
    cmd_critique_rubric,
    cmd_evolve,
    cmd_feedback,
    cmd_review_brand,
    cmd_submit_critique,
    cmd_validate_set,
)
from .commands.state import cmd_bootstrap, cmd_create_brand, cmd_init, cmd_list_brands, cmd_start_testing, cmd_use
from .commands.composite import cmd_composite_illustration


@dataclass(frozen=True)
class CommandSpec:
    name: str
    handler: Callable
    help: str = ''
    aliases: tuple[str, ...] = ()
    cli_builder: CliBuilder | None = None
    read_only: bool = False
    mutates_state: bool = True
    primitive: bool = True
    convenience: bool = False
    feature_tags: tuple[str, ...] = ()

READ_ONLY_COMMANDS = {
    "types",
    "list-brands",
    "show-identity",
    "show-blackboard",
    "show-session-summary",
    "context-snapshot",
    "capabilities",
    "workspace-status",
    "improvement-questions",
    "show-workflow-lineage",
    "show-reference-analysis",
    "show-iteration-memory",
    "show",
    "compare",
    "diagnose",
    "review-brand",
    "review-prompt",
    "resolve-prompt",
    "validate-identity",
    "parse-design-memory",
    "extract-css-variables",
    "diff-design-memory",
    "export-design-tokens",
    "inspiration-status",
    "show-rubric",
    "example-sources",
    "social-specs",
    "critique-rubric",
    "reference-rubric",
    "prompts-list",
    "prompts-get",
}

CONVENIENCE_COMMANDS = {"pipeline", "generate", "inspire"}

FEATURE_TAGS_BY_COMMAND: dict[str, tuple[str, ...]] = {
    "pipeline": ("workflow", "generation"),
    "generate": ("workflow", "generation"),
    "generate-once": ("generation", "primitive"),
    "context-snapshot": ("context",),
    "workspace-status": ("context", "workspace"),
    "capabilities": ("context", "discovery"),
    "prompts-list": ("context", "prompts"),
    "prompts-get": ("context", "prompts"),
    "inspiration-capture": ("inspiration",),
    "inspiration-list": ("inspiration",),
    "inspiration-configure": ("inspiration",),
    "inspiration-clear": ("inspiration",),
}


def command_spec(
    name: str,
    handler: Callable,
    help: str = '',
    aliases: tuple[str, ...] = (),
    *,
    read_only: bool | None = None,
    primitive: bool | None = None,
    feature_tags: tuple[str, ...] | None = None,
) -> CommandSpec:
    resolved_read_only = name in READ_ONLY_COMMANDS if read_only is None else read_only
    resolved_primitive = name not in CONVENIENCE_COMMANDS if primitive is None else primitive
    resolved_convenience = not resolved_primitive
    return CommandSpec(
        name=name,
        handler=handler,
        help=help,
        aliases=aliases,
        cli_builder=get_cli_builder(name),
        read_only=resolved_read_only,
        mutates_state=not resolved_read_only,
        primitive=resolved_primitive,
        convenience=resolved_convenience,
        feature_tags=feature_tags or FEATURE_TAGS_BY_COMMAND.get(name, ()),
    )


COMMAND_SPECS = [
    command_spec('bootstrap', cmd_bootstrap, 'Scan existing brand files into manifest.'),
    command_spec('types', lambda args: list_material_types(), 'List supported material types.'),
    command_spec('init', cmd_init, 'Initialize .brand-gen structure and optionally migrate a legacy brand-materials workspace.'),
    command_spec('create-brand', cmd_create_brand, 'Create a saved brand from a conversational brief and scaffold profile + identity files.'),
    command_spec('start-testing', cmd_start_testing, 'Start an explicit brand testing session instead of defaulting to a saved brand.'),
    command_spec('use', cmd_use, 'Switch the active brand in .brand-gen/config.json.'),
    command_spec('list-brands', cmd_list_brands, 'List available brands under .brand-gen/brands.'),
    command_spec('extract-brand', cmd_extract_brand, 'Extract a structured brand profile from a local project.'),
    command_spec('build-identity', cmd_build_identity, 'Build brand identity memory files from a saved profile.'),
    command_spec('describe-brand', cmd_describe_brand, 'Generate brand description and prompt blocks from a saved profile.'),
    command_spec('show-identity', cmd_show_identity, 'Show a readable or JSON summary of stored brand identity.'),
    command_spec('show-blackboard', cmd_show_blackboard, 'Show the shared brand blackboard / specialist state.'),
    command_spec('show-session-summary', cmd_show_session_summary, 'Show one current-workspace summary.'),
    command_spec('context-snapshot', cmd_context_snapshot, 'Show the canonical machine-readable agent context snapshot for the current workspace.'),
    command_spec('capabilities', cmd_capabilities, 'List material/model/tool capabilities and feature flags.'),
    command_spec('workspace-status', cmd_workspace_status, 'Show canonical workspace root, plugin marker alignment, and divergence warnings.'),
    command_spec('improvement-questions', cmd_improvement_questions, 'Surface contextual questions the agent should ask to improve brand understanding over time.'),
    command_spec('show-workflow-lineage', cmd_show_workflow_lineage, 'Show blackboard lineage and saved artifact paths for a workflow_id.'),
    command_spec('show-reference-analysis', cmd_show_reference_analysis, 'Show cached reference-analysis results for the current workspace.'),
    command_spec('prompts-list', cmd_prompts_list, 'List prompt/skill resources under prompts/ using stable prompt-relative names.'),
    command_spec('prompts-get', cmd_prompts_get, 'Read one prompt/skill resource by prompt-relative name.'),
    command_spec('route-request', cmd_route_request, 'Route a request to the right specialist path before planning or generation.'),
    command_spec('resolve-prompt', cmd_resolve_prompt, 'Show the effective prompt after applying brand guardrails.'),
    command_spec('review-prompt', cmd_review_prompt, 'Review and refine a resolved prompt before generation.'),
    command_spec('validate-identity', cmd_validate_identity, 'Validate whether stored brand memory is complete enough for generation.'),
    command_spec('parse-design-memory', cmd_parse_design_memory, 'Parse an existing .design-memory folder into a compact structured summary.'),
    command_spec('extract-css-variables', cmd_extract_css_variables, 'Extract CSS custom properties from .design-memory, CSS, HTML, or markdown files.'),
    command_spec('diff-design-memory', cmd_diff_design_memory, 'Compare two .design-memory folders to inspect token and doctrine drift.'),
    command_spec('export-design-tokens', cmd_export_design_tokens, 'Export brand identity as production design tokens (css, tailwind, json, or w3c DTCG) with a WCAG audit.'),
    command_spec('inspiration-status', cmd_inspiration_status, 'Phase 1 preflight: report configured vs extracted inspiration sources and per-mode readiness before planning.'),
    command_spec('show-rubric', cmd_show_rubric, 'Dump the scoring rubric registry (universal axes + material overlays + disqualifiers). Used by the brand-critic agent and by scoring CLIs.'),
    command_spec('extract-inspiration', cmd_extract_inspiration, 'Run built-in semantic extraction for curated inspiration sources.'),
    command_spec('consolidate-inspiration', cmd_consolidate_inspiration, 'Standalone inspiration-memory consolidation: remote per-image VLM analysis followed by local aggregation into reusable inspiration-memory artifacts.'),
    command_spec('inspiration-mode', cmd_inspiration_mode, 'Toggle whether inspiration tokens are injected in addition to principles.'),
    command_spec('shotlist', cmd_shotlist, 'Create a product screenshot shotlist markdown file.'),
    command_spec('capture-product', cmd_capture_product, 'Capture product screenshots with agent-browser.'),
    command_spec('explore-brand', cmd_explore_brand, 'Suggest exploratory concept directions, source packs, and prompt seeds.'),
    command_spec('plan-set', cmd_plan_set, 'Establish a coherent material set from translated inspiration and brand truth.'),
    command_spec('validate-brand-fit', cmd_validate_brand_fit, 'Validate that a material plan or set stays clearly branded and product-fit.'),
    command_spec('validate-set', cmd_validate_set, 'Validate set-level coherence, product-fit, and brand-anchor coverage.'),
    command_spec('generate-set', cmd_generate_set, 'Generate the explicit generateable members of a saved set manifest.'),
    command_spec('ideate-copy', cmd_ideate_copy, 'Generate headline, slogan, and CTA candidates for branded materials.'),
    command_spec('ideate-messaging', cmd_ideate_messaging, 'Assemble brand context for messaging ideation.'),
    command_spec('promote-messaging', cmd_promote_messaging, 'Promote session messaging into the saved brand identity for cross-session persistence.'),
    command_spec('update-messaging', cmd_update_messaging, 'Update brand messaging in the brand identity.'),
    command_spec('show-iteration-memory', cmd_show_iteration_memory, 'Show the evolving scratchpad of negative examples, messaging/copy notes, and wins.'),
    command_spec('update-iteration-memory', cmd_update_iteration_memory, 'Record positive/negative examples or explicit brand/messaging/copy/material notes.'),
    command_spec('review-brand', cmd_review_brand, 'Build a structured critique/refine packet for a generated or composed artifact.'),
    command_spec('suggest-role-pack', cmd_suggest_role_pack, 'Inspect candidate reference-role selections before generation.'),
    command_spec('suggest-layout', cmd_suggest_layout, 'Suggest composition layouts from the vocabulary for a material type.', read_only=True),
    command_spec('plan-material', cmd_plan_material, 'Write an explicit material plan so the agent can reason before generating.'),
    command_spec('plan-draft', cmd_plan_draft, 'Write a plan draft scratchpad that the critic can inspect before generation.'),
    command_spec('critique-plan', cmd_critique_plan, 'Critique a plan or plan draft before building a generation scratchpad.'),
    command_spec('build-generation-scratchpad', cmd_build_generation_scratchpad, 'Build the execution scratchpad that generate now requires.'),
    command_spec('ideate-material', cmd_ideate_material, 'Generate idea tracks and alignment questions for an evolving brand material.'),
    command_spec('example-sources', cmd_example_sources, 'List or search curated brand example sources.'),
    command_spec('collect-examples', cmd_collect_examples, 'Capture curated brand example references into categorized folders.'),
    command_spec('social-specs', cmd_social_specs, 'Show recommended social and podcast dimensions.'),
    command_spec('critique-rubric', cmd_critique_rubric, 'Return the critique rubric + image path for the calling agent to evaluate.'),
    command_spec('submit-critique', cmd_submit_critique, 'Accept agent-provided critique JSON for a version.'),
    command_spec('reference-rubric', cmd_reference_rubric, 'Return reference image paths + analysis rubric for the calling agent to evaluate.'),
    command_spec('submit-reference-analysis', cmd_submit_reference_analysis, 'Accept agent-provided reference analysis JSON.'),
    command_spec('generate-once', cmd_generate_once, 'Generate exactly one output from a generation scratchpad with no internal critique loop.'),
    command_spec('generate', cmd_generate, 'Generate a new brand material version from a generation scratchpad.', aliases=('gen','g')),
    command_spec('derive-mockup', cmd_derive_mockup, 'Derive a generated contextual mockup scene from an approved still version (not pixel-precise compositing).'),
    command_spec('derive-video', cmd_derive_video, 'Derive a short branded video from an approved still version.'),
    command_spec('create-video', cmd_create_video, 'Create a long-form video end-to-end from a brief JSON: generates each shot via derive-video, stitches timeline segments into a single mp4, registers it in the manifest.'),
    command_spec('pipeline', cmd_pipeline, 'Run the generative pipeline in-process.', aliases=()),
    command_spec('feedback', cmd_feedback, 'Record feedback.', aliases=('fb','f')),
    command_spec('show', cmd_show, 'Show manifest.', aliases=('s',)),
    command_spec('compare', cmd_compare, 'HTML comparison board.', aliases=('cmp','c')),
    command_spec('diagnose', cmd_diagnose, 'Compare diagnostic metadata for versions side-by-side.', aliases=('diag',)),
    command_spec('evolve', cmd_evolve, 'Analyze prompt patterns.', aliases=('ev','e')),
    command_spec('inspire', cmd_inspire, 'Browse or list inspiration.', aliases=('insp','i')),
    command_spec('inspiration-list', cmd_inspiration_list, 'List configured or captured inspiration sources/assets.'),
    command_spec('inspiration-capture', cmd_inspiration_capture, 'Capture inspiration screenshots into the current workspace.'),
    command_spec('inspiration-configure', cmd_inspiration_configure, 'Configure which indexed inspiration sources a brand borrows from.'),
    command_spec('inspiration-clear', cmd_inspiration_clear, 'Clear configured inspiration sources for the active or specified brand.'),
    command_spec('composite-illustration', cmd_composite_illustration, 'Create a feature-highlight browser illustration by compositing screenshot, text, and brand layers.', aliases=('composite',)),
]

COMMAND_HANDLERS = {}
for spec in COMMAND_SPECS:
    COMMAND_HANDLERS[spec.name] = spec.handler
    for alias in spec.aliases:
        COMMAND_HANDLERS[alias] = spec.handler


def build_parser() -> argparse.ArgumentParser:
    return build_cli_parser(COMMAND_SPECS, inspire_urls=INSPIRE_URLS, epilog=__doc__)


def dispatch_command(args: argparse.Namespace, ctx: RuntimeContext | None = None):
    handler = COMMAND_HANDLERS[args.command]
    signature = inspect.signature(handler)
    if len(signature.parameters) >= 2:
        return handler(args, ctx)
    return handler(args)
