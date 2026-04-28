from __future__ import annotations

import json
import unittest
from pathlib import Path


class ReferenceRolePackConfigTests(unittest.TestCase):
    def test_role_pack_source_keys_exist_in_brand_source_registry(self):
        role_packs = json.loads(Path("data/reference_role_packs.json").read_text())
        registry = json.loads(Path("data/brand_example_sources.json").read_text())
        source_keys = {str(source.get("key") or "") for source in registry.get("sources", [])}
        referenced: set[str] = set()
        for pack in (role_packs.get("packs") or {}).values():
            if not isinstance(pack, dict):
                continue
            for role, values in pack.items():
                if role in {"priority", "required_roles"} or not isinstance(values, list):
                    continue
                referenced.update(str(value) for value in values if str(value).strip())
        self.assertEqual(sorted(referenced - source_keys), [])


if __name__ == "__main__":
    unittest.main()
