"""Calibration metrics — v1 minimum.

Ships:
- weighted Cohen's kappa (quadratic weights) for ordinal 1-5 scores
- raw agreement % (guards qualitatively against the approve-heavy kappa
  paradox — when κ is low but raw agreement is high, the paradox is
  visible to the reader without needing formal Gwet's AC1 yet)

v2 adds: Gwet's AC1, PABAK, Krippendorff's alpha, Cronbach's alpha for
axis redundancy. Trigger: ≥100 disagreement examples collected.

All computations are pure Python + scipy. No external state.
"""
from __future__ import annotations

from typing import Iterable, Sequence


def raw_agreement_rate(agent_scores: Sequence[int], user_scores: Sequence[int]) -> float:
    """Fraction of items where agent and user scores are equal.

    Complement to kappa. When raw agreement is >>0 but kappa is ~0, you
    are hitting the kappa paradox (class imbalance + high agreement →
    kappa can't distinguish skill from base-rate guessing).
    """
    if not agent_scores or not user_scores:
        return 0.0
    if len(agent_scores) != len(user_scores):
        raise ValueError(
            f"agent_scores ({len(agent_scores)}) and user_scores "
            f"({len(user_scores)}) must be the same length"
        )
    matches = sum(1 for a, u in zip(agent_scores, user_scores) if a == u)
    return matches / len(agent_scores)


def weighted_cohen_kappa(
    agent_scores: Sequence[int],
    user_scores: Sequence[int],
    *,
    weights: str = "quadratic",
    categories: tuple[int, ...] = (1, 2, 3, 4, 5),
) -> float:
    """Weighted Cohen's kappa for ordinal 1-5 scores.

    Quadratic weights penalize distant disagreements more than adjacent
    ones, which matches how humans read score deltas ("2 vs 5" is much
    worse than "3 vs 4"). Use linear weights if you want each step to
    count equally; don't use unweighted kappa on ordinal data — it
    treats all disagreements as equally bad.

    Returns kappa in [-1, 1]. 1 = perfect agreement; 0 = chance-level;
    negative = worse than chance. For aesthetic rubrics, expect
    0.3-0.5 in practice; <0.2 = miscalibrated; >0.6 = substantial.

    Handles edge cases:
    - Empty inputs → 0.0
    - All same score on one side (zero variance) → 0.0 (kappa is
      undefined; we return 0 rather than raise, so dashboards stay up)
    """
    if not agent_scores or not user_scores:
        return 0.0
    if len(agent_scores) != len(user_scores):
        raise ValueError(
            f"length mismatch: {len(agent_scores)} vs {len(user_scores)}"
        )
    try:
        from sklearn.metrics import cohen_kappa_score
        # sklearn is not a hard dep; if available, use it (battle-tested)
        return float(cohen_kappa_score(agent_scores, user_scores, weights=weights))
    except ImportError:
        pass

    # Fallback pure-python implementation using scipy for the matrix math
    try:
        import numpy as np
    except ImportError:  # pragma: no cover - scipy is a declared dep
        return _weighted_kappa_pure_python(
            list(agent_scores), list(user_scores), weights, categories
        )

    cats = np.array(categories, dtype=int)
    n_cats = len(cats)
    cat_index = {c: i for i, c in enumerate(cats.tolist())}

    # Build confusion matrix
    cm = np.zeros((n_cats, n_cats), dtype=float)
    for a, u in zip(agent_scores, user_scores):
        ai = cat_index.get(int(a))
        ui = cat_index.get(int(u))
        if ai is None or ui is None:
            continue  # silently drop out-of-range values
        cm[ai, ui] += 1

    total = cm.sum()
    if total == 0:
        return 0.0

    row_totals = cm.sum(axis=1)
    col_totals = cm.sum(axis=0)
    expected = np.outer(row_totals, col_totals) / total

    # Weight matrix: quadratic: ((i-j) / (n-1))**2
    i = np.arange(n_cats).reshape(-1, 1)
    j = np.arange(n_cats).reshape(1, -1)
    denom = max(n_cats - 1, 1)
    if weights == "quadratic":
        w = ((i - j) / denom) ** 2
    elif weights == "linear":
        w = np.abs(i - j) / denom
    else:
        raise ValueError(f"unsupported weights: {weights!r}")

    num = (w * cm).sum()
    den = (w * expected).sum()
    if den == 0:
        return 0.0
    kappa = 1.0 - num / den
    return float(kappa)


