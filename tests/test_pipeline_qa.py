import json
import tempfile
import unittest
from pathlib import Path

from brand_gen.pipeline_qa import build_pipeline_qa_report, write_pipeline_qa_report


class PipelineQaTests(unittest.TestCase):
    def _write_manifest(self, brand_dir: Path, *, scratchpad_path: Path, material_type: str = "social") -> None:
        manifest = {
            "versions": {
                "v001": {
                    "material_type": material_type,
                    "mode": "hybrid",
                    "model": "recraft-v4",
                    "files": ["v001-social.png"],
                    "generation_scratchpad": str(scratchpad_path),
                }
            }
        }
        (brand_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")

    def test_pipeline_qa_report_contains_findings_not_template_placeholders(self):
        with tempfile.TemporaryDirectory() as tmp:
            brand_dir = Path(tmp)
            scratchpad = {
                "material_type": "social",
                "workflow_mode": "hybrid",
                "profile_path": str(brand_dir / "brand-profile.json"),
                "identity_path": str(brand_dir / "brand-identity.json"),
                "checks": {"blocking": [], "warnings": []},
                "plan": {
                    "material_type": "social",
                    "brand_anchor_policy": {
                        "logo_mode": "required",
                        "product_truth_expression": "a clearly branded product claim",
                    },
                },
                "plan_critique": {
                    "plan_validation": {"ok": True, "errors": [], "warnings": []},
                    "checks": {"blocking": [], "warnings": []},
                },
                "prompt_review": {
                    "issues": ["Resolved prompt is too long for an interface material."],
                    "recommendations": ["Shorten the prompt."],
                },
                "reference_context": {
                    "passed_reference_paths": [],
                    "selected_role_names": ["composition"],
                },
                "prompt_context": {
                    "reference_role_pack": [{"role": "composition", "source_key": "clay"}],
                    "reference_analysis": {
                        "per_image": [{"vlm_available": False, "confidence": 0.31}],
                        "warnings": ["Reference set pulls in multiple directions; keep inspiration translated."],
                        "consistency_score": 0.31,
                    },
                },
            }
            scratchpad_path = brand_dir / "scratchpads" / "generation" / "v001.json"
            scratchpad_path.parent.mkdir(parents=True, exist_ok=True)
            scratchpad_path.write_text(json.dumps(scratchpad, indent=2) + "\n")
            self._write_manifest(brand_dir, scratchpad_path=scratchpad_path)

            report, markdown = build_pipeline_qa_report(brand_dir, "v001")

            self.assertEqual(report["auto_review_kind"], "pipeline_qa")
            self.assertIn("# Pipeline QA report — v001", markdown)
            self.assertIn("This report is deterministic pipeline QA only.", markdown)
            self.assertIn("Reference analysis ran in deterministic-only mode", markdown)
            self.assertIn("Policy/setup risk:", markdown)
            self.assertIn("decorative-only", markdown)
            self.assertIn("Resolved prompt is too long for an interface material.", markdown)
            self.assertNotIn("[Critical message, fidelity, or balance issues.]", markdown)
            self.assertNotIn("[Important clarity, hierarchy, or composition issues.]", markdown)

    def test_pipeline_qa_records_blocking_bypass_if_metadata_still_blocking(self):
        with tempfile.TemporaryDirectory() as tmp:
            brand_dir = Path(tmp)
            scratchpad = {
                "material_type": "browser-illustration",
                "workflow_mode": "hybrid",
                "checks": {"blocking": ["Missing required role refs: product_truth"], "warnings": []},
                "plan": {
                    "material_type": "browser-illustration",
                    "brand_anchor_policy": {"logo_mode": "preferred"},
                },
                "plan_critique": {
                    "plan_validation": {"ok": True, "errors": [], "warnings": []},
                    "checks": {"blocking": ["Plan critique blocking issue"], "warnings": []},
                },
                "prompt_review": {"issues": [], "recommendations": []},
                "reference_context": {"passed_reference_paths": []},
                "prompt_context": {"reference_role_pack": [{"role": "composition", "source_key": "clay"}]},
            }
            scratchpad_path = brand_dir / "scratchpads" / "generation" / "v001.json"
            scratchpad_path.parent.mkdir(parents=True, exist_ok=True)
            scratchpad_path.write_text(json.dumps(scratchpad, indent=2) + "\n")
            self._write_manifest(brand_dir, scratchpad_path=scratchpad_path, material_type="browser-illustration")

            report, output = write_pipeline_qa_report(brand_dir, "v001")
            markdown = output.read_text()

            self.assertEqual(report["status"], "blocked")
            self.assertTrue(report["proceeded_despite_blocking"])
            self.assertIn("Generation produced an artifact even though blocking critique/scratchpad issues are still present", markdown)
            self.assertTrue(output.name.endswith("-auto-review.md"))

    def test_pipeline_qa_surfaces_recorded_bypass_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            brand_dir = Path(tmp)
            scratchpad = {
                "material_type": "social",
                "workflow_mode": "hybrid",
                "checks": {"blocking": ["Missing required role refs: product_truth"], "warnings": []},
                "critique_policy": {
                    "critique_mode": "strict",
                    "blocking_policy": "allow_with_recorded_bypass",
                    "entrypoint": "pipeline",
                    "has_blocking_issues": True,
                    "blocks_generation": False,
                    "bypass_requested": True,
                    "bypass_recorded": True,
                    "bypass_reason": "pipeline ran with --allow-blocking despite blocking scratchpad findings.",
                    "bypass_recorded_at": "2026-03-17T00:00:00",
                },
                "plan": {"material_type": "social", "brand_anchor_policy": {"logo_mode": "preferred"}},
                "plan_critique": {
                    "plan_validation": {"ok": True, "errors": [], "warnings": []},
                    "checks": {"blocking": [], "warnings": []},
                },
                "prompt_review": {"issues": [], "recommendations": []},
                "reference_context": {"passed_reference_paths": []},
                "prompt_context": {"reference_role_pack": []},
            }
            scratchpad_path = brand_dir / "scratchpads" / "generation" / "v001.json"
            scratchpad_path.parent.mkdir(parents=True, exist_ok=True)
            scratchpad_path.write_text(json.dumps(scratchpad, indent=2) + "\n")
            self._write_manifest(brand_dir, scratchpad_path=scratchpad_path)

            report, markdown = build_pipeline_qa_report(brand_dir, "v001")

            self.assertEqual(report["critique_mode"], "strict")
            self.assertEqual(report["blocking_policy"], "allow_with_recorded_bypass")
            self.assertTrue(report["bypass_recorded"])
            self.assertIn("- Critique mode: strict", markdown)
            self.assertIn("- Blocking policy: allow_with_recorded_bypass", markdown)
            self.assertIn("Generation proceeded under an explicitly recorded bypass", markdown)

    def test_pipeline_qa_reports_separate_visual_critique_when_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            brand_dir = Path(tmp)
            scratchpad = {
                "material_type": "social",
                "workflow_mode": "hybrid",
                "checks": {"blocking": [], "warnings": []},
                "plan": {"material_type": "social", "brand_anchor_policy": {"logo_mode": "preferred"}},
                "plan_critique": {
                    "plan_validation": {"ok": True, "errors": [], "warnings": []},
                    "checks": {"blocking": [], "warnings": []},
                },
                "prompt_review": {"issues": [], "recommendations": []},
                "reference_context": {"passed_reference_paths": []},
                "prompt_context": {"reference_role_pack": []},
            }
            scratchpad_path = brand_dir / "scratchpads" / "generation" / "v001.json"
            scratchpad_path.parent.mkdir(parents=True, exist_ok=True)
            scratchpad_path.write_text(json.dumps(scratchpad, indent=2) + "\n")
            manifest = {
                "versions": {
                    "v001": {
                        "material_type": "social",
                        "mode": "hybrid",
                        "model": "recraft-v4",
                        "files": ["v001-social.png"],
                        "generation_scratchpad": str(scratchpad_path),
                        "vlm_critique_path": str(brand_dir / "reviews" / "v001-vlm-critique.json"),
                        "vlm_critique": {"approved": True, "provider": "agent"},
                    }
                }
            }
            (brand_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")

            report, markdown = build_pipeline_qa_report(brand_dir, "v001")

            self.assertTrue(report["visual_review_performed"])
            self.assertEqual(report["visual_review_provider"], "agent")
            self.assertIn("- Separate visual critique: yes", markdown)
            self.assertIn("Separate visual critique artifact: agent", markdown)

    def test_pipeline_qa_surfaces_pending_agent_review_packet_when_visual_review_not_submitted(self):
        with tempfile.TemporaryDirectory() as tmp:
            brand_dir = Path(tmp)
            scratchpad = {
                "material_type": "social",
                "workflow_mode": "hybrid",
                "checks": {"blocking": [], "warnings": []},
                "plan": {"material_type": "social", "brand_anchor_policy": {"logo_mode": "preferred"}},
                "plan_critique": {
                    "plan_validation": {"ok": True, "errors": [], "warnings": []},
                    "checks": {"blocking": [], "warnings": []},
                },
                "prompt_review": {"issues": [], "recommendations": []},
                "reference_context": {"passed_reference_paths": []},
                "prompt_context": {"reference_role_pack": []},
            }
            scratchpad_path = brand_dir / "scratchpads" / "generation" / "v001.json"
            scratchpad_path.parent.mkdir(parents=True, exist_ok=True)
            scratchpad_path.write_text(json.dumps(scratchpad, indent=2) + "\n")
            manifest = {
                "versions": {
                    "v001": {
                        "material_type": "social",
                        "mode": "hybrid",
                        "model": "recraft-v4",
                        "files": ["v001-social.png"],
                        "generation_scratchpad": str(scratchpad_path),
                        "agent_review_path": str(brand_dir / "reviews" / "v001-agent-review.json"),
                    }
                }
            }
            (brand_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")

            report, markdown = build_pipeline_qa_report(brand_dir, "v001")

            self.assertFalse(report["visual_review_performed"])
            self.assertTrue(report["visual_review_pending"])
            self.assertIn("Agent review packet is ready", markdown)

    def test_pipeline_qa_flags_announcement_card_screenshot_conflict(self):
        with tempfile.TemporaryDirectory() as tmp:
            brand_dir = Path(tmp)
            scratchpad = {
                "material_type": "announcement-card",
                "workflow_mode": "reference",
                "raw_prompt": "Announcement card with a preserved screenshot proof panel and exact product crop.",
                "execution": {"base_image": "/tmp/base.png"},
                "checks": {"blocking": [], "warnings": []},
                "plan": {"material_type": "announcement-card", "brand_anchor_policy": {"logo_mode": "preferred"}},
                "plan_critique": {
                    "plan_validation": {"ok": True, "errors": [], "warnings": []},
                    "checks": {"blocking": [], "warnings": []},
                },
                "prompt_review": {"issues": [], "recommendations": []},
                "reference_context": {"passed_reference_paths": ["/tmp/base.png"]},
                "prompt_context": {
                    "reference_role_pack": [{"role": "product_truth", "source_key": "base-image", "path": "/tmp/base.png"}]
                },
            }
            scratchpad_path = brand_dir / "scratchpads" / "generation" / "v001.json"
            scratchpad_path.parent.mkdir(parents=True, exist_ok=True)
            scratchpad_path.write_text(json.dumps(scratchpad, indent=2) + "\n")
            self._write_manifest(brand_dir, scratchpad_path=scratchpad_path, material_type="announcement-card")

            report, markdown = build_pipeline_qa_report(brand_dir, "v001")

            self.assertTrue(any("announcement-card is headline/illustration-led" in item for item in report["policy_setup_risks"]))
            self.assertIn("tiny deterministic chip", markdown)

    def test_pipeline_qa_explains_base_image_truth_without_aux_transport_refs(self):
        with tempfile.TemporaryDirectory() as tmp:
            brand_dir = Path(tmp)
            scratchpad = {
                "material_type": "social",
                "workflow_mode": "reference",
                "execution": {"base_image": "/tmp/base.png"},
                "checks": {"blocking": [], "warnings": []},
                "plan": {"material_type": "social", "brand_anchor_policy": {"logo_mode": "preferred"}},
                "plan_critique": {
                    "plan_validation": {"ok": True, "errors": [], "warnings": []},
                    "checks": {"blocking": [], "warnings": []},
                },
                "prompt_review": {"issues": [], "recommendations": []},
                "reference_context": {
                    "authoritative_reference_paths": ["/tmp/base.png"],
                    "model_transport_reference_paths": [],
                    "base_image_reference_path": "/tmp/base.png",
                },
                "prompt_context": {"reference_role_pack": [{"role": "product_truth", "path": "/tmp/base.png"}]},
            }
            scratchpad_path = brand_dir / "scratchpads" / "generation" / "v001.json"
            scratchpad_path.parent.mkdir(parents=True, exist_ok=True)
            scratchpad_path.write_text(json.dumps(scratchpad, indent=2) + "\n")
            self._write_manifest(brand_dir, scratchpad_path=scratchpad_path)

            report, markdown = build_pipeline_qa_report(brand_dir, "v001")

            self.assertIn("authoritative reference asset", markdown)
            self.assertIn("base image carried product truth directly", markdown)
            self.assertIn("authoritative reference asset", "\n".join(report["clean"]))

    def test_pipeline_qa_uses_explicit_reference_analysis_signals_when_payload_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            brand_dir = Path(tmp)
            scratchpad = {
                "material_type": "social",
                "workflow_mode": "hybrid",
                "reference_analysis_mode": "deterministic_only",
                "reference_analysis_confidence": "low",
                "checks": {"blocking": [], "warnings": []},
                "plan": {"material_type": "social", "brand_anchor_policy": {"logo_mode": "preferred"}},
                "plan_critique": {
                    "plan_validation": {"ok": True, "errors": [], "warnings": []},
                    "checks": {"blocking": [], "warnings": []},
                },
                "prompt_review": {"issues": [], "recommendations": []},
                "reference_context": {"passed_reference_paths": []},
                "prompt_context": {"reference_role_pack": []},
            }
            scratchpad_path = brand_dir / "scratchpads" / "generation" / "v001.json"
            scratchpad_path.parent.mkdir(parents=True, exist_ok=True)
            scratchpad_path.write_text(json.dumps(scratchpad, indent=2) + "\n")
            self._write_manifest(brand_dir, scratchpad_path=scratchpad_path)

            report, markdown = build_pipeline_qa_report(brand_dir, "v001")

            self.assertEqual(report["reference_analysis_mode"], "deterministic_only")
            self.assertEqual(report["reference_analysis_confidence"], "low")
            self.assertIn("- Reference-analysis mode: deterministic_only", markdown)

    def test_pipeline_qa_surfaces_reference_role_assignment_warnings(self):
        with tempfile.TemporaryDirectory() as tmp:
            brand_dir = Path(tmp)
            scratchpad = {
                "material_type": "social",
                "workflow_mode": "hybrid",
                "checks": {"blocking": [], "warnings": []},
                "plan": {
                    "material_type": "social",
                    "brand_anchor_policy": {"logo_mode": "preferred"},
                    "role_pack": {
                        "role_assignment_warnings": [
                            "Ref 'Library Live Viewport' looks like product proof but is assigned to `composition`; keep the explicit pick if intentional, but consider assigning a `product_truth` role so real UI/workflow truth stays authoritative."
                        ]
                    },
                },
                "plan_critique": {
                    "plan_validation": {"ok": True, "errors": [], "warnings": []},
                    "checks": {"blocking": [], "warnings": []},
                },
                "prompt_review": {"issues": [], "recommendations": []},
                "reference_context": {"passed_reference_paths": []},
                "prompt_context": {
                    "reference_role_pack": [{"role": "composition", "source_name": "Library Live Viewport"}],
                    "reference_role_assignment_warnings": [
                        "Ref 'Library Live Viewport' looks like product proof but is assigned to `composition`; keep the explicit pick if intentional, but consider assigning a `product_truth` role so real UI/workflow truth stays authoritative."
                    ],
                },
            }
            scratchpad_path = brand_dir / "scratchpads" / "generation" / "v001.json"
            scratchpad_path.parent.mkdir(parents=True, exist_ok=True)
            scratchpad_path.write_text(json.dumps(scratchpad, indent=2) + "\n")
            self._write_manifest(brand_dir, scratchpad_path=scratchpad_path)

            report, markdown = build_pipeline_qa_report(brand_dir, "v001")

            self.assertTrue(any("looks like product proof" in item for item in report["policy_setup_risks"]))
            self.assertIn("looks like product proof", markdown)

    def test_pipeline_qa_flags_logo_asset_and_product_truth_setup_risks(self):
        with tempfile.TemporaryDirectory() as tmp:
            brand_dir = Path(tmp)
            scratchpad = {
                "material_type": "landing-hero",
                "workflow_mode": "hybrid",
                "profile_path": str(brand_dir / "brand-profile.json"),
                "identity_path": str(brand_dir / "brand-identity.json"),
                "checks": {"blocking": [], "warnings": []},
                "plan": {
                    "material_type": "landing-hero",
                    "brand_anchor_policy": {
                        "logo_mode": "required",
                        "product_truth_expression": "real product proof such as a UI or CLI moment",
                    },
                },
                "plan_critique": {
                    "plan_validation": {"ok": True, "errors": [], "warnings": []},
                    "checks": {"blocking": [], "warnings": []},
                },
                "prompt_review": {"issues": [], "recommendations": []},
                "reference_context": {"passed_reference_paths": []},
                "prompt_context": {
                    "reference_role_pack": [{"role": "composition", "source_name": "Clay"}],
                },
            }
            (brand_dir / "brand-profile.json").write_text(json.dumps({"brand_assets": {}}, indent=2) + "\n")
            (brand_dir / "brand-identity.json").write_text(json.dumps({}, indent=2) + "\n")
            scratchpad_path = brand_dir / "scratchpads" / "generation" / "v001.json"
            scratchpad_path.parent.mkdir(parents=True, exist_ok=True)
            scratchpad_path.write_text(json.dumps(scratchpad, indent=2) + "\n")
            self._write_manifest(brand_dir, scratchpad_path=scratchpad_path, material_type="landing-hero")

            with unittest.mock.patch("brand_gen.pipeline_qa.load_brand_memory", return_value=(None, None, {"brand_assets": {}}, {})):
                report, markdown = build_pipeline_qa_report(brand_dir, "v001")

            self.assertTrue(any("lacks a selected `product_truth` role" in item for item in report["policy_setup_risks"]))
            self.assertTrue(any("requires an approved logo/mark asset" in item for item in report["policy_setup_risks"]))
            self.assertTrue(any("not carrying passed product-truth references" in item for item in report["policy_setup_risks"]))
            self.assertIn("Policy/setup risk: material policy requires an approved logo/mark asset", markdown)


if __name__ == "__main__":
    unittest.main()
