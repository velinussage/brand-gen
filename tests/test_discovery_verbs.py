"""Phase C: discovery verbs (brand_list_brands / brand_switch_brand /
brand_get_pending_reviews) wired through canonical registry + bridges.
"""
from __future__ import annotations

import unittest
from pathlib import Path


class PhaseCCanonicalTests(unittest.TestCase):
    def test_three_discovery_verbs_are_canonical(self) -> None:
        registry_path = Path(__file__).resolve().parents[1] / "packages" / "brand-gen-core" / "src" / "tool-registry.ts"
        text = registry_path.read_text(encoding="utf-8")
        for verb in (
            "brand_list_brands",
            "brand_switch_brand",
            "brand_get_pending_reviews",
        ):
            self.assertIn(f'name: "{verb}"', text)

    def test_list_brands_and_pending_reviews_in_inspection_pool(self) -> None:
        from brand_gen.agent_specialization import AGENT_BY_ID

        explorer = AGENT_BY_ID["brand-explorer"]
        self.assertIn("brand_list_brands", explorer.canonical_tools)
        self.assertIn("brand_get_pending_reviews", explorer.canonical_tools)

    def test_switch_brand_is_orchestrator_only(self) -> None:
        """brand_switch_brand writes .brand-gen/config.json — must NOT be
        granted to read-only agents."""
        from brand_gen.agent_specialization import AGENT_BY_ID

        orchestrator = AGENT_BY_ID["brand-orchestrator"]
        explorer = AGENT_BY_ID["brand-explorer"]
        router = AGENT_BY_ID["brand-router"]
        self.assertIn("brand_switch_brand", orchestrator.canonical_tools)
        self.assertNotIn("brand_switch_brand", explorer.canonical_tools)
        self.assertNotIn("brand_switch_brand", router.canonical_tools)

    def test_bridges_wired(self) -> None:
        from brand_gen.mcp_bridge_registry import BRIDGE_BY_TOOL

        self.assertIn("brand_list_brands", BRIDGE_BY_TOOL)
        self.assertIn("brand_switch_brand", BRIDGE_BY_TOOL)
        self.assertIn("brand_get_pending_reviews", BRIDGE_BY_TOOL)
        # list-brands was previously exposed as brand_list; the rename to
        # brand_list_brands is the canonical name going forward.
        self.assertNotIn("brand_list", BRIDGE_BY_TOOL)

    def test_switch_brand_is_mutation_not_readonly_bridge(self) -> None:
        from brand_gen.mcp_bridge_registry import BRIDGE_BY_TOOL

        self.assertFalse(BRIDGE_BY_TOOL["brand_switch_brand"].read_only)


if __name__ == "__main__":
    unittest.main()
