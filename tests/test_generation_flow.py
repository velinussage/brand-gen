from concurrent.futures import ThreadPoolExecutor
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from brand_gen.generation_flow import (
    _reserve_manifest_version,
    auto_capture_generation_feedback,
    auto_capture_vlm_feedback,
    build_base_image_reference_role,
    build_structural_auto_critic,
    ensure_base_image_reference_role,
    execute_generation_scratchpad,
)
from brand_gen.iteration_memory import load_iteration_memory
from brand_gen.runtime_brand import load_manifest
from brand_gen.runtime_models import recommend_text_model


class SourceCritiqueModelOverrideTests(unittest.TestCase):
    """Test that source version critique auto-overrides model in generation flow."""

    def test_source_version_critique_triggers_model_recommendation(self):
        """When source version has text issues in critique, recommend_text_model returns a recommendation."""
        critique = {
            "text_accuracy": 0.3,
            "text_issues": ["misspelled 'Discover' as 'Dicover'"],
            "p1": ["Text spelling error"],
        }
        rec = recommend_text_model(
            critique,
            current_model="nano-banana-2",
            material_type="browser-illustration",
            has_reference_images=True,
        )
        self.assertEqual(rec, "flux-2-flex")

    def test_source_version_clean_critique_no_recommendation(self):
        """Clean critique from source version should not trigger model override."""
        critique = {
            "text_accuracy": 0.95,
            "text_issues": [],
            "p1": [],
        }
        rec = recommend_text_model(
            critique,
            current_model="nano-banana-2",
            material_type="browser-illustration",
            has_reference_images=True,
        )
        self.assertIsNone(rec)

    def test_critique_file_loaded_and_model_overridden(self):
        """Integration: verify that critique JSON is loadable and produces recommendation."""
        tmp = Path(tempfile.mkdtemp())
        critique = {
            "approved": False,
            "text_accuracy": 0.2,
            "text_issues": ["garbled text in header"],
            "p1": ["Text rendering: 'Dicover' instead of 'Discover'"],
            "p2": [],
        }
        critique_path = tmp / "v004-vlm-critique.json"
        critique_path.write_text(json.dumps(critique))

        # Simulate what generation_flow does: load critique, call recommend_text_model
        loaded = json.loads(critique_path.read_text())
        rec = recommend_text_model(
            loaded,
            current_model="recraft-v4",
            material_type="browser-illustration",
            has_reference_images=True,
        )
        self.assertEqual(rec, "flux-2-flex")


