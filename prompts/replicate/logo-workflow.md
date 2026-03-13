# Logo Generation Workflow

<required_reading>
Before starting: verify setup with `workflows/setup.md` if first run.
Model details: `references/models.md` (recraft section)
</required_reading>

<process>

## 1. Iteration Wrapper

All logo work flows through `logo_iterate.py` — it wraps generate.py with version tracking, feedback scoring, and prompt evolution.

```bash
source ~/.claude/.env
SCRIPT=".claude/skills/imagevideogen/scripts/logo_iterate.py"
export SCREENSHOTS_DIR="${SCREENSHOTS_DIR:-docs/sage_webapp_screens}"
```

### Quick Reference

```bash
# Bootstrap manifest from existing files (first time only)
python3 $SCRIPT bootstrap

# Generate a new version (auto-increments, auto-converts webp→png)
python3 $SCRIPT generate -p "your prompt" -m recraft-v4 --tag "icon"

# Record feedback after reviewing
python3 $SCRIPT feedback v108 --score 4 --notes "Good mark, shelf too narrow"
python3 $SCRIPT feedback v108 --status favorite --lock "5 flat vertical rectangles"

# View manifest
python3 $SCRIPT show              # all versions
python3 $SCRIPT show --top 5      # best scored
python3 $SCRIPT show --favorites  # favorites only

# Compare versions side-by-side (opens HTML in browser)
python3 $SCRIPT compare v90 v103 v104
python3 $SCRIPT compare --favorites

# Analyze prompt patterns (what works vs what fails)
python3 $SCRIPT evolve
```

## 2. Gather Inspiration (Optional)

If the user wants design references, use Chrome DevTools MCP to browse logosystem.co:

```bash
# Start Chrome DevTools MCP if not running
<your-mcp-host> start chrome-devtools
```

Navigate to: `https://logosystem.co/`
Categories: **Symbol** (icons/marks), **Wordmark** (text-only), **Symbol & Text**

Capture screenshots to `docs/sage_webapp_screens/logo-redesigns/inspiration/` for reference.
Scroll the page first (content is lazy-loaded), then screenshot.

Existing reference screenshots may already be at:
`docs/sage_webapp_screens/logo-redesigns/inspiration/logosystem-*.png`

## 3. Model Selection

**Always use recraft-v4** for logo work. Use recraft-v4-svg for editable vector output.

Do NOT use flux-pro or flux-schnell for logos — wrong model for clean marks.

| Model | Cost | Output | Best For |
|-------|------|--------|----------|
| recraft-v4 | $0.04 | webp (auto→png) | Design-aware logos, composition |
| recraft-v4-svg | $0.08 | svg | Editable vector output |
| recraft-v3 | $0.04 | png | Vector art, icons |
| ideogram | $0.04 | png | Logos with text/typography |

## 4. Prompt Engineering

### What Works (from 100+ iterations)

Use **geometric description language** — flat shapes, not architectural terms:
- "flat vertical rectangles" not "columns" or "pillars"
- "horizontal bar" or "horizontal shelf" not "entablature"
- "wider bar extending past" not "flared capital"

### Prompt Template

```
[Framing type]: [composition description],
[mark description using geometric language],
warm muted brown terracotta background not orange not red,
cream colored, clean minimalist flat vector, no gradients no shadows
```

### Aspect Ratios by Framing

| Framing | Aspect Ratio | Tag |
|---------|-------------|-----|
| Icon/mark only | 1:1 | icon |
| Horizontal lockup (mark + text) | 2:1 | horizontal-lockup |
| Stacked lockup (text over mark) | 4:5 | stacked-lockup |
| Social banner | 16:9 | banner |

### Anti-Patterns

- "column capital" → triggers ornamental arches, fluting, grooves
- "entablature" → too architectural, over-detailed
- "classical" → pulls in unwanted historical detail
- Long prompts (80+ words) → worse results than short (40 words)
- Hex codes → use color names instead

## 5. Iteration Loop

**ONE at a time. Generate → Review → Score → Iterate.**

```
1. python3 $SCRIPT evolve                    # check what works
2. python3 $SCRIPT generate -p "..." --tag X # generate one
3. Read the output file to review
4. python3 $SCRIPT feedback vN --score S --notes "..." # score it
5. Repeat from 1, refining prompt based on feedback
```

After 3+ iterations, use compare to see progress:
```
python3 $SCRIPT compare --top 5
```

## 6. Locking Good Fragments

When a prompt fragment consistently works across high-scoring versions, lock it:
```bash
python3 $SCRIPT feedback v108 --lock "5 flat vertical rectangles" "cream colored"
```

Locked fragments show in `evolve` output and should be preserved in all future prompts.

## 7. Output

Save to: `docs/sage_webapp_screens/logo-redesigns/`
Manifest: `docs/sage_webapp_screens/logo-redesigns/manifest.json`

</process>

<success_criteria>
- Used logo_iterate.py for all generations (not raw generate.py)
- Every version scored with feedback before generating next
- Locked fragments preserved across iterations
- compare board used every 3-5 iterations to review progress
- Final versions marked as favorites
</success_criteria>
