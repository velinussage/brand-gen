"""Phase D: policy_class tags + 4 policy verbs.

Covers:
  - Envelope round-trip (default → set → load again).
  - check_policy_for_tool returns the right decision for each class.
  - request_approval mints pending entries; resolve_approval drains them.
  - POLICY_CLASSES_BY_TOOL covers every canonical tool.
  - 4 policy verbs are in the TS canonical registry, in bridges, and in
    the orchestrator allowlist.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from brand_gen.policy import (
    POLICY_CLASSES_BY_TOOL,
    check_policy_for_tool,
    find_pending,
    load_policy_envelope,
    policy_class_for_tool,
    policy_path,
    request_approval,
    resolve_approval,
    save_policy_envelope,
    set_policy_class,
)


class PolicyEnvelopeTests(unittest.TestCase):
    def test_default_envelope_allows_reads_writes_and_gens(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env = load_policy_envelope(Path(tmp))
            self.assertEqual(env["classes"]["read_only"]["mode"], "allow")
            self.assertEqual(env["classes"]["local_mutation"]["mode"], "allow")
            self.assertEqual(env["classes"]["costly_generation"]["mode"], "allow")
            self.assertEqual(env["classes"]["publish_external"]["mode"], "deny")
            self.assertEqual(env["pending_approvals"], [])

    def test_set_policy_persists_to_disk(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            brand = Path(tmp)
            set_policy_class(brand, policy_class="costly_generation", mode="require_approval")
            reloaded = load_policy_envelope(brand)
            self.assertEqual(reloaded["classes"]["costly_generation"]["mode"], "require_approval")
            self.assertTrue(policy_path(brand).exists())

    def test_set_policy_rejects_unknown_class(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                set_policy_class(Path(tmp), policy_class="made_up", mode="allow")  # type: ignore[arg-type]

    def test_set_policy_rejects_unknown_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                set_policy_class(Path(tmp), policy_class="read_only", mode="maybe")  # type: ignore[arg-type]


class CheckPolicyTests(unittest.TestCase):
    def test_inspection_tools_map_to_read_only_allow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env = load_policy_envelope(Path(tmp))
            result = check_policy_for_tool(env, "brand_show_blackboard")
            self.assertEqual(result, {"decision": "allow", "class": "read_only", "tool": "brand_show_blackboard"})

    def test_execute_run_is_costly_generation(self) -> None:
        self.assertEqual(policy_class_for_tool("brand_execute_run"), "costly_generation")

    def test_switch_brand_is_local_mutation(self) -> None:
        self.assertEqual(policy_class_for_tool("brand_switch_brand"), "local_mutation")

    def test_publish_external_is_denied_by_default(self) -> None:
        env = load_policy_envelope(Path(tempfile.gettempdir()))
        self.assertEqual(env["classes"]["publish_external"]["mode"], "deny")

    def test_require_approval_flips_decision(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            brand = Path(tmp)
            set_policy_class(brand, policy_class="costly_generation", mode="require_approval")
            env = load_policy_envelope(brand)
            result = check_policy_for_tool(env, "brand_orchestrate_material")
            self.assertEqual(result["decision"], "require_approval")
            self.assertEqual(result["class"], "costly_generation")


class ApprovalQueueTests(unittest.TestCase):
    def test_request_and_approve_flow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            brand = Path(tmp)
            env = load_policy_envelope(brand)
            pending_id = request_approval(env, tool="brand_execute_run", args_summary="hero image for launch")
            self.assertIsNotNone(find_pending(env, pending_id))
            entry = resolve_approval(env, pending_id=pending_id, decision="approved", reason="looks good")
            assert entry is not None
            self.assertEqual(entry["decision"], "approved")
            self.assertIsNone(find_pending(env, pending_id))
            self.assertEqual(env["recent_decisions"][0]["pending_id"], pending_id)
            save_policy_envelope(brand, env)

    def test_reject_flow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env = load_policy_envelope(Path(tmp))
            pid = request_approval(env, tool="brand_execute_run")
            entry = resolve_approval(env, pending_id=pid, decision="rejected", reason="too expensive")
            assert entry is not None
            self.assertEqual(entry["decision"], "rejected")
            self.assertEqual(entry["reason"], "too expensive")

    def test_resolve_missing_pending_returns_none(self) -> None:
        env = load_policy_envelope(Path(tempfile.gettempdir()))
        self.assertIsNone(resolve_approval(env, pending_id="ghost", decision="approved"))


class ClassMappingCoverageTests(unittest.TestCase):
    def test_every_canonical_tool_has_a_policy_class(self) -> None:
        registry_path = Path(__file__).resolve().parents[1] / "packages" / "brand-gen-core" / "src" / "tool-registry.ts"
        import re

        names = set(re.findall(r'name:\s*"([a-z_]+)"\s*,\s*category:\s*"[a-z]+"', registry_path.read_text()))
        # Every canonical tool must be in POLICY_CLASSES_BY_TOOL.
        missing = [name for name in names if name not in POLICY_CLASSES_BY_TOOL and not name.startswith("brand_get_policy") and not name.startswith("brand_set_policy") and not name.startswith("brand_approve_action") and not name.startswith("brand_reject_action")]
        self.assertEqual(
            missing,
            [],
            f"Canonical tools not tagged with a policy class in "
            f"brand_gen/policy.py::POLICY_CLASSES_BY_TOOL: {missing}",
        )


class PhaseDCanonicalTests(unittest.TestCase):
    def test_four_policy_verbs_are_canonical(self) -> None:
        registry_path = Path(__file__).resolve().parents[1] / "packages" / "brand-gen-core" / "src" / "tool-registry.ts"
        text = registry_path.read_text(encoding="utf-8")
        for verb in (
            "brand_get_policy",
            "brand_set_policy",
            "brand_approve_action",
            "brand_reject_action",
        ):
            self.assertIn(f'name: "{verb}"', text)

    def test_policy_verbs_bridged(self) -> None:
        from brand_gen.mcp_bridge_registry import BRIDGE_BY_TOOL

        for verb in (
            "brand_get_policy",
            "brand_set_policy",
            "brand_approve_action",
            "brand_reject_action",
        ):
            self.assertIn(verb, BRIDGE_BY_TOOL)
        # brand_get_policy is read-only; the rest are mutations.
        self.assertTrue(BRIDGE_BY_TOOL["brand_get_policy"].read_only)
        self.assertFalse(BRIDGE_BY_TOOL["brand_set_policy"].read_only)

    def test_policy_mutations_are_orchestrator_only(self) -> None:
        from brand_gen.agent_specialization import AGENT_BY_ID

        orchestrator = AGENT_BY_ID["orchestrator"]
        strategist = AGENT_BY_ID["strategist"]
        for verb in ("brand_set_policy", "brand_approve_action", "brand_reject_action"):
            self.assertIn(verb, orchestrator.canonical_tools)
            self.assertNotIn(verb, strategist.canonical_tools)

    def test_get_policy_granted_broadly(self) -> None:
        from brand_gen.agent_specialization import AGENT_BY_ID

        strategist = AGENT_BY_ID["strategist"]
        self.assertIn("brand_get_policy", strategist.canonical_tools)


if __name__ == "__main__":
    unittest.main()
