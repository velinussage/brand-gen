"""Sage Protocol card data plugin.

Fetches structured page data from Sage Protocol APIs (IPFS-backed
prompts, skills, libraries, communities, and profiles).
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote, urlencode, urlparse

from . import CardDataPlugin
from ..card_text import (
    _clean_sage_title,
    _extract_prompt_share_blocks,
    _extract_skill_share_blocks,
    _fetch_json_url,
    _fetch_page_text,
    _humanize_key,
    _is_page_chrome_line,
    _markdown_doc_to_page,
    _short_detail_copy,
)


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def _looks_like_cid(value: str) -> bool:
    return bool(re.fullmatch(r"baf[a-z0-9]+", (value or "").strip().lower()))


def _looks_like_eth_address(value: str) -> bool:
    return bool(re.fullmatch(r"0x[a-fA-F0-9]{40}", str(value or "").strip()))


def _short_address(value: str) -> str:
    raw = str(value or "").strip()
    if len(raw) <= 12:
        return raw
    return f"{raw[:6]}...{raw[-4:]}"


def _looks_like_short_address(value: str) -> bool:
    return bool(re.fullmatch(r"0x[a-fA-F0-9]{4,}\.\.\.[a-fA-F0-9]{4}", str(value or "").strip()))


def _try_sage_local_skill(key: str) -> dict[str, Any] | None:
    """Read a locally installed Sage skill's SKILL.md for real content."""
    import glob as glob_mod
    home = Path.home()
    patterns = [
        str(home / ".local/share/sage/skills/versions" / key / "*/SKILL.md"),
        str(home / ".claude/plugins/marketplaces/sage-marketplace/plugins" / key / "SKILL.md"),
    ]
    skill_md = ""
    for pattern in patterns:
        matches = sorted(glob_mod.glob(pattern))
        if matches:
            try:
                skill_md = Path(matches[-1]).read_text(encoding="utf-8")
                break
            except Exception:
                continue
    if not skill_md:
        return None
    lines = skill_md.split("\n")
    name = _humanize_key(key)
    description = ""
    body_start = 0
    if lines and lines[0].strip() == "---":
        for i, line in enumerate(lines[1:], 1):
            if line.strip() == "---":
                body_start = i + 1
                break
            if line.startswith("name:"):
                name = line.split(":", 1)[1].strip() or name
            elif line.startswith("description:"):
                description = line.split(":", 1)[1].strip()
    body = "\n".join(lines[body_start:]).strip()
    return {"name": name, "description": description, "content": body}


def _find_skill_entry(manifest: Any, key: str) -> dict[str, Any] | None:
    if not isinstance(manifest, dict):
        return None
    candidates: list[Any] = []
    for container_key in ("prompts", "skills"):
        values = manifest.get(container_key)
        if isinstance(values, list):
            candidates.extend(values)
    library = manifest.get("library")
    if isinstance(library, dict):
        for container_key in ("prompts", "skills"):
            values = library.get(container_key)
            if isinstance(values, list):
                candidates.extend(values)
    metadata = manifest.get("metadata")
    if isinstance(metadata, dict):
        values = metadata.get("prompts")
        if isinstance(values, list):
            candidates.extend(values)
    wanted = str(key or "").strip()
    for item in candidates:
        if not isinstance(item, dict):
            continue
        item_key = str(item.get("id") or item.get("key") or "").strip()
        if item_key == wanted:
            return item
    return None


