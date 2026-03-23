"""Share card renderer — re-export facade.

Module map:
    card_text     — text analysis, HTTP utilities, line scoring
    card_engine   — ShareCardPayload, LayoutSpec, HTML rendering, PNG render
    card_builder  — payload construction, entity defaults
    card_plugins  — plugin interface, Sage plugin, generic web plugin
"""
from .card_text import *  # noqa: F401,F403
from .card_engine import *  # noqa: F401,F403
from .card_builder import *  # noqa: F401,F403
from .card_plugins import fetch_card_page_data, CardDataPlugin, register_plugin  # noqa: F401

# Backwards-compat aliases that tests / consumers may reference directly.
from .card_builder import _proof_weight_for, _infer_entity_type, _cta_for_entity  # noqa: F401
from .card_builder import _default_proof_meta, _default_proof_excerpt, _select_composition_profile  # noqa: F401
from .card_engine import _manifest_write_lock, _reserve_manifest_version, _update_manifest_version  # noqa: F401
from .card_engine import _render_prompt_detail_html, _render_detail_blocks_html, _render_entity_detail_html  # noqa: F401
from .card_engine import _surface_label, _entity_proof_title, _entity_proof_label  # noqa: F401
from .card_engine import _qr_code_url, _headline_font_size, _escape_list  # noqa: F401
from .card_engine import _write_generated_svg, _generate_composition_assets, _copy_asset  # noqa: F401
from .card_engine import _surface_size, _find_chrome_binary, render_html_to_png  # noqa: F401
from .card_engine import _verify_render, _PNG_MAGIC, _MIN_RENDER_BYTES  # noqa: F401
from .card_engine import compose_share_card_html, taste_design_directives  # noqa: F401
from .card_engine import _load_taste_directives, _variance_band  # noqa: F401
from .card_text import _VisibleTextParser, _extract_meta, _fetch_json_url, _fetch_page_text  # noqa: F401
from .card_text import _humanize_key, _clean_sage_title, _normalize_content_text  # noqa: F401
from .card_text import _strip_leading_frontmatter, _clean_markdown_line  # noqa: F401
from .card_text import _strip_markdown_code_fences, _extract_markdown_sections  # noqa: F401
from .card_text import _markdown_doc_to_page  # noqa: F401
from .card_text import _is_page_chrome_line, _PROCEDURAL_HEADINGS, _is_procedural_line  # noqa: F401
from .card_text import _semantic_line_score, _rank_share_card_lines  # noqa: F401
from .card_text import _select_short_lines, _select_excerpt, _select_row  # noqa: F401
from .card_text import _join_compact, _short_detail_copy  # noqa: F401
from .card_text import _extract_prompt_share_blocks, _extract_skill_share_blocks  # noqa: F401
from .card_text import _prompt_body_lines, _truncate_multiline_copy  # noqa: F401
from .card_text import _detail_card_budget, _prompt_detail_items  # noqa: F401

# Sage plugin internals that old code may reference via share_card_renderer
from .card_plugins.sage import (  # noqa: F401
    _looks_like_cid,
    _try_sage_local_skill,
    _find_skill_entry,
    _search_sage_worker,
    _fetch_sage_prompt_page,
    _fetch_sage_skill_page,
    _fetch_sage_profile_page,
    _fetch_sage_community_page,
    _fetch_sage_library_page,
    _looks_like_eth_address,
    _short_address,
    _looks_like_short_address,
)


def _fetch_sage_share_card_text(url: str, entity_type: str) -> dict | None:
    """Legacy dispatcher — delegates to SageCardPlugin."""
    from .card_plugins.sage import SageCardPlugin
    plugin = SageCardPlugin()
    if plugin.can_handle(url, entity_type):
        return plugin.fetch_page_data(url, entity_type)
    return None
