import json
import unittest
from unittest.mock import patch

from brand_gen import brand_iterate_mcp


class McpBridgeTests(unittest.TestCase):
    def test_bridged_tools_are_exposed(self):
        tools = {tool["name"] for tool in brand_iterate_mcp.TOOLS}
        self.assertIn("brand_context_snapshot", tools)
        self.assertIn("brand_capabilities", tools)
        self.assertIn("brand_workspace_status", tools)
        self.assertIn("brand_prompts_list", tools)
        self.assertIn("brand_prompts_get", tools)
        self.assertIn("brand_show_identity", tools)
        self.assertIn("brand_validate_set", tools)
        self.assertIn("brand_diagnose", tools)
        self.assertIn("brand_generate_once", tools)
        self.assertIn("brand_generate", tools)
        self.assertIn("brand_consolidate_inspiration", tools)
        self.assertIn("brand_derive_mockup", tools)
        self.assertIn("brand_derive_video", tools)
        self.assertIn("brand_create", tools)

    def test_show_identity_uses_bridge_dispatch(self):
        with patch("brand_gen.brand_iterate_mcp.run_brand_iterate", return_value=('{"ok":true}', True)) as mocked:
            output, is_error = brand_iterate_mcp.handle_tool_call(
                "brand_show_identity",
                {"profile": "/tmp/profile.json", "format": "json", "show_prelude": True},
            )
        mocked.assert_called_once()
        argv = mocked.call_args.args[0]
        self.assertEqual(argv[0], "show-identity")
        self.assertIn("--profile", argv)
        self.assertIn("/tmp/profile.json", argv)
        self.assertIn("--show-prelude", argv)
        self.assertFalse(is_error)
        self.assertEqual(json.loads(output)["ok"], True)

    def test_diagnose_uses_bridge_for_positional_lists(self):
        with patch("brand_gen.brand_iterate_mcp.run_brand_iterate", return_value=('{"ok":true}', True)) as mocked:
            brand_iterate_mcp.handle_tool_call(
                "brand_diagnose",
                {"versions": ["v1", "v2"], "format": "json"},
            )
        argv = mocked.call_args.args[0]
        self.assertEqual(argv[0], "diagnose")
        self.assertIn("v1", argv)
        self.assertIn("v2", argv)

    def test_generate_uses_registry_bridge_dispatch(self):
        with patch("brand_gen.brand_iterate_mcp.run_brand_iterate", return_value=('{"ok":true}', True)) as mocked:
            brand_iterate_mcp.handle_tool_call(
                "brand_generate",
                {"scratchpad": "/tmp/run.json", "max_iterations": 2, "skip_vlm": True},
            )
        argv = mocked.call_args.args[0]
        self.assertEqual(argv[0], "generate")
        self.assertIn("--scratchpad", argv)
        self.assertIn("/tmp/run.json", argv)
        self.assertIn("--max-iterations", argv)
        self.assertIn("2", argv)
        self.assertIn("--skip-vlm", argv)

    def test_generate_bridge_supports_internal_vlm_opt_in(self):
        with patch("brand_gen.brand_iterate_mcp.run_brand_iterate", return_value=('{"ok":true}', True)) as mocked:
            brand_iterate_mcp.handle_tool_call(
                "brand_generate",
                {"scratchpad": "/tmp/run.json", "internal_vlm_critique": True},
            )
        argv = mocked.call_args.args[0]
        self.assertEqual(argv[0], "generate")
        self.assertIn("--internal-vlm-critique", argv)

    def test_create_brand_uses_renamed_registry_args(self):
        with patch("brand_gen.brand_iterate_mcp.run_brand_iterate", return_value=('{"ok":true}', True)) as mocked:
            brand_iterate_mcp.handle_tool_call(
                "brand_create",
                {"name": "Acme", "value_props": ["Fast", "Trusted"]},
            )
        argv = mocked.call_args.args[0]
        self.assertEqual(argv[0], "create-brand")
        self.assertEqual(argv.count("--value-prop"), 2)

    def test_only_custom_tools_remain_outside_bridge_registry(self):
        bridged = set(brand_iterate_mcp.BRIDGE_BY_TOOL)
        all_tools = {tool["name"] for tool in brand_iterate_mcp.TOOLS}
        self.assertEqual(all_tools - bridged, {"brand_inspire", "brand_pipeline"})


if __name__ == "__main__":
    unittest.main()