def _search_sage_worker(key: str, entity_type: str = "skill") -> dict[str, Any] | None:
    """Search the Sage worker API for a skill/prompt by name and return IPFS content."""
    source = "https://api.sageprotocol.io"
    search_params = urlencode({"q": key, "type": entity_type, "limit": 5})
    results_payload = _fetch_json_url(f"{source}/prompts/search?{search_params}")
    results = results_payload.get("results") if isinstance(results_payload, dict) else []
    if not isinstance(results, list) or not results:
        return None
    norm_key = key.lower().replace(".md", "").replace("_", "-").replace(" ", "-")
    match = None
    for r in results:
        if not isinstance(r, dict):
            continue
        candidate = str(r.get("name") or r.get("key") or "").lower().replace(".md", "").replace("_", "-").replace(" ", "-")
        if candidate == norm_key:
            match = r
            break
    if not match:
        match = results[0] if isinstance(results[0], dict) else None
    if not match:
        return None
    cid = str(match.get("cid") or "").strip()
    if not cid:
        return None
    ipfs_data = _fetch_json_url(f"{source}/ipfs/content/{quote(cid)}")
    content = ""
    if isinstance(ipfs_data, dict):
        raw = ipfs_data.get("content")
        if isinstance(raw, str):
            content = raw
    return {
        "cid": cid,
        "name": str(match.get("name") or key),
        "description": str(match.get("description") or ""),
        "content": content,
        "tags": match.get("tags") if isinstance(match.get("tags"), list) else [],
        "library_name": str(match.get("libraryName") or ""),
        "author": str(match.get("author") or ""),
    }


# ---------------------------------------------------------------------------
# Entity fetchers
# ---------------------------------------------------------------------------

def _fetch_sage_prompt_page(url: str) -> dict[str, Any] | None:
    parsed = urlparse(url)
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 2 or parts[0] != "prompts":
        return None
    source = "https://api.sageprotocol.io"
    prompt_payload: dict[str, Any] | None = None
    cid = ""
    content = ""
    title_hint = ""
    description_hint = ""

    if len(parts) == 2 and _looks_like_cid(parts[1]):
        cid = parts[1]
        prompt_payload = _fetch_json_url(f"{source}/prompts/{quote(cid)}")
    elif len(parts) >= 3:
        subdao = unquote(parts[1])
        key = unquote(parts[2])
        prompt_payload = _fetch_json_url(f"{source}/prompts/{quote(subdao)}/{quote(key)}")
    elif len(parts) == 2 and not _looks_like_cid(parts[1]):
        key = unquote(parts[1])
        worker_result = _search_sage_worker(key, entity_type="skill")
        if worker_result:
            cid = worker_result.get("cid") or ""
            content = worker_result.get("content") or ""
            title_hint = worker_result.get("name") or _humanize_key(key)
            description_hint = worker_result.get("description") or ""

    prompt = prompt_payload.get("prompt") if isinstance(prompt_payload, dict) and isinstance(prompt_payload.get("prompt"), dict) else (prompt_payload if isinstance(prompt_payload, dict) else {})
    if not isinstance(prompt, dict):
        prompt = {}
    cid = str(prompt.get("cid") or cid or "").strip()
    if not content:
        content = str(prompt.get("content") or "").strip()
    if not content and cid:
        envelope = _fetch_json_url(f"{source}/ipfs/content/{quote(cid)}")
        if isinstance(envelope, dict):
            inner = envelope.get("content")
            if isinstance(inner, str):
                content = inner
    title_hint = title_hint or str(prompt.get("name") or prompt.get("title") or "")
    description_hint = description_hint or str(prompt.get("description") or "")
    page = _markdown_doc_to_page(
        url=url,
        title_hint=title_hint,
        description_hint=description_hint,
        content=content,
    )
    prompt_share = _extract_prompt_share_blocks(
        content=content,
        description=str(page.get("description") or description_hint).strip(),
    )
    page["share_card"] = {
        "headline": str(page.get("h1") or page.get("title") or title_hint or "").strip(),
        "subhead": str(page.get("description") or description_hint or "").strip(),
        "proof_title": "",
        "proof_meta": [],
        "proof_excerpt": prompt_share.get("proof_excerpt") or str(page.get("description") or "").strip(),
        "proof_row": prompt_share.get("proof_row") or "",
        "detail_label": "Prompt structure",
        "cta": "Open prompt",
        "detail_blocks": prompt_share.get("detail_blocks") or [],
    }
    if cid:
        page["cid"] = cid
    page["source_kind"] = "sage-ipfs"
    return page if any(page.get(key) for key in ("title", "description", "lines")) else None


