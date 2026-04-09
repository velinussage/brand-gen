"""Card text analysis, HTTP utilities, and line scoring.

Leaf module — no internal ``mcp/`` dependencies.  Used by both card
plugins and the card builder to normalise, score and select text for
share-card rendering.
"""
from __future__ import annotations

import html
import json
import re
import urllib.error
import urllib.request
from html.parser import HTMLParser
from typing import Any
from urllib.parse import quote, unquote


# ---------------------------------------------------------------------------
# HTML visible-text parser
# ---------------------------------------------------------------------------

class _VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._stack: list[str] = []
        self._skip_depth = 0
        self.title = ""
        self.h1 = ""
        self.h2 = ""
        self.lines: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        t = tag.lower()
        self._stack.append(t)
        if t in {"script", "style", "noscript", "svg"}:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        t = tag.lower()
        if t in {"script", "style", "noscript", "svg"} and self._skip_depth:
            self._skip_depth -= 1
        if self._stack:
            self._stack.pop()

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        text = re.sub(r"\s+", " ", data or "").strip()
        if not text:
            return
        current = self._stack[-1] if self._stack else ""
        if current == "title" and not self.title:
            self.title = text
        elif current == "h1" and not self.h1:
            self.h1 = text
        elif current == "h2" and not self.h2:
            self.h2 = text
        if 2 <= len(text) <= 220 and text not in self.lines:
            self.lines.append(text)


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _extract_meta(html_text: str, key: str, *, prop: bool = False) -> str:
    attr = "property" if prop else "name"
    pattern = re.compile(rf'<meta[^>]+{attr}=["\']{re.escape(key)}["\'][^>]+content=["\']([^"\']+)["\']', re.I)
    match = pattern.search(html_text)
    return html.unescape(match.group(1).strip()) if match else ""


def _fetch_json_url(url: str, *, timeout: int = 25) -> dict[str, Any] | list[Any] | None:
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "brand-gen/1.0", "Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError):
        return None


def _fetch_page_text(url: str) -> dict[str, Any]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "brand-gen/1.0"})
        with urllib.request.urlopen(req, timeout=25) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, TimeoutError) as exc:
        return {"url": url, "error": str(exc), "title": "", "description": "", "h1": "", "h2": "", "lines": []}
    parser = _VisibleTextParser()
    parser.feed(raw)
    return {
        "url": url,
        "title": _extract_meta(raw, "og:title", prop=True) or parser.title,
        "description": _extract_meta(raw, "og:description", prop=True) or _extract_meta(raw, "description") or "",
        "h1": parser.h1,
        "h2": parser.h2,
        "lines": parser.lines[:40],
    }


# ---------------------------------------------------------------------------
# Text normalisation
# ---------------------------------------------------------------------------

def _humanize_key(key: str) -> str:
    """Turn a URL slug like 'solidity-auditor' into 'Solidity Auditor'."""
    return " ".join(w.capitalize() for w in re.split(r"[-_]+", key.strip())) if key else ""


def _clean_sage_title(text: str) -> str:
    raw = str(text or "").strip()
    if not raw:
        return ""
    cleaned = re.sub(r"\.(md|txt|markdown)$", "", raw, flags=re.I)
    cleaned = cleaned.replace("_", " ").strip()
    return cleaned


def _normalize_content_text(text: str) -> str:
    output = str(text or "")
    if not output:
        return ""
    output = output.replace("\r\n", "\n")
    if output.startswith('"') and output.endswith('"'):
        try:
            parsed = json.loads(output)
            if isinstance(parsed, str):
                output = parsed
        except json.JSONDecodeError:
            pass
    if "\\n" in output:
        output = output.replace("\\n", "\n")
    if "\\t" in output:
        output = output.replace("\\t", "\t")
    return output.strip()


def _strip_leading_frontmatter(text: str) -> str:
    output = str(text or "")
    if not output.startswith("---"):
        return output
    parts = output.splitlines()
    if not parts or parts[0].strip() != "---":
        return output
    for idx in range(1, min(len(parts), 80)):
        if parts[idx].strip() == "---":
            return "\n".join(parts[idx + 1 :]).lstrip()
    return output


