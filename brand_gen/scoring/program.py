"""BrandScorer DSPy program — v1 hand-written (no GEPA optimization yet).

Architecture (M2 scope):
- `describe` (dspy.ChainOfThought(DescribeImage)) — one call, uses Signature
- `score_axis` for each rubric axis — bypasses Signature for the cache-sensitive
  path, calls the LM directly with messages that carry `cache_control`
  breakpoints. This lets us ship a caching strategy that works regardless of
  DSPy's internal Signature-to-messages normalization behavior.
- `synthesize` (dspy.Predict(Synthesize)) — one call, uses Signature

The parent `BrandScorer.forward()` returns a `dspy.Prediction` with:
- `description`: DescribeImage output
- `axis_scores: dict[str, int]`
- `axis_rationales: dict[str, str]`
- `axis_evidence: dict[str, list[str]]`
- `disqualifier_triggered: bool`
- `disqualifier_rule_id: str`
- `decision`: Synthesize output ("approve" | "iterate" | "reject")
- `top_failure_reasons: list[str]`
- `recommended_next_change: str`
- `why_user_might_dislike_if_polished: str`
- `rubric_version: str`
- `scorer_version: str`
- `material_rubric_key: str`

The output shape exactly matches the v2 critique packet that
`agent_review.py` will carry (M3 wires the packet extension).

Disqualifier detection in v1: a small separate LM call that reads
`disqualifier.detection_prompt` and returns a boolean. Isolated from
axis scoring so a false positive here doesn't poison axis rationales.
The universal `value_proposition_fidelity` axis is the user-calibrated guard
for polished-but-wrong Sage outputs; a score of 1 should be treated as a hard
iteration/rejection signal through min-biased aggregation.
"""
from __future__ import annotations

import json
from typing import Any

import dspy

from .rubric_registry import (
    RUBRIC_VERSION,
    axes_for,
    disqualifier_for,
    material_rubric_key,
)
from .signatures import AxisScore, DescribeImage, Synthesize

SCORER_VERSION = "v1-handwritten"


_AXIS_SYSTEM_PROMPT_TEMPLATE = """You are a rubric-based design evaluator. You score ONE axis at a time on a 1-5 integer scale.

Rubric version: {rubric_version}
Material type: {material_type}
Material rubric key: {material_rubric_key}

This axis you are about to score:
  name: {axis_name}
  definition: {axis_definition}

Brand DNA (palette, approved devices, forbidden elements, tone):
{brand_dna}

Story objective for this material:
{story_objective}

Scoring discipline:
- 5 = excellent on this axis; could not improve
- 4 = strong; minor polish possible
- 3 = acceptable; visible gap but not disqualifying
- 2 = weak; significant gap on this axis
- 1 = fails this axis
Score the axis IN ISOLATION. Another axis may be strong or weak; only this one counts here.

Output strictly in this JSON shape (no prose outside JSON):
{{"score": <1-5 integer>, "rationale": "<1-2 sentences>", "evidence": ["<concrete visual element>", ...]}}"""


_DISQUALIFIER_SYSTEM_PROMPT_TEMPLATE = """You check a single material-specific disqualifier rule against an image.

Rubric version: {rubric_version}
Material type: {material_type}
Disqualifier rule id: {rule_id}
Rule description: {description}

Detection prompt (apply this exactly):
{detection_prompt}

Output strictly in this JSON shape (no prose outside JSON):
{{"triggered": <true|false>, "matched_phrase": "<why it triggered, or empty string>"}}"""


