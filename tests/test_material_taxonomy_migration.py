from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from brand_gen.material_taxonomy_migration import (
    find_saved_workspaces,
    migrate_generation_scratchpad_payload,
    migrate_manifest_payload,
    migrate_plan_payload,
    migrate_set_manifest_payload,
    migrate_workspace,
    report_workspace_deprecated_usage,
    report_workspaces_deprecated_usage,
)
from brand_gen.plan_builder import default_alignment_questions, default_idea_tracks
from brand_gen.runtime_models import SOCIAL_SPECS


class MaterialTaxonomyMigrationTests(unittest.TestCase):
    def test_plan_migration_prefers_system_explainer_for_old_concept_type(self):
        plan = {
            "material_type": "concept-illustration",
            "purpose": "Explain how routing works",
            "product_truth_expression": "one visible routing mechanic",
            "brand_anchor_policy": {"purpose": "old purpose"},
            "role_pack": {"material_key": "concept_illustration"},
        }
        out, changes = migrate_plan_payload(plan)
        self.assertGreater(changes, 0)
        self.assertEqual(out["material_type"], "system-explainer-illustration")
        self.assertEqual(out["requested_material_type"], "concept-illustration")
        self.assertTrue(out["material_type_resolution"]["changed"])
        self.assertEqual(out["brand_anchor_policy"]["material_key"], "system_explainer_illustration")

    def test_plan_migration_can_route_old_pattern_system_to_pattern_board(self):
        plan = {
            "material_type": "pattern-system",
            "briefing": "Exploration board with a few variants for internal review",
        }
        out, changes = migrate_plan_payload(plan)
        self.assertGreater(changes, 0)
        self.assertEqual(out["material_type"], "pattern-board")

    def test_set_manifest_migrates_items(self):
        payload = {
            "materials": [
                {"material_type": "campaign-poster"},
                {"material_type": "bumper-animation"},
                {"material_type": "pattern-system", "briefing": "one subtle site background pattern"},
            ]
        }
        out, changes = migrate_set_manifest_payload(payload)
        self.assertEqual(changes, 3)
        self.assertEqual(out["materials"][0]["material_type"], "proof-poster")
        self.assertEqual(out["materials"][1]["material_type"], "feature-animation")
        self.assertEqual(out["materials"][2]["material_type"], "site-pattern-tile")

    def test_manifest_payload_migrates_entries(self):
        payload = {
            "versions": {
                "v1": {"material_type": "brand-scene", "notes": "worldbuilding still"},
                "v2": {"material_type": "campaign-poster"},
            }
        }
        out, changes = migrate_manifest_payload(payload)
        self.assertEqual(changes, 2)
        self.assertEqual(out["versions"]["v1"]["material_type"], "illustrated-brand-world")
        self.assertEqual(out["versions"]["v1"]["legacy_material_type"], "brand-scene")
        self.assertEqual(out["versions"]["v2"]["material_type"], "proof-poster")

    def test_generation_scratchpad_migrates_material_type(self):
        payload = {
            "schema_type": "generation_scratchpad",
            "material_type": "concept-illustration",
            "purpose": "Explain one system mechanic",
            "prompt_context": {"material_type": "concept-illustration"},
        }
        out, changes = migrate_generation_scratchpad_payload(payload)
        self.assertEqual(changes, 1)
        self.assertEqual(out["material_type"], "system-explainer-illustration")
        self.assertEqual(out["prompt_context"]["material_type"], "system-explainer-illustration")

    def test_workspace_migration_writes_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            brand_dir = Path(tmp)
            (brand_dir / "plans").mkdir(parents=True, exist_ok=True)
            (brand_dir / "sets").mkdir(parents=True, exist_ok=True)
            (brand_dir / "scratchpads" / "plan-drafts").mkdir(parents=True, exist_ok=True)
            (brand_dir / "scratchpads" / "generation").mkdir(parents=True, exist_ok=True)

            (brand_dir / "manifest.json").write_text(json.dumps({"versions": {"v1": {"material_type": "campaign-poster"}}}))
            (brand_dir / "plans" / "old.json").write_text(json.dumps({"material_type": "concept-illustration", "purpose": "Explain one routing mechanic"}))
            (brand_dir / "sets" / "set.json").write_text(json.dumps({"materials": [{"material_type": "pattern-system"}]}))
            (brand_dir / "scratchpads" / "plan-drafts" / "draft.json").write_text(json.dumps({"schema_type": "plan_draft", "plan": {"material_type": "brand-scene"}}))
            (brand_dir / "scratchpads" / "generation" / "gen.json").write_text(json.dumps({"schema_type": "generation_scratchpad", "material_type": "concept-illustration", "purpose": "Explain routing"}))

            dry = migrate_workspace(brand_dir, apply=False)
            self.assertGreaterEqual(dry["changes"], 5)

            applied = migrate_workspace(brand_dir, apply=True)
            self.assertGreaterEqual(applied["changes"], 5)

            manifest = json.loads((brand_dir / "manifest.json").read_text())
            plan = json.loads((brand_dir / "plans" / "old.json").read_text())
            set_manifest = json.loads((brand_dir / "sets" / "set.json").read_text())
            draft = json.loads((brand_dir / "scratchpads" / "plan-drafts" / "draft.json").read_text())
            scratchpad = json.loads((brand_dir / "scratchpads" / "generation" / "gen.json").read_text())

            self.assertEqual(manifest["versions"]["v1"]["material_type"], "proof-poster")
            self.assertEqual(plan["material_type"], "system-explainer-illustration")
            self.assertEqual(set_manifest["materials"][0]["material_type"], "site-pattern-tile")
            self.assertEqual(draft["plan"]["material_type"], "illustrated-brand-world")
            self.assertEqual(scratchpad["material_type"], "system-explainer-illustration")

    def test_find_saved_workspaces_discovers_repo_and_brand_gen_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "brands" / "alpha").mkdir(parents=True)
            (root / ".brand-gen" / "brands" / "beta").mkdir(parents=True)
            (root / ".brand-gen" / "sessions" / "sess-1" / "brand-materials").mkdir(parents=True)

            saved_only = find_saved_workspaces(root, root / ".brand-gen")
            self.assertEqual({p.name for p in saved_only}, {"alpha", "beta"})

            with_sessions = find_saved_workspaces(root, root / ".brand-gen", include_sessions=True)
            self.assertTrue(any(str(p).endswith("brand-materials") for p in with_sessions))

    def test_report_workspace_deprecated_usage_ignores_legacy_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            brand_dir = Path(tmp)
            (brand_dir / "plans").mkdir(parents=True, exist_ok=True)
            (brand_dir / "manifest.json").write_text(json.dumps({
                "versions": {
                    "v1": {
                        "material_type": "campaign-poster",
                        "legacy_material_type": "campaign-poster",
                        "material_type_resolution": {"requested": "campaign-poster", "resolved": "proof-poster"},
                    }
                }
            }))
            (brand_dir / "plans" / "old.json").write_text(json.dumps({
                "material_type": "concept-illustration",
                "requested_material_type": "concept-illustration",
            }))

            report = report_workspace_deprecated_usage(brand_dir)
            self.assertEqual(report["deprecated_usage_count"], 2)
            self.assertEqual(report["deprecated_material_types"]["campaign-poster"]["count"], 1)
            self.assertEqual(report["deprecated_material_types"]["concept-illustration"]["count"], 1)
            self.assertEqual(report["by_file_class"]["manifest"]["count"], 1)
            self.assertEqual(report["by_file_class"]["plans"]["count"], 1)

    def test_report_workspaces_aggregates_results(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            a = root / "a"
            b = root / "b"
            a.mkdir()
            b.mkdir()
            (a / "manifest.json").write_text(json.dumps({"versions": {"v1": {"material_type": "campaign-poster"}}}))
            (b / "manifest.json").write_text(json.dumps({"versions": {"v1": {"material_type": "campaign-poster"}, "v2": {"material_type": "brand-scene"}}}))

            report = report_workspaces_deprecated_usage([a, b])
            self.assertEqual(report["deprecated_usage_count"], 3)
            self.assertEqual(report["aggregate"]["campaign-poster"]["count"], 2)
            self.assertEqual(report["aggregate"]["brand-scene"]["count"], 1)
            self.assertEqual(report["aggregate_by_file_class"]["manifest"]["count"], 3)


class MaterialTaxonomyPlanningSupportTests(unittest.TestCase):
    def test_new_material_types_have_idea_tracks(self):
        self.assertGreaterEqual(len(default_idea_tracks("system-explainer-illustration")), 2)
        self.assertGreaterEqual(len(default_idea_tracks("proof-poster")), 2)
        self.assertGreaterEqual(len(default_idea_tracks("site-pattern-tile")), 2)

    def test_new_material_types_have_alignment_questions(self):
        questions = default_alignment_questions("editorial-metaphor-illustration")
        self.assertTrue(any("single metaphor" in item.lower() for item in questions))
        questions = default_alignment_questions("pattern-board")
        self.assertTrue(any("internal review" in item.lower() or "coherent system" in item.lower() for item in questions))

    def test_old_social_specs_are_marked_deprecated(self):
        self.assertTrue(SOCIAL_SPECS["concept-illustration"]["label"].startswith("[DEPRECATED]"))
        self.assertIn("Prefer system-explainer-illustration", SOCIAL_SPECS["concept-illustration"]["notes"])
        self.assertTrue(SOCIAL_SPECS["brand-scene"]["label"].startswith("[DEPRECATED]"))
        self.assertIn("Prefer illustrated-brand-world", SOCIAL_SPECS["brand-scene"]["notes"])


if __name__ == "__main__":
    unittest.main()
