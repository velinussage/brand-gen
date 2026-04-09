import tempfile
import unittest
from pathlib import Path

from brand_gen.inspiration_board import (
    build_inspiration_board_summary,
    load_inspiration_board,
    persist_inspiration_source_selection,
    persist_plan_inspiration_board,
)


class InspirationBoardTests(unittest.TestCase):
    def test_persist_plan_inspiration_board_records_typed_objects(self):
        with tempfile.TemporaryDirectory() as tmp:
            brand_dir = Path(tmp)
            plan = {
                "workflow_id": "wf-plan-1",
                "material_type": "social",
                "mode": "hybrid",
                "purpose": "Show one product moment with a calm branded frame.",
                "system_mechanic": "one editorial product crop",
                "preserve": ["real product truth"],
                "push": ["clear focal hierarchy"],
                "ban": ["invented product chrome"],
                "role_pack": {
                    "selected_roles": [
                        {
                            "role": "composition",
                            "source_key": "clay-case-study",
                            "source_name": "Clay",
                            "path": "/tmp/clay.png",
                            "translation": {"summary": "Borrow composition framing only."},
                        }
                    ],
                    "missing_required_roles": [],
                    "quality_warnings": ["Composition ref is broad; keep it translated."],
                },
            }

            selection = persist_plan_inspiration_board(brand_dir, plan, workflow_id="wf-plan-1")
            board = load_inspiration_board(brand_dir)
            summary = build_inspiration_board_summary(board)

            self.assertTrue(selection["direction_id"])
            self.assertEqual(plan["selected_reference_ids"], selection["selected_reference_ids"])
            self.assertIn("Direction", summary["object_types"])
            self.assertIn("Reference", summary["object_types"])
            self.assertIn("Decision", summary["object_types"])
            self.assertIn("Constraint", summary["object_types"])
            self.assertIn("CritiqueFinding", summary["object_types"])

        # tempdir cleans up

    def test_persist_inspiration_source_selection_creates_source_refs(self):
        with tempfile.TemporaryDirectory() as tmp:
            brand_dir = Path(tmp)
            plan = {
                "workflow_id": "wf-plan-2",
                "material_type": "banner",
                "mode": "inspiration",
                "system_mechanic": "one calm field",
                "role_pack": {"selected_roles": []},
            }
            selection = persist_plan_inspiration_board(brand_dir, plan, workflow_id="wf-plan-2")
            source_ids, _ = persist_inspiration_source_selection(
                brand_dir,
                [
                    {
                        "source_key": "ramotion",
                        "source_name": "Ramotion",
                        "source_url": "https://www.ramotion.com/work",
                        "design_memory_path": "/tmp/ramotion/.design-memory",
                    }
                ],
                workflow_id="wf-plan-2",
                direction_id=selection["direction_id"],
            )
            board = load_inspiration_board(brand_dir)
            refs = [item for item in (board.get("objects") or []) if item.get("id") in source_ids]
            rels = [item for item in (board.get("relations") or []) if item.get("from_id") in source_ids]

            self.assertEqual(len(source_ids), 1)
            self.assertEqual(refs[0]["data"]["category"], "inspiration_source")
            self.assertTrue(any(item.get("type") == "supports" for item in rels))


if __name__ == "__main__":
    unittest.main()