def _fetch_sage_skill_page(url: str) -> dict[str, Any] | None:
    parsed = urlparse(url)
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 2 or parts[0] != "skills":
        return None
    decoded = unquote(parts[1])
    source = "https://api.sageprotocol.io"
    cid = ""
    key = decoded.split(":", 1)[-1] if ":" in decoded else decoded
    content = ""
    description_hint = ""
    title_hint = _humanize_key(key)

    if ":" in decoded:
        subdao, key = decoded.split(":", 1)
        query = urlencode({"subdao": subdao, "key": key, "first": 5})
        lookup = _fetch_json_url(f"https://app.sageprotocol.io/api/subgraph/prompts-by-key?{query}")
        items = lookup.get("items") if isinstance(lookup, dict) and isinstance(lookup.get("items"), list) else []
        if items:
            newest = sorted(
                [item for item in items if isinstance(item, dict)],
                key=lambda item: int(item.get("ts") or 0),
                reverse=True,
            )
            cid = str((newest[0] or {}).get("cid") or "").strip() if newest else ""

    if not cid:
        worker_result = _search_sage_worker(key, entity_type="skill")
        if worker_result:
            cid = worker_result.get("cid") or ""
            content = worker_result.get("content") or ""
            title_hint = worker_result.get("name") or title_hint
            description_hint = worker_result.get("description") or ""

    if cid and not content:
        ipfs_data = _fetch_json_url(f"{source}/ipfs/content/{quote(cid)}")
        if isinstance(ipfs_data, dict):
            raw = ipfs_data.get("content")
            if isinstance(raw, str):
                content = raw

    if not content:
        local = _try_sage_local_skill(key)
        if local and local.get("content"):
            content = local["content"]
            title_hint = local.get("name") or title_hint
            description_hint = local.get("description") or description_hint

    if not content:
        page = _fetch_page_text(url)
        page["source_kind"] = "sage-page"
        human_name = _humanize_key(key)
        if human_name and page.get("title", "").endswith("Sage Protocol"):
            page["title"] = human_name
            page["h1"] = human_name
        skill_share = _extract_skill_share_blocks(page.get("lines") or [], page.get("description") or "")
        page["share_card"] = {
            "headline": human_name or str(page.get("title") or "").strip(),
            "subhead": str(page.get("description") or "").strip(),
            "proof_title": "",
            "proof_meta": skill_share.get("proof_meta") or [],
            "proof_excerpt": skill_share.get("proof_excerpt") or str(page.get("description") or "").strip(),
            "proof_row": skill_share.get("proof_row") or "",
            "detail_label": "Skill snapshot",
            "cta": "Open skill",
            "detail_blocks": skill_share.get("detail_blocks") or [],
        }
        return page if any(page.get(k) for k in ("title", "description", "lines")) else None

    page = _markdown_doc_to_page(url=url, title_hint=title_hint, description_hint=description_hint, content=content)
    skill_share = _extract_skill_share_blocks(
        page.get("lines") or [],
        str(page.get("description") or description_hint).strip(),
    )
    page["share_card"] = {
        "headline": str(page.get("h1") or page.get("title") or title_hint).strip(),
        "subhead": str(page.get("description") or description_hint).strip(),
        "proof_title": "",
        "proof_meta": skill_share.get("proof_meta") or [],
        "proof_excerpt": skill_share.get("proof_excerpt") or str(page.get("description") or "").strip(),
        "proof_row": skill_share.get("proof_row") or "",
        "detail_label": "Skill coverage",
        "cta": "Open skill",
        "detail_blocks": skill_share.get("detail_blocks") or [],
    }
    if cid:
        page["cid"] = cid
    page["source_kind"] = "sage-ipfs" if cid else "sage-local"
    return page if any(page.get(k) for k in ("title", "description", "lines")) else None


