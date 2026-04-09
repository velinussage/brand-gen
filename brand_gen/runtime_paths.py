from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
REPO_ROOT = SCRIPT_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"

ENV_CANDIDATES = [REPO_ROOT / ".env", Path.home() / ".claude" / ".env"]

GENERATE_PY = SCRIPT_DIR / "generate.py"
EXTRACT_BRAND_PY = REPO_ROOT / "scripts" / "extract_brand_profile.py"
DESCRIBE_BRAND_PY = REPO_ROOT / "scripts" / "describe_brand_profile.py"
BUILD_IDENTITY_PY = REPO_ROOT / "scripts" / "build_brand_identity.py"
DESIGN_MEMORY_LITE_PY = REPO_ROOT / "scripts" / "design_memory_lite.py"
PRODUCT_SCREENS_PY = REPO_ROOT / "scripts" / "product_screens.py"
EXPLORE_BRAND_PY = REPO_ROOT / "scripts" / "explore_brand_concepts.py"
BUILD_REVIEW_PACKET_PY = REPO_ROOT / "scripts" / "build_brand_review_packet.py"
BRAND_EXAMPLES_PY = REPO_ROOT / "scripts" / "collect_brand_examples.py"

REFERENCE_ROLE_PACKS_PATH = REPO_ROOT / "data" / "reference_role_packs.json"
PROMPT_REVIEW_RULES_PATH = REPO_ROOT / "data" / "prompt_review_rules.json"
WORKFLOW_ROUTER_RULES_PATH = REPO_ROOT / "data" / "workflow_router_rules.json"
SYSTEM_PROMPTS_DIR = REPO_ROOT / "prompts" / "system"
PROMPT_BUDGET_PATH = REPO_ROOT / "data" / "prompt_budget.json"
MATERIAL_SNIPPETS_PATH = REPO_ROOT / "data" / "material_snippets.json"
MATERIAL_POLICY_PATH = REPO_ROOT / "data" / "material_policy.json"
PROMPT_FRAGMENTS_PATH = REPO_ROOT / "data" / "prompt_fragments.json"
IDEA_TRACKS_PATH = REPO_ROOT / "data" / "idea_tracks.json"
ALIGNMENT_QUESTIONS_PATH = REPO_ROOT / "data" / "alignment_questions.json"
PIPELINE_CONFIG_PATH = REPO_ROOT / "data" / "pipeline_config.json"


@dataclass(frozen=True)
class RuntimeContext:
    repo_root: Path = REPO_ROOT
    script_dir: Path = SCRIPT_DIR
    scripts_dir: Path = SCRIPTS_DIR

    def build_env(self) -> dict[str, str]:
        from .runtime_io import build_env

        return build_env()
