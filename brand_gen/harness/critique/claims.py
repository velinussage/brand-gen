"""Argue-style surviving-claim aggregation and debate synthesis."""

from __future__ import annotations

from typing import Any

def categorize_claim_axis(text: str) -> str:
    """Categorizes a claim text into one of the universal rubric axes."""
    text_lower = text.lower()
    if any(k in text_lower for k in ("composition", "layout", "focal", "whitespace", "clutter", "balance")):
        return "composition"
    if any(k in text_lower for k in ("palette", "color", "device", "typography", "font", "brand")):
        return "brand_coherence"
    if any(k in text_lower for k in ("restraint", "slop", "purple", "neon", "gibberish", "effect")):
        return "restraint"
    if any(k in text_lower for k in ("story", "fidelity", "message", "category", "brief")):
        return "story_fidelity"
    if any(k in text_lower for k in ("clarity", "visitor", "legible", "understand", "decode")):
        return "meaning_clarity"
    if any(k in text_lower for k in ("proposition", "skill", "mcp", "library", "trust", "provenance")):
        return "value_proposition_fidelity"
    return "general"

def aggregate_surviving_claims(critics_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Aggregates and deduplicates findings from the critic panel into 'surviving claims'.
    
    Argue-style debate resolution:
    - Deduplicates identical or highly similar observations.
    - Groups claims by axis.
    - Identifies consensus (if multiple critics raised it) vs. unique concerns.
    - Rates priority based on blocking severity and agreement.
    """
    surviving_claims: list[dict[str, Any]] = []

    for res in critics_results:
        critic_id = res.get("critic_id", "unknown")
        
        # 1. Process blocking claims
        for block in res.get("blocking", []):
            if not isinstance(block, str) or not block.strip():
                continue
            block_clean = block.strip()
            block_lower = block_clean.lower()
            
            # Check for near-duplicate or semantic overlaps
            is_duplicate = False
            for existing in surviving_claims:
                if block_lower == existing["text"].lower() or (
                    len(block_lower) > 10 and block_lower[:20] in existing["text"].lower()
                ):
                    is_duplicate = True
                    # Add critic as supporting
                    if critic_id not in existing["source_critics"]:
                        existing["source_critics"].append(critic_id)
                        existing["consensus_level"] = "consensus"
                    break
            
            if not is_duplicate:
                surviving_claims.append({
                    "text": block_clean,
                    "severity": "blocking",
                    "axis": categorize_claim_axis(block_clean),
                    "source_critics": [critic_id],
                    "consensus_level": "unique",
                })

        # 2. Process advisory/evidence claims
        for evidence in res.get("evidence", []):
            if not isinstance(evidence, str) or not evidence.strip():
                continue
            evidence_clean = evidence.strip()
            evidence_lower = evidence_clean.lower()
            
            # Check for duplicates across blocking and advisory
            is_duplicate = False
            for existing in surviving_claims:
                if evidence_lower == existing["text"].lower() or (
                    len(evidence_lower) > 10 and evidence_lower[:20] in existing["text"].lower()
                ):
                    is_duplicate = True
                    if critic_id not in existing["source_critics"]:
                        existing["source_critics"].append(critic_id)
                        existing["consensus_level"] = "consensus"
                    break
            
            if not is_duplicate:
                surviving_claims.append({
                    "text": evidence_clean,
                    "severity": "advisory",
                    "axis": categorize_claim_axis(evidence_clean),
                    "source_critics": [critic_id],
                    "consensus_level": "unique",
                })

    # Add prioritizing score
    for claim in surviving_claims:
        score = 0
        if claim["severity"] == "blocking":
            score += 10
        if claim["consensus_level"] == "consensus":
            score += 5
        claim["priority_score"] = score

    # Sort surviving claims by priority score descending
    surviving_claims.sort(key=lambda c: c["priority_score"], reverse=True)
    return surviving_claims