def _fetch_sage_profile_page(url: str) -> dict[str, Any] | None:
    parsed = urlparse(url)
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 2 or parts[0] != "u":
        return None
    handle = unquote(parts[1]).strip()
    source = "https://api.sageprotocol.io"
    address = handle if _looks_like_eth_address(handle) else ""
    if not address:
        resolved = _fetch_json_url(f"{source}/handle/resolve/{quote(handle)}")
        if isinstance(resolved, dict):
            address = str(resolved.get("address") or "").strip()
    reverse = _fetch_json_url(f"{source}/handle/reverse/{quote(address or handle)}")
    profile = _fetch_json_url(f"https://app.sageprotocol.io/api/profile/{quote(address or handle)}")
    page = _fetch_page_text(url)
    profile_payload = profile.get("profile") if isinstance(profile, dict) and isinstance(profile.get("profile"), dict) else {}
    display_name = (
        str((reverse or {}).get("handle") or "").strip()
        or str((reverse or {}).get("ensName") or "").strip()
        or str((reverse or {}).get("username") or "").strip()
        or _short_address(str((reverse or {}).get("address") or address or handle))
    )
    headline_name = display_name if not (_looks_like_eth_address(display_name) or _looks_like_short_address(display_name)) else "Creator on Sage"
    bio = str((profile_payload or {}).get("bio") or "").strip()
    summary = bio or "Public creator profile on Sage with published demos and contribution history."
    tip_state = next(
        (
            line
            for line in list(page.get("lines") or [])
            if "no tips" in str(line or "").lower() or "tips indexed" in str(line or "").lower()
        ),
        "Tips indexed from the subgraph.",
    )
    lines = []
    for candidate in [
        summary,
        "Capability demos",
        "Tips received",
        "Browse creator demos",
    ] + list(page.get("lines") or []):
        text = str(candidate or "").strip()
        if text and text not in lines:
            lines.append(text)
    share_card = {
        "headline": headline_name,
        "subhead": f"{display_name} · {summary}" if headline_name != display_name else summary,
        "proof_title": "Creator profile",
        "proof_meta": ["Public profile", "Capability demos", "Tips received"],
        "proof_excerpt": "Examples this creator has published to show what their Sage workflows produce in practice.",
        "proof_row": "Public profile · Browse creator demos · Tips indexed from the subgraph",
        "cta": "Open profile",
        "detail_label": "Creator profile",
        "detail_blocks": [
            {"label": "Identity", "body": display_name or _short_address(handle)},
            {"label": "Address", "body": _short_address(str((reverse or {}).get("address") or address or handle))},
            {"label": "Demos", "body": "Published capability demos available from the public profile."},
            {"label": "Tips", "body": _short_detail_copy(tip_state, max_chars=90) or "Tips indexed from the subgraph."},
            {"label": "Profile", "body": "Public creator profile and contribution history on Sage."},
        ],
    }
    return {
        "url": url,
        "title": display_name or _short_address(handle),
        "description": summary,
        "h1": display_name or _short_address(handle),
        "h2": "Public profile",
        "lines": lines[:40],
        "source_kind": "sage-profile",
        "share_card": share_card,
    }


