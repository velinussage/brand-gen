---
name: sage-brand-gen
description: >
  Context provisioning for brand-gen sessions. Use when the user is generating,
  iterating, scoring, or animating brand materials via bgen, brand-* subagents,
  or the concept-illustration / feature-animation / campaign-poster / brand-scene
  material types. Provisions the active brand's design philosophy, style carriers,
  iteration memory, v7 narrative rules, and reviewer calibration so Sage suggest
  hooks land useful context instead of generic test prompts.
tags:
  - brand-gen
  - bgen
  - concept-illustration
  - design
  - brand
  - illustration
  - launch-video
  - seedance
match:
  - bgen
  - brand-gen
  - concept-illustration
  - feature-animation
  - brand-scene
  - campaign-poster
  - launch video
  - seedance
  - first frame
  - style anchor
---

# Sage brand-gen context provisioning

## When to use this skill

When the user is working inside a brand-gen repo, generating or reviewing brand
materials, or discussing launch videos, style anchors, or design philosophy
alongside Sage tooling. This skill is a context provisioner — it does not
replace the brand-gen skill at `skills/brand-gen/SKILL.md`; it complements it
by surfacing the right operating parameters per session.

## What this skill provisions

### Active-brand orientation
Check the active brand:

```bash
source .venv/bin/activate && bgen context-snapshot --format json | jq '.active_brand // .brand'
```

### Style carriers (keeper anchors)
Rank-scored keepers from `manifest.json`; pass the top 2-3 as `--pick composition=<path>`
or `--pick application=<path>` on any new pipeline run:

```bash
python3 - <<'EOF'
import json
m = json.load(open('brands/<ACTIVE_BRAND>/manifest.json'))
vs = [(int(v.get('score') or 0), k, v.get('material_type',''), (v.get('files') or [''])[0]) for k, v in m['versions'].items() if v.get('score')]
vs.sort(reverse=True)
for s, k, mt, f in vs[:5]:
    print(f"{s}/5  {k}  {mt}  {f}")
EOF
```

### Design philosophy
Pull the brand's `design-philosophy.md` material metaphors, composition rules,
and quality boosters into the prompt seed. Never paste verbatim.

```bash
test -f brands/<ACTIVE_BRAND>/design-philosophy.md && cat brands/<ACTIVE_BRAND>/design-philosophy.md
```

### Iteration memory
Recent rejections and approvals; the user's scoring is usually stricter than the
agent-side critic by approximately 2 points. Trust iteration memory over
agent-generated scores:

```bash
test -f brands/<ACTIVE_BRAND>/iteration-memory.md && head -60 brands/<ACTIVE_BRAND>/iteration-memory.md
```

### v7 narrative rules (when sage is the active brand)
If the active brand is `sage`, absorb:

- `/Users/twells/Downloads/sagedesign/v7/02-v7-narrative-brief.md` — approved
  lines, message hierarchy, anti-patterns.
- `/Users/twells/Downloads/sagedesign/v7/03-video-feedback-and-plan.md` — scene
  structure, motion-language guidance, caption rule.
- `/Users/twells/Downloads/sagedesign/v7/04-visual-system-feedback.md` — logo
  fidelity rule, typography, composition guidance, retired-hero-motif list.

Hard rules from v7:
- Every caption matches the exact footage. No exception.
- Use canonical `sage-mark-1024.png` directly; never regenerate the Doric column.
- Five fluted shafts, narrow base, broad capital. Not four, not Ionic.
- Retire temple/cathedral/foundry-worldbuilding AS HERO. Use v012/v021 dense
  isometric vocabulary only when it genuinely serves evidence-led gravitas.

## What to provision INSTEAD of generic suggestions

When `sage suggest hook skill --limit 3 --provision` runs on a brand-gen prompt,
match this skill first if any of these are true:

- Working directory under a brand-gen repo (`.brand-gen/` or `skills/brand-gen/`
  visible)
- Prompt mentions `bgen`, `brand-gen`, `concept-illustration`, `feature-animation`,
  `seedance`, `launch video`, `first frame`, `style anchor`, or `iteration memory`
- An active conversation references a brand version ID (e.g. `v012`, `v066`)

Provision the sections above AS-NEEDED rather than dumping all of them. Prefer:
1. Active brand + style carriers (always)
2. Design philosophy (when generating or critiquing)
3. Iteration memory (when iterating from a prior version or scoring)
4. v7 narrative rules (only when `sage` is the active brand and the work is
   launch-video or narrative-facing)

## What this skill deliberately does NOT do

- It does not run `bgen pipeline` or any generation command itself. The user
  drives those.
- It does not invent brand claims. `messaging.forbidden_claims` in the active
  brand's `brand-identity.json` is authoritative.
- It does not override the user's scoring. Agent-side scores calibrate high by
  approximately 2 points; defer to the user's explicit feedback in every loop.

## Installation

```bash
sage library skill add /Users/twells/Documents/brand-gen/skills/brand-gen/sage-brand-gen-skill.md -l <your-library>
sage library push <your-library>
```

Or promote to a DAO-governed library:

```bash
sage library promote <your-library> --dao 0x... --collection default
```

## Evidence anchors

- brand-gen skill: `skills/brand-gen/SKILL.md`
- Claude Code agents (if used): `skills/brand-gen/claude-agents/`
- pi agents (if used): `.pi/agents/brand-*.md`
- per-brand fat skill (for Sage specifically): `brands/sage/SKILL.local.md`