def _weighted_kappa_pure_python(
    agent_scores: list[int],
    user_scores: list[int],
    weights: str,
    categories: tuple[int, ...],
) -> float:
    """Pure-Python fallback when numpy is unavailable (shouldn't happen
    in practice since scipy is a declared dep and pulls numpy)."""
    n = len(agent_scores)
    cat_list = list(categories)
    n_cats = len(cat_list)
    cat_index = {c: i for i, c in enumerate(cat_list)}
    cm = [[0.0] * n_cats for _ in range(n_cats)]
    for a, u in zip(agent_scores, user_scores):
        ai = cat_index.get(int(a))
        ui = cat_index.get(int(u))
        if ai is None or ui is None:
            continue
        cm[ai][ui] += 1
    total = sum(sum(r) for r in cm)
    if total == 0:
        return 0.0
    row_totals = [sum(r) for r in cm]
    col_totals = [sum(cm[i][j] for i in range(n_cats)) for j in range(n_cats)]
    expected = [[row_totals[i] * col_totals[j] / total for j in range(n_cats)] for i in range(n_cats)]

    def weight(i: int, j: int) -> float:
        denom = max(n_cats - 1, 1)
        if weights == "quadratic":
            return ((i - j) / denom) ** 2
        if weights == "linear":
            return abs(i - j) / denom
        raise ValueError(f"unsupported weights: {weights!r}")

    num = sum(weight(i, j) * cm[i][j] for i in range(n_cats) for j in range(n_cats))
    den = sum(weight(i, j) * expected[i][j] for i in range(n_cats) for j in range(n_cats))
    if den == 0:
        return 0.0
    return 1.0 - num / den


def score_pairs_from_disagreement_records(
    records: Iterable[dict],
) -> tuple[list[int], list[int]]:
    """Extract parallel (agent_scores, user_scores) from disagreement records.

    Skips records missing either score. For v1 agent scoring, the
    "agent_score" field is the scorer's overall / min-biased decision
    encoded as an integer 1-5 (not the per-axis scores). This keeps the
    calibration metric scoped to the ship/iterate/reject decision the
    critic actually surfaces to the user.
    """
    agent: list[int] = []
    user: list[int] = []
    for r in records:
        a = r.get("agent_score")
        u = r.get("user_score")
        if a is None or u is None:
            continue
        try:
            agent.append(int(a))
            user.append(int(u))
        except (TypeError, ValueError):
            continue
    return agent, user


def compute_agreement_stats(records: list[dict]) -> dict:
    """Compute the v1 calibration dashboard payload.

    Returns a dict with:
    - `n_total`: total records
    - `n_scored`: records with both agent and user scores
    - `raw_agreement`: fraction where agent == user
    - `weighted_kappa`: quadratic-weighted Cohen's kappa
    - `n_per_bucket`: count per agreement_bucket
    - `n_per_material`: count per material_type (for "flag <10 examples" UI)
    """
    agent, user = score_pairs_from_disagreement_records(records)
    n_total = len(records)
    n_scored = len(agent)
    raw_agree = raw_agreement_rate(agent, user) if n_scored else 0.0
    wk = weighted_cohen_kappa(agent, user) if n_scored else 0.0
    buckets: dict[str, int] = {}
    materials: dict[str, int] = {}
    for r in records:
        b = str(r.get("agreement_bucket") or "")
        if b:
            buckets[b] = buckets.get(b, 0) + 1
        m = str(r.get("material_type") or "")
        if m:
            materials[m] = materials.get(m, 0) + 1
    return {
        "n_total": n_total,
        "n_scored": n_scored,
        "raw_agreement": round(raw_agree, 3),
        "weighted_kappa": round(wk, 3),
        "n_per_bucket": buckets,
        "n_per_material": materials,
    }
