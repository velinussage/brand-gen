from __future__ import annotations

import argparse
from dataclasses import dataclass
import inspect
from typing import Callable

from .cli_builders import CliBuilder, build_cli_parser, get_cli_builder
from .runtime import INSPIRE_URLS, RuntimeContext, list_material_types
from .commands.generation import (
    cmd_create_video,
    cmd_derive_mockup,
    cmd_derive_video,
    cmd_evolve_run,
    cmd_execute_run,
    cmd_generate,
    cmd_generate_once,
    cmd_generate_set,
    cmd_orchestrate_material,
    cmd_pipeline,
    cmd_plan_run,
    cmd_prepare_run,
    cmd_review_run,
    cmd_validate_run,
)
from .commands.identity import (
    cmd_build_identity,
    cmd_describe_brand,
    cmd_export_design_tokens,
    cmd_extract_brand,
    cmd_extract_css_variables,
    cmd_diff_design_memory,
    cmd_parse_design_memory,
    cmd_show_identity,
    cmd_update_devices,
    cmd_update_palette,
    cmd_update_typography,
    cmd_validate_identity,
)
from .commands.inspection import (
    cmd_capabilities,
    cmd_context_snapshot,
    cmd_compare,
    cmd_compare_versions,
    cmd_diagnose,
    cmd_get_critique,
    cmd_get_plan,
    cmd_get_review_packet,
    cmd_get_run,
    cmd_get_scratchpad,
    cmd_get_version,
    cmd_inspiration_status,
    cmd_list_runs,
    cmd_prompts_get,
    cmd_prompts_list,
    cmd_show,
    cmd_show_blackboard,
    cmd_show_iteration_memory,
    cmd_show_reference_analysis,
    cmd_rebucket_inspiration,
    cmd_show_disagreements,
    cmd_show_rubric,
    cmd_show_session_summary,
    cmd_scoring_status,
    cmd_source_knowledge,
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
    cmd_submit_review,
    cmd_validate_set,
)
from .commands.state import (
    cmd_append_custom_scratchpad_note,
    cmd_append_forbidden_pattern,
    cmd_bootstrap,
    cmd_create_brand,
    cmd_get_pending_reviews,
    cmd_init,
    cmd_migrate_material_taxonomy,
    cmd_list_brands,
    cmd_report_material_taxonomy,
    cmd_promote_learning,
    cmd_promote_style_policy,
    cmd_set_motion_grammar,
    cmd_start_testing,
    cmd_switch_brand,
    cmd_use,
)
from .commands.composite import cmd_composite_illustration
from .commands.policy import (
    cmd_approve_action,
    cmd_get_policy,
    cmd_reject_action,
    cmd_set_policy,
)


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
    "list-runs",
    "get-run",
    "get-plan",
    "get-critique",
    "get-scratchpad",
    "get-review-packet",
    "get-version",
    "compare-versions",
    "get-pending-reviews",
    "get-policy",
    "show-identity",
    "show-blackboard",
    "show-session-summary",
    "context-snapshot",
    "source-knowledge",
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
    "show-disagreements",
    "scoring-status",
    "example-sources",
    "social-specs",
    "critique-rubric",
    "reference-rubric",
    "prompts-list",
    "prompts-get",
}

CONVENIENCE_COMMANDS = {"pipeline", "generate", "inspire", "orchestrate-material"}