def _clean_markdown_line(text: str) -> str:
    cleaned = str(text or "")
    if not cleaned:
        return ""
    cleaned = re.sub(r"^\s*\[[ xX]\]\s*", "", cleaned)
    cleaned = re.sub(r"^\s*[-*+]\s*\[[ xX]\]\s*", "", cleaned)
    cleaned = cleaned.replace("`", "")
    cleaned = cleaned.replace("**", "").replace("__", "")
    cleaned = re.sub(r"(?<!\w)[*_](?!\w)", "", cleaned)
    cleaned = re.sub(r"\[(.*?)\]\((.*?)\)", r"\1", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _strip_markdown_code_fences(text: str) -> str:
    output_lines: list[str] = []
    in_fence = False
    for raw_line in str(text or "").splitlines():
        if raw_line.strip().startswith("```"):
            in_fence = not in_fence
            continue
        if not in_fence:
            output_lines.append(raw_line)
    return "\n".join(output_lines)


def _extract_markdown_sections(text: str) -> dict[str, list[str]]:
    content = _strip_markdown_code_fences(_strip_leading_frontmatter(text))
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for raw_line in content.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue
        heading_match = re.match(r"^(#{2,6})\s+(.*)$", stripped)
        if heading_match:
            heading = _clean_markdown_line(heading_match.group(2)).strip(" -")
            current = heading
            sections.setdefault(current, [])
            continue
        if current is None:
            continue
        line = _clean_markdown_line(stripped)
        if not line or _is_page_chrome_line(line):
            continue
        bullet_match = re.match(r"^(?:[-*+]\s+|\d+\.\s+)(.*)$", stripped)
        if bullet_match:
            line = _clean_markdown_line(bullet_match.group(1))
        if line:
            sections.setdefault(current, []).append(line)
    return sections


# ---------------------------------------------------------------------------
# Markdown → page dict
# ---------------------------------------------------------------------------

def _markdown_doc_to_page(
    *,
    url: str,
    title_hint: str = "",
    description_hint: str = "",
    content: str = "",
) -> dict[str, Any]:
    text = _strip_leading_frontmatter(_normalize_content_text(content))
    lines: list[str] = []
    fallback_title = _clean_sage_title(title_hint)
    h1 = ""
    h2 = ""
    description = str(description_hint or "").strip()
    if not text:
        return {
            "url": url,
            "title": h1 or description or "",
            "description": description,
            "h1": h1,
            "h2": h2,
            "lines": lines,
        }

    code_fence = False
    skip_section = False
    skip_headers = {"prerequisites", "installation", "install", "requirements"}
    paragraph_buffer: list[str] = []

    def flush_paragraph() -> None:
        nonlocal description
        if not paragraph_buffer:
            return
        paragraph = _clean_markdown_line(" ".join(paragraph_buffer))
        paragraph_buffer.clear()
        if not paragraph or _is_page_chrome_line(paragraph) or _is_procedural_line(paragraph):
            return
        if not description and len(paragraph) >= 24:
            description = paragraph
            return
        if paragraph not in lines and 16 <= len(paragraph) <= 180:
            lines.append(paragraph)

    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if stripped.startswith("```"):
            flush_paragraph()
            code_fence = not code_fence
            continue
        if code_fence:
            continue
        if not stripped:
            flush_paragraph()
            continue

        heading_match = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if heading_match:
            flush_paragraph()
            level = len(heading_match.group(1))
            heading = _clean_markdown_line(heading_match.group(2)).strip(" -")
            heading_clean = _clean_sage_title(heading)
            heading_key = heading_clean.lower()
            skip_section = heading_key in skip_headers
            if level == 1 and heading_clean:
                if not h1 or re.fullmatch(r"[a-z0-9._-]+", fallback_title.lower()):
                    h1 = heading_clean
            elif not skip_section:
                if level == 2 and heading_clean and not h2:
                    h2 = heading_clean
                if heading_clean and heading_clean not in lines and 6 <= len(heading_clean) <= 72 and not _is_procedural_line(heading_clean):
                    lines.append(heading_clean)
            continue

        if skip_section:
            continue

        bullet_match = re.match(r"^(?:[-*+]\s+|\d+\.\s+)(.*)$", stripped)
        if bullet_match:
            flush_paragraph()
            bullet = _clean_markdown_line(bullet_match.group(1))
            if bullet and bullet not in lines and 12 <= len(bullet) <= 180 and not _is_page_chrome_line(bullet) and not _is_procedural_line(bullet):
                lines.append(bullet)
            continue

        if stripped.startswith("|") and stripped.endswith("|"):
            continue

        plain = _clean_markdown_line(stripped)
        if re.fullmatch(r"[-:| ]+", plain):
            continue
        paragraph_buffer.append(plain)

    flush_paragraph()
    title = fallback_title or h1 or (lines[0] if lines else "")
    return {
        "url": url,
        "title": title,
        "description": description,
        "h1": h1 or title,
        "h2": h2,
        "lines": lines[:40],
    }


# ---------------------------------------------------------------------------
# Line chrome / procedural detection
# ---------------------------------------------------------------------------

def _is_page_chrome_line(line: str) -> bool:
    normalized = line.strip().lower()
    if not normalized:
        return True
    blocked_exact = {
        "loading…",
        "loading...",
        "skip to main content",
        "check if python is installed:",
        "home",
        "discover",
        "communities",
        "my library",
        "explore",
        "prompt",
        "skill",
        "library",
        "copy cid",
        "copy brief",
        "agent brief",
        "prompt ref",
        "raw manifest json",
        "contents",
        "security: unavailable",
        "bash",
        "powershell",
        "macos:",
        "ubuntu/debian:",
        "windows:",
        "prerequisites",
    }
    if normalized in blocked_exact:
        return True
    blocked_prefixes = (
        "use the cid directly",
        "paste this into an agent",
        "open the prompt",
        "brew install ",
        "winget install ",
        "sudo apt ",
        "python3 --version",
        "python --version",
        "copy ",
        "security:",
        "http://",
        "https://",
    )
    if normalized.startswith(blocked_prefixes):
        return True
    if re.fullmatch(r"[a-z0-9]{8,}\.\.\.[a-z0-9]{4,}", normalized):
        return True
    if re.fullmatch(r"baf[a-z0-9]+", normalized):
        return True
    if re.fullmatch(r"[-_*`#=]{2,}", normalized):
        return True
    return False


_PROCEDURAL_HEADINGS = {
    "how to use this skill", "how to use", "getting started", "quick start",
    "setup", "configuration", "usage", "table of contents", "prerequisites",
    "installation", "requirements", "workflow steps", "workflow",
    "search reference", "available domains", "available stacks",
    "example workflow", "tips for better results",
    "common rules for professional ui", "pre-delivery checklist",
}


def _is_procedural_line(line: str) -> bool:
    """Return True for generic instructional lines unsuitable as proof content."""
    normalized = _clean_markdown_line(line).strip().lower()
    if not normalized:
        return False
    if normalized in _PROCEDURAL_HEADINGS:
        return True
    if re.match(r"^step\s+\d+", normalized):
        return True
    if normalized.startswith((
        "extract key information from user request",
        "recommended search order",
        "use search.py",
        "search until you have enough context",
        "if user doesn't specify",
        "if user does not specify",
        "available stacks:",
        "available domains:",
        "user request:",
        "then:",
        "check if ",
    )):
        return True
    if " - get " in normalized or normalized.startswith("get "):
        return True
    if normalized.endswith(("follow this workflow:", "follow these steps:")):
        return True
    return False


# ---------------------------------------------------------------------------
# Line scoring + selection
# ---------------------------------------------------------------------------

def _semantic_line_score(line: str, *, entity_type: str) -> int:
    normalized = _clean_markdown_line(line).strip()
    lowered = normalized.lower()
    if not normalized or _is_page_chrome_line(normalized) or _is_procedural_line(normalized):
        return -999
    score = 0
    if entity_type in {"prompt", "skill"}:
        strong_terms = (
            "best practices", "anti-patterns", "accessibility", "responsive",
            "color", "typography", "font", "layout", "interaction",
            "contrast", "icons", "visual elements", "hover", "spacing",
            "glass", "light mode", "dark mode", "design system",
        )
        weak_terms = (
            "product type:", "style keywords:", "industry:", "stack:",
            "available ", "default to ", "user request:", "then:",
            "search.py", "python3", "brew install", "winget install", "sudo apt",
        )
        if any(term in lowered for term in strong_terms):
            score += 4
        if any(term in lowered for term in weak_terms):
            score -= 5
        if normalized.endswith(":"):
            score -= 2
        if 18 <= len(normalized) <= 80:
            score += 2
        elif len(normalized) > 120:
            score -= 2
        if re.fullmatch(r"[A-Za-z/&+\- ]{3,48}", normalized):
            score += 2
    return score


def _rank_share_card_lines(lines: list[str], *, entity_type: str, exclusions: set[str]) -> list[str]:
    candidates: list[tuple[int, int, str]] = []
    seen: set[str] = set()
    for idx, line in enumerate(lines or []):
        normalized = _clean_markdown_line(line).strip()
        lowered = normalized.lower()
        if not normalized or normalized in exclusions or lowered in seen:
            continue
        score = _semantic_line_score(normalized, entity_type=entity_type)
        if score <= -999:
            continue
        seen.add(lowered)
        candidates.append((score, idx, normalized))
    candidates.sort(key=lambda item: (-item[0], item[1]))
    return [line for _, _, line in candidates]


def _select_short_lines(lines: list[str], exclusions: set[str], *, limit: int = 3) -> list[str]:
    out: list[str] = []
    for line in lines:
        normalized = line.strip()
        if not normalized or normalized in exclusions:
            continue
        if _is_page_chrome_line(normalized):
            continue
        if _is_procedural_line(normalized):
            continue
        if len(normalized) > 44:
            continue
        if normalized.lower().startswith(("cookie", "javascript", "sign in", "log in")):
            continue
        out.append(normalized)
        if len(out) >= limit:
            break
    return out


def _select_excerpt(lines: list[str], exclusions: set[str], fallback: str = "") -> str:
    for line in lines:
        normalized = line.strip()
        if not normalized or normalized in exclusions:
            continue
        if _is_page_chrome_line(normalized):
            continue
        if _is_procedural_line(normalized):
            continue
        if 28 <= len(normalized) <= 180:
            return normalized
    return fallback


def _select_row(lines: list[str], exclusions: set[str]) -> str:
    for line in lines:
        normalized = line.strip()
        if not normalized or normalized in exclusions:
            continue
        if _is_page_chrome_line(normalized):
            continue
        if _is_procedural_line(normalized):
            continue
        if 12 <= len(normalized) <= 72:
            return normalized
    return "Trusted distribution through the current CLI and MCP tools"


# ---------------------------------------------------------------------------
# Content extraction helpers
# ---------------------------------------------------------------------------

def _join_compact(items: list[str], *, limit: int = 4) -> str:
    cleaned: list[str] = []
    for item in items:
        text = _clean_markdown_line(item).strip(" -")
        if not text or text.lower() in {entry.lower() for entry in cleaned}:
            continue
        cleaned.append(text)
        if len(cleaned) >= limit:
            break
    return " · ".join(cleaned)


def _short_detail_copy(text: str, *, max_chars: int = 120) -> str:
    normalized = _clean_markdown_line(text)
    if not normalized:
        return ""
    normalized = re.sub(r"^(?i:always use when:\s*)", "", normalized).strip()
    normalized = re.sub(r"^(?i:use when:\s*)", "", normalized).strip()
    for splitter in (
        r"(?i)\s+provides\s+",
        r"(?i)\s+covers\s+",
        r"(?i)\s+invoke with\s+",
        r"(?i)\s+load this\s+",
        r"(?i)\s+for any\s+",
    ):
        normalized = re.split(splitter, normalized, maxsplit=1)[0].strip()
    if ":" in normalized and len(normalized.split(":", 1)[0]) < 24:
        normalized = normalized.split(":", 1)[1].strip() or normalized
    sentence = re.split(r"(?<=[.!?])\s+", normalized, maxsplit=1)[0].strip()
    output = sentence or normalized
    if len(output) > max_chars:
        output = output[: max_chars - 1].rsplit(" ", 1)[0].rstrip(" ,;:") + "…"
    return output


def _extract_prompt_share_blocks(*, content: str, description: str) -> dict[str, Any]:
    sections = _extract_markdown_sections(content)
    problem_lines = [
        line
        for line in sections.get("The Problem", [])
        if line.lower() != "agents forget. every session starts fresh. without persistent knowledge:"
    ]
    memory_lines = sections.get("1. Types of Memory", [])
    storage_lines = sections.get("2. Knowledge Storage Options", [])
    maintenance_lines = sections.get("5. Knowledge Maintenance", [])
    checklist_lines = sections.get("Implementation Checklist", [])

    memory_summary: list[str] = []
    for line in memory_lines:
        cleaned = _clean_markdown_line(line)
        if " - " in cleaned:
            memory_summary.append(cleaned)
    storage_summary: list[str] = []
    for line in storage_lines:
        cleaned = _clean_markdown_line(line)
        if cleaned.startswith("Option "):
            storage_summary.append(cleaned.replace("Option ", "", 1))
        elif cleaned.lower().startswith("best for:"):
            continue
    maintenance_summary = [line for line in maintenance_lines if not line.lower().startswith("best for:")]
    checklist_summary = [line for line in checklist_lines if len(line) <= 72]

    detail_blocks = [
        {
            "label": "Problem",
            "body": _join_compact(problem_lines, limit=4) or "Repeated work · Lost context · No learning over time · Inconsistent responses",
        },
        {
            "label": "Memory model",
            "body": _join_compact(memory_summary, limit=3) or "Episodic · Semantic · Procedural memory",
        },
        {
            "label": "Storage options",
            "body": _join_compact(storage_summary, limit=3) or "Vector database · Structured database · Graph database",
        },
        {
            "label": "Operational loop",
            "body": _join_compact(maintenance_summary or checklist_summary, limit=4) or "Ingest · Retrieve · Deduplicate · Prune stale knowledge",
        },
    ]
    return {
        "proof_excerpt": description,
        "proof_row": _join_compact(checklist_summary, limit=3) or "Choose storage · Design schema · Build retrieval functions",
        "detail_blocks": detail_blocks,
    }


def _extract_skill_share_blocks(lines: list[str], description: str) -> dict[str, Any]:
    """Build structured share card data from parsed skill content lines."""
    proof_meta: list[str] = []
    proof_lines: list[str] = []
    detail_blocks: list[dict[str, str]] = []
    for line in lines[:30]:
        text = str(line or "").strip()
        if not text:
            continue
        if _is_page_chrome_line(text) or _is_procedural_line(text):
            continue
        if 8 <= len(text) <= 38 and text not in proof_meta:
            proof_meta.append(text)
        elif 30 <= len(text) <= 200 and text not in proof_lines:
            proof_lines.append(text)
    # Build detail blocks from the best content lines
    for line in proof_lines[:6]:
        if len(line) <= 50:
            detail_blocks.append({"label": line, "body": ""})
        else:
            label = line.split(".")[0].split(":")[0].split("—")[0].strip()[:40]
            detail_blocks.append({"label": label, "body": line})
    excerpt = "\n".join(proof_lines[:3]) if proof_lines else description
    row = " · ".join(proof_meta[:4]) if proof_meta else ""
    return {
        "proof_meta": proof_meta[:6],
        "proof_excerpt": excerpt,
        "proof_row": row,
        "detail_blocks": detail_blocks[:6],
    }


def _prompt_body_lines(lines: list[str], exclusions: set[str], *, limit: int = 8) -> list[str]:
    out: list[str] = []
    for line in lines or []:
        normalized = _clean_markdown_line(line).strip()
        if not normalized or normalized in exclusions:
            continue
        if _is_page_chrome_line(normalized):
            continue
        if len(normalized) < 24 and not any(ch in normalized for ch in (":", ",", "-", "—")):
            continue
        if re.fullmatch(r"[A-Za-z/&+\- ]{1,28}", normalized) and ":" not in normalized:
            continue
        out.append(normalized)
        if len(out) >= limit:
            break
    return out


def _truncate_multiline_copy(text: str, *, max_lines: int = 8, max_chars: int = 520) -> str:
    lines = [line.strip() for line in str(text or "").splitlines() if line.strip()]
    if not lines:
        return ""
    kept: list[str] = []
    total = 0
    for line in lines:
        next_total = total + len(line) + (1 if kept else 0)
        if len(kept) >= max_lines or next_total > max_chars:
            break
        kept.append(line)
        total = next_total
    truncated = "\n".join(kept).strip()
    if not truncated:
        truncated = lines[0][: max(max_chars - 1, 1)].rstrip()
    if len(kept) < len(lines) or len(truncated) < len("\n".join(lines).strip()):
        truncated = truncated.rstrip(" .,:;") + "…"
    return truncated


def _detail_card_budget(family: str) -> tuple[int, int]:
    family_key = str(family or "").strip().lower()
    if family_key in {"detail_matrix", "reference_sheet"}:
        return (10, 760)
    if family_key in {"artifact_monolith", "prompt_sheet"}:
        return (9, 680)
    if family_key in {"statement_poster", "split_editorial"}:
        return (8, 620)
    return (7, 520)


def _prompt_detail_items(text: str, *, max_items: int = 8) -> tuple[str, list[tuple[str, str, str]]]:
    lines = [line.strip() for line in str(text or "").splitlines() if line.strip()]
    if not lines:
        return "", []
    lead = lines[0]
    items: list[tuple[str, str, str]] = []
    for raw in lines[1:]:
        line = raw.strip()
        if not line:
            continue
        if re.match(r"^\d+\.\s+", line):
            items.append(("section", re.sub(r"^\d+\.\s*", "", line).strip(), ""))
        elif ":" in line:
            label, value = line.split(":", 1)
            items.append(("kv", label.strip(), value.strip()))
        elif " - " in line:
            label, value = line.split(" - ", 1)
            items.append(("pair", label.strip(), value.strip()))
        elif " — " in line:
            label, value = line.split(" — ", 1)
            items.append(("pair", label.strip(), value.strip()))
        else:
            items.append(("body", line, ""))
        if len(items) >= max_items:
            break
    return lead, items
