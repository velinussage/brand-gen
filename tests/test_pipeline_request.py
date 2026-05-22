import argparse
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from brand_gen import brand_iterate_mcp
from brand_gen.cli_builders import build_pipeline_cli
from brand_gen.generation_flow import (
    build_base_image_edit_policy,
    build_base_image_reference_role,
    ensure_base_image_reference_role,
    filter_reference_paths_for_base_image_edit,
)
from brand_gen.pipeline_request import PipelineRequest
from brand_gen.plan_builder import build_plan_critique_payload
from brand_gen.runtime_models import MATERIAL_CONFIG, MATERIAL_PROMPT_SNIPPET_ALIASES


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

    def test_plan_critique_uses_cli_base_image_for_validation(self):
        plan = {
            "material_type": "product-banner",
            "purpose": "launch banner",
            "target_surface": "X header",
            "product_truth_expression": "USDC boons become creator points",
            "abstraction_level": "medium",
            "brand_anchor_policy": {"rule": "Keep the output clearly branded."},
            "system_mechanic": "receipt to points ledger",
            "preserve": ["USDC truth"],
            "push": ["simple launch narrative"],
            "ban": ["token claims"],
            "prompt_seed": "Boon product banner.",
            "role_pack": {},
        }
        args = argparse.Namespace(
            plan="/tmp/plan.json",
            material_type="product-banner",
            base_image="/tmp/base.png",
            render_backend="native",
            generation_mode="auto",
            mode="auto",
        )
        with tempfile.TemporaryDirectory() as tmpdir, patch(
            "brand_gen.generation_flow.assemble_generation_scratchpad",
            return_value={"checks": {"blocking": [], "warnings": []}, "prompt_review": {}},
        ):
            critique = build_plan_critique_payload(
                args,
                brand_dir=Path(tmpdir),
                wrapper={},
                plan=plan,
                critique_mode="strict",
                entrypoint="pipeline",
            )
        self.assertEqual(critique["plan"]["base_image"], "/tmp/base.png")
        self.assertFalse(
            any("Interface material is missing base_image" in item for item in critique["plan_validation"]["errors"])
        )


if __name__ == "__main__":
    unittest.main()
