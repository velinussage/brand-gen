"""Seven-rule validator for Seedance shot-design prompts.

Mechanical checks only — the creative judgment (right director token? is this
intensity appropriate?) belongs to the brand-cinematographer agent. This
module implements §8 of `skills/brand-gen/references/seedance-shot-design.md`
so the pipeline can hard-gate bad prompts before spending on generation.

Usage:

    from brand_gen.seedance_validation import validate_seedance_prompt
    result = validate_seedance_prompt(prompt, duration_seconds=7, asset_counts={"image": 2})
    if not result.ok:
        raise SystemExit("prompt rejected:\n" + result.report())
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


FILLER_WORDS = {
    "4k", "8k", "masterpiece", "best quality", "ultra hd", "ultra-hd", "ultrahd",
    "extremely detailed", "hyper-realistic", "hyperrealistic", "super resolution",
    "ultra-sharp", "ultra sharp",
}

# Safe camera-move phrasings from §3 of the reference. If any of these (or
# recognised suffix phrasings) appears, rule 3 passes.
SAFE_CAMERA_PHRASES = [
    "pan shot", "tilt up", "tilt down",
    "dolly tracking shot", "dolly push-in", "dolly pull-out",
    "zoom in", "zoom out",
    "truck left", "truck right",
    "crane shot", "jib shot",
    "orbital camera movement", "arc shot",
    "tracking shot", "static shot", "locked-off shot",
    "slow push-in", "slow pull-out",
    "pedestal up", "pedestal down",
    "epic drone reveal shot", "reveal through obstacle shot",
    "leading shot pulling back", "fpv drone shot",
    "steadicam follow", "snorricam body-mounted",
    "crash cam ground level", "whip pan transition",
    "snap zoom", "crash zoom",
    "close-up", "medium shot", "medium close-up", "wide shot",
    "extreme close-up", "extreme wide shot", "over-the-shoulder",
    "pov shot", "aerial drone shot", "establishing shot",
]

# Bare words that get misclassified by moderation. Detect them as standalone
# tokens (word-boundary), not as substrings of longer phrases.
BARE_WORD_VIOLATIONS = ["dolly", "aerial", "crane", "pan", "arc", "dutch", "steadicam"]

# Conflict pairs (lowercased substring checks).
CONFLICT_PAIRS = [
    (("slow motion", "speed ramp"),
     "slow-motion and speed-ramp cannot coexist in one slice"),
    (("14mm", "shallow depth of field"),
     "14mm ultra-wide is incompatible with shallow DOF"),
    (("14mm", "shallow dof"),
     "14mm ultra-wide is incompatible with shallow DOF"),
    (("handheld", "strict symmetrical"),
     "handheld motion and strict symmetry contradict each other"),
    (("kodak portra", "ultra-sharp"),
     "film stock and ultra-sharp digital are mutually exclusive"),
    (("cinestill 800t", "ultra-sharp"),
     "film stock and ultra-sharp digital are mutually exclusive"),
    (("cel-shaded", "subsurface scattering"),
     "cel-shaded rendering is incompatible with photoreal PBR materials"),
    (("cel-shaded", "realistic skin texture"),
     "cel-shaded rendering is incompatible with photoreal PBR materials"),
]

# Time-slice pattern — `0-3s:` or `0-3 s:` or `0-3 seconds:`.
TIME_SLICE_RE = re.compile(r"\b\d+\s*-\s*\d+\s*(s|sec|seconds?)\s*:", re.IGNORECASE)


@dataclass
class ValidationResult:
    ok: bool
    failures: list[tuple[int, str]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def report(self) -> str:
        lines = []
        for rule_id, message in self.failures:
            lines.append(f"  rule {rule_id}: {message}")
        if self.warnings:
            lines.append("  warnings:")
            for w in self.warnings:
                lines.append(f"    - {w}")
        return "\n".join(lines) or "ok"


def _word_count(text: str) -> int:
    return len(re.findall(r"\b[A-Za-z][A-Za-z0-9'-]*\b", text))


def validate_seedance_prompt(
    prompt: str,
    *,
    duration_seconds: float | None = None,
    asset_counts: dict | None = None,
) -> ValidationResult:
    """Run the seven-rule checklist from the seedance-shot-design reference.

    - duration_seconds: used by rule 2 to require time slices for >5s videos.
    - asset_counts: optional dict like {"image": 3, "video": 1, "audio": 0}.
    """
    failures: list[tuple[int, str]] = []
    warnings: list[str] = []
    lower = prompt.lower()

    # Rule 1 — length
    word_count = _word_count(prompt)
    if word_count > 1000:
        failures.append((1, f"prompt is {word_count} words (>1000)"))
    elif word_count > 850:
        warnings.append(f"prompt length is {word_count} words (>85% of 1000-word cap)")

    # Rule 2 — time slices
    if duration_seconds is not None and duration_seconds > 5 and not TIME_SLICE_RE.search(prompt):
        failures.append((2, f"duration is {duration_seconds}s but no time slices found (expected format `0-3s:`)"))

    # Rule 3 — at least one camera phrase
    if not any(phrase in lower for phrase in SAFE_CAMERA_PHRASES):
        failures.append((3, "no safe camera phrase detected (monitor-cam prompt)"))

    # Rule 4 — filler words
    hit_fillers = sorted({w for w in FILLER_WORDS if w in lower})
    if hit_fillers:
        failures.append((4, "filler words present: " + ", ".join(hit_fillers)))

    # Rule 5 — asset caps
    if asset_counts:
        i = int(asset_counts.get("image") or 0)
        v = int(asset_counts.get("video") or 0)
        a = int(asset_counts.get("audio") or 0)
        total = i + v + a
        if i > 9:
            failures.append((5, f"image ref count {i} exceeds 9"))
        if v > 3:
            failures.append((5, f"video ref count {v} exceeds 3"))
        if a > 3:
            failures.append((5, f"audio ref count {a} exceeds 3"))
        if total > 12:
            failures.append((5, f"combined ref count {total} exceeds 12"))

    # Rule 6 — conflicts
    for (left, right), message in CONFLICT_PAIRS:
        if left in lower and right in lower:
            failures.append((6, message))

    # Rule 7 — bare camera words
    bare_hits: list[str] = []
    for word in BARE_WORD_VIOLATIONS:
        pattern = rf"(?<![a-z]){re.escape(word)}(?![a-z-])"
        for match in re.finditer(pattern, lower):
            # Safe: part of a known multi-word phrase (e.g. `dolly tracking shot`,
            # `aerial drone shot`, `crane shot`, `pan shot`, `arc shot`,
            # `dutch angle`, `steadicam follow`).
            span_start = max(0, match.start() - 2)
            span_end = min(len(lower), match.end() + 32)
            window = lower[span_start:span_end]
            if any(safe in window for safe in SAFE_CAMERA_PHRASES):
                continue
            if word == "dutch" and "dutch angle" in lower:
                continue
            bare_hits.append(word)
            break
    if bare_hits:
        failures.append((7, "bare-word camera tokens present: " + ", ".join(sorted(set(bare_hits)))))

    return ValidationResult(ok=not failures, failures=failures, warnings=warnings)
