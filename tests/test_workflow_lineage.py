import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MCP_DIR = REPO_ROOT / 'mcp'
if str(MCP_DIR) not in sys.path:
    sys.path.insert(0, str(MCP_DIR))

from brand_iterate import (  # type: ignore
    collect_workflow_artifacts,
    get_workflow_lineage,
    load_blackboard,
    resolve_workflow_id,
    save_blackboard,
)


class WorkflowLineageTests(unittest.TestCase):
    def test_resolve_workflow_id_prefers_existing(self):
        self.assertEqual(resolve_workflow_id({'workflow_id': 'wf-1'}), 'wf-1')
        self.assertEqual(resolve_workflow_id({'meta': {'workflow_id': 'wf-2'}}), 'wf-2')
        self.assertTrue(resolve_workflow_id({}))

    def test_collect_workflow_artifacts_groups_saved_payloads(self):
        with tempfile.TemporaryDirectory() as tmp:
            brand_dir = Path(tmp)
            (brand_dir / 'scratchpads' / 'plan-drafts').mkdir(parents=True)
            (brand_dir / 'scratchpads' / 'plan-critiques').mkdir(parents=True)
            (brand_dir / 'scratchpads' / 'generation').mkdir(parents=True)
            wf = 'wf-abc123'
            payloads = [
                (brand_dir / 'scratchpads' / 'plan-drafts' / 'a.json', {'schema_type': 'plan_draft', 'workflow_id': wf, 'plan': {'material_type': 'social', 'mode': 'hybrid'}}),
                (brand_dir / 'scratchpads' / 'plan-critiques' / 'b.json', {'schema_type': 'plan_critique', 'workflow_id': wf, 'plan': {'material_type': 'social', 'mode': 'hybrid'}}),
                (brand_dir / 'scratchpads' / 'generation' / 'c.json', {'schema_type': 'generation_scratchpad', 'workflow_id': wf, 'material_type': 'social', 'workflow_mode': 'hybrid'}),
                (brand_dir / 'scratchpads' / 'generation' / 'd.json', {'schema_type': 'generation_scratchpad', 'workflow_id': 'other'}),
            ]
            for path, payload in payloads:
                path.write_text(json.dumps(payload))

            grouped = collect_workflow_artifacts(brand_dir, wf)
            self.assertEqual(len(grouped['plan_drafts']), 1)
            self.assertEqual(len(grouped['plan_critiques']), 1)
            self.assertEqual(len(grouped['generation_scratchpads']), 1)
            self.assertTrue(grouped['generation_scratchpads'][0]['path'].endswith('c.json'))

    def test_get_workflow_lineage_filters_blackboard_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            brand_dir = Path(tmp)
            board = load_blackboard(brand_dir)
            board['decisions'] = [
                {'workflow_id': 'wf-1', 'decision': 'drafted'},
                {'workflow_id': 'wf-2', 'decision': 'ignored'},
            ]
            board['generated_assets'] = [
                {'workflow_id': 'wf-1', 'version': 'v1'},
                {'workflow_id': 'wf-2', 'version': 'v2'},
            ]
            save_blackboard(brand_dir, board)
            loaded = load_blackboard(brand_dir)
            lineage = get_workflow_lineage(loaded, 'wf-1')
            self.assertEqual(len(lineage['decisions']), 1)
            self.assertEqual(len(lineage['assets']), 1)
            self.assertEqual(lineage['assets'][0]['version'], 'v1')


if __name__ == '__main__':
    unittest.main()
