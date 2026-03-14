#!/usr/bin/env python3
"""MCP server wrapper for brand_iterate.py."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
REPO_ROOT = SCRIPT_DIR.parent
BRAND_ITERATE = SCRIPT_DIR / "brand_iterate.py"
COLLECT_INSPIRATION = REPO_ROOT / "scripts" / "collect_inspiration.py"
ENV_CANDIDATES = [REPO_ROOT / ".env", Path.home() / ".claude" / ".env"]

SERVER_INFO = {"name": "brand-iterate", "version": "1.19.0"}
CAPABILITIES = {"tools": {"listChanged": False}}
TOOLS = [
    {
        "name": "brand_generate",
        "description": "Execute a prepared generation scratchpad with optional VLM critique loop. Build the scratchpad first with brand_build_generation_scratchpad after planning and critique. Supports iterative refinement: generate → VLM critique → refine prompt → re-generate up to max_iterations times.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "scratchpad": {"type": "string", "description": "Path to a generation scratchpad JSON created by brand_build_generation_scratchpad."},
                "max_iterations": {"type": "integer", "minimum": 1, "maximum": 3, "default": 1, "description": "Max generate→VLM-critique→refine loops (1=single-shot, 2-3=iterative). Requires ANTHROPIC_API_KEY or OPENAI_API_KEY."},
                "skip_vlm": {"type": "boolean", "default": False, "description": "Skip VLM image critique even when max_iterations > 1."}
            },
            "required": ["scratchpad"]
        }
    },
    {
        "name": "brand_feedback",
        "description": "Record feedback (score, notes, status) for a brand material version.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "version": {"type": "string"},
                "score": {"type": "integer", "minimum": 1, "maximum": 5},
                "notes": {"type": "string"},
                "status": {"type": "string", "enum": ["favorite", "rejected"]},
                "lock_fragments": {"type": "array", "items": {"type": "string"}},
                "prompt": {"type": "string"}
            },
            "required": ["version"]
        }
    },
    {
        "name": "brand_show",
        "description": "Show the brand manifest.",
        "inputSchema": {"type": "object", "properties": {"version": {"type": "string"}, "favorites": {"type": "boolean"}, "top": {"type": "integer"}, "latest": {"type": "integer"}, "format": {"type": "string", "enum": ["text", "json"], "default": "json"}}}
    },
    {
        "name": "brand_diagnose",
        "description": "Compare diagnostic metadata for one or more generated versions side-by-side, including prompt length, prelude length, refs, prompt review, critic issues, and workflow lineage.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "versions": {"type": "array", "items": {"type": "string"}},
                "format": {"type": "string", "enum": ["text", "json"], "default": "json"}
            },
            "required": ["versions"]
        }
    },
    {
        "name": "brand_compare",
        "description": "Generate an HTML comparison board for images, gifs, or short videos.",
        "inputSchema": {"type": "object", "properties": {"versions": {"type": "array", "items": {"type": "string"}}, "favorites": {"type": "boolean"}, "top": {"type": "integer"}}}
    },
    {
        "name": "brand_evolve",
        "description": "Analyze prompt patterns across scored brand materials.",
        "inputSchema": {"type": "object", "properties": {}}
    },
    {
        "name": "brand_bootstrap",
        "description": "Scan existing brand files into the manifest.",
        "inputSchema": {"type": "object", "properties": {}}
    },
    {
        "name": "brand_init",
        "description": "Initialize .brand-gen structure, copy the curated source registry, and optionally migrate an existing legacy brand-materials workspace.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "brand_name": {"type": "string", "description": "Brand key to initialize / activate."},
                "brand_gen_dir": {"type": "string", "description": "Optional override for .brand-gen location."},
                "legacy_brand_dir": {"type": "string", "description": "Optional legacy brand-materials directory to migrate."}
            }
        }
    },
    {
        "name": "brand_start_testing",
        "description": "Start an explicit testing session with a temporary working brand context instead of defaulting to a saved brand. Optionally seed the session from an existing saved brand.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "session_name": {"type": "string", "description": "Optional session key."},
                "working_name": {"type": "string", "description": "Temporary working brand name for this session."},
                "brand": {"type": "string", "description": "Optional saved brand key to seed the session from."},
                "goal": {"type": "string", "description": "What this testing session is trying to learn or generate."},
                "brand_gen_dir": {"type": "string", "description": "Optional override for .brand-gen location."}
            }
        }
    },
    {
        "name": "brand_use",
        "description": "Switch the active saved brand in .brand-gen/config.json and clear any active testing session.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "brand": {"type": "string", "description": "Brand key to activate."},
                "list_only": {"type": "boolean", "default": False}
            }
        }
    },
    {
        "name": "brand_list",
        "description": "List available brands under .brand-gen/brands with validation status and inspiration counts.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "format": {"type": "string", "enum": ["text", "json"], "default": "json"}
            }
        }
    },
    {
        "name": "brand_inspire",
        "description": "Collect or list inspiration screenshots from Logo System or any URL, or configure which extracted inspiration sources a brand should borrow doctrine from.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "category": {"type": "string", "default": "symbol", "enum": ["symbol", "wordmark", "symbol-text", "brown", "beige", "black", "all"]},
                "url": {"type": "string"},
                "label": {"type": "string"},
                "list_only": {"type": "boolean"},
                "capture": {"type": "boolean", "default": True},
                "count": {"type": "integer", "default": 3},
                "out_dir": {"type": "string"},
                "open_folder": {"type": "boolean", "default": True},
                "brand": {"type": "string", "description": "Brand key to configure inspiration sources for."},
                "sources": {"type": "array", "items": {"type": "string"}, "description": "Curated inspiration source keys to attach to the brand."},
                "show": {"type": "boolean", "default": False},
                "clear": {"type": "boolean", "default": False},
                "format": {"type": "string", "enum": ["text", "json"], "default": "json"}
            }
        }
    },
    {
        "name": "brand_extract_inspiration",
        "description": "Run batch design-memory extraction against the curated inspiration source registry.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "category": {"type": "string", "description": "Optional category filter."},
                "sources": {"type": "array", "items": {"type": "string"}, "description": "Specific inspiration source keys to extract."},
                "workers": {"type": "integer", "default": 4},
                "force": {"type": "boolean", "default": False},
                "limit": {"type": "integer"},
                "timeout": {"type": "integer", "default": 120}
            }
        }
    },
    {
        "name": "brand_inspiration_mode",
        "description": "Toggle whether inspiration design tokens are injected in addition to inspiration principles.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "state": {"type": "string", "enum": ["on", "off"]}
            }
        }
    },
    {
        "name": "brand_extract",
        "description": "Extract a structured brand profile from a local codebase, docs folder, or project root, automatically merge parsed .design-memory doctrine when present, then build brand-identity.json and brand-identity.md.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_root": {"type": "string", "description": "Codebase or docs root to inspect.", "default": "."},
                "brand_name": {"type": "string"},
                "homepage_url": {"type": "string"},
                "notes_file": {"type": "string"},
                "reference_dir": {"type": "string", "description": "Optional reference asset directory to include as brand anchors."},
                "design_tokens_json": {"type": "string", "description": "Optional dembrandt-style design tokens JSON to merge into the profile."},
                "design_memory_path": {"type": "string", "description": "Optional .design-memory folder or project root containing one; defaults to <project_root>/.design-memory when present."},
                "output_json": {"type": "string"},
                "output_markdown": {"type": "string"},
                "output_identity_json": {"type": "string"},
                "output_identity_markdown": {"type": "string"}
            }
        }
    },
    {
        "name": "brand_build_identity",
        "description": "Build brand-identity.json and brand-identity.md from an existing brand-profile.json so brand truth and design language can be reused across generations.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "profile": {"type": "string", "description": "Path to brand-profile.json."},
                "output_json": {"type": "string", "description": "Optional output path for brand-identity.json."},
                "output_markdown": {"type": "string", "description": "Optional output path for brand-identity.md."}
            }
        }
    },
    {
        "name": "brand_describe",
        "description": "Generate reusable brand description prompts from a saved brand profile.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "profile": {"type": "string"},
                "identity": {"type": "string"},
                "output": {"type": "string"}
            }
        }
    },
    {
        "name": "brand_show_identity",
        "description": "Show a structured summary of stored brand identity, including tone words, palette direction, typography cues, component cues, and the global guardrail prelude.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "profile": {"type": "string", "description": "Optional path to brand-profile.json."},
                "identity": {"type": "string", "description": "Optional path to brand-identity.json."},
                "format": {"type": "string", "enum": ["text", "json"], "default": "json"},
                "show_prelude": {"type": "boolean", "default": False}
            }
        }
    },
    {
        "name": "brand_show_blackboard",
        "description": "Show the shared brand blackboard used by the supervisor/specialist loop: active brief, recent decisions, reference assignments, and latest artifacts.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "profile": {"type": "string"},
                "identity": {"type": "string"},
                "format": {"type": "string", "enum": ["text", "json"], "default": "json"}
            }
        }
    },
    {
        "name": "brand_show_session_summary",
        "description": "Show one current-workspace summary: generated versions, feedback, iteration notes, messaging, and latest artifacts.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "profile": {"type": "string"},
                "identity": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "default": 5},
                "format": {"type": "string", "enum": ["text", "json"], "default": "json"}
            }
        }
    },
    {
        "name": "brand_show_reference_analysis",
        "description": "Show the cached reference-analysis summary for the current workspace, including observed product palette and inspiration mechanics.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "profile": {"type": "string"},
                "identity": {"type": "string"},
                "refresh_reference_analysis": {"type": "boolean"},
                "format": {"type": "string", "enum": ["text", "json"], "default": "json"}
            }
        }
    },
    {
        "name": "brand_show_workflow_lineage",
        "description": "Show blackboard decisions, generated assets, and saved artifact paths for a workflow_id.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "workflow_id": {"type": "string"},
                "format": {"type": "string", "enum": ["text", "json"], "default": "json"}
            },
            "required": ["workflow_id"]
        }
    },
    {
        "name": "brand_pipeline",
        "description": "Run the full generative pipeline in one call: route → plan-draft → critique → build-generation-scratchpad → generate. Stops at critique when blocking issues remain and returns every completed stage.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "material_type": {"type": "string"},
                "mode": {"type": "string", "enum": ["reference", "inspiration", "hybrid"], "default": "hybrid"},
                "prompt_seed": {"type": "string"},
                "mechanic": {"type": "string"},
                "purpose": {"type": "string"},
                "target_surface": {"type": "string"},
                "product_truth_expression": {"type": "string"},
                "abstraction_level": {"type": "string", "enum": ["low", "medium", "high"]},
                "goal": {"type": "string"},
                "request": {"type": "string"},
                "motion_reference": {"type": "string"},
                "base_image": {"type": "string", "description": "Path to an image to edit/overlay on. The model will use this as the base and apply brand overlays, text, icons per the prompt. Auto-selects flux-2-pro."},
                "set_scope": {"type": "boolean", "default": False},
                "preserve": {"type": "array", "items": {"type": "string"}},
                "push": {"type": "array", "items": {"type": "string"}},
                "ban": {"type": "array", "items": {"type": "string"}},
                "pick": {"type": "array", "items": {"type": "string"}},
                "max_iterations": {"type": "integer", "minimum": 1, "maximum": 3, "default": 1},
                "skip_vlm": {"type": "boolean", "default": False},
                "skip_route": {"type": "boolean", "default": False},
                "profile": {"type": "string"},
                "identity": {"type": "string"}
            },
            "required": ["material_type"]
        }
    },
    {
        "name": "brand_route_request",
        "description": "Classify a request into the right specialist path before planning or generation: deterministic compose, reference translate, generative explore, motion specialist, or set orchestrator.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "material_type": {"type": "string"},
                "goal": {"type": "string"},
                "request": {"type": "string"},
                "motion_reference": {"type": "string"},
                "set_scope": {"type": "boolean", "default": False},
                "profile": {"type": "string"},
                "identity": {"type": "string"},
                "format": {"type": "string", "enum": ["text", "json"], "default": "json"}
            }
        }
    },
    {
        "name": "brand_resolve_prompt",
        "description": "Resolve the final prompt after applying the stored brand guardrail prelude from brand identity or brand profile memory.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "Base prompt body."},
                "plan": {"type": "string", "description": "Optional material plan JSON generated by plan-material."},
                "profile": {"type": "string", "description": "Optional path to brand-profile.json."},
                "identity": {"type": "string", "description": "Optional path to brand-identity.json."},
                "material_type": {"type": "string", "description": "Optional material type used to tailor inspiration doctrine loading."},
                "mode": {"type": "string", "enum": ["auto", "reference", "inspiration", "hybrid"], "default": "auto", "description": "Optional workflow mode used to select a material-specific doctrine snippet variant."},
                "disable_brand_guardrails": {"type": "boolean", "default": False},
                "refresh_reference_analysis": {"type": "boolean"},
                "format": {"type": "string", "enum": ["text", "json"], "default": "json"}
            }
        }
    },
    {
        "name": "brand_review_prompt",
        "description": "Review and refine a material prompt before generation. Flags prompt-architecture problems and returns a shorter refined prompt.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "Base prompt body."},
                "plan": {"type": "string", "description": "Optional material plan JSON generated by plan-material."},
                "profile": {"type": "string", "description": "Optional path to brand-profile.json."},
                "identity": {"type": "string", "description": "Optional path to brand-identity.json."},
                "material_type": {"type": "string", "description": "Optional material type used to tailor prompt review."},
                "mode": {"type": "string", "enum": ["auto", "reference", "inspiration", "hybrid"], "default": "auto", "description": "Optional workflow mode used to select a material-specific doctrine snippet variant."},
                "disable_brand_guardrails": {"type": "boolean", "default": False},
                "refresh_reference_analysis": {"type": "boolean"},
                "format": {"type": "string", "enum": ["text", "json"], "default": "json"}
            }
        }
    },
    {
        "name": "brand_suggest_role_pack",
        "description": "Inspect candidate reference-role sources for a material before generating so the agent can reason about composition, motif, application, and motion explicitly.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "material_type": {"type": "string", "description": "Material type such as pattern-system, sticker-family, campaign-poster, merch-poster, or logo-animation."},
                "format": {"type": "string", "enum": ["text", "json"], "default": "json"},
                "top": {"type": "integer", "default": 3}
            },
            "required": ["material_type"]
        }
    },
    {
        "name": "brand_plan_material",
        "description": "Create an explicit material plan with purpose, surface, product-truth expression, brand-anchor policy, preserve/push/ban, one chosen system mechanic, and selected role refs so the agent can generate from a reasoned brief instead of hidden automation.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "material_type": {"type": "string"},
                "mode": {"type": "string", "enum": ["reference", "inspiration", "hybrid"], "default": "hybrid"},
                "mechanic": {"type": "string"},
                "purpose": {"type": "string"},
                "target_surface": {"type": "string"},
                "product_truth_expression": {"type": "string"},
                "abstraction_level": {"type": "string", "enum": ["low", "medium", "high"]},
                "preserve": {"type": "array", "items": {"type": "string"}},
                "push": {"type": "array", "items": {"type": "string"}},
                "ban": {"type": "array", "items": {"type": "string"}},
                "pick": {"type": "array", "items": {"type": "string"}, "description": "Repeatable role=source-key-or-path values."},
                "prompt_seed": {"type": "string"},
                "profile": {"type": "string"},
                "identity": {"type": "string"},
                "output": {"type": "string"},
                "format": {"type": "string", "enum": ["text", "json"], "default": "json"}
            },
            "required": ["material_type"]
        }
    },
    {
        "name": "brand_plan_draft",
        "description": "Create a plan-draft scratchpad that the agent can critique before building a generation scratchpad.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "material_type": {"type": "string"},
                "mode": {"type": "string", "enum": ["reference", "inspiration", "hybrid"], "default": "hybrid"},
                "mechanic": {"type": "string"},
                "purpose": {"type": "string"},
                "target_surface": {"type": "string"},
                "product_truth_expression": {"type": "string"},
                "abstraction_level": {"type": "string", "enum": ["low", "medium", "high"]},
                "preserve": {"type": "array", "items": {"type": "string"}},
                "push": {"type": "array", "items": {"type": "string"}},
                "ban": {"type": "array", "items": {"type": "string"}},
                "pick": {"type": "array", "items": {"type": "string"}},
                "prompt_seed": {"type": "string"},
                "profile": {"type": "string"},
                "identity": {"type": "string"},
                "output": {"type": "string"},
                "format": {"type": "string", "enum": ["text", "json"], "default": "json"}
            },
            "required": ["material_type"]
        }
    },
    {
        "name": "brand_critique_plan",
        "description": "Critique a material plan or plan draft before generation. Produces plan-validation and prompt-architecture feedback plus blocking issues.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "plan": {"type": "string"},
                "prompt": {"type": "string"},
                "material_type": {"type": "string"},
                "generation_mode": {"type": "string", "enum": ["auto", "image", "video"], "default": "auto"},
                "mode": {"type": "string", "enum": ["auto", "reference", "inspiration", "hybrid"], "default": "auto"},
                "model": {"type": "string"},
                "aspect_ratio": {"type": "string"},
                "resolution": {"type": "string"},
                "duration": {"type": "integer"},
                "tag": {"type": "string"},
                "reference_assets": {"type": "array", "items": {"type": "string"}},
                "reference_dir": {"type": "string"},
                "motion_reference": {"type": "string"},
                "motion_mode": {"type": "string", "enum": ["std", "pro"]},
                "character_orientation": {"type": "string", "enum": ["image", "video"]},
                "keep_original_sound": {"type": "boolean"},
                "preset": {"type": "string"},
                "negative_prompt": {"type": "string"},
                "style": {"type": "string"},
                "make_gif": {"type": "boolean"},
                "profile": {"type": "string"},
                "identity": {"type": "string"},
                "disable_brand_guardrails": {"type": "boolean"},
                "output": {"type": "string"},
                "format": {"type": "string", "enum": ["text", "json"], "default": "json"}
            },
            "required": ["plan"]
        }
    },
    {
        "name": "brand_build_generation_scratchpad",
        "description": "Build the generation scratchpad that brand_generate now requires. Resolves prompt blocks, refs, model choice, and blocking checks into one execution artifact.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "plan": {"type": "string"},
                "prompt": {"type": "string"},
                "material_type": {"type": "string"},
                "generation_mode": {"type": "string", "enum": ["auto", "image", "video"], "default": "auto"},
                "mode": {"type": "string", "enum": ["auto", "reference", "inspiration", "hybrid"], "default": "auto"},
                "model": {"type": "string"},
                "aspect_ratio": {"type": "string"},
                "resolution": {"type": "string"},
                "duration": {"type": "integer"},
                "tag": {"type": "string"},
                "reference_assets": {"type": "array", "items": {"type": "string"}},
                "reference_dir": {"type": "string"},
                "motion_reference": {"type": "string"},
                "motion_mode": {"type": "string", "enum": ["std", "pro"]},
                "character_orientation": {"type": "string", "enum": ["image", "video"]},
                "keep_original_sound": {"type": "boolean"},
                "preset": {"type": "string"},
                "negative_prompt": {"type": "string"},
                "style": {"type": "string"},
                "make_gif": {"type": "boolean"},
                "profile": {"type": "string"},
                "identity": {"type": "string"},
                "disable_brand_guardrails": {"type": "boolean"},
                "skip_extraction": {"type": "boolean"},
                "refresh_reference_analysis": {"type": "boolean"},
                "allow_blocking": {"type": "boolean"},
                "output": {"type": "string"},
                "format": {"type": "string", "enum": ["text", "json"], "default": "json"}
            },
            "required": ["plan"]
        }
    },
    {
        "name": "brand_plan_set",
        "description": "Establish a coherent branded material set from translated inspiration, product truth, and brand-anchor rules. Writes child material plans so the agent can refine or generate the set explicitly.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "template": {"type": "string", "description": "Set template key such as product-core, launch-core, brand-system-core, or social-launch."},
                "set_name": {"type": "string"},
                "goal": {"type": "string"},
                "surface": {"type": "string"},
                "mode": {"type": "string", "enum": ["reference", "inspiration", "hybrid"], "default": "hybrid"},
                "profile": {"type": "string"},
                "identity": {"type": "string"},
                "output": {"type": "string"},
                "format": {"type": "string", "enum": ["text", "json"], "default": "json"}
            }
        }
    },
    {
        "name": "brand_ideate_material",
        "description": "Generate a few concrete direction tracks plus targeted alignment questions so the agent and user can refine an evolving brand identity before planning or generating.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "material_type": {"type": "string"},
                "mode": {"type": "string", "enum": ["reference", "inspiration", "hybrid"], "default": "hybrid"},
                "goal": {"type": "string"},
                "use_surface": {"type": "string"},
                "concern": {"type": "string"},
                "profile": {"type": "string"},
                "identity": {"type": "string"},
                "format": {"type": "string", "enum": ["text", "json"], "default": "json"}
            },
            "required": ["material_type"]
        }
    },
    {
        "name": "brand_ideate_copy",
        "description": "Generate headline, slogan, subheadline, CTA, and visual-angle candidates so branded materials can include stronger message hooks instead of relying only on screenshots.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "material_type": {"type": "string"},
                "goal": {"type": "string"},
                "surface": {"type": "string"},
                "profile": {"type": "string"},
                "identity": {"type": "string"},
                "format": {"type": "string", "enum": ["text", "json"], "default": "json"}
            },
            "required": ["material_type"]
        }
    },
    {
        "name": "brand_ideate_messaging",
        "description": "Generate positioning angles, tagline candidates, elevator pitches, and voice directions from brand context plus accumulated iteration notes.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "profile": {"type": "string"},
                "identity": {"type": "string"},
                "format": {"type": "string", "enum": ["text", "json"], "default": "json"}
            }
        }
    },
    {
        "name": "brand_update_messaging",
        "description": "Persist brand messaging such as tagline, elevator pitch, voice description, value propositions, and approved copy-bank entries into the active brand identity.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "tagline": {"type": "string"},
                "elevator": {"type": "string"},
                "voice_description": {"type": "string"},
                "add_value_prop": {"type": "array", "items": {"type": "string"}},
                "add_headline": {"type": "array", "items": {"type": "string"}},
                "add_slogan": {"type": "array", "items": {"type": "string"}},
                "add_subheadline": {"type": "array", "items": {"type": "string"}},
                "profile": {"type": "string"},
                "identity": {"type": "string"},
                "format": {"type": "string", "enum": ["text", "json"], "default": "json"}
            }
        }
    },
    {
        "name": "brand_promote_messaging",
        "description": "Promote session messaging and messaging/copy iteration notes into the saved brand identity for future sessions.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "profile": {"type": "string"},
                "identity": {"type": "string"},
                "include_copy_notes": {"type": "boolean", "default": False}
            }
        }
    },
    {
        "name": "brand_validate_identity",
        "description": "Validate whether the stored brand profile and brand identity are complete enough for strong branded generation outputs.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "profile": {"type": "string", "description": "Optional path to brand-profile.json."},
                "identity": {"type": "string", "description": "Optional path to brand-identity.json."},
                "format": {"type": "string", "enum": ["text", "json"], "default": "json"},
                "strict": {"type": "boolean", "default": False}
            }
        }
    },
    {
        "name": "brand_show_iteration_memory",
        "description": "Show the evolving scratchpad of negative examples, positive examples, brand notes, and copy notes for consistent ideation.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "format": {"type": "string", "enum": ["text", "json"], "default": "json"}
            }
        }
    },
    {
        "name": "brand_update_iteration_memory",
        "description": "Record positive/negative examples or explicit brand/copy/material notes so future prompt resolution can learn from wins and misses.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "version": {"type": "string"},
                "material_type": {"type": "string"},
                "kind": {"type": "string", "enum": ["brand", "copy", "messaging", "material"], "default": "brand"},
                "note": {"type": "string"},
                "negative": {"type": "string"},
                "positive": {"type": "string"},
                "score": {"type": "integer"},
                "format": {"type": "string", "enum": ["text", "json"], "default": "json"}
            }
        }
    },
    {
        "name": "brand_validate_brand_fit",
        "description": "Validate whether a material plan or set stays clearly branded, product-fit, and explicit about how inspiration should be translated into mechanics.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "plan": {"type": "string"},
                "set": {"type": "string"},
                "format": {"type": "string", "enum": ["text", "json"], "default": "json"},
                "strict": {"type": "boolean", "default": False}
            }
        }
    },
    {
        "name": "brand_validate_set",
        "description": "Validate set-level coherence, product-fit coverage, and brand-anchor coverage for a saved material set manifest.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "set": {"type": "string"},
                "format": {"type": "string", "enum": ["text", "json"], "default": "json"},
                "strict": {"type": "boolean", "default": False}
            },
            "required": ["set"]
        }
    },
    {
        "name": "brand_generate_set",
        "description": "Generate only the explicit generateable members of a saved set manifest. Supports parallel generation for independent materials. Deterministic composer entries are left for separate explicit compose tools.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "set": {"type": "string"},
                "only": {"type": "array", "items": {"type": "string"}},
                "skip": {"type": "array", "items": {"type": "string"}},
                "model": {"type": "string"},
                "aspect_ratio": {"type": "string"},
                "parallel": {"type": "boolean", "default": False, "description": "Generate independent materials in parallel using a thread pool."},
                "workers": {"type": "integer", "minimum": 1, "maximum": 5, "default": 3, "description": "Max parallel workers when parallel is true."}
            },
            "required": ["set"]
        }
    },
    {
        "name": "brand_parse_design_memory",
        "description": "Parse an existing .design-memory folder into a compact structured summary with doctrine, components, layout, motion, palette, typography, breakpoints, and CSS variable blocks.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to a .design-memory folder, file inside it, or project root containing one."},
                "format": {"type": "string", "enum": ["text", "json"], "default": "json"},
                "output_json": {"type": "string", "description": "Optional output path for the parsed summary."}
            },
            "required": ["path"]
        }
    },
    {
        "name": "brand_extract_css_variables",
        "description": "Extract CSS custom properties from a .design-memory folder or local CSS, HTML, or Markdown files so brand-gen can preserve real token values.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to a .design-memory folder, local file, or project root."},
                "format": {"type": "string", "enum": ["text", "json"], "default": "json"},
                "output_json": {"type": "string", "description": "Optional output path for the extracted variables."},
                "max_files": {"type": "integer", "default": 250, "description": "Maximum number of files to scan when the input is a directory."}
            },
            "required": ["path"]
        }
    },
    {
        "name": "brand_diff_design_memory",
        "description": "Compare two .design-memory folders to inspect token, doctrine, and layout drift between references or brand snapshots.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "before": {"type": "string", "description": "Earlier .design-memory folder or project root containing one."},
                "after": {"type": "string", "description": "Later .design-memory folder or project root containing one."},
                "format": {"type": "string", "enum": ["text", "json"], "default": "json"},
                "output_json": {"type": "string", "description": "Optional output path for the diff report."}
            },
            "required": ["before", "after"]
        }
    },
    {
        "name": "brand_shotlist",
        "description": "Create a markdown shot list for product screenshots before capture.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "product_name": {"type": "string"},
                "goal": {"type": "string"},
                "output": {"type": "string"}
            }
        }
    },
    {
        "name": "brand_capture_product",
        "description": "Capture one or more product screenshots with agent-browser.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "label": {"type": "string"},
                "shots": {"type": "array", "items": {"type": "string"}, "description": "Repeatable label=url capture targets."},
                "out_dir": {"type": "string"},
                "count": {"type": "integer", "default": 1},
                "scroll_px": {"type": "integer", "default": 1400},
                "session": {"type": "string"},
                "open_folder": {"type": "boolean", "default": True}
            }
        }
    },
    {
        "name": "brand_review",
        "description": "Build a structured critique/refine packet for a generated or composed brand artifact so an agent can review copy, balance, fidelity, and next-step fixes.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "version": {"type": "string", "description": "Version id to review; defaults to latest."},
                "output": {"type": "string", "description": "Optional review markdown output path."},
                "open": {"type": "boolean", "default": True}
            }
        }
    },
    {
        "name": "brand_explore",
        "description": "Suggest exploratory brand concept directions, matching example sources, and prompt seeds based on a business brief or brand profile.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "profile": {"type": "string", "description": "Optional brand-profile.json path."},
                "brand_name": {"type": "string", "description": "Explicit brand name."},
                "business": {"type": "string", "description": "Business or product summary."},
                "audience": {"type": "string", "description": "Target audience summary."},
                "tone": {"type": "string", "description": "Comma-separated tone words."},
                "avoid": {"type": "string", "description": "Comma-separated anti-patterns or avoid words."},
                "product_context": {"type": "string", "description": "Which product surfaces matter and what product truth should anchor the work."},
                "materials": {"type": "array", "items": {"type": "string"}, "description": "Target material types such as browser-illustration, x-feed, or product-banner."},
                "sources": {"type": "array", "items": {"type": "string"}, "description": "Preferred curated source keys to constrain suggested example sources."},
                "top": {"type": "integer", "default": 4},
                "output": {"type": "string", "description": "Optional markdown output path."},
                "output_json": {"type": "string", "description": "Optional JSON output path."}
            }
        }
    },
    {
        "name": "brand_example_sources",
        "description": "List or search the curated brand-example source registry for SaaS, product, and premium branding references.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "category": {"type": "string", "description": "Optional category key such as saas-product-specialists or premium-branding."},
                "query": {"type": "string", "description": "Optional search query across source names, notes, and tags."},
                "format": {"type": "string", "enum": ["table", "json"], "default": "table"}
            }
        }
    },
    {
        "name": "brand_collect_examples",
        "description": "Capture curated brand-example references into categorized folders for prompt building and screenshot-derived generation.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "category": {"type": "string", "description": "Optional category key such as saas-product-specialists, premium-branding, or strong-studios."},
                "query": {"type": "string", "description": "Optional search query across source names, notes, and tags."},
                "sites": {"type": "array", "items": {"type": "string"}, "description": "Specific source keys to capture."},
                "limit": {"type": "integer", "description": "Limit number of captures after filtering."},
                "out_dir": {"type": "string", "description": "Output directory for categorized captures."},
                "open_folder": {"type": "boolean", "default": True}
            }
        }
    },
    {
        "name": "brand_social_specs",
        "description": "Show current X, LinkedIn, and Open Graph card/feed dimensions and working presets.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "format": {"type": "string", "description": "Optional single format filter (x-card, x-feed, x-feed-square, x-feed-portrait, linkedin-card, linkedin-feed, linkedin-feed-square, linkedin-feed-portrait, og-card, podcast-cover, podcast-banner)."},
                "verbose": {"type": "boolean", "default": False}
            }
        }
    }
]


def load_env_values() -> dict[str, str]:
    data: dict[str, str] = {}
    for path in reversed(ENV_CANDIDATES):
        if not path.exists():
            continue
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            data[key.strip()] = value.strip().strip('"').strip("'")
    return data


def build_env() -> dict[str, str]:
    env = dict(os.environ)
    env.update(load_env_values())
    return env


def default_inspiration_dir(env: dict[str, str]) -> Path:
    brand_gen_root = Path(env.get("BRAND_GEN_DIR")).expanduser() if env.get("BRAND_GEN_DIR") else (REPO_ROOT / ".brand-gen")
    if brand_gen_root.exists():
        config_path = brand_gen_root / "config.json"
        if config_path.exists():
            try:
                config = json.loads(config_path.read_text())
            except Exception:
                config = {}
            active_session = config.get("activeSession")
            if active_session:
                return brand_gen_root / "sessions" / str(active_session) / "brand-materials" / "inspiration"
            active = config.get("active")
            if active:
                return brand_gen_root / "brands" / str(active) / "inspiration"
    if env.get("BRAND_DIR"):
        return Path(env["BRAND_DIR"]).expanduser() / "inspiration"
    if env.get("LOGO_DIR"):
        return Path(env["LOGO_DIR"]).expanduser() / "inspiration"
    if env.get("SCREENSHOTS_DIR"):
        return Path(env["SCREENSHOTS_DIR"]).expanduser() / "brand-materials" / "inspiration"
    return REPO_ROOT / "examples" / "inspiration"


def run_python(script: Path, args: list[str]):
    env = build_env()
    result = subprocess.run([sys.executable, str(script)] + args, env=env, capture_output=True, text=True, cwd=str(REPO_ROOT))
    output = result.stdout
    if result.stderr:
        output += ("\n" if output else "") + result.stderr
    return output.strip(), result.returncode == 0


def run_brand_iterate(args: list[str]):
    return run_python(BRAND_ITERATE, args)


def run_collect_inspiration(args: dict):
    env = build_env()
    out_dir = Path(args["out_dir"]).expanduser() if args.get("out_dir") else default_inspiration_dir(env)
    cmd = ["--out-dir", str(out_dir), "--count", str(args.get("count") or 3)]
    if args.get("url"):
        cmd += ["--url", args["url"]]
        if args.get("label"):
            cmd += ["--label", args["label"]]
    else:
        cmd += ["--category", args.get("category", "symbol")]
    if args.get("open_folder", True):
        cmd.append("--open-folder")
    output, ok = run_python(COLLECT_INSPIRATION, cmd)
    if ok:
        output = (output + "\n" if output else "") + f"Inspiration folder: {out_dir}"
    return output, ok


def build_pipeline_args_from_mcp(args: dict) -> argparse.Namespace:
    return argparse.Namespace(
        material_type=args.get("material_type"),
        mode=args.get("mode") or "hybrid",
        prompt_seed=args.get("prompt_seed"),
        mechanic=args.get("mechanic"),
        purpose=args.get("purpose"),
        target_surface=args.get("target_surface"),
        product_truth_expression=args.get("product_truth_expression"),
        abstraction_level=args.get("abstraction_level"),
        goal=args.get("goal"),
        request=args.get("request"),
        motion_reference=args.get("motion_reference"),
        base_image=args.get("base_image"),
        set_scope=bool(args.get("set_scope", False)),
        preserve=list(args.get("preserve") or []),
        push=list(args.get("push") or []),
        ban=list(args.get("ban") or []),
        pick=list(args.get("pick") or []),
        max_iterations=int(args.get("max_iterations") or 1),
        skip_vlm=bool(args.get("skip_vlm", False)),
        skip_route=bool(args.get("skip_route", False)),
        profile=args.get("profile"),
        identity=args.get("identity"),
    )


def handle_tool_call(name, arguments):
    args = arguments or {}
    if name == "brand_generate":
        cmd = ["generate"]
        cmd += ["--scratchpad", args["scratchpad"]]
        if args.get("max_iterations") and args["max_iterations"] > 1:
            cmd += ["--max-iterations", str(args["max_iterations"])]
        if args.get("skip_vlm"):
            cmd.append("--skip-vlm")
        output, ok = run_brand_iterate(cmd)
        return output, not ok
    if name == "brand_feedback":
        cmd = ["feedback", args["version"]]
        if args.get("score"):
            cmd += ["--score", str(args["score"])]
        if args.get("notes"):
            cmd += ["--notes", args["notes"]]
        if args.get("status"):
            cmd += ["--status", args["status"]]
        if args.get("prompt"):
            cmd += ["--prompt", args["prompt"]]
        if args.get("lock_fragments"):
            cmd += ["--lock"] + args["lock_fragments"]
        output, ok = run_brand_iterate(cmd)
        return output, not ok
    if name == "brand_show":
        cmd = ["show"]
        if args.get("version"):
            cmd.append(args["version"])
        if args.get("favorites"):
            cmd.append("--favorites")
        if args.get("top"):
            cmd += ["--top", str(args["top"])]
        if args.get("latest"):
            cmd += ["--latest", str(args["latest"])]
        if args.get("format"):
            cmd += ["--format", args["format"]]
        output, ok = run_brand_iterate(cmd)
        return output, not ok
    if name == "brand_diagnose":
        cmd = ["diagnose"]
        for version in args.get("versions") or []:
            cmd.append(version)
        if args.get("format"):
            cmd += ["--format", args["format"]]
        output, ok = run_brand_iterate(cmd)
        return output, not ok
    if name == "brand_compare":
        cmd = ["compare"]
        if args.get("versions"):
            cmd += args["versions"]
        if args.get("favorites"):
            cmd.append("--favorites")
        if args.get("top"):
            cmd += ["--top", str(args["top"])]
        output, ok = run_brand_iterate(cmd)
        return output, not ok
    if name == "brand_evolve":
        output, ok = run_brand_iterate(["evolve"])
        return output, not ok
    if name == "brand_bootstrap":
        output, ok = run_brand_iterate(["bootstrap"])
        return output, not ok
    if name == "brand_init":
        cmd = ["init"]
        if args.get("brand_name"):
            cmd += ["--brand-name", args["brand_name"]]
        if args.get("brand_gen_dir"):
            cmd += ["--brand-gen-dir", args["brand_gen_dir"]]
        if args.get("legacy_brand_dir"):
            cmd += ["--legacy-brand-dir", args["legacy_brand_dir"]]
        output, ok = run_brand_iterate(cmd)
        return output, not ok
    if name == "brand_start_testing":
        cmd = ["start-testing"]
        if args.get("session_name"):
            cmd += ["--session-name", args["session_name"]]
        if args.get("working_name"):
            cmd += ["--working-name", args["working_name"]]
        if args.get("brand"):
            cmd += ["--brand", args["brand"]]
        if args.get("goal"):
            cmd += ["--goal", args["goal"]]
        if args.get("brand_gen_dir"):
            cmd += ["--brand-gen-dir", args["brand_gen_dir"]]
        output, ok = run_brand_iterate(cmd)
        return output, not ok
    if name == "brand_use":
        cmd = ["use"]
        if args.get("brand"):
            cmd.append(args["brand"])
        if args.get("list_only"):
            cmd.append("--list")
        output, ok = run_brand_iterate(cmd)
        return output, not ok
    if name == "brand_list":
        cmd = ["list-brands"]
        if args.get("format"):
            cmd += ["--format", args["format"]]
        output, ok = run_brand_iterate(cmd)
        return output, not ok
    if name == "brand_inspire":
        if args.get("brand") or args.get("sources") or args.get("show") or args.get("clear"):
            cmd = ["inspire"]
            if args.get("brand"):
                cmd += ["--brand", args["brand"]]
            if args.get("category") and not args.get("brand"):
                cmd.append(args["category"])
            for source in args.get("sources", []) or []:
                cmd += ["--sources", source]
            if args.get("show"):
                cmd += ["--show"]
            if args.get("clear"):
                cmd += ["--clear"]
            if args.get("format"):
                cmd += ["--format", args["format"]]
            output, ok = run_brand_iterate(cmd)
            return output, not ok
        if args.get("list_only"):
            cmd = ["inspire", args.get("category", "symbol"), "--list"]
            if args.get("url"):
                cmd += ["--url", args["url"]]
            output, ok = run_brand_iterate(cmd)
            return output, not ok
        if args.get("capture", True):
            output, ok = run_collect_inspiration(args)
            return output, not ok
        cmd = ["inspire"]
        if args.get("category"):
            cmd.append(args["category"])
        if args.get("url"):
            cmd += ["--url", args["url"]]
        if args.get("label"):
            cmd += ["--label", args["label"]]
        output, ok = run_brand_iterate(cmd)
        return output, not ok
    if name == "brand_extract_inspiration":
        cmd = ["extract-inspiration"]
        if args.get("category"):
            cmd += ["--category", args["category"]]
        for source in args.get("sources", []) or []:
            cmd += ["--source", source]
        if args.get("workers"):
            cmd += ["--workers", str(args["workers"])]
        if args.get("force"):
            cmd += ["--force"]
        if args.get("limit"):
            cmd += ["--limit", str(args["limit"])]
        if args.get("timeout"):
            cmd += ["--timeout", str(args["timeout"])]
        output, ok = run_brand_iterate(cmd)
        return output, not ok
    if name == "brand_inspiration_mode":
        cmd = ["inspiration-mode"]
        if args.get("state"):
            cmd.append(args["state"])
        output, ok = run_brand_iterate(cmd)
        return output, not ok
    if name == "brand_extract":
        cmd = ["extract-brand"]
        if args.get("project_root"):
            cmd += ["--project-root", args["project_root"]]
        if args.get("brand_name"):
            cmd += ["--brand-name", args["brand_name"]]
        if args.get("homepage_url"):
            cmd += ["--homepage-url", args["homepage_url"]]
        if args.get("notes_file"):
            cmd += ["--notes-file", args["notes_file"]]
        if args.get("reference_dir"):
            cmd += ["--reference-dir", args["reference_dir"]]
        if args.get("design_tokens_json"):
            cmd += ["--design-tokens-json", args["design_tokens_json"]]
        if args.get("design_memory_path"):
            cmd += ["--design-memory-path", args["design_memory_path"]]
        if args.get("output_json"):
            cmd += ["--output-json", args["output_json"]]
        if args.get("output_markdown"):
            cmd += ["--output-markdown", args["output_markdown"]]
        if args.get("output_identity_json"):
            cmd += ["--output-identity-json", args["output_identity_json"]]
        if args.get("output_identity_markdown"):
            cmd += ["--output-identity-markdown", args["output_identity_markdown"]]
        output, ok = run_brand_iterate(cmd)
        return output, not ok
    if name == "brand_build_identity":
        cmd = ["build-identity"]
        if args.get("profile"):
            cmd += ["--profile", args["profile"]]
        if args.get("output_json"):
            cmd += ["--output-json", args["output_json"]]
        if args.get("output_markdown"):
            cmd += ["--output-markdown", args["output_markdown"]]
        output, ok = run_brand_iterate(cmd)
        return output, not ok
    if name == "brand_describe":
        cmd = ["describe-brand"]
        if args.get("profile"):
            cmd += ["--profile", args["profile"]]
        if args.get("identity"):
            cmd += ["--identity", args["identity"]]
        if args.get("output"):
            cmd += ["--output", args["output"]]
        output, ok = run_brand_iterate(cmd)
        return output, not ok
    if name == "brand_show_identity":
        cmd = ["show-identity"]
        if args.get("profile"):
            cmd += ["--profile", args["profile"]]
        if args.get("identity"):
            cmd += ["--identity", args["identity"]]
        if args.get("format"):
            cmd += ["--format", args["format"]]
        if args.get("show_prelude"):
            cmd += ["--show-prelude"]
        output, ok = run_brand_iterate(cmd)
        return output, not ok
    if name == "brand_show_blackboard":
        cmd = ["show-blackboard"]
        if args.get("profile"):
            cmd += ["--profile", args["profile"]]
        if args.get("identity"):
            cmd += ["--identity", args["identity"]]
        if args.get("format"):
            cmd += ["--format", args["format"]]
        output, ok = run_brand_iterate(cmd)
        return output, not ok
    if name == "brand_show_session_summary":
        cmd = ["show-session-summary"]
        if args.get("profile"):
            cmd += ["--profile", args["profile"]]
        if args.get("identity"):
            cmd += ["--identity", args["identity"]]
        if args.get("limit"):
            cmd += ["--limit", str(args["limit"])]
        if args.get("format"):
            cmd += ["--format", args["format"]]
        output, ok = run_brand_iterate(cmd)
        return output, not ok
    if name == "brand_show_reference_analysis":
        cmd = ["show-reference-analysis"]
        if args.get("profile"):
            cmd += ["--profile", args["profile"]]
        if args.get("identity"):
            cmd += ["--identity", args["identity"]]
        if args.get("refresh_reference_analysis"):
            cmd += ["--refresh-reference-analysis"]
        if args.get("format"):
            cmd += ["--format", args["format"]]
        output, ok = run_brand_iterate(cmd)
        return output, not ok
    if name == "brand_show_workflow_lineage":
        cmd = ["show-workflow-lineage", "--workflow-id", args["workflow_id"]]
        if args.get("format"):
            cmd += ["--format", args["format"]]
        output, ok = run_brand_iterate(cmd)
        return output, not ok
    if name == "brand_pipeline":
        from pipeline_runner import PipelineRunner  # type: ignore
        from brand_iterate import get_brand_dir, load_brand_memory  # type: ignore

        brand_dir = get_brand_dir()
        _, _, profile, identity = load_brand_memory(brand_dir, args.get("profile"), args.get("identity"))
        runner = PipelineRunner(
            brand_dir=brand_dir,
            profile=profile,
            identity=identity,
            max_iterations=int(args.get("max_iterations") or 1),
            skip_vlm=bool(args.get("skip_vlm", False)),
            skip_route=bool(args.get("skip_route", False)),
        )
        result = runner.run(build_pipeline_args_from_mcp(args))
        is_error = result.stopped_at not in {"complete", "critique"}
        return json.dumps(result.to_dict(), indent=2), is_error
    if name == "brand_route_request":
        cmd = ["route-request"]
        if args.get("material_type"):
            cmd += ["--material-type", args["material_type"]]
        if args.get("goal"):
            cmd += ["--goal", args["goal"]]
        if args.get("request"):
            cmd += ["--request", args["request"]]
        if args.get("motion_reference"):
            cmd += ["--motion-reference", args["motion_reference"]]
        if args.get("set_scope"):
            cmd += ["--set-scope"]
        if args.get("profile"):
            cmd += ["--profile", args["profile"]]
        if args.get("identity"):
            cmd += ["--identity", args["identity"]]
        if args.get("format"):
            cmd += ["--format", args["format"]]
        output, ok = run_brand_iterate(cmd)
        return output, not ok
    if name == "brand_resolve_prompt":
        cmd = ["resolve-prompt"]
        if args.get("prompt"):
            cmd += ["--prompt", args["prompt"]]
        if args.get("plan"):
            cmd += ["--plan", args["plan"]]
        if args.get("profile"):
            cmd += ["--profile", args["profile"]]
        if args.get("identity"):
            cmd += ["--identity", args["identity"]]
        if args.get("material_type"):
            cmd += ["--material-type", args["material_type"]]
        if args.get("mode"):
            cmd += ["--mode", args["mode"]]
        if args.get("format"):
            cmd += ["--format", args["format"]]
        if args.get("disable_brand_guardrails"):
            cmd += ["--disable-brand-guardrails"]
        if args.get("refresh_reference_analysis"):
            cmd += ["--refresh-reference-analysis"]
        output, ok = run_brand_iterate(cmd)
        return output, not ok
    if name == "brand_review_prompt":
        cmd = ["review-prompt"]
        if args.get("prompt"):
            cmd += ["--prompt", args["prompt"]]
        if args.get("plan"):
            cmd += ["--plan", args["plan"]]
        if args.get("profile"):
            cmd += ["--profile", args["profile"]]
        if args.get("identity"):
            cmd += ["--identity", args["identity"]]
        if args.get("material_type"):
            cmd += ["--material-type", args["material_type"]]
        if args.get("mode"):
            cmd += ["--mode", args["mode"]]
        if args.get("format"):
            cmd += ["--format", args["format"]]
        if args.get("disable_brand_guardrails"):
            cmd += ["--disable-brand-guardrails"]
        if args.get("refresh_reference_analysis"):
            cmd += ["--refresh-reference-analysis"]
        output, ok = run_brand_iterate(cmd)
        return output, not ok
    if name == "brand_suggest_role_pack":
        cmd = ["suggest-role-pack", "--material-type", args["material_type"]]
        if args.get("format"):
            cmd += ["--format", args["format"]]
        if args.get("top"):
            cmd += ["--top", str(args["top"])]
        output, ok = run_brand_iterate(cmd)
        return output, not ok
    if name == "brand_plan_material":
        cmd = ["plan-material", "--material-type", args["material_type"]]
        if args.get("mode"):
            cmd += ["--mode", args["mode"]]
        if args.get("mechanic"):
            cmd += ["--mechanic", args["mechanic"]]
        if args.get("purpose"):
            cmd += ["--purpose", args["purpose"]]
        if args.get("target_surface"):
            cmd += ["--target-surface", args["target_surface"]]
        if args.get("product_truth_expression"):
            cmd += ["--product-truth-expression", args["product_truth_expression"]]
        if args.get("abstraction_level"):
            cmd += ["--abstraction-level", args["abstraction_level"]]
        for item in args.get("preserve", []) or []:
            cmd += ["--preserve", item]
        for item in args.get("push", []) or []:
            cmd += ["--push", item]
        for item in args.get("ban", []) or []:
            cmd += ["--ban", item]
        for item in args.get("pick", []) or []:
            cmd += ["--pick", item]
        if args.get("prompt_seed"):
            cmd += ["--prompt-seed", args["prompt_seed"]]
        if args.get("profile"):
            cmd += ["--profile", args["profile"]]
        if args.get("identity"):
            cmd += ["--identity", args["identity"]]
        if args.get("output"):
            cmd += ["--output", args["output"]]
        if args.get("format"):
            cmd += ["--format", args["format"]]
        output, ok = run_brand_iterate(cmd)
        return output, not ok
    if name == "brand_plan_draft":
        cmd = ["plan-draft", "--material-type", args["material_type"]]
        if args.get("mode"):
            cmd += ["--mode", args["mode"]]
        if args.get("mechanic"):
            cmd += ["--mechanic", args["mechanic"]]
        if args.get("purpose"):
            cmd += ["--purpose", args["purpose"]]
        if args.get("target_surface"):
            cmd += ["--target-surface", args["target_surface"]]
        if args.get("product_truth_expression"):
            cmd += ["--product-truth-expression", args["product_truth_expression"]]
        if args.get("abstraction_level"):
            cmd += ["--abstraction-level", args["abstraction_level"]]
        for item in args.get("preserve", []) or []:
            cmd += ["--preserve", item]
        for item in args.get("push", []) or []:
            cmd += ["--push", item]
        for item in args.get("ban", []) or []:
            cmd += ["--ban", item]
        for item in args.get("pick", []) or []:
            cmd += ["--pick", item]
        if args.get("prompt_seed"):
            cmd += ["--prompt-seed", args["prompt_seed"]]
        if args.get("profile"):
            cmd += ["--profile", args["profile"]]
        if args.get("identity"):
            cmd += ["--identity", args["identity"]]
        if args.get("output"):
            cmd += ["--output", args["output"]]
        if args.get("format"):
            cmd += ["--format", args["format"]]
        output, ok = run_brand_iterate(cmd)
        return output, not ok
    if name == "brand_critique_plan":
        cmd = ["critique-plan", "--plan", args["plan"]]
        if args.get("prompt"):
            cmd += ["--prompt", args["prompt"]]
        if args.get("material_type"):
            cmd += ["--material-type", args["material_type"]]
        if args.get("generation_mode"):
            cmd += ["--generation-mode", args["generation_mode"]]
        if args.get("mode"):
            cmd += ["--mode", args["mode"]]
        if args.get("model"):
            cmd += ["--model", args["model"]]
        if args.get("aspect_ratio"):
            cmd += ["--aspect-ratio", args["aspect_ratio"]]
        if args.get("resolution"):
            cmd += ["--resolution", args["resolution"]]
        if args.get("duration"):
            cmd += ["--duration", str(args["duration"])]
        if args.get("tag"):
            cmd += ["--tag", args["tag"]]
        for ref in args.get("reference_assets", []) or []:
            cmd += ["--image", ref]
        if args.get("reference_dir"):
            cmd += ["--reference-dir", args["reference_dir"]]
        if args.get("motion_reference"):
            cmd += ["--motion-reference", args["motion_reference"]]
        if args.get("motion_mode"):
            cmd += ["--motion-mode", args["motion_mode"]]
        if args.get("character_orientation"):
            cmd += ["--character-orientation", args["character_orientation"]]
        if args.get("keep_original_sound"):
            cmd += ["--keep-original-sound"]
        if args.get("preset"):
            cmd += ["--preset", args["preset"]]
        if args.get("negative_prompt"):
            cmd += ["--negative-prompt", args["negative_prompt"]]
        if args.get("style"):
            cmd += ["--style", args["style"]]
        if args.get("make_gif"):
            cmd += ["--make-gif"]
        if args.get("profile"):
            cmd += ["--profile", args["profile"]]
        if args.get("identity"):
            cmd += ["--identity", args["identity"]]
        if args.get("disable_brand_guardrails"):
            cmd += ["--disable-brand-guardrails"]
        if args.get("output"):
            cmd += ["--output", args["output"]]
        if args.get("format"):
            cmd += ["--format", args["format"]]
        output, ok = run_brand_iterate(cmd)
        return output, not ok
    if name == "brand_build_generation_scratchpad":
        cmd = ["build-generation-scratchpad", "--plan", args["plan"]]
        if args.get("prompt"):
            cmd += ["--prompt", args["prompt"]]
        if args.get("material_type"):
            cmd += ["--material-type", args["material_type"]]
        if args.get("generation_mode"):
            cmd += ["--generation-mode", args["generation_mode"]]
        if args.get("mode"):
            cmd += ["--mode", args["mode"]]
        if args.get("model"):
            cmd += ["--model", args["model"]]
        if args.get("aspect_ratio"):
            cmd += ["--aspect-ratio", args["aspect_ratio"]]
        if args.get("resolution"):
            cmd += ["--resolution", args["resolution"]]
        if args.get("duration"):
            cmd += ["--duration", str(args["duration"])]
        if args.get("tag"):
            cmd += ["--tag", args["tag"]]
        for ref in args.get("reference_assets", []) or []:
            cmd += ["--image", ref]
        if args.get("reference_dir"):
            cmd += ["--reference-dir", args["reference_dir"]]
        if args.get("motion_reference"):
            cmd += ["--motion-reference", args["motion_reference"]]
        if args.get("motion_mode"):
            cmd += ["--motion-mode", args["motion_mode"]]
        if args.get("character_orientation"):
            cmd += ["--character-orientation", args["character_orientation"]]
        if args.get("keep_original_sound"):
            cmd += ["--keep-original-sound"]
        if args.get("preset"):
            cmd += ["--preset", args["preset"]]
        if args.get("negative_prompt"):
            cmd += ["--negative-prompt", args["negative_prompt"]]
        if args.get("style"):
            cmd += ["--style", args["style"]]
        if args.get("make_gif"):
            cmd += ["--make-gif"]
        if args.get("profile"):
            cmd += ["--profile", args["profile"]]
        if args.get("identity"):
            cmd += ["--identity", args["identity"]]
        if args.get("disable_brand_guardrails"):
            cmd += ["--disable-brand-guardrails"]
        if args.get("skip_extraction"):
            cmd += ["--skip-extraction"]
        if args.get("refresh_reference_analysis"):
            cmd += ["--refresh-reference-analysis"]
        if args.get("allow_blocking"):
            cmd += ["--allow-blocking"]
        if args.get("output"):
            cmd += ["--output", args["output"]]
        if args.get("format"):
            cmd += ["--format", args["format"]]
        output, ok = run_brand_iterate(cmd)
        return output, not ok
    if name == "brand_plan_set":
        cmd = ["plan-set"]
        if args.get("template"):
            cmd += ["--template", args["template"]]
        if args.get("set_name"):
            cmd += ["--set-name", args["set_name"]]
        if args.get("goal"):
            cmd += ["--goal", args["goal"]]
        if args.get("surface"):
            cmd += ["--surface", args["surface"]]
        if args.get("mode"):
            cmd += ["--mode", args["mode"]]
        if args.get("profile"):
            cmd += ["--profile", args["profile"]]
        if args.get("identity"):
            cmd += ["--identity", args["identity"]]
        if args.get("output"):
            cmd += ["--output", args["output"]]
        if args.get("format"):
            cmd += ["--format", args["format"]]
        output, ok = run_brand_iterate(cmd)
        return output, not ok
    if name == "brand_ideate_material":
        cmd = ["ideate-material", "--material-type", args["material_type"]]
        if args.get("mode"):
            cmd += ["--mode", args["mode"]]
        if args.get("goal"):
            cmd += ["--goal", args["goal"]]
        if args.get("use_surface"):
            cmd += ["--use-surface", args["use_surface"]]
        if args.get("concern"):
            cmd += ["--concern", args["concern"]]
        if args.get("profile"):
            cmd += ["--profile", args["profile"]]
        if args.get("identity"):
            cmd += ["--identity", args["identity"]]
        if args.get("format"):
            cmd += ["--format", args["format"]]
        output, ok = run_brand_iterate(cmd)
        return output, not ok
    if name == "brand_ideate_copy":
        cmd = ["ideate-copy", "--material-type", args["material_type"]]
        if args.get("goal"):
            cmd += ["--goal", args["goal"]]
        if args.get("surface"):
            cmd += ["--surface", args["surface"]]
        if args.get("profile"):
            cmd += ["--profile", args["profile"]]
        if args.get("identity"):
            cmd += ["--identity", args["identity"]]
        if args.get("format"):
            cmd += ["--format", args["format"]]
        output, ok = run_brand_iterate(cmd)
        return output, not ok
    if name == "brand_ideate_messaging":
        cmd = ["ideate-messaging"]
        if args.get("profile"):
            cmd += ["--profile", args["profile"]]
        if args.get("identity"):
            cmd += ["--identity", args["identity"]]
        if args.get("format"):
            cmd += ["--format", args["format"]]
        output, ok = run_brand_iterate(cmd)
        return output, not ok
    if name == "brand_update_messaging":
        cmd = ["update-messaging"]
        if args.get("tagline"):
            cmd += ["--tagline", args["tagline"]]
        if args.get("elevator"):
            cmd += ["--elevator", args["elevator"]]
        if args.get("voice_description"):
            cmd += ["--voice-description", args["voice_description"]]
        for item in args.get("add_value_prop", []) or []:
            cmd += ["--add-value-prop", item]
        for item in args.get("add_headline", []) or []:
            cmd += ["--add-headline", item]
        for item in args.get("add_slogan", []) or []:
            cmd += ["--add-slogan", item]
        for item in args.get("add_subheadline", []) or []:
            cmd += ["--add-subheadline", item]
        if args.get("profile"):
            cmd += ["--profile", args["profile"]]
        if args.get("identity"):
            cmd += ["--identity", args["identity"]]
        if args.get("format"):
            cmd += ["--format", args["format"]]
        output, ok = run_brand_iterate(cmd)
        return output, not ok
    if name == "brand_promote_messaging":
        cmd = ["promote-messaging"]
        if args.get("profile"):
            cmd += ["--profile", args["profile"]]
        if args.get("identity"):
            cmd += ["--identity", args["identity"]]
        if args.get("include_copy_notes"):
            cmd += ["--include-copy-notes"]
        output, ok = run_brand_iterate(cmd)
        return output, not ok
    if name == "brand_validate_identity":
        cmd = ["validate-identity"]
        if args.get("profile"):
            cmd += ["--profile", args["profile"]]
        if args.get("identity"):
            cmd += ["--identity", args["identity"]]
        if args.get("format"):
            cmd += ["--format", args["format"]]
        if args.get("strict"):
            cmd += ["--strict"]
        output, ok = run_brand_iterate(cmd)
        return output, not ok
    if name == "brand_show_iteration_memory":
        cmd = ["show-iteration-memory"]
        if args.get("format"):
            cmd += ["--format", args["format"]]
        output, ok = run_brand_iterate(cmd)
        return output, not ok
    if name == "brand_update_iteration_memory":
        cmd = ["update-iteration-memory"]
        if args.get("version"):
            cmd += ["--version", args["version"]]
        if args.get("material_type"):
            cmd += ["--material-type", args["material_type"]]
        if args.get("kind"):
            cmd += ["--kind", args["kind"]]
        if args.get("note"):
            cmd += ["--note", args["note"]]
        if args.get("negative"):
            cmd += ["--negative", args["negative"]]
        if args.get("positive"):
            cmd += ["--positive", args["positive"]]
        if args.get("score") is not None:
            cmd += ["--score", str(args["score"])]
        if args.get("format"):
            cmd += ["--format", args["format"]]
        output, ok = run_brand_iterate(cmd)
        return output, not ok
    if name == "brand_validate_brand_fit":
        cmd = ["validate-brand-fit"]
        if args.get("plan"):
            cmd += ["--plan", args["plan"]]
        if args.get("set"):
            cmd += ["--set", args["set"]]
        if args.get("format"):
            cmd += ["--format", args["format"]]
        if args.get("strict"):
            cmd += ["--strict"]
        output, ok = run_brand_iterate(cmd)
        return output, not ok
    if name == "brand_validate_set":
        cmd = ["validate-set", "--set", args["set"]]
        if args.get("format"):
            cmd += ["--format", args["format"]]
        if args.get("strict"):
            cmd += ["--strict"]
        output, ok = run_brand_iterate(cmd)
        return output, not ok
    if name == "brand_generate_set":
        cmd = ["generate-set", "--set", args["set"]]
        for item in args.get("only", []) or []:
            cmd += ["--only", item]
        for item in args.get("skip", []) or []:
            cmd += ["--skip", item]
        if args.get("model"):
            cmd += ["--model", args["model"]]
        if args.get("aspect_ratio"):
            cmd += ["--aspect-ratio", args["aspect_ratio"]]
        if args.get("parallel"):
            cmd.append("--parallel")
        if args.get("workers"):
            cmd += ["--workers", str(args["workers"])]
        output, ok = run_brand_iterate(cmd)
        return output, not ok
    if name == "brand_parse_design_memory":
        cmd = ["parse-design-memory", "--path", args["path"]]
        if args.get("format"):
            cmd += ["--format", args["format"]]
        if args.get("output_json"):
            cmd += ["--output-json", args["output_json"]]
        output, ok = run_brand_iterate(cmd)
        return output, not ok
    if name == "brand_extract_css_variables":
        cmd = ["extract-css-variables", "--path", args["path"]]
        if args.get("format"):
            cmd += ["--format", args["format"]]
        if args.get("output_json"):
            cmd += ["--output-json", args["output_json"]]
        if args.get("max_files"):
            cmd += ["--max-files", str(args["max_files"])]
        output, ok = run_brand_iterate(cmd)
        return output, not ok
    if name == "brand_diff_design_memory":
        cmd = ["diff-design-memory", "--before", args["before"], "--after", args["after"]]
        if args.get("format"):
            cmd += ["--format", args["format"]]
        if args.get("output_json"):
            cmd += ["--output-json", args["output_json"]]
        output, ok = run_brand_iterate(cmd)
        return output, not ok
    if name == "brand_shotlist":
        cmd = ["shotlist"]
        if args.get("product_name"):
            cmd += ["--product-name", args["product_name"]]
        if args.get("goal"):
            cmd += ["--goal", args["goal"]]
        if args.get("output"):
            cmd += ["--output", args["output"]]
        output, ok = run_brand_iterate(cmd)
        return output, not ok
    if name == "brand_capture_product":
        cmd = ["capture-product"]
        if args.get("url"):
            cmd += ["--url", args["url"]]
        if args.get("label"):
            cmd += ["--label", args["label"]]
        for shot in args.get("shots", []) or []:
            cmd += ["--shot", shot]
        if args.get("out_dir"):
            cmd += ["--out-dir", args["out_dir"]]
        if args.get("count"):
            cmd += ["--count", str(args["count"])]
        if args.get("scroll_px"):
            cmd += ["--scroll-px", str(args["scroll_px"])]
        if args.get("session"):
            cmd += ["--session", args["session"]]
        if args.get("open_folder", True):
            cmd.append("--open-folder")
        output, ok = run_brand_iterate(cmd)
        return output, not ok
    if name == "brand_review":
        cmd = ["review-brand"]
        if args.get("version"):
            cmd.append(args["version"])
        if args.get("output"):
            cmd += ["--output", args["output"]]
        if args.get("open", True):
            cmd.append("--open")
        output, ok = run_brand_iterate(cmd)
        return output, not ok
    if name == "brand_explore":
        cmd = ["explore-brand"]
        if args.get("profile"):
            cmd += ["--profile", args["profile"]]
        if args.get("brand_name"):
            cmd += ["--brand-name", args["brand_name"]]
        if args.get("business"):
            cmd += ["--business", args["business"]]
        if args.get("audience"):
            cmd += ["--audience", args["audience"]]
        if args.get("tone"):
            cmd += ["--tone", args["tone"]]
        if args.get("avoid"):
            cmd += ["--avoid", args["avoid"]]
        if args.get("product_context"):
            cmd += ["--product-context", args["product_context"]]
        for material in args.get("materials", []) or []:
            cmd += ["--material", material]
        for source in args.get("sources", []) or []:
            cmd += ["--source", source]
        if args.get("top"):
            cmd += ["--top", str(args["top"])]
        if args.get("output"):
            cmd += ["--output", args["output"]]
        if args.get("output_json"):
            cmd += ["--output-json", args["output_json"]]
        output, ok = run_brand_iterate(cmd)
        return output, not ok
    if name == "brand_example_sources":
        cmd = ["example-sources"]
        if args.get("category"):
            cmd += ["--category", args["category"]]
        if args.get("query"):
            cmd += ["--query", args["query"]]
        if args.get("format"):
            cmd += ["--format", args["format"]]
        output, ok = run_brand_iterate(cmd)
        return output, not ok
    if name == "brand_collect_examples":
        cmd = ["collect-examples"]
        if args.get("category"):
            cmd += ["--category", args["category"]]
        if args.get("query"):
            cmd += ["--query", args["query"]]
        for site in args.get("sites", []) or []:
            cmd += ["--site", site]
        if args.get("limit"):
            cmd += ["--limit", str(args["limit"])]
        if args.get("out_dir"):
            cmd += ["--out-dir", args["out_dir"]]
        if args.get("open_folder", True):
            cmd.append("--open-folder")
        output, ok = run_brand_iterate(cmd)
        return output, not ok
    if name == "brand_social_specs":
        cmd = ["social-specs"]
        if args.get("format"):
            cmd.append(args["format"])
        if args.get("verbose"):
            cmd.append("--verbose")
        output, ok = run_brand_iterate(cmd)
        return output, not ok
    return f"Unknown tool: {name}", True


def send_response(id, result):
    msg = {"jsonrpc": "2.0", "id": id, "result": result}
    data = json.dumps(msg)
    sys.stdout.write(f"Content-Length: {len(data)}\r\n\r\n{data}")
    sys.stdout.flush()


def send_error(id, code, message):
    msg = {"jsonrpc": "2.0", "id": id, "error": {"code": code, "message": message}}
    data = json.dumps(msg)
    sys.stdout.write(f"Content-Length: {len(data)}\r\n\r\n{data}")
    sys.stdout.flush()


def read_message():
    headers = {}
    while True:
        line = sys.stdin.readline()
        if not line:
            return None
        line = line.strip()
        if not line:
            break
        if ":" in line:
            key, val = line.split(":", 1)
            headers[key.strip()] = val.strip()
    content_length = int(headers.get("Content-Length", 0))
    if content_length == 0:
        return None
    body = sys.stdin.read(content_length)
    return json.loads(body)


def handle_message(msg):
    method = msg.get("method", "")
    id = msg.get("id")
    params = msg.get("params", {})
    if method == "initialize":
        send_response(id, {"protocolVersion": "2024-11-05", "serverInfo": SERVER_INFO, "capabilities": CAPABILITIES})
    elif method == "notifications/initialized":
        pass
    elif method == "tools/list":
        send_response(id, {"tools": TOOLS})
    elif method == "tools/call":
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})
        try:
            output, is_error = handle_tool_call(tool_name, arguments)
            send_response(id, {"content": [{"type": "text", "text": output}], "isError": is_error})
        except Exception as exc:
            send_response(id, {"content": [{"type": "text", "text": f"Error: {exc}"}], "isError": True})
    elif id is not None:
        send_error(id, -32601, f"Method not found: {method}")


def main():
    while True:
        msg = read_message()
        if msg is None:
            break
        handle_message(msg)


if __name__ == "__main__":
    main()
