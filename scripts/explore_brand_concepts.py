#!/usr/bin/env python3
"""Suggest exploratory brand concept directions from a brief or brand profile."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE_DATA = REPO_ROOT / "data" / "brand_example_sources.json"
WORD_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9-]{2,}")
STOPWORDS = {
    "about", "after", "again", "also", "and", "app", "asset", "assets", "before", "both", "brand", "can",
    "cards", "clean", "context", "create", "create", "different", "feed", "for", "from", "good", "hero",
    "image", "images", "into", "just", "kind", "landing", "light", "like", "make", "material", "materials",
    "minimal", "need", "new", "not", "only", "page", "pages", "post", "posts", "product", "real", "really",
    "screen", "screens", "screenshot", "screenshots", "should", "show", "site", "startup", "style", "sage",
    "that", "the", "their", "them", "these", "they", "this", "too", "use", "used", "using", "views", "visual",
    "visuals", "want", "with", "without", "work",
}

DIRECTION_TEMPLATES = [
    {
        "key": "curated-intelligence-feed",
        "title": "Curated intelligence feed",
        "summary": "Frame the product as a living stream of high-signal artifacts, activity, and curation rather than as a generic dashboard.",
        "signals": {
            "activity", "alive", "artifact", "artifacts", "browse", "community", "curated", "curation", "discover",
            "discovery", "feed", "knowledge", "library", "libraries", "network", "prompt", "prompts", "skill",
            "skills", "stream", "trust", "active",
        },
        "anti_signals": {"casino", "meme", "noisy", "trader", "terminal"},
        "visual_cues": [
            "one dominant browser crop on the strongest real activity or library moment",
            "airy whitespace with a light editorial field behind the UI",
            "visible rhythm between cards, filters, and metadata without extra chrome",
            "a clear feeling that the product is active and curated",
        ],
        "avoid": [
            "fake notification widgets or invented activity cards",
            "dense multi-panel dashboard packaging",
            "crypto-trading or command-center energy",
        ],
        "materials": ["browser-illustration", "x-feed", "product-banner"],
        "source_keys": ["ramotion", "metalab", "parallel", "stanvision", "eleken"],
        "source_tags": {"saas", "product", "mockups", "clean", "case-studies", "premium"},
    },
    {
        "key": "calm-governed-network",
        "title": "Calm governed network",
        "summary": "Lead with trust, governance, and structure so the product feels credible, durable, and coordinated without looking institutional.",
        "signals": {
            "calm", "community", "coordination", "credible", "governance", "governed", "network", "professional",
            "protocol", "reliable", "security", "serious", "structured", "trust", "trustworthy",
        },
        "anti_signals": {"chaotic", "casino", "flashy", "meme", "noisy"},
        "visual_cues": [
            "quiet browser framing with generous margins",
            "soft neutral or cream field with restrained depth",
            "clear trust surfaces such as library identity, governance state, or system metadata",
            "calm grid alignment that makes the product feel organized instead of busy",
        ],
        "avoid": [
            "dark neon crypto styling",
            "aggressive motion blur or loud gradients",
            "throwing away trust or governance cues that make the product distinct",
        ],
        "materials": ["browser-illustration", "x-feed", "linkedin-feed", "product-banner"],
        "source_keys": ["clay", "focus-lab", "metalab", "koto", "designstudio"],
        "source_tags": {"enterprise", "premium", "brand", "saas", "ui"},
    },
    {
        "key": "approachable-startup-utility",
        "title": "Approachable startup utility",
        "summary": "Package the product like a modern startup tool: clear, fast, and friendly, with one obvious story and almost no decorative friction.",
        "signals": {
            "approachable", "clear", "curiosity", "easy", "explanatory", "friendly", "light", "simple", "startup",
            "understand", "utility", "fast", "launch", "clean",
        },
        "anti_signals": {"abstract", "confusing", "dense", "heavy", "technical"},
        "visual_cues": [
            "bright whitespace and one strong UI crop",
            "simple browser chrome or editorial frame",
            "minimal or no text overlays",
            "one obvious focal area that reads well on social and landing pages",
        ],
        "avoid": [
            "over-explaining with labels inside the image",
            "turning the app into a generic dashboard mockup",
            "extra decorative elements that compete with the real UI",
        ],
        "materials": ["browser-illustration", "x-feed", "x-card", "product-banner"],
        "source_keys": ["ramotion", "uitop", "stanvision", "parallel", "eleken"],
        "source_tags": {"saas", "clean", "product", "mockups", "ui"},
    },
    {
        "key": "editorial-trust-layer",
        "title": "Editorial trust layer",
        "summary": "Use a more premium editorial presentation so the product feels curated, intelligent, and taste-driven instead of purely functional.",
        "signals": {
            "curated", "editorial", "elegant", "intelligence", "knowledge", "premium", "quality", "taste",
            "trust", "refined", "library",
        },
        "anti_signals": {"chaotic", "loud", "meme", "overloaded"},
        "visual_cues": [
            "more whitespace than a normal SaaS promo card",
            "quiet brand field with refined browser or panel framing",
            "tight crop discipline and elegant type-safe negative space",
            "UI as the hero, with almost all supporting decoration removed",
        ],
        "avoid": [
            "decorative illustration that obscures the product",
            "overly playful color explosions",
            "copy-heavy marketing layouts inside the generated image",
        ],
        "materials": ["browser-illustration", "linkedin-feed", "og-card", "product-banner"],
        "source_keys": ["clay", "koto", "portorocha", "motto", "focus-lab"],
        "source_tags": {"premium", "brand", "illustration", "saas", "product"},
    },
    {
        "key": "living-agent-activity-system",
        "title": "Living agent activity system",
        "summary": "Emphasize that the product is alive with agents, automation, and real activity while staying legible and product-led.",
        "signals": {
            "agent", "agents", "automation", "dynamic", "flow", "live", "motion", "network", "orchestration",
            "real-time", "stream", "system", "activity", "active",
        },
        "anti_signals": {"casino", "glitch", "overwhelm", "sci-fi"},
        "visual_cues": [
            "layered but readable UI depth with one live activity region",
            "subtle sense of motion or throughput without distorting the interface",
            "strong hierarchy between the main product moment and supporting context",
            "clean light background so the activity feels energized but not chaotic",
        ],
        "avoid": [
            "fake futuristic HUD overlays",
            "glitch effects, neon streaks, or science-fiction control rooms",
            "rewriting the interface to look more animated than it is",
        ],
        "materials": ["browser-illustration", "x-feed", "feature-animation", "product-banner"],
        "source_keys": ["parallel", "stanvision", "blissful-studio", "ramotion", "lazarev"],
        "source_tags": {"ai", "product", "mockups", "illustration", "saas"},
    },
]


def tokenize(*parts: str) -> set[str]:
    tokens: set[str] = set()
    for part in parts:
        if not part:
            continue
        for word in WORD_RE.findall(part.lower()):
            if word in STOPWORDS:
                continue
            tokens.add(word)
    return tokens


def split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in re.split(r"[,\n]+", value) if item.strip()]


def load_profile(path: str | None) -> dict:
    if not path:
        return {}
    profile_path = Path(path).expanduser()
    if not profile_path.exists():
        raise SystemExit(f"Profile not found: {profile_path}")
    return json.loads(profile_path.read_text())


def load_sources() -> dict:
    return json.loads(SOURCE_DATA.read_text())


def sentence_join(items: list[str]) -> str:
    items = [item for item in items if item]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return ", ".join(items[:-1]) + f", and {items[-1]}"


def infer_materials(items: list[str]) -> list[str]:
    normalized = []
    seen = set()
    for item in items or []:
        low = item.strip().lower()
        if not low or low in seen:
            continue
        seen.add(low)
        normalized.append(low)
    return normalized or ["browser-illustration", "x-feed", "product-banner"]


def build_context(args, profile: dict) -> dict:
    tone_words = split_csv(args.tone) or profile.get("keywords", [])[:5]
    avoid_words = split_csv(args.avoid)
    materials = infer_materials(args.material)
    business = args.business or profile.get("description") or ""
    product_context = args.product_context or ""
    audience = args.audience or ""
    brand_name = args.brand_name or profile.get("brand_name") or "The brand"
    profile_colors = profile.get("color_candidates", [])[:4]
    profile_fonts = profile.get("font_candidates", [])[:3]
    tokens = tokenize(
        brand_name,
        business,
        audience,
        product_context,
        " ".join(tone_words),
        " ".join(profile.get("keywords", [])),
    )
    avoid_tokens = tokenize(" ".join(avoid_words))
    return {
        "brand_name": brand_name,
        "business": business,
        "audience": audience,
        "tone_words": tone_words,
        "avoid_words": avoid_words,
        "materials": materials,
        "product_context": product_context,
        "profile_colors": profile_colors,
        "profile_fonts": profile_fonts,
        "tokens": tokens,
        "avoid_tokens": avoid_tokens,
        "preferred_source_keys": sorted({item.strip() for item in (args.source or []) if item and item.strip()}),
    }


def score_direction(template: dict, context: dict) -> dict:
    signals = template["signals"]
    anti = template["anti_signals"]
    tokens = context["tokens"]
    avoid_tokens = context["avoid_tokens"]
    material_hits = set(context["materials"]) & set(template["materials"])
    matched = sorted(tokens & signals)
    blocked = sorted((tokens & anti) | (avoid_tokens & signals))
    score = 10 + (len(matched) * 7) + (len(material_hits) * 4) - (len(blocked) * 6)
    reasons = []
    if matched:
        reasons.append(f"Matches your brief around {sentence_join(matched[:4])}.")
    if material_hits:
        reasons.append(f"Fits the requested outputs: {sentence_join(sorted(material_hits))}.")
    reasons.append(template["summary"])
    if blocked:
        reasons.append(f"Watch-outs from your brief: {sentence_join(blocked[:3])}.")
    return {
        "score": score,
        "matched_signals": matched,
        "blocked_signals": blocked,
        "material_hits": sorted(material_hits),
        "reasons": reasons,
    }


def score_sources(template: dict, context: dict, data: dict, limit: int = 4) -> list[dict]:
    categories = {item["key"]: item["label"] for item in data["categories"]}
    preferred_source_keys = set(context.get("preferred_source_keys") or [])
    scored = []
    for source in data["sources"]:
        if preferred_source_keys and source["key"] not in preferred_source_keys:
            continue
        score = 0
        if source["key"] in template["source_keys"]:
            score += 12
        tag_hits = sorted(set(source.get("tags", [])) & set(template["source_tags"]))
        if tag_hits:
            score += len(tag_hits) * 3
        context_hits = sorted(set(source.get("tags", [])) & context["tokens"])
        if context_hits:
            score += len(context_hits) * 2
        if source["category"] == "saas-product-specialists":
            score += 2
        if score <= 0:
            continue
        why = []
        if source["key"] in template["source_keys"]:
            why.append("named fit")
        if tag_hits:
            why.append(f"tag overlap: {sentence_join(tag_hits[:3])}")
        if context_hits:
            why.append(f"brief overlap: {sentence_join(context_hits[:3])}")
        scored.append({
            "key": source["key"],
            "name": source["name"],
            "url": source["url"],
            "category": source["category"],
            "category_label": categories.get(source["category"], source["category"]),
            "notes": source["notes"],
            "tags": source.get("tags", []),
            "score": score,
            "why": "; ".join(why) or "fit by category",
        })
    scored.sort(key=lambda item: (-item["score"], item["name"]))
    return scored[:limit]


def general_prompt_prefix(context: dict, direction: dict) -> str:
    tone = sentence_join(context["tone_words"][:5]) or "clear, modern, and trustworthy"
    colors = sentence_join(context["profile_colors"][:3])
    fonts = sentence_join(context["profile_fonts"][:2])
    extras = []
    if colors:
        extras.append(f"stay compatible with the current palette cues such as {colors}")
    if fonts:
        extras.append(f"respect typography cues like {fonts}")
    extra = ""
    if extras:
        extra = " Also " + " and ".join(extras) + "."
    return (
        f"Present {context['brand_name']} through the '{direction['title']}' direction. "
        f"It should feel {tone}.{extra}"
    )


def build_prompt_seed(context: dict, direction: dict, material: str) -> str:
    base = general_prompt_prefix(context, direction)
    cues = sentence_join(direction["visual_cues"][:3])
    avoid = sentence_join(direction["avoid"][:3])
    business = context["business"] or f"{context['brand_name']} is a modern digital product."
    product_context = context["product_context"] or "Use the strongest approved product screenshot as the central visual asset."

    if material == "browser-illustration":
        return (
            f"Use the real {context['brand_name']} product screenshot as product truth. Do not redesign the UI. "
            f"{base} Frame the UI inside a refined browser or editorial presentation. "
            f"Borrow only presentation cues from the external references: {cues}. "
            f"Emphasize this product story: {business}. Focus on {product_context}. "
            f"Keep the composition airy, launch-ready, and minimally decorated. Avoid {avoid}."
        )
    if material in {"x-feed", "x-card", "linkedin-feed", "linkedin-card", "og-card"}:
        return (
            f"Use the real {context['brand_name']} product screenshot as the hero asset. Do not redesign the UI. "
            f"{base} Reframe it for a {material} composition with safe margins, a tighter focal crop, and mobile readability. "
            f"Borrow only presentation cues from the external references: {cues}. "
            f"Keep minimal or no text overlays and avoid {avoid}."
        )
    if material == "product-banner":
        return (
            f"Use the real {context['brand_name']} screenshot as the hero asset for a product banner. Do not redesign the UI. "
            f"{base} Package one clear product story with {cues}. "
            f"Use negative space for headline-safe composition and avoid {avoid}."
        )
    return (
        f"Create a {material} for {context['brand_name']} using the '{direction['title']}' direction. "
        f"{base} Borrow these cues from the references: {cues}. Avoid {avoid}."
    )


def build_direction(template: dict, context: dict, data: dict) -> dict:
    meta = score_direction(template, context)
    sources = score_sources(template, context, data)
    prompt_seeds = {material: build_prompt_seed(context, template, material) for material in context["materials"]}
    example_sites = [item["key"] for item in sources[:3]]
    capture_cmd = ""
    if example_sites:
        capture_cmd = "python3 mcp/brand_iterate.py collect-examples " + " ".join(f"--site {site}" for site in example_sites)
    return {
        "key": template["key"],
        "title": template["title"],
        "summary": template["summary"],
        "score": meta["score"],
        "matched_signals": meta["matched_signals"],
        "blocked_signals": meta["blocked_signals"],
        "material_hits": meta["material_hits"],
        "reasons": meta["reasons"],
        "visual_cues": template["visual_cues"],
        "avoid": template["avoid"],
        "recommended_materials": template["materials"],
        "sources": sources,
        "capture_command": capture_cmd,
        "prompt_seeds": prompt_seeds,
    }


def render_markdown(context: dict, directions: list[dict]) -> str:
    top = directions[0]
    secondary = directions[1] if len(directions) > 1 else None
    lines = [
        f"# {context['brand_name']} concept directions",
        "",
        "## Brand snapshot",
        f"- Brand: {context['brand_name']}",
        f"- Business: {context['business'] or 'n/a'}",
        f"- Audience: {context['audience'] or 'n/a'}",
        f"- Tone: {sentence_join(context['tone_words']) or 'n/a'}",
        f"- Avoid: {sentence_join(context['avoid_words']) or 'n/a'}",
        f"- Product context: {context['product_context'] or 'n/a'}",
        f"- Target materials: {sentence_join(context['materials'])}",
        "",
        "## Recommended path",
        f"- Primary direction: **{top['title']}**",
    ]
    if secondary:
        lines.append(f"- Borrow presentation discipline from: **{secondary['title']}**")
    lines += [
        f"- Why: {top['summary']}",
        f"- Best first materials: {sentence_join(top['material_hits'] or context['materials'][:2])}",
        "",
    ]

    for idx, direction in enumerate(directions, start=1):
        lines += [
            f"## {idx}. {direction['title']}",
            "",
            f"**Score:** {direction['score']}",
            "",
            f"**Why it fits:** {sentence_join(direction['reasons'])}",
            "",
            "**Visual cues**",
        ]
        for cue in direction["visual_cues"]:
            lines.append(f"- {cue}")
        lines += ["", "**Avoid**"]
        for item in direction["avoid"]:
            lines.append(f"- {item}")
        if direction["sources"]:
            lines += ["", "**Suggested example sources**"]
            for source in direction["sources"]:
                lines.append(f"- `{source['key']}` — {source['name']} ({source['url']}) — {source['why']}")
        if direction["capture_command"]:
            lines += ["", "**Capture command**", "```bash", direction["capture_command"], "```"]
        lines += ["", "**Prompt seeds**"]
        for material, prompt in direction["prompt_seeds"].items():
            lines += [f"- `{material}`", "```text", prompt, "```"]
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def json_ready_context(context: dict) -> dict:
    payload = dict(context)
    payload["tokens"] = sorted(context.get("tokens", []))
    payload["avoid_tokens"] = sorted(context.get("avoid_tokens", []))
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Suggest exploratory brand concept directions")
    parser.add_argument("--profile", help="Optional brand-profile.json path")
    parser.add_argument("--brand-name", help="Explicit brand name")
    parser.add_argument("--business", help="Business or product summary")
    parser.add_argument("--audience", help="Target audience summary")
    parser.add_argument("--tone", help="Comma-separated tone words")
    parser.add_argument("--avoid", help="Comma-separated anti-patterns or avoid words")
    parser.add_argument("--product-context", help="Where the product truth comes from or which surfaces matter")
    parser.add_argument("--material", action="append", help="Target material type; repeat as needed")
    parser.add_argument("--source", action="append", help="Preferred curated source key to constrain suggested example sources; repeat as needed")
    parser.add_argument("--top", type=int, default=4, help="How many directions to include")
    parser.add_argument("--output", required=True, help="Markdown output path")
    parser.add_argument("--output-json", help="Optional JSON output path")
    args = parser.parse_args()

    profile = load_profile(args.profile)
    data = load_sources()
    context = build_context(args, profile)
    directions = [build_direction(template, context, data) for template in DIRECTION_TEMPLATES]
    directions.sort(key=lambda item: (-item["score"], item["title"]))
    directions = directions[: max(1, args.top)]

    output = Path(args.output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_markdown(context, directions))

    if args.output_json:
        output_json = Path(args.output_json).expanduser().resolve()
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps({"context": json_ready_context(context), "directions": directions}, indent=2) + "\n")

    print(f"Brand concept directions: {output}")
    if args.output_json:
        print(f"Brand concept directions JSON: {Path(args.output_json).expanduser().resolve()}")
    print(f"Recommended direction: {directions[0]['title']}")
    if directions[0]["sources"]:
        print("Suggested sources: " + ", ".join(item["key"] for item in directions[0]["sources"][:3]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
