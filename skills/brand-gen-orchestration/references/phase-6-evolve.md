# Phase 6: Evolve

## Table of Contents

1. [When to Run Evolve](#when-to-run-evolve)
2. [Running Evolve](#running-evolve)
3. [Pattern Extraction](#pattern-extraction)
4. [Learnings Format](#learnings-format)
5. [Updating Iteration Memory](#updating-iteration-memory)
6. [Feeding Back into Phase 1](#feeding-back-into-phase-1)

---

## When to Run Evolve

**Why:** Evolution is the compound interest of the pipeline. Each evolve run extracts
patterns from scored outputs and writes them to `learnings.json`, which Phase 1 reads
on the next generation. Without evolve, each generation starts from scratch.

### After Each Generation Cycle

Run evolve after final acceptance or after max retries are exhausted:

```bash
source .venv/bin/activate && bgen evolve --format json
```

### Auto-Evolve Trigger

Check how many versions have been scored since the last evolve run. Track the last
evolve timestamp in iteration memory (look for notes starting with `EVOLVE_RUN:`).

If 5 or more versions have been scored since the last evolve, run evolve automatically
even if this specific generation did not trigger it.

```bash
# Check iteration memory for last evolve
source .venv/bin/activate && bgen show-iteration-memory --format json
```

Look for brand_notes containing `EVOLVE_RUN:` and compare the timestamp against the
manifest to count scored versions since then.

---

## Running Evolve

```bash
source .venv/bin/activate && bgen evolve --format json
```

The evolve command analyzes scored versions and extracts patterns across multiple
dimensions:

1. **Model preferences** — Which model + mode combinations score highest for each
   material type
2. **Color insights** — Which palette applications work best
3. **Composition patterns** — Which layout structures score well
4. **Failure patterns** — Which setups reliably fail
5. **Messaging insights** — Which copy approaches resonate
6. **Style reference policies** — Which prior versions must remain present as style anchors to prevent drift

The output includes:
- New patterns discovered
- Updated learnings
- Promotion decisions (patterns seen 2+ times get promoted to learnings)

---

## Pattern Extraction

**Why:** Raw generation results contain noise. Pattern extraction separates signal
(reproducible insights) from noise (one-off flukes).

### Promotion Thresholds

Patterns are promoted to `learnings.json` only after appearing in 2+ scored versions:

| Learning type | Promotion threshold | Example |
|--------------|--------------------:|---------|
| `modelPreferences` | 2 consistent wins | "social + hybrid + nano-banana-2 scores 4+" |
| `compositionPatterns` | 2 consistent wins | "vertical stacking + single focal works for social" |
| `failurePatterns` | 2 consistent failures | "ideogram + concept-illustration always muddy" |
| `colorInsights` | 2 consistent observations | "warm undertones score higher than cool" |
| `messagingInsights` | 2 consistent observations | "short imperatives outperform questions" |
| `styleReferencePolicies` | 2+ high scores with same style anchor, or 1 strong cluster + repeated drift when absent | "`v014` must remain the style carrier for campaign posters" |

### What Gets Extracted

From high-scoring versions (4-5):
- Model and mode used
- Composition approach (symmetric, asymmetric, stacked, editorial)
- Color treatment (warm/cool, contrast level, palette usage)
- Texture and material treatment
- Prompt strategies that worked
- Style-anchor references that stayed constant across the best results

From low-scoring versions (1-2):
- Failure conditions to avoid
- Model/mode combinations that underperform
- Prompt patterns that produce AI slop
- Material type mismatches
- Style drift conditions (e.g. concept changed and the anchor style ref was missing)

---

## Learnings Format

`learnings.json` has this structure:

```json
{
  "version": 1,
  "brand": "<brand-name>",
  "modelPreferences": [
    {
      "text": "[social] Winning setup: hybrid + nano-banana-2 + with refs",
      "material_type": "social",
      "evidence_versions": ["v069", "v071"],
      "source": "blackboard_promotion",
      "promoted_at": "2026-03-20T23:12:17",
      "correction_note": "works best with warm palette direction"
    }
  ],
  "styleReferencePolicies": [
    {
      "text": "[campaign_poster] Keep v014 as the mandatory style anchor",
      "material_type": "campaign_poster",
      "required_style_reference_versions": ["v014"],
      "reference_policy": "single_style_anchor",
      "evidence_versions": ["v031", "v032", "v033"],
      "source": "score_pattern_promotion",
      "promoted_at": "2026-03-21T01:26:46",
      "failure_mode_if_missing": "style drift",
      "correction_note": "When concepts change, nano-banana-2 does not reliably preserve the v014 art direction without that exact style anchor."
    }
  ],
  "colorInsights": [],
  "compositionPatterns": [],
  "failurePatterns": [
    {
      "text": "[concept-illustration] gradient text always produces gibberish",
      "material_type": "concept-illustration",
      "evidence_versions": ["v023", "v025"],
      "source": "blackboard_promotion",
      "promoted_at": "2026-03-18T14:30:00"
    }
  ],
  "messagingInsights": [],
  "audienceInsights": [],
  "lastUpdated": "2026-03-21T01:26:46"
}
```

### Reading Learnings in Phase 1

When Phase 1 reads learnings, it matches `material_type` against the requested type:

1. Exact match: Use the winning setup directly
2. No match: Check if a related material type has learnings (e.g., `social` learnings
   may apply to `announcement-card`)
3. No related match: Default to `hybrid` mode and let the current run establish a baseline

For `styleReferencePolicies`:
1. Exact match: lock the required style reference version(s) into the next plan
2. Adjacent family match: inherit cautiously if the visual family is clearly shared
3. No match: do not invent a style lock

---

## Updating Iteration Memory

**Why:** Iteration memory is the narrative layer on top of structured learnings. It
captures qualitative insights, user preferences, and contextual notes that do not fit
into the structured `learnings.json` format.

After evolve runs, update iteration memory with the evolve timestamp:

```bash
source .venv/bin/activate && bgen update-iteration-memory \
  --kind brand \
  --note "EVOLVE_RUN: <ISO-timestamp>"
```

### What to Record

Record discoveries that Phase 1 should know about:

- **Winning styles:** "v058 + v061 are the art direction — use as positive reference"
- **Style locks:** "STYLE LOCK: v014 must remain the only style carrier for campaign posters"
- **Critical constraints:** "CRITICAL: No realistic textures for this brand"
- **Benchmark versions:** "5-STAR BENCHMARK: v087 is the definitive art style target"
- **New metaphors from vault:** "VAULT AUDIT — NEW METAPHORS: garden tending, gallery wall"

Use `--kind` to categorize:
- `brand` — Brand-level notes (philosophy, direction, constraints)
- `positive` — Positive examples with version and summary
- `negative` — Negative examples with version and what went wrong
- `copy` — Copy/messaging notes
- `material` — Material-type-specific notes

---

## Feeding Back into Phase 1

The evolution cycle closes the loop:

```
Phase 6 writes → learnings.json → Phase 1 reads
Phase 6 writes → iteration-memory.json → Phase 1 reads
Phase 6 records → EVOLVE_RUN timestamp → Phase 1 checks for auto-evolve trigger
```

### What Changes for the Next Run

After evolve, the next generation run will:

1. **Apply new model preferences** — If evolve discovered that `inspiration` mode wins
   for `social`, the next social generation will default to `inspiration`
2. **Apply style locks** — If evolve discovered that `v014` is the mandatory style carrier
   for `campaign_poster`, the next campaign-poster plan must explicitly include it
3. **Apply new failure patterns** — If evolve identified that `gradient text` fails for
   `concept-illustration`, the next concept illustration will auto-ban it
4. **Reference positive examples** — High-scoring versions become implicit quality
   benchmarks for future critiques
5. **Avoid negative patterns** — Documented failures become automatic bans

This is how the pipeline gets smarter over time. Each generation contributes to the
learnings that shape future generations. The first 5 generations for a new material type
are exploratory; by generation 10, the pipeline has strong opinions about what works.
