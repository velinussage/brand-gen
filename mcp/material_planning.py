"""Material planning — re-export facade.

All functions have moved to focused modules.  This file re-exports every
public name so that existing ``from .material_planning import *`` and
explicit ``from .material_planning import foo`` statements keep working.

Module map:
    brand_policy          — brand policies, identity summary, copy candidates
    reference_role_packs  — reference quality, role packs, inspiration selection
    plan_validation       — plan / manifest / identity validation
    prompt_assembly       — prompt building, review, execution prompt, text utils
    plan_builder          — plan creation, route classification, plan critique
"""
from __future__ import annotations

# Keep runtime symbols accessible — the old module had ``from .runtime import *``
# and consumers (including test patches) rely on these names being reachable
# through ``mcp.material_planning``.
from .runtime import *

# Re-export all names from the five focused modules.  Because these wildcard
# imports run *after* the runtime import, any name that a focused module also
# defines will shadow the runtime version (which is the correct behavior).
from .brand_policy import *
from .plan_builder import *
from .plan_validation import *
from .prompt_assembly import *
from .reference_role_packs import *
