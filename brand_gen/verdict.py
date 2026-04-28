"""Unified quality Verdict model for brand-gen.

The pipeline has several quality gates (structural critic, VLM critique,
rubric scorer, blackboard/user feedback).  This module keeps their native
payloads intact while exposing one small, provenance-bearing shape for memory,
run-ledger, and prompt-context consumers.
"""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import Any, Literal


VerdictGate = Literal["critic", "vlm", "rubric", "blackboard", "user", "legacy"]
VerdictDecision = Literal["approve", "iterate", "reject"]

VALID_GATES = {"critic", "vlm", "rubric", "blackboard", "user", "legacy"}
VALID_DECISIONS = {"approve", "iterate", "reject"}


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def normalize_decision(value: str | None, *, score: int | None = None, status: str | None = None) -> VerdictDecision:
    text = str(value or "").strip().lower()
    if text in {"approved", "approve", "favorite", "pass", "ship"}:
        return "approve"
    if text in {"rejected", "reject", "fail", "block"}:
        return "reject"
    if text in {"iterate", "needs_refinement", "needs-refinement", "revise", "retry"}:
        return "iterate"
    status_text = str(status or "").strip().lower()
    if status_text == "favorite":
        return "approve"
    if status_text == "rejected":
        return "reject"
    if score is not None:
        if score >= 4:
            return "approve"
        if score <= 1:
            return "reject"
        return "iterate"
    return "iterate"


@dataclass(frozen=True)
class Verdict:
    gate: VerdictGate
    score: int
    decision: VerdictDecision
    rationale: str
    source_paths: list[str] = field(default_factory=list)
    version_id: str = ""
    created_at: str = field(default_factory=_now_iso)
    payload: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.gate not in VALID_GATES:
            raise ValueError(f"invalid verdict gate: {self.gate}")
        if self.decision not in VALID_DECISIONS:
            raise ValueError(f"invalid verdict decision: {self.decision}")
        if not isinstance(self.score, int) or not (1 <= self.score <= 5):
            raise ValueError(f"verdict score must be an integer 1-5, got {self.score!r}")
        object.__setattr__(self, "source_paths", [str(item) for item in (self.source_paths or []) if str(item).strip()])
        object.__setattr__(self, "payload", dict(self.payload or {}))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "Verdict":
        if not isinstance(raw, dict):
            raise ValueError("verdict payload must be a dict")
        score = int(raw.get("score") or 1)
        return cls(
            gate=str(raw.get("gate") or "legacy"),  # type: ignore[arg-type]
            score=score,
            decision=normalize_decision(str(raw.get("decision") or ""), score=score),  # type: ignore[arg-type]
            rationale=str(raw.get("rationale") or ""),
            source_paths=list(raw.get("source_paths") or []),
            version_id=str(raw.get("version_id") or ""),
            created_at=str(raw.get("created_at") or _now_iso()),
            payload=dict(raw.get("payload") or {}),
        )


def coerce_verdicts(items: list[Verdict | dict[str, Any]] | None) -> list[Verdict]:
    out: list[Verdict] = []
    for item in items or []:
        if isinstance(item, Verdict):
            out.append(item)
        elif isinstance(item, dict):
            out.append(Verdict.from_dict(item))
    return out


def verdict_from_user_feedback(
    *,
    version_id: str,
    score: int | None,
    decision: str | None = None,
    status: str | None = None,
    rationale: str = "",
    payload: dict[str, Any] | None = None,
) -> Verdict:
    normalized_score = int(score if score is not None else (1 if str(decision or "").lower() == "reject" else 3))
    normalized_score = max(1, min(5, normalized_score))
    normalized_decision = normalize_decision(decision, score=normalized_score, status=status)
    return Verdict(
        gate="user",
        score=normalized_score,
        decision=normalized_decision,
        rationale=rationale or "User feedback recorded.",
        version_id=version_id,
        payload=dict(payload or {}),
    )


def verdict_from_critic(version_id: str, critic_summary: dict[str, Any]) -> Verdict | None:
    p1 = list((critic_summary or {}).get("p1") or [])
    p2 = list((critic_summary or {}).get("p2") or [])
    p3 = list((critic_summary or {}).get("p3") or [])
    if not (p1 or p2 or p3):
        return None
    if p1:
        score, decision, rationale_items = 1, "reject", p1
    elif p2:
        score, decision, rationale_items = 2, "iterate", p2
    else:
        score, decision, rationale_items = 4, "approve", p3
    return Verdict(
        gate="critic",
        score=score,
        decision=decision,  # type: ignore[arg-type]
        rationale="; ".join(str(item) for item in rationale_items[:3]),
        version_id=version_id,
        payload={"p1": p1, "p2": p2, "p3": p3},
    )


def verdict_from_vlm(version_id: str, vlm_critique: dict[str, Any]) -> Verdict | None:
    if not (vlm_critique or {}).get("vlm_available"):
        return None
    p1 = list(vlm_critique.get("p1") or [])
    p2 = list(vlm_critique.get("p2") or [])
    approved = bool(vlm_critique.get("approved", False))
    if p1:
        score, decision, rationale = 1, "reject", "; ".join(str(item) for item in p1[:3])
    elif p2:
        score, decision, rationale = 2, "iterate", "; ".join(str(item) for item in p2[:3])
    elif approved:
        score, decision, rationale = 4, "approve", "VLM approved visual review."
    else:
        score, decision, rationale = 3, "iterate", "VLM critique did not approve and gave no blocking issues."
    return Verdict(
        gate="vlm",
        score=score,
        decision=decision,  # type: ignore[arg-type]
        rationale=rationale,
        version_id=version_id,
        payload=dict(vlm_critique or {}),
    )


