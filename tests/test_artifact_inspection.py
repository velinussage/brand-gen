"""Phase B: 6 artifact inspection verbs.

Verifies the fetch_* helpers locate artifacts by run_id or by explicit
path, and that the canonical registry + agent allowlists include the
new verbs.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from brand_gen.artifact_inspection import (
    compare_versions,
    fetch_critique,
    fetch_plan,
    fetch_review_packet,
    fetch_scratchpad,
    fetch_version,
)


def _write_scratchpad_artifact(brand: Path, kind_dir: str, workflow_id: str, payload: dict) -> Path:
    folder = brand / "scratchpads" / kind_dir
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{workflow_id}.json"
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


class ArtifactInspectionTests(unittest.TestCase):
    def test_fetch_plan_by_run_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            brand = Path(tmp)
            workflow_id = "wf-plan"
            _write_scratchpad_artifact(
                brand,
                "plan-drafts",
                workflow_id,
                {"schema_type": "plan_draft", "workflow_id": workflow_id, "plan": {"material_type": "x-feed"}},
            )
            result = fetch_plan(brand, run_id=workflow_id)
            self.assertEqual(result["status"], "ok")
            self.assertIsNotNone(result["payload"])
            self.assertEqual(result["payload"]["schema_type"], "plan_draft")

    def test_fetch_plan_by_explicit_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            brand = Path(tmp)
            path = _write_scratchpad_artifact(
                brand,
                "plan-drafts",
                "wf-path",
                {"schema_type": "plan_draft", "workflow_id": "wf-path"},
            )
            result = fetch_plan(brand, path=str(path))
            self.assertEqual(result["status"], "ok")
            self.assertEqual(Path(result["path"]).resolve(), path.resolve())

    def test_fetch_plan_not_found(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            brand = Path(tmp)
            result = fetch_plan(brand, run_id="ghost")
            self.assertEqual(result["status"], "not_found")

    def test_fetch_critique_and_scratchpad(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            brand = Path(tmp)
            workflow_id = "wf-full"
            _write_scratchpad_artifact(
                brand,
                "plan-critiques",
                workflow_id,
                {"schema_type": "plan_critique", "workflow_id": workflow_id, "checks": {"blocking": []}},
            )
            _write_scratchpad_artifact(
                brand,
                "generation",
                workflow_id,
                {"schema_type": "generation_scratchpad", "workflow_id": workflow_id, "execution_prompt": "hi"},
            )
            critique = fetch_critique(brand, run_id=workflow_id)
            scratch = fetch_scratchpad(brand, run_id=workflow_id)
            self.assertEqual(critique["status"], "ok")
            self.assertEqual(scratch["status"], "ok")
            self.assertEqual(scratch["payload"]["execution_prompt"], "hi")

    def test_fetch_review_packet_prefers_agent_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            brand = Path(tmp)
            reviews = brand / "reviews"
            reviews.mkdir(parents=True)
            (reviews / "v3-auto-review.json").write_text(json.dumps({"kind": "auto"}))
            (reviews / "v3-agent-review.json").write_text(json.dumps({"kind": "agent", "axis_scores": {}}))
            result = fetch_review_packet(brand, version_id="v3")
            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["payload"]["kind"], "agent")
            self.assertTrue(result["path"].endswith("-agent-review.json"))

    def test_fetch_review_packet_falls_back_to_auto(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            brand = Path(tmp)
            reviews = brand / "reviews"
            reviews.mkdir(parents=True)
            (reviews / "v4-auto-review.json").write_text(json.dumps({"kind": "auto"}))
            result = fetch_review_packet(brand, version_id="v4")
            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["payload"]["kind"], "auto")

    def test_fetch_review_packet_not_found(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = fetch_review_packet(Path(tmp), version_id="ghost")
            self.assertEqual(result["status"], "not_found")

    def test_fetch_version_uses_manifest_dict(self) -> None:
        manifest = {"versions": {"v7": {"material_type": "x-feed", "score": 4, "files": ["/tmp/x.png"]}}}
        with tempfile.TemporaryDirectory() as tmp:
            result = fetch_version(Path(tmp), version_id="v7", manifest=manifest)
            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["entry"]["score"], 4)

    def test_fetch_version_not_found(self) -> None:
        manifest = {"versions": {}}
        result = fetch_version(Path("/tmp"), version_id="v7", manifest=manifest)
        self.assertEqual(result["status"], "not_found")

    def test_compare_versions_diff(self) -> None:
        manifest = {
            "versions": {
                "v1": {"material_type": "x-feed", "score": 3, "model": "flux-pro"},
                "v2": {"material_type": "x-feed", "score": 5, "model": "seedream"},
            },
        }
        result = compare_versions(Path("/tmp"), version_a="v1", version_b="v2", manifest=manifest)
        self.assertEqual(result["status"], "ok")
        self.assertIn("score", result["diff"])
        self.assertIn("model", result["diff"])
        self.assertNotIn("material_type", result["diff"])


class PhaseBCanonicalTests(unittest.TestCase):
    def test_six_inspection_verbs_are_canonical(self) -> None:
        registry_path = Path(__file__).resolve().parents[1] / "packages" / "brand-gen-core" / "src" / "tool-registry.ts"
        text = registry_path.read_text(encoding="utf-8")
        for verb in (
            "brand_get_plan",
            "brand_get_critique",
            "brand_get_scratchpad",
            "brand_get_review_packet",
            "brand_get_version",
            "brand_compare_versions",
        ):
            self.assertIn(f'name: "{verb}"', text)

    def test_strategist_allowlist_includes_artifact_verbs(self) -> None:
        from brand_gen.agent_specialization import AGENT_BY_ID

        strategist = AGENT_BY_ID["strategist"]
        self.assertIn("brand_get_plan", strategist.canonical_tools)
        self.assertIn("brand_compare_versions", strategist.canonical_tools)

    def test_bridges_wired(self) -> None:
        from brand_gen.mcp_bridge_registry import BRIDGE_BY_TOOL

        for verb in (
            "brand_get_plan",
            "brand_get_critique",
            "brand_get_scratchpad",
            "brand_get_review_packet",
            "brand_get_version",
            "brand_compare_versions",
        ):
            self.assertIn(verb, BRIDGE_BY_TOOL)
            self.assertTrue(BRIDGE_BY_TOOL[verb].read_only, f"{verb} should be read_only")


if __name__ == "__main__":
    unittest.main()