FEATURE_TAGS_BY_COMMAND: dict[str, tuple[str, ...]] = {
    "pipeline": ("workflow", "generation"),
    "orchestrate-material": ("workflow", "orchestration"),
    "prepare-run": ("workflow", "orchestration"),
    "plan-run": ("workflow", "orchestration"),
    "validate-run": ("workflow", "orchestration"),
    "execute-run": ("workflow", "orchestration", "generation"),
    "review-run": ("workflow", "orchestration", "review"),
    "evolve-run": ("workflow", "orchestration", "learning"),
    "generate": ("workflow", "generation"),
    "generate-once": ("generation", "primitive"),
    "context-snapshot": ("context",),
    "source-knowledge": ("context", "source-knowledge"),
    "workspace-status": ("context", "workspace"),
    "capabilities": ("context", "discovery"),
    "prompts-list": ("context", "prompts"),
    "prompts-get": ("context", "prompts"),
    "inspiration-capture": ("inspiration",),
    "inspiration-list": ("inspiration",),
    "inspiration-configure": ("inspiration",),
    "inspiration-clear": ("inspiration",),
    "append-forbidden-pattern": ("mutation", "scratchpad"),
    "promote-learning": ("mutation", "learnings"),
    "append-custom-scratchpad-note": ("mutation", "scratchpad"),
    "set-motion-grammar": ("mutation", "scratchpad"),
    "promote-style-policy": ("mutation", "learnings"),
    "update-palette": ("mutation", "identity"),
    "update-typography": ("mutation", "identity"),
    "update-devices": ("mutation", "identity"),
    "submit-review": ("mutation", "review"),
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
    command_spec('source-knowledge', cmd_source_knowledge, 'Search configured brand-scoped Obsidian/docs markdown and return bounded source-truth excerpts.'),
    command_spec('capabilities', cmd_capabilities, 'List material/model/tool capabilities and feature flags.'),
    command_spec('workspace-status', cmd_workspace_status, 'Show canonical workspace root, plugin marker alignment, and divergence warnings.'),
    command_spec('improvement-questions', cmd_improvement_questions, 'Surface contextual questions the agent should ask to improve brand understanding over time.'),
    command_spec('show-workflow-lineage', cmd_show_workflow_lineage, 'Show blackboard lineage and saved artifact paths for a workflow_id.'),
    command_spec('list-runs', cmd_list_runs, 'List projected Run objects from the run ledger. Filter by status or material type.'),
    command_spec('get-run', cmd_get_run, 'Fetch a projected Run object by workflow id (aka run_id).'),
    command_spec('get-plan', cmd_get_plan, 'Fetch a plan-draft artifact by run-id (most recent) or by explicit path.'),
    command_spec('get-critique', cmd_get_critique, 'Fetch a plan-critique artifact by run-id (most recent) or by explicit path.'),
    command_spec('get-scratchpad', cmd_get_scratchpad, 'Fetch a generation-scratchpad artifact by run-id (most recent) or by explicit path.'),
    command_spec('get-review-packet', cmd_get_review_packet, 'Fetch the agent/auto review packet for a generated version.'),
    command_spec('get-version', cmd_get_version, 'Fetch manifest entry and file paths for one version.'),
    command_spec('compare-versions', cmd_compare_versions, 'Side-by-side diff of two version manifest entries.'),
    command_spec('switch-brand', cmd_switch_brand, 'Typed switch-active-brand verb (takes --brand-key).'),
    command_spec('migrate-material-taxonomy', cmd_migrate_material_taxonomy, 'Rewrite saved plans, scratchpads, sets, and manifest entries to the newer material taxonomy. Dry-run by default.'),
    command_spec('report-material-taxonomy', cmd_report_material_taxonomy, 'Report remaining deprecated material-type usage in one workspace or across all saved workspaces.'),
    command_spec('get-pending-reviews', cmd_get_pending_reviews, 'List runs whose derived status is awaiting_review.'),
    command_spec('get-policy', cmd_get_policy, 'Return the per-brand policy envelope (classes + pending_approvals + recent_decisions).'),
    command_spec('set-policy', cmd_set_policy, 'Update the mode for a policy class (allow|require_approval|deny).'),
    command_spec('approve-action', cmd_approve_action, 'Approve a pending action (by --pending-id) or pre-approve a tool call (--tool).'),
    command_spec('reject-action', cmd_reject_action, 'Reject a pending action by --pending-id.'),
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
    command_spec('show-disagreements', cmd_show_disagreements, 'List recent agent-vs-user disagreement records, filterable by material type / bucket / partition tag.'),
    command_spec('scoring-status', cmd_scoring_status, 'Report current scoring calibration: weighted Cohen kappa, raw agreement percent, per-material and per-bucket counts, and partition split.'),
    command_spec('rebucket-inspiration', cmd_rebucket_inspiration, 'Pin a PRIMARY bucket (composition / narrative_system / rendering_style) per inspiration source so the role-pack ranker stops defaulting to first-by-index when every source declares every bucket.'),
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
    command_spec('update-palette', cmd_update_palette, 'Update the brand identity palette and rerun a WCAG audit.'),
    command_spec('update-typography', cmd_update_typography, 'Update the brand identity typography roles and cues.'),
    command_spec('update-devices', cmd_update_devices, 'Add or remove approved graphic devices in the brand identity.'),
    command_spec('show-iteration-memory', cmd_show_iteration_memory, 'Show the evolving scratchpad of negative examples, messaging/copy notes, and wins.'),
    command_spec('update-iteration-memory', cmd_update_iteration_memory, 'Record positive/negative examples or explicit brand/messaging/copy/material notes.'),
    command_spec('append-forbidden-pattern', cmd_append_forbidden_pattern, 'Append a forbidden pattern to the custom scratchpad hard-ban list.'),
    command_spec('append-custom-scratchpad-note', cmd_append_custom_scratchpad_note, 'Append a bullet note under a custom scratchpad markdown section.'),
    command_spec('set-motion-grammar', cmd_set_motion_grammar, 'Set the structured motion grammar and sync it to the custom scratchpad.'),
    command_spec('promote-learning', cmd_promote_learning, 'Promote a typed learning entry into the active brand learnings memory.'),
    command_spec('promote-style-policy', cmd_promote_style_policy, 'Promote a structured style-reference policy into brand learnings.'),
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
    command_spec('submit-review', cmd_submit_review, 'Submit an agent review for a version (discoverability alias for submit-critique).'),
    command_spec('reference-rubric', cmd_reference_rubric, 'Return reference image paths + analysis rubric for the calling agent to evaluate.'),
    command_spec('submit-reference-analysis', cmd_submit_reference_analysis, 'Accept agent-provided reference analysis JSON.'),
    command_spec('prepare-run', cmd_prepare_run, 'Prepare one typed orchestration run: apply learnings, check inspiration readiness, and route the brief.'),
    command_spec('plan-run', cmd_plan_run, 'Create a typed plan draft artifact for an orchestration run.'),
    command_spec('validate-run', cmd_validate_run, 'Validate a typed plan draft and return blocking findings or next execution action.'),
    command_spec('execute-run', cmd_execute_run, 'Build the generation scratchpad and execute one typed orchestration run.'),
    command_spec('review-run', cmd_review_run, 'Return typed review packet status for a generated version.'),
    command_spec('evolve-run', cmd_evolve_run, 'Promote new learnings and surface the next recommended evolution action.'),
    command_spec('orchestrate-material', cmd_orchestrate_material, 'Run the typed orchestration API end-to-end and return stage completion + next action.'),
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