def aggregate_rubric_score(axis_scores: dict[str, Any] | None, *, disqualifier_triggered: bool = False, overall_score: Any = None) -> int:
    if disqualifier_triggered:
        return 1
    if overall_score is not None:
        try:
            value = int(overall_score)
            if 1 <= value <= 5:
                return value
        except (TypeError, ValueError):
            pass
    values: list[int] = []
    for value in (axis_scores or {}).values():
        try:
            ivalue = int(value)
        except (TypeError, ValueError):
            continue
        if 1 <= ivalue <= 5:
            values.append(ivalue)
    return min(values) if values else 3


def verdict_from_rubric_payload(version_id: str, payload: dict[str, Any]) -> Verdict:
    disqualified = bool(payload.get("disqualifier_triggered", False))
    score = aggregate_rubric_score(
        payload.get("axis_scores") if isinstance(payload.get("axis_scores"), dict) else {},
        disqualifier_triggered=disqualified,
        overall_score=payload.get("overall_score"),
    )
    decision = "reject" if disqualified else normalize_decision(str(payload.get("decision") or ""), score=score)
    rationale = (
        str(payload.get("why_user_might_dislike_if_polished") or "").strip()
        or str(payload.get("recommended_next_change") or "").strip()
        or "; ".join(str(item) for item in (payload.get("top_failure_reasons") or [])[:3])
        or "Rubric verdict recorded."
    )
    return Verdict(
        gate="rubric",
        score=score,
        decision=decision,  # type: ignore[arg-type]
        rationale=rationale,
        version_id=version_id,
        payload=dict(payload or {}),
    )


def verdict_from_blackboard_feedback(version_id: str, item: dict[str, Any]) -> Verdict:
    score = item.get("score")
    try:
        score_int = int(score) if score is not None else None
    except (TypeError, ValueError):
        score_int = None
    decision = item.get("primary_decision") or item.get("decision")
    rationale = str(item.get("notes") or item.get("summary") or "Blackboard learning signal.").strip()
    if score_int is None:
        score_int = 4 if normalize_decision(str(decision or ""), status=item.get("status")) == "approve" else 2
    return Verdict(
        gate="blackboard",
        score=max(1, min(5, int(score_int))),
        decision=normalize_decision(str(decision or ""), score=score_int, status=item.get("status")),
        rationale=rationale,
        version_id=version_id,
        payload=dict(item or {}),
    )


def legacy_verdict_from_entry(version_id: str, entry: dict[str, Any]) -> Verdict:
    score = entry.get("score")
    try:
        score_int = int(score) if score is not None else 3
    except (TypeError, ValueError):
        score_int = 3
    score_int = max(1, min(5, score_int))
    return Verdict(
        gate="legacy",
        score=score_int,
        decision=normalize_decision(entry.get("decision"), score=score_int, status=entry.get("status")),
        rationale=str(entry.get("summary") or entry.get("notes") or "Legacy iteration-memory entry.").strip(),
        version_id=version_id,
        payload=dict(entry or {}),
    )


_PRIORITIES: dict[str, list[str]] = {
    "structural": ["user", "critic", "vlm", "rubric", "blackboard", "legacy"],
    "visual": ["user", "vlm", "critic", "rubric", "blackboard", "legacy"],
    "numeric": ["user", "rubric", "vlm", "critic", "blackboard", "legacy"],
}
_DECISION_STRENGTH = {"reject": 0, "iterate": 1, "approve": 2}


def _claim_type(verdicts: list[Verdict]) -> str:
    if any(v.gate == "user" for v in verdicts):
        return "numeric"
    if any(v.gate == "critic" and v.decision == "reject" for v in verdicts):
        return "structural"
    if any(v.gate == "rubric" and v.decision == "reject" for v in verdicts):
        return "numeric"
    if any(v.gate == "vlm" and v.decision != "approve" for v in verdicts):
        return "visual"
    return "numeric"


def reconcile_verdicts(verdicts: list[Verdict | dict[str, Any]] | None) -> dict[str, Any]:
    coerced = coerce_verdicts(verdicts)
    if not coerced:
        return {
            "primary_decision": "",
            "primary_score": None,
            "primary_gate": "",
            "verdict_conflict": False,
            "conflict_summary": "",
            "verdicts": [],
        }
    claim = _claim_type(coerced)
    priority = _PRIORITIES[claim]
    indexed = {gate: idx for idx, gate in enumerate(priority)}
    primary = sorted(
        coerced,
        key=lambda v: (
            indexed.get(v.gate, 99),
            _DECISION_STRENGTH.get(v.decision, 1),
            v.score,
        ),
    )[0]
    decisions = {v.decision for v in coerced}
    conflict = "reject" in decisions and "approve" in decisions
    conflict_summary = ""
    if conflict:
        bits = [f"{v.gate}={v.decision}" for v in coerced]
        conflict_summary = "Verdict conflict: " + ", ".join(bits)
    return {
        "primary_decision": primary.decision,
        "primary_score": primary.score,
        "primary_gate": primary.gate,
        "verdict_conflict": conflict,
        "conflict_summary": conflict_summary,
        "verdicts": [v.to_dict() for v in coerced],
    }