def _fetch_sage_community_page(url: str) -> dict[str, Any] | None:
    parsed = urlparse(url)
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 2 or parts[0] != "c":
        return None
    community_id = unquote(parts[1]).strip()
    source = "https://api.sageprotocol.io"
    subdao_payload = _fetch_json_url(f"{source}/subdaos?ids={quote(community_id)}")
    stats_payload = _fetch_json_url(f"{source}/communities/{quote(community_id)}/stats")
    page = _fetch_page_text(url)
    subdao = {}
    if isinstance(subdao_payload, dict):
        by_id = subdao_payload.get("subdaosById")
        if isinstance(by_id, dict):
            subdao = by_id.get(community_id) or {}
        if not subdao and isinstance(subdao_payload.get("subdaos"), list):
            subdao = next((item for item in subdao_payload.get("subdaos") or [] if isinstance(item, dict)), {}) or {}
    stats = stats_payload if isinstance(stats_payload, dict) else {}
    name = str(subdao.get("name") or "").strip() or f"DAO {_short_address(community_id)}"
    description = str(subdao.get("description") or "").strip() or "A decentralized community on Sage Protocol."
    member_count = int(stats.get("memberCount") or 0)
    skill_count = int(stats.get("skillCount") or stats.get("skills") or 0)
    prompt_count = int(stats.get("promptCount") or stats.get("prompts") or 0)
    stream_count = int(stats.get("streamCount") or stats.get("streams") or 0)
    governance_note = "Shared prompt and skill libraries with proposal, voting, and execution rules."
    lines = []
    for candidate in [
        description,
        f"Members - {member_count}",
        f"Skills - {skill_count}",
        f"Prompts - {prompt_count}",
        f"Streams - {stream_count}",
        "Open library",
        "Governance",
    ] + list(page.get("lines") or []):
        text = str(candidate or "").strip()
        if text and text not in lines:
            lines.append(text)
    share_card = {
        "headline": name,
        "subhead": description,
        "proof_title": "Community snapshot",
        "proof_meta": [
            f"{member_count} members",
            f"{skill_count} skills",
            f"{stream_count or 1} stream",
        ],
        "proof_excerpt": description,
        "proof_row": f"Open library · {prompt_count} prompts · Governance context on Sage",
        "cta": "View community",
        "detail_label": "Community snapshot",
        "detail_blocks": [
            {"label": "Members", "value": str(member_count), "body": "Current member count"},
            {"label": "Skills", "value": str(skill_count), "body": "Reusable skills in scope"},
            {"label": "Prompts", "value": str(prompt_count), "body": "Standalone prompts governed here"},
            {"label": "Streams", "value": str(stream_count), "body": "Active distribution streams"},
            {"label": "Governance", "body": governance_note},
        ],
    }
    return {
        "url": url,
        "title": name,
        "description": description,
        "h1": name,
        "h2": "Community snapshot",
        "lines": lines[:40],
        "source_kind": "sage-community",
        "share_card": share_card,
    }


