"""PromptResolver — stateless prompt composition facade.

Wraps build_execution_prompt + the typed PromptBlock system so callers
that don't want to touch the internals of prompt_assembly.py have a
clean resolve() entry point.

Does NOT import MemoryService or OrchestrationService. The caller
assembles a context dict from both services (or elsewhere) and passes
it in. This keeps PromptResolver truly stateless — it's a pure
function of (body, context, material, mode).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..prompt_assembly import build_execution_prompt
from ..prompt_block import PromptBlock, blocks_from_sections, evict_to_budget


@dataclass(frozen=True)
class ResolvedPrompt:
    """Typed result of resolving a prompt — includes the final string,
    the per-block provenance trail, and any blocks dropped under budget
    pressure.
    """

    execution_prompt: str
    blocks: tuple[dict[str, Any], ...]
    dropped_blocks: tuple[dict[str, Any], ...]
    execution_prompt_kind: str
    execution_prompt_compressed: bool
    body_compressed: bool = False
    body_original_chars: int = 0
    body_compressed_chars: int = 0
    prelude_chars: int = 0


class PromptResolver:
    """Stateless composer over build_execution_prompt + PromptBlock
    eviction. Instantiate with defaults (usually none needed).

    Called by the generator stage and the critic's image-review helper.
    """

    def resolve(
        self,
        raw_prompt: str,
        context: dict[str, Any],
        *,
        material_type: str | None = None,
        generation_mode: str = "image",
    ) -> ResolvedPrompt:
        """Build an execution prompt from typed context blocks.

        Phase 4 already typed the prompt surface. This resolver wraps
        build_execution_prompt so future callers can pin to the typed
        ResolvedPrompt dataclass instead of the dict payload.
        """
        payload = build_execution_prompt(
            raw_prompt,
            context,
            material_type=material_type,
            generation_mode=generation_mode,
        )
        blocks = tuple(payload.get("execution_prompt_blocks") or [])
        dropped = tuple(payload.get("dropped_blocks") or [])
        return ResolvedPrompt(
            execution_prompt=str(payload.get("execution_prompt") or ""),
            blocks=blocks,
            dropped_blocks=dropped,
            execution_prompt_kind=str(payload.get("execution_prompt_kind") or ""),
            execution_prompt_compressed=bool(payload.get("execution_prompt_compressed", False)),
            body_compressed=bool(payload.get("body_compressed", False)),
            body_original_chars=int(payload.get("body_original_chars") or 0),
            body_compressed_chars=int(payload.get("body_compressed_chars") or 0),
            prelude_chars=int(payload.get("prelude_chars") or 0),
        )

    def evict_to_budget(
        self,
        blocks: list[PromptBlock],
        budget_chars: int,
    ) -> tuple[list[PromptBlock], list[PromptBlock]]:
        """Explicit priority-tier eviction — useful for callers that
        assemble their own PromptBlock lists outside build_execution_prompt.
        Returns (kept, dropped) preserving the hard-constraint invariant.
        """
        return evict_to_budget(blocks, budget_chars)

    @staticmethod
    def blocks_from_sections(sections: dict[str, str]) -> list[PromptBlock]:
        """Pass-through to brand_gen.prompt_block — exposed here so
        callers don't need to reach into prompt_block directly.
        """
        return blocks_from_sections(sections)
