"""Tests for the learnings material_type → hyphen migration.

Material_type canonical form across the codebase is hyphen
(`concept-illustration`). Legacy learnings.json files were written with
underscore (`concept_illustration`) because the internal role-pack
normalizer returned underscore form. The migration rewrites
material_type fields inside known buckets to hyphen form.

Tests cover:
- A known-underscore file gets rewritten.
- A known-hyphen file is unchanged (idempotent).
- The rewrite covers both `material_type` scalar and
  `applies_to_material_types` list fields.
- Unknown bucket fields are not disturbed.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path


from scripts.migrate_learnings_material_type_hyphens import (
    migrate_entry,
    migrate_learnings_payload,
    migrate_brand,
)


class MigrateEntryTests(unittest.TestCase):
    def test_underscore_material_type_rewritten(self):
        entry = {"material_type": "concept_illustration", "text": "[concept_illustration] ..."}
        out, changes = migrate_entry(entry)
        self.assertEqual(out["material_type"], "concept-illustration")
        self.assertEqual(changes, 1)

    def test_hyphen_material_type_unchanged(self):
        entry = {"material_type": "concept-illustration", "text": "..."}
        out, changes = migrate_entry(entry)
        self.assertEqual(out["material_type"], "concept-illustration")
        self.assertEqual(changes, 0)

    def test_applies_to_list_rewritten(self):
        entry = {"applies_to_material_types": ["concept_illustration", "brand_scene"]}
        out, changes = migrate_entry(entry)
        self.assertEqual(out["applies_to_material_types"], ["concept-illustration", "brand-scene"])
        self.assertEqual(changes, 1)

    def test_other_fields_untouched(self):
        entry = {"material_type": "concept_illustration", "text": "This has underscore_words"}
        out, _ = migrate_entry(entry)
        # 'text' field must NOT be rewritten — only material-type fields
        self.assertEqual(out["text"], "This has underscore_words")


class MigratePayloadTests(unittest.TestCase):
    def test_full_payload_rewrite(self):
        payload = {
            "version": 1,
            "modelPreferences": [
                {"material_type": "concept_illustration", "text": "..."},
            ],
            "styleReferencePolicies": [
                {
                    "material_type": "brand_scene",
                    "applies_to_material_types": ["brand_scene", "other_thing"],
                },
            ],
            "failurePatterns": [
                {"material_type": "concept_illustration", "text": "..."},
                {"material_type": "concept-illustration", "text": "..."},  # already hyphen
            ],
        }
        _, changes = migrate_learnings_payload(payload)
        self.assertGreater(changes, 0)
        self.assertEqual(payload["modelPreferences"][0]["material_type"], "concept-illustration")
        self.assertEqual(payload["styleReferencePolicies"][0]["material_type"], "brand-scene")
        self.assertEqual(
            payload["styleReferencePolicies"][0]["applies_to_material_types"],
            ["brand-scene", "other-thing"],
        )
        # The already-hyphen entry still in place
        self.assertEqual(payload["failurePatterns"][1]["material_type"], "concept-illustration")

    def test_idempotent_run(self):
        payload = {
            "modelPreferences": [
                {"material_type": "concept-illustration", "text": "..."},
            ],
            "failurePatterns": [
                {"material_type": "brand-scene", "text": "..."},
            ],
        }
        _, changes_first = migrate_learnings_payload(payload)
        self.assertEqual(changes_first, 0)
        # Run again — still zero changes
        _, changes_second = migrate_learnings_payload(payload)
        self.assertEqual(changes_second, 0)


class MigrateBrandTests(unittest.TestCase):
    def test_dry_run_does_not_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            brand_dir = Path(tmp)
            payload_before = {
                "modelPreferences": [{"material_type": "concept_illustration", "text": "..."}],
            }
            (brand_dir / "learnings.json").write_text(json.dumps(payload_before))
            result = migrate_brand(brand_dir, apply=False)
            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["changes"], 1)
            # File should be unchanged on disk
            on_disk = json.loads((brand_dir / "learnings.json").read_text())
            self.assertEqual(on_disk["modelPreferences"][0]["material_type"], "concept_illustration")

    def test_apply_writes_hyphen_form(self):
        with tempfile.TemporaryDirectory() as tmp:
            brand_dir = Path(tmp)
            payload_before = {
                "modelPreferences": [{"material_type": "brand_scene", "text": "..."}],
            }
            (brand_dir / "learnings.json").write_text(json.dumps(payload_before))
            result = migrate_brand(brand_dir, apply=True)
            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["changes"], 1)
            on_disk = json.loads((brand_dir / "learnings.json").read_text())
            self.assertEqual(on_disk["modelPreferences"][0]["material_type"], "brand-scene")

    def test_missing_learnings_returns_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            brand_dir = Path(tmp)
            result = migrate_brand(brand_dir, apply=True)
            self.assertEqual(result["status"], "skipped")


if __name__ == "__main__":
    unittest.main()