def _fetch_sage_library_page(url: str) -> dict[str, Any] | None:
    parsed = urlparse(url)
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 2 or parts[0] != "library":
        return None
    library_id = unquote(parts[1]).strip()
    source = "https://api.sageprotocol.io"
    libraries_payload = _fetch_json_url(f"{source}/libraries?address={quote(library_id)}&limit=5")
    page = _fetch_page_text(url)
    libraries = libraries_payload.get("libraries") if isinstance(libraries_payload, dict) and isinstance(libraries_payload.get("libraries"), list) else []
    library = next((item for item in libraries if isinstance(item, dict)), {}) if libraries else {}
    name = str(library.get("name") or "").strip() or str(page.get("title") or "").strip() or "Library"
    description = str(library.get("description") or "").strip() or str(page.get("description") or "").strip() or "Governed library on Sage Protocol."
    prompt_count = int(library.get("promptCount") or 0)
    skill_enabled = bool(library.get("skillEnabled"))
    manifest_items = "skills" if skill_enabled else "items"
    featured: list[str] = []
    featured_cards: list[dict[str, str]] = []
    manifest_cid = str(library.get("manifestCid") or library.get("manifestCID") or "").strip()
    manifest = _fetch_json_url(f"{source}/ipfs/content/{quote(manifest_cid)}") if manifest_cid else None
    import json
    manifest_obj: Any = manifest
    if isinstance(manifest, dict):
        content = manifest.get("content")
        if isinstance(content, dict):
            manifest_obj = content
        elif isinstance(content, str):
            try:
                manifest_obj = json.loads(content)
            except json.JSONDecodeError:
                manifest_obj = manifest
    if isinstance(manifest_obj, dict):
        entries: list[dict[str, Any]] = []
        for key in ("skills", "prompts"):
            value = manifest_obj.get(key)
            if isinstance(value, list):
                entries.extend(item for item in value if isinstance(item, dict))
        nested = manifest_obj.get("library")
        if isinstance(nested, dict):
            for key in ("skills", "prompts"):
                value = nested.get(key)
                if isinstance(value, list):
                    entries.extend(item for item in value if isinstance(item, dict))
        for entry in entries:
            candidate = str(entry.get("name") or entry.get("title") or "").strip()
            if candidate and candidate not in featured:
                featured.append(candidate)
                featured_cards.append(
                    {
                        "label": candidate,
                        "body": _short_detail_copy(str(entry.get("description") or "").strip(), max_chars=84),
                    }
                )
            if len(featured) >= 3:
                break
    for line in list(page.get("lines") or []):
        text = str(line or "").strip()
        if (
            not text
            or _is_page_chrome_line(text)
            or text.lower().startswith(("browse the current governed contents", "all items", "included in current manifest", "open skill", "open prompt"))
        ):
            continue
        if text.startswith("#") or len(text) > 36:
            continue
        if text.lower() in {"home", "discover", "communities", "my library"}:
            continue
        if text not in featured:
            featured.append(text)
        if len(featured) >= 3:
            break
    featured_row = f"Featured: {', '.join(featured)}" if featured else "Included in current manifest"
    lines = []
    for candidate in [
        description,
        f"{prompt_count} reusable {manifest_items}",
        featured_row,
    ] + list(page.get("lines") or []):
        text = str(candidate or "").strip()
        if text and text not in lines:
            lines.append(text)
    share_card = {
        "headline": name,
        "subhead": description,
        "proof_title": "Library snapshot",
        "proof_meta": [
            f"{prompt_count} {manifest_items}",
            "Governed library",
            "Current manifest",
        ],
        "proof_excerpt": f"{prompt_count} reusable {manifest_items} currently ship in the governed manifest for this library.",
        "proof_row": f"Manifest CID · {manifest_cid[:14]}… · Featured items pulled from the current manifest" if manifest_cid else featured_row,
        "cta": "Open library",
        "detail_label": "Current library",
        "detail_blocks": [
            {"label": "Current manifest", "value": str(prompt_count), "body": f"Reusable {manifest_items} in the current version"},
            *[
                {
                    "label": card.get("label") or "Entry",
                    "body": str(card.get("body") or "Included in the current governed manifest.").strip(),
                }
                for card in featured_cards[:3]
            ],
        ],
    }
    return {
        "url": url,
        "title": name,
        "description": description,
        "h1": name,
        "h2": "Library snapshot",
        "lines": lines[:40],
        "source_kind": "sage-library",
        "share_card": share_card,
    }


# ---------------------------------------------------------------------------
# Plugin class
# ---------------------------------------------------------------------------

class SageCardPlugin(CardDataPlugin):
    """Sage Protocol data fetching plugin (priority 10)."""

    priority = 10

    @property
    def name(self) -> str:
        return "sage"

    def can_handle(self, url: str, entity_type: str) -> bool:
        host = urlparse(url).netloc.lower()
        return "sageprotocol.io" in host

    def fetch_page_data(self, url: str, entity_type: str) -> dict[str, Any] | None:
        if entity_type == "prompt":
            return _fetch_sage_prompt_page(url)
        if entity_type == "skill":
            return _fetch_sage_skill_page(url)
        if entity_type == "library":
            return _fetch_sage_library_page(url)
        if entity_type in {"community", "dao"}:
            return _fetch_sage_community_page(url)
        if entity_type == "profile":
            return _fetch_sage_profile_page(url)
        return None