class BrandScorer(dspy.Module):
    """v2 rubric-based image scorer with defensive caching design."""

    def __init__(self):
        super().__init__()
        self.describe = dspy.ChainOfThought(DescribeImage)
        self.synthesize = dspy.Predict(Synthesize)
        # Axis scoring bypasses Signatures; see forward() below.

    def forward(
        self,
        image: dspy.Image,
        material_type: str,
        brand_dna: str,
        story_objective: str,
        *,
        lm: dspy.LM | None = None,
    ) -> dspy.Prediction:
        """Score an image against the universal + overlay rubric.

        Args:
            image: the image to score (dspy.Image; wraps a URL or local path).
            material_type: e.g. "landing-hero", "concept-illustration".
            brand_dna: palette + approved devices + forbidden elements + tone.
            story_objective: what this material is meant to communicate.
            lm: override the default LM. If None, uses `dspy.settings.lm`.

        Returns:
            dspy.Prediction with the full v2 packet fields as attributes.
        """
        target_lm = lm or dspy.settings.lm
        if target_lm is None:
            raise RuntimeError(
                "No LM configured. Call brand_gen.scoring.config.configure_judge_lm() "
                "or pass lm= explicitly."
            )

        # Stage 1: describe (one call, through Signature)
        desc = self.describe(image=image, material_type=material_type)

        # Stage 2: per-axis scoring (N calls, messages built inline for caching)
        axes = axes_for(material_type)
        axis_scores: dict[str, int] = {}
        axis_rationales: dict[str, str] = {}
        axis_evidence: dict[str, list[str]] = {}

        for axis in axes:
            score, rationale, evidence = self._score_axis(
                lm=target_lm,
                image=image,
                material_type=material_type,
                axis_name=axis["name"],
                axis_definition=axis["definition"],
                brand_dna=brand_dna,
                story_objective=story_objective,
            )
            axis_scores[axis["name"]] = score
            axis_rationales[axis["name"]] = rationale
            axis_evidence[axis["name"]] = evidence

        # Stage 3: disqualifier check (one call if the material has a rule)
        dq_rule = disqualifier_for(material_type)
        dq_triggered = False
        dq_rule_id = ""
        if dq_rule is not None:
            dq_triggered, _ = self._check_disqualifier(
                lm=target_lm,
                image=image,
                material_type=material_type,
                rule=dq_rule,
            )
            dq_rule_id = str(dq_rule.get("rule_id") or "") if dq_triggered else ""

        # Stage 4: synthesize (one call, through Signature)
        synth = self.synthesize(
            axis_scores=axis_scores,
            axis_rationales=axis_rationales,
            disqualifier_triggered=dq_triggered,
            disqualifier_rule_id=dq_rule_id,
            material_type=material_type,
        )

        return dspy.Prediction(
            description=desc,
            axis_scores=axis_scores,
            axis_rationales=axis_rationales,
            axis_evidence=axis_evidence,
            disqualifier_triggered=dq_triggered,
            disqualifier_rule_id=dq_rule_id,
            decision=synth.decision,
            top_failure_reasons=synth.top_failure_reasons,
            recommended_next_change=synth.recommended_next_change,
            why_user_might_dislike_if_polished=synth.why_user_might_dislike_if_polished,
            rubric_version=RUBRIC_VERSION,
            scorer_version=SCORER_VERSION,
            material_rubric_key=material_rubric_key(material_type),
        )

    def _score_axis(
        self,
        *,
        lm: dspy.LM,
        image: dspy.Image,
        material_type: str,
        axis_name: str,
        axis_definition: str,
        brand_dna: str,
        story_objective: str,
    ) -> tuple[int, str, list[str]]:
        """Score one axis via direct LM call with cache_control breakpoints.

        Bypasses dspy.Signature formatting to keep explicit control over the
        Anthropic content-block shape. This is the cache-sensitive path
        (image repeats across axes).
        """
        from .config import build_cached_messages, image_source_from_path

        system_prompt = _AXIS_SYSTEM_PROMPT_TEMPLATE.format(
            rubric_version=RUBRIC_VERSION,
            material_type=material_type,
            material_rubric_key=material_rubric_key(material_type) or "(universal only)",
            axis_name=axis_name,
            axis_definition=axis_definition,
            brand_dna=brand_dna or "(none provided)",
            story_objective=story_objective or "(not specified)",
        )
        user_text = (
            f"Score this image on the axis '{axis_name}'. "
            f"Return only the JSON object described in the instructions."
        )

        image_source = _resolve_image_source(image)
        messages = build_cached_messages(
            system_prompt=system_prompt,
            image_source=image_source,
            user_text=user_text,
        )

        # dspy.LM.__call__(messages=...) forwards to LiteLLM → Anthropic.
        # We parse the response defensively.
        raw = lm(messages=messages)
        text = _extract_text(raw)
        parsed = _extract_json_dict(text)
        score = int(parsed.get("score") or 3)
        score = max(1, min(5, score))  # clamp
        rationale = str(parsed.get("rationale") or "").strip()
        evidence_raw = parsed.get("evidence") or []
        evidence = [str(item).strip() for item in evidence_raw if str(item).strip()]
        return score, rationale, evidence

    def _check_disqualifier(
        self,
        *,
        lm: dspy.LM,
        image: dspy.Image,
        material_type: str,
        rule: dict[str, str],
    ) -> tuple[bool, str]:
        """Check one disqualifier rule.

        Returns (triggered, matched_phrase). On parse failure, returns
        (False, "") — safer to let the critic agent catch it downstream
        than to falsely auto-fail.
        """
        from .config import build_cached_messages

        system_prompt = _DISQUALIFIER_SYSTEM_PROMPT_TEMPLATE.format(
            rubric_version=RUBRIC_VERSION,
            material_type=material_type,
            rule_id=rule.get("rule_id", ""),
            description=rule.get("description", ""),
            detection_prompt=rule.get("detection_prompt", ""),
        )
        user_text = "Apply the disqualifier detection prompt to this image."

        image_source = _resolve_image_source(image)
        messages = build_cached_messages(
            system_prompt=system_prompt,
            image_source=image_source,
            user_text=user_text,
        )

        try:
            raw = lm(messages=messages)
            text = _extract_text(raw)
            parsed = _extract_json_dict(text)
            triggered = bool(parsed.get("triggered", False))
            matched = str(parsed.get("matched_phrase") or "").strip()
            return triggered, matched
        except Exception:
            return False, ""


def _resolve_image_source(image: Any) -> dict[str, Any]:
    """Extract Anthropic image-source block from dspy.Image or compatible.

    Supports:
    - dspy.Image (from_url / from_file)
    - dict with {"type": "base64", ...} (passed through)
    - dict with {"type": "url", "url": "..."} (passed through)
    - str path to a local image file
    """
    from .config import image_source_from_path

    if isinstance(image, dict):
        return image
    if isinstance(image, (str,)) or hasattr(image, "__fspath__"):
        return image_source_from_path(image)
    # dspy.Image — try to extract URL or path
    url = getattr(image, "url", None)
    if url:
        return {"type": "url", "url": url}
    path = getattr(image, "path", None)
    if path:
        return image_source_from_path(path)
    # Fallback: try str() coercion
    return image_source_from_path(str(image))


def _extract_text(raw: Any) -> str:
    """dspy.LM returns list[str] or str; normalize to str."""
    if isinstance(raw, list) and raw:
        return str(raw[0])
    return str(raw)


def _extract_json_dict(text: str) -> dict[str, Any]:
    """Parse JSON even when the model wraps it in prose or fences."""
    text = text.strip()
    # Strip common markdown fences
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) >= 2:
            text = "\n".join(lines[1:-1]) if lines[-1].startswith("```") else "\n".join(lines[1:])
    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Find first { and last }
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass
    return {}
