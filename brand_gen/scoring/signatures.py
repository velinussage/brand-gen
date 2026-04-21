"""DSPy signatures for the v2 brand scorer.

Three signatures compose into `BrandScorer`:
- `DescribeImage`: one-shot visual description (no judgment)
- `AxisScore`: score a single rubric axis with rationale + evidence
- `Synthesize`: per-axis scores → decision + top failure reasons

`AxisScore` is called many times per critique (once per axis).
The per-axis calls repeat the same image; that's where caching matters.
See `program.py` for how the scorer constructs messages defensively —
it bypasses Signature formatting for `AxisScore` calls and builds
Anthropic-shaped messages inline with `cache_control` breakpoints.

`DescribeImage` and `Synthesize` run once per critique; Signature
formatting is fine there.
"""
from __future__ import annotations

from typing import Literal

import dspy


class DescribeImage(dspy.Signature):
    """Describe what is visually in the image without judgment.

    Used once per critique to produce a shared understanding that axis
    scoring references. Do not score here — describe.
    """

    image: dspy.Image = dspy.InputField(desc="Rendered candidate design")
    material_type: str = dspy.InputField(desc="e.g. landing-hero, concept-illustration")
    scene_summary: str = dspy.OutputField(
        desc="1-2 sentence neutral description of what is in the frame"
    )
    visual_elements: list[str] = dspy.OutputField(
        desc="List concrete visual elements present (typography treatment, figures, textures, etc.)"
    )
    first_impression: str = dspy.OutputField(
        desc="What a new viewer would understand about this in 2-3 seconds, without context"
    )


class AxisScore(dspy.Signature):
    """Score one rubric axis for this image with rationale and evidence.

    Called once per universal axis + once per overlay axis. The same image
    is passed on every call, so `program.py` routes around Signature
    formatting for these to place cache_control breakpoints correctly.
    """

    image: dspy.Image = dspy.InputField()
    material_type: str = dspy.InputField()
    axis_name: str = dspy.InputField(desc="Which axis is being scored")
    axis_definition: str = dspy.InputField(desc="What this axis measures")
    brand_dna: str = dspy.InputField(
        desc="Brand palette, approved devices, forbidden elements, tone words"
    )
    story_objective: str = dspy.InputField(
        desc="What this specific material is meant to communicate"
    )

    score: Literal[1, 2, 3, 4, 5] = dspy.OutputField(
        desc="Integer 1-5 on this axis"
    )
    rationale: str = dspy.OutputField(
        desc="1-2 sentences explaining the score in concrete terms"
    )
    evidence: list[str] = dspy.OutputField(
        desc="Concrete visual elements in the image that support the score"
    )


class Synthesize(dspy.Signature):
    """Synthesize per-axis scores into a ship/iterate/reject decision.

    Called once per critique after all axes are scored. Produces the
    final decision + the specific `why_user_might_dislike` field that is
    the signal the whole system was built for.
    """

    axis_scores: dict[str, int] = dspy.InputField(
        desc="axis_name -> 1-5 score"
    )
    axis_rationales: dict[str, str] = dspy.InputField(
        desc="axis_name -> rationale"
    )
    disqualifier_triggered: bool = dspy.InputField(
        desc="True if the material's disqualifier rule fired"
    )
    disqualifier_rule_id: str = dspy.InputField(
        desc="rule_id if triggered, empty otherwise"
    )
    material_type: str = dspy.InputField()

    decision: Literal["approve", "iterate", "reject"] = dspy.OutputField(
        desc="Final decision. Min-biased aggregation: any axis <2 => iterate; disqualifier_triggered => reject"
    )
    top_failure_reasons: list[str] = dspy.OutputField(
        desc="2-3 concrete reasons this might miss (not a restatement of rationales)"
    )
    recommended_next_change: str = dspy.OutputField(
        desc="One specific thing to change for the next iteration"
    )
    why_user_might_dislike_if_polished: str = dspy.OutputField(
        desc=(
            "The meaning-vs-craft mismatch, if any. What could make a user reject "
            "this even if it is technically polished? This is the crucial field "
            "for the 'tasteful but meaningless' failure mode."
        )
    )
