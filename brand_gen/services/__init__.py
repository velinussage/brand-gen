"""Phase 6 — three-layer service facade.

Separates blended concerns into three services callers can pin to:

  MemoryService         durable taste accumulation (read-mostly)
                        learnings, iteration memory, inspiration memory

  OrchestrationService  per-run state + rotation window
                        blackboard projection over the run ledger,
                        style-anchor + archetype rotation state,
                        stage events

  PromptResolver        stateless composition
                        typed PromptBlock list + priority-tier eviction

Design rule: services do NOT cross-import each other. Callers that
need data from two layers call both services and stitch the result.
Existing helpers (brand_gen.blackboard, brand_gen.iteration_memory,
brand_gen.prompt_assembly) remain importable — the services are
facades over them, not replacements. Over time new typed callers
should pin to the service interfaces; the underlying helpers can then
migrate without breaking callers.

Enforced by tests/test_service_layer_isolation.py.
"""
from __future__ import annotations

from .memory_service import MemoryService
from .orchestration_service import OrchestrationService
from .prompt_resolver import PromptResolver

__all__ = [
    "MemoryService",
    "OrchestrationService",
    "PromptResolver",
]
