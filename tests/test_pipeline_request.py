import argparse
import unittest
from pathlib import Path

from mcp import brand_iterate_mcp
from mcp.cli_builders import build_pipeline_cli
from mcp.generation_flow import (
    build_base_image_edit_policy,
    build_base_image_reference_role,
    ensure_base_image_reference_role,
    filter_reference_paths_for_base_image_edit,
)
from mcp.pipeline_request import PipelineRequest
from mcp.runtime_models import MATERIAL_CONFIG, MATERIAL_PROMPT_SNIPPET_ALIASES


class PipelineRequestTests(unittest.TestCase):
    def test_from_mcp_args_normalizes_defaults_and_bounds(self):
        request = PipelineRequest.from_mcp_args(
            {
                "material_type": "social",
                "mode": "invalid",
                "max_iterations": 9,
                "critique_mode": "INVALID",
                "preserve": ["  Keep this  ", "", "Also this"],
                "skip_route": 1,
            }
        )

        self.assertEqual(request.material_type, "social")
        self.assertEqual(request.mode, "hybrid")
        self.assertEqual(request.max_iterations, 3)
        self.assertEqual(request.critique_mode, "strict")
        self.assertEqual(request.preserve, ["Keep this", "Also this"])
        self.assertTrue(request.skip_route)

    def test_build_critique_namespace_uses_shared_policy_defaults(self):
        args = PipelineRequest.build_critique_namespace("/tmp/plan.json", critique_mode="advisory", allow_blocking=True, base_image="/tmp/base.png")
        self.assertEqual(args.plan, "/tmp/plan.json")
        self.assertEqual(args.critique_mode, "advisory")
        self.assertTrue(args.allow_blocking)
        self.assertEqual(args.base_image, "/tmp/base.png")
        self.assertEqual(args.format, "json")

    def test_build_scratchpad_namespace_carries_branch_fields(self):
        args = PipelineRequest.build_scratchpad_namespace(
            "/tmp/plan.json",
            {"material_type": "social"},
            critique_mode="strict",
            allow_blocking=False,
            source_version="v012",
            base_image="/tmp/base.png",
            tag="launch-card",
            branch_id="wf-123",
            parent_branch_id="wf-parent",
        )
        self.assertEqual(args.material_type, "social")
        self.assertEqual(args.source_version, "v012")
        self.assertEqual(args.base_image, "/tmp/base.png")
        self.assertEqual(args.tag, "launch-card")
        self.assertEqual(args.branch_id, "wf-123")
        self.assertEqual(args.parent_branch_id, "wf-parent")

    def test_brand_pipeline_schema_matches_pipeline_request_model(self):
        tool = next(tool for tool in brand_iterate_mcp.TOOLS if tool["name"] == "brand_pipeline")
        self.assertEqual(tool["inputSchema"], PipelineRequest.mcp_input_schema())

    def test_pipeline_cli_accepts_base_image_briefing_and_tag_fields(self):
        parser = argparse.ArgumentParser()
        build_pipeline_cli(parser, inspire_urls={})
        args = parser.parse_args(
            [
                "--material-type",
                "state-card",
                "--tag",
                "launch-card",
                "--briefing",
                "truth-first share card",
                "--audience",
                "protocol followers",
                "--base-image",
                "/tmp/base.png",
            ]
        )
        self.assertEqual(args.material_type, "state-card")
        self.assertEqual(args.tag, "launch-card")
        self.assertEqual(args.briefing, "truth-first share card")
        self.assertEqual(args.audience, "protocol followers")
        self.assertEqual(args.base_image, "/tmp/base.png")

    def test_state_card_material_type_is_registered(self):
        self.assertIn("state-card", MATERIAL_CONFIG)
        self.assertEqual(MATERIAL_PROMPT_SNIPPET_ALIASES["state-card"], "state_card")

    def test_base_image_edit_policy_mentions_truth_and_bounds(self):
        policy = build_base_image_edit_policy("state-card")
        self.assertIn("authoritative truth", policy)
        self.assertIn("card bounds", policy)

    def test_base_image_edit_filter_keeps_only_motif_refs(self):
        kept, trimmed = filter_reference_paths_for_base_image_edit(
            ["/tmp/logo.png", "/tmp/screenshot.png"],
            [
                {"role": "motif", "path": "/tmp/logo.png"},
                {"role": "product_truth", "path": "/tmp/screenshot.png"},
            ],
        )
        self.assertTrue(trimmed)
        self.assertEqual(kept, [Path("/tmp/logo.png").resolve()])

    def test_base_image_registers_product_truth_reference_role(self):
        role = build_base_image_reference_role(Path("/tmp/base.png"))
        self.assertEqual(role["role"], "product_truth")
        self.assertIn("authoritative", role["role_help"])

    def test_base_image_reference_role_updates_required_roles(self):
        override, added = ensure_base_image_reference_role(
            {"roles": [], "required_roles": [], "priority": []},
            Path("/tmp/base.png"),
        )
        self.assertTrue(added)
        self.assertEqual(override["roles"][0]["role"], "product_truth")
        self.assertIn("product_truth", override["required_roles"])
        self.assertEqual(override["priority"][0], "product_truth")


if __name__ == "__main__":
    unittest.main()