class ManifestReservationTests(unittest.TestCase):
    def test_reserve_manifest_version_is_unique_under_parallel_calls(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            brand_dir = Path(tmpdir).resolve()
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = [
                    pool.submit(
                        _reserve_manifest_version,
                        brand_dir,
                        material_type="social",
                        workflow_id=f"wf-{idx}",
                        tag="social",
                    )
                    for idx in range(2)
                ]
            versions = sorted(f.result() for f in futures)
            self.assertEqual(versions, ["v001", "v002"])
            manifest = load_manifest(brand_dir)
            self.assertEqual(sorted((manifest.get("versions") or {}).keys()), ["v001", "v002"])


class BaseImageReferenceTests(unittest.TestCase):
    def test_base_image_role_defaults_to_product_truth(self):
        role = build_base_image_reference_role(Path("/tmp/sage-base.png"))
        self.assertEqual(role["role"], "product_truth")
        self.assertIn("carrier proof", role["notes"])

    def test_base_image_role_is_added_when_no_product_truth_exists(self):
        override, added = ensure_base_image_reference_role(
            {"roles": [{"role": "composition", "path": "/tmp/composition.png"}]},
            Path("/tmp/base.png"),
        )

        self.assertTrue(added)
        roles = override["roles"]
        self.assertEqual([item["role"] for item in roles], ["composition", "product_truth"])
        self.assertEqual(roles[-1]["path"], str(Path("/tmp/base.png").resolve()))

    def test_existing_product_truth_role_is_not_duplicated(self):
        override, added = ensure_base_image_reference_role(
            {"roles": [{"role": "product_truth", "path": "/tmp/existing.png"}]},
            Path("/tmp/base.png"),
        )

        self.assertFalse(added)
        self.assertEqual(len(override["roles"]), 1)


class PipelineQaOrderingTests(unittest.TestCase):
    def test_execute_generation_scratchpad_writes_agent_review_metadata_before_pipeline_qa(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            brand_dir = Path(tmpdir)
            payload = {
                "schema_type": "generation_scratchpad",
                "brand_dir": str(brand_dir),
                "material_type": "social",
                "workflow_mode": "reference",
                "generation_mode": "image",
                "tag": "social",
                "raw_prompt": "Create a social card.",
                "effective_prompt": "Create a social card.",
                "execution_prompt": "Create a social card.",
                "selected_reference_ids": [],
                "selected_inspiration_ids": [],
                "prompt_context": {
                    "material_prompt_key": "social",
                    "material_prompt_variant": "default",
                    "reference_role_pack_priority": [],
                    "reference_role_pack_prefer_unique_sources": True,
                    "reference_role_pack_required_roles": [],
                    "reference_role_pack_missing_roles": [],
                    "brand_prelude": "",
                    "material_prompt_snippet": "",
                    "reference_role_pack_snippet": "",
                    "inspiration_doctrine": "",
                },
                "reference_context": {
                    "passed_reference_paths": [],
                    "all_context_refs": [],
                    "missing_required_roles": [],
                },
                "execution": {
                    "model": "flux-2-pro",
                    "aspect_ratio": "1:1",
                    "reference_tags": [],
                },
                "checks": {"blocking": [], "warnings": []},
                "critique_policy": {"blocks_generation": True},
            }

            def fake_run(cmd, env=None, capture_output=True, text=True):
                out_file = Path(cmd[cmd.index("-o") + 1])
                out_file.write_bytes(b"\x89PNG\r\n")
                class Result:
                    returncode = 0
                    stdout = ""
                    stderr = ""
                return Result()

            def fake_run_auto_brand_review(current_brand_dir, version_id):
                manifest = load_manifest(current_brand_dir)
                entry = manifest["versions"][version_id]
                self.assertTrue(str(entry.get("agent_review_path") or "").endswith(f"{version_id}-agent-review.json"))
                out = Path(current_brand_dir) / "reviews" / f"{version_id}-auto-review.md"
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text("ok\n")
                return str(out), True

            with patch("brand_gen.generation_flow.subprocess.run", side_effect=fake_run), \
                 patch("brand_gen.generation_flow.validate_brand_workspace_dir", return_value=brand_dir), \
                 patch("brand_gen.generation_flow.stage_reference_assets", return_value=[]), \
                 patch("brand_gen.generation_flow.write_agent_visual_review_packet", return_value=({}, brand_dir / "reviews" / "v001-agent-review.json")), \
                 patch("brand_gen.generation_flow.run_auto_brand_review", side_effect=fake_run_auto_brand_review), \
                 patch("brand_gen.generation_flow.append_run_event"), \
                 patch("brand_gen.generation_flow.persist_generated_asset_to_blackboard"), \
                 patch("brand_gen.generation_flow.generate_compare_board"), \
                 patch("brand_gen.generation_flow.load_brand_memory", return_value=(None, None, {}, {})):
                version_id = execute_generation_scratchpad(payload)

            manifest = load_manifest(brand_dir)
            self.assertEqual(version_id, "v001")
            self.assertTrue(str(manifest["versions"]["v001"].get("agent_review_path") or "").endswith("v001-agent-review.json"))
            self.assertTrue(str(manifest["versions"]["v001"].get("auto_review_path") or "").endswith("v001-auto-review.md"))

    def test_base_image_reference_context_tracks_authoritative_vs_transport_paths(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            brand_dir = Path(tmpdir).resolve()
            base_image = brand_dir / "base.png"
            mark = brand_dir / "mark.png"
            base_image.write_bytes(b"\x89PNG\r\n")
            mark.write_bytes(b"\x89PNG\r\n")
            args = type(
                "Args",
                (),
                {
                    "material_type": "social",
                    "tag": "social",
                    "prompt": "Create a mark-led social card.",
                    "plan": "",
                    "image": [str(mark)],
                    "reference_dir": None,
                    "mode": "reference",
                    "generation_mode": "image",
                    "profile": None,
                    "identity": None,
                    "skip_extraction": False,
                    "refresh_reference_analysis": False,
                    "disable_brand_guardrails": False,
                    "motion_reference": None,
                    "model": None,
                    "aspect_ratio": None,
                    "resolution": None,
                    "duration": None,
                    "preset": None,
                    "negative_prompt": None,
                    "style": None,
                    "make_gif": False,
                    "base_image": str(base_image),
                    "source_version": None,
                    "branch_id": None,
                    "parent_branch_id": None,
                    "selected_direction_id": None,
                    "motion_mode": None,
                    "character_orientation": None,
                    "keep_original_sound": False,
                },
            )()
            plan = {"material_type": "social", "mode": "reference", "brand_anchor_policy": {"logo_mode": "required"}}
            with patch("brand_gen.generation_flow.load_brand_memory", return_value=(brand_dir / "brand-profile.json", brand_dir / "brand-identity.json", {"brand_assets": {"icon": str(mark)}}, {"brand_assets": {"icon": str(mark)}})), \
                 patch("brand_gen.generation_flow.ensure_reference_analysis", return_value={"reference_set_hash": "abc", "warnings": [], "per_image": []}), \
                 patch("brand_gen.generation_flow.build_effective_prompt", return_value={
                     "material_prompt_key": "social",
                     "material_prompt_variant": "default",
                     "reference_role_pack": [{"role": "product_truth", "path": str(base_image), "source_name": "base"}],
                     "reference_role_pack_paths": [],
                     "reference_role_pack_motion_paths": [],
                     "reference_role_pack_required_roles": ["product_truth"],
                     "reference_role_pack_missing_required_roles": [],
                     "reference_role_pack_priority": ["product_truth", "application"],
                     "reference_role_pack_prefer_unique_sources": True,
                     "reference_role_assignment_warnings": [],
                     "token_block": "",
                     "resolved_prompt": "Create a mark-led social card.",
                 }), \
                 patch("brand_gen.generation_flow.persist_inspiration_source_selection", return_value=([], "")), \
                 patch("brand_gen.generation_flow.resolve_default_model", return_value="flux-2-pro"), \
                 patch("brand_gen.generation_flow.resolve_default_aspect_ratio", return_value="1:1"), \
                 patch("brand_gen.generation_flow.review_prompt_architecture", return_value={"refined_prompt": "refined", "execution_prompt": "exec", "recommendations": [], "issues": []}), \
                 patch("brand_gen.generation_flow.check_inspiration_pipeline_status", return_value={"ok": True, "warnings": [], "suggestions": []}):
                payload = __import__("brand_gen.generation_flow", fromlist=["assemble_generation_scratchpad"]).assemble_generation_scratchpad(
                    args,
                    brand_dir=brand_dir,
                    plan_wrapper={},
                    plan=plan,
                )

            ref_ctx = payload["reference_context"]
            self.assertEqual(ref_ctx["base_image_reference_path"], str(base_image.resolve()))
            self.assertEqual(ref_ctx["authoritative_reference_paths"], [str(base_image.resolve())])
            self.assertEqual(ref_ctx["model_transport_reference_paths"], [])

    def test_scratchpad_persists_only_selected_inspiration_sources(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            brand_dir = Path(tmpdir).resolve()
            args = type(
                "Args",
                (),
                {
                    "material_type": "social",
                    "tag": "social",
                    "prompt": "Create a Sage social card.",
                    "plan": "",
                    "image": [],
                    "reference_dir": None,
                    "mode": "hybrid",
                    "generation_mode": "image",
                    "profile": None,
                    "identity": None,
                    "skip_extraction": False,
                    "refresh_reference_analysis": False,
                    "disable_brand_guardrails": False,
                    "motion_reference": None,
                    "model": None,
                    "aspect_ratio": None,
                    "resolution": None,
                    "duration": None,
                    "preset": None,
                    "negative_prompt": None,
                    "style": None,
                    "make_gif": False,
                    "base_image": None,
                    "source_version": None,
                    "branch_id": None,
                    "parent_branch_id": None,
                    "selected_direction_id": None,
                    "motion_mode": None,
                    "character_orientation": None,
                    "keep_original_sound": False,
                },
            )()
            selected = [{"source_key": "pentagram", "source_name": "Pentagram"}]
            all_sources = selected + [{"source_key": "gretel-work", "source_name": "Gretel"}]
            plan = {
                "material_type": "social",
                "mode": "hybrid",
                "selected_inspiration_sources": selected,
                "inspiration_board": {"direction_id": "direction_123"},
            }
            persisted_records: list[dict] = []

            def fake_persist(_brand_dir, source_records, **_kwargs):
                persisted_records.extend(source_records)
                return ["reference_selected"], "board.json"

            with patch("brand_gen.generation_flow.load_brand_memory", return_value=(brand_dir / "brand-profile.json", brand_dir / "brand-identity.json", {}, {})), \
                 patch("brand_gen.generation_flow.ensure_reference_analysis", return_value={"reference_set_hash": "abc", "warnings": [], "per_image": []}), \
                 patch("brand_gen.generation_flow.build_effective_prompt", return_value={
                     "material_prompt_key": "social",
                     "material_prompt_variant": "default",
                     "reference_role_pack": [],
                     "reference_role_pack_paths": [],
                     "reference_role_pack_motion_paths": [],
                     "reference_role_pack_required_roles": [],
                     "reference_role_pack_missing_required_roles": [],
                     "reference_role_pack_priority": [],
                     "reference_role_pack_prefer_unique_sources": True,
                     "reference_role_assignment_warnings": [],
                     "token_block": "",
                     "resolved_prompt": "Create a Sage social card.",
                     "selected_inspiration_source_records": selected,
                     "selected_inspiration_ids": ["pentagram"],
                     "inspiration_source_records": all_sources,
                 }), \
                 patch("brand_gen.generation_flow.persist_inspiration_source_selection", side_effect=fake_persist), \
                 patch("brand_gen.generation_flow.resolve_default_model", return_value="flux-2-pro"), \
                 patch("brand_gen.generation_flow.resolve_default_aspect_ratio", return_value="1:1"), \
                 patch("brand_gen.generation_flow.review_prompt_architecture", return_value={"refined_prompt": "refined", "execution_prompt": "exec", "recommendations": [], "issues": []}), \
                 patch("brand_gen.generation_flow.check_inspiration_pipeline_status", return_value={"ok": True, "warnings": [], "suggestions": []}):
                payload = __import__("brand_gen.generation_flow", fromlist=["assemble_generation_scratchpad"]).assemble_generation_scratchpad(
                    args,
                    brand_dir=brand_dir,
                    plan_wrapper={},
                    plan=plan,
                )

            self.assertEqual(persisted_records, selected)
            self.assertEqual(payload["selected_inspiration_ids"], ["reference_selected"])
            self.assertEqual(payload["prompt_context"]["selected_inspiration_ids"], ["reference_selected"])
            self.assertEqual(payload["prompt_context"]["selected_inspiration_source_records"], selected)


class StructuralAutoCriticTests(unittest.TestCase):
    """Tests for build_structural_auto_critic P2 hardening."""

    def _base_payload(self, material_type="social", **plan_overrides):
        plan = {"brand_anchor_policy": {}, **plan_overrides}
        return {
            "material_type": material_type,
            "plan": plan,
            "reference_context": {"passed_reference_paths": [], "all_context_refs": []},
            "prompt_review": {},
            "checks": {"blocking": [], "warnings": []},
        }

    def test_social_no_seed_no_truth_is_p2(self):
        """Social with no prompt_seed and no product_truth_expression triggers P2."""
        payload = self._base_payload()
        review = build_structural_auto_critic(payload)
        self.assertTrue(any("no prompt seed" in msg for msg in review["p2"]))

    def test_social_with_prompt_seed_no_p2(self):
        """Social with a prompt_seed does not trigger the P2."""
        payload = self._base_payload(prompt_seed="Governance vote in progress")
        review = build_structural_auto_critic(payload)
        self.assertFalse(any("no prompt seed" in msg for msg in review["p2"]))

    def test_social_with_product_truth_but_no_seed_triggers_softer_p2(self):
        """Social with product_truth but no prompt_seed triggers the softer P2."""
        payload = self._base_payload(product_truth_expression="Real governance vote")
        review = build_structural_auto_critic(payload)
        self.assertTrue(any("no prompt seed or purpose" in msg for msg in review["p2"]))

    def test_social_with_product_truth_and_purpose_no_p2(self):
        """Social with product_truth + purpose does not trigger P2."""
        payload = self._base_payload(
            product_truth_expression="Real governance vote",
            purpose="Show Sage as a working protocol",
        )
        review = build_structural_auto_critic(payload)
        self.assertFalse(any("no prompt seed" in msg for msg in review["p2"]))

    def test_social_with_refs_no_p2(self):
        """Social with passed refs does not trigger the P2 even without seed."""
        payload = self._base_payload()
        payload["reference_context"]["passed_reference_paths"] = ["/some/ref.png"]
        review = build_structural_auto_critic(payload)
        self.assertFalse(any("no prompt seed" in msg for msg in review["p2"]))

    def test_non_proof_sensitive_material_no_p2(self):
        """Non-proof-sensitive material (concept-illustration) doesn't trigger P2."""
        payload = self._base_payload(material_type="concept-illustration")
        review = build_structural_auto_critic(payload)
        self.assertFalse(any("no prompt seed" in msg for msg in review["p2"]))

    def test_interface_material_still_triggers_p1(self):
        """Interface material without refs still triggers the existing P1."""
        payload = self._base_payload(material_type="browser-illustration")
        review = build_structural_auto_critic(payload)
        self.assertTrue(any("Product-led material" in msg for msg in review["p1"]))


class AutoFeedbackCaptureTests(unittest.TestCase):
    """Tests for auto_capture_generation_feedback and auto_capture_vlm_feedback."""

    def test_p1_creates_negative_example(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            brand_dir = Path(tmpdir)
            entry = {"material_type": "social", "model": "flux-2-pro"}
            critic = {"p1": ["Product-led material has no proof refs"], "p2": [], "p3": []}
            auto_capture_generation_feedback(brand_dir, "v001", entry, critic)
            memory = load_iteration_memory(brand_dir)
            self.assertEqual(len(memory["negative_examples"]), 1)
            self.assertIn("Auto-critic", memory["negative_examples"][0]["summary"])
            self.assertEqual(memory["negative_examples"][0]["score"], 1)

    def test_p2_creates_negative_example(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            brand_dir = Path(tmpdir)
            entry = {"material_type": "social", "model": "flux-2-pro"}
            critic = {"p1": [], "p2": ["No prompt seed"], "p3": []}
            auto_capture_generation_feedback(brand_dir, "v001", entry, critic)
            memory = load_iteration_memory(brand_dir)
            self.assertEqual(len(memory["negative_examples"]), 1)
            self.assertEqual(memory["negative_examples"][0]["score"], 2)

    def test_p3_creates_material_note(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            brand_dir = Path(tmpdir)
            entry = {"material_type": "social", "model": "flux-2-pro"}
            critic = {"p1": [], "p2": [], "p3": ["Reference analysis unavailable"]}
            auto_capture_generation_feedback(brand_dir, "v001", entry, critic)
            memory = load_iteration_memory(brand_dir)
            self.assertEqual(len(memory["negative_examples"]), 0)
            social_notes = memory["material_notes"].get("social", [])
            self.assertTrue(any("P3:" in note for note in social_notes))

    def test_clean_critic_no_memory_change(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            brand_dir = Path(tmpdir)
            entry = {"material_type": "social"}
            critic = {"p1": [], "p2": [], "p3": [], "clean": ["Passed"]}
            auto_capture_generation_feedback(brand_dir, "v001", entry, critic)
            self.assertFalse((brand_dir / "iteration-memory.json").exists())

    def test_vlm_p1_creates_negative_example(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            brand_dir = Path(tmpdir)
            entry = {"material_type": "social"}
            vlm = {"vlm_available": True, "approved": False, "p1": ["Garbled text"], "p2": [],
                    "text_accuracy": 0.2, "hallucinated_elements": ["phantom button"]}
            auto_capture_vlm_feedback(brand_dir, "v001", entry, vlm)
            memory = load_iteration_memory(brand_dir)
            self.assertEqual(len(memory["negative_examples"]), 1)
            summary = memory["negative_examples"][0]["summary"]
            self.assertIn("VLM critique", summary)
            self.assertIn("text_accuracy=0.2", summary)
            self.assertIn("hallucinated=phantom button", summary)

    def test_vlm_approved_creates_positive_example(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            brand_dir = Path(tmpdir)
            entry = {"material_type": "social"}
            vlm = {"vlm_available": True, "approved": True, "p1": [], "p2": [],
                    "palette_match": 0.92}
            auto_capture_vlm_feedback(brand_dir, "v001", entry, vlm)
            memory = load_iteration_memory(brand_dir)
            self.assertEqual(len(memory["positive_examples"]), 1)
            summary = memory["positive_examples"][0]["summary"]
            self.assertIn("VLM approved", summary)
            self.assertIn("palette=0.92", summary)

    def test_vlm_unavailable_no_capture(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            brand_dir = Path(tmpdir)
            entry = {"material_type": "social"}
            vlm = {"vlm_available": False, "approved": False, "p1": ["Fake"]}
            auto_capture_vlm_feedback(brand_dir, "v001", entry, vlm)
            self.assertFalse((brand_dir / "iteration-memory.json").exists())
