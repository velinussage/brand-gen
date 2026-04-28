from __future__ import annotations

import unittest
from dataclasses import asdict

from brand_gen.pipeline_types import AestheticExperiment, MaterialPlan, VariantSpec, plan_draft_from_dict


class AestheticExperimentTests(unittest.TestCase):
    def test_branch_id_is_deterministic(self) -> None:
        a = AestheticExperiment.stable_branch_id(
            brand_key="sage",
            material_type="social",
            seed="show reusable skills",
            iteration=1,
        )
        b = AestheticExperiment.stable_branch_id(
            brand_key="sage",
            material_type="social",
            seed="show reusable skills",
            iteration=1,
        )
        self.assertEqual(a, b)

    def test_validation_rejects_bad_variant_state(self) -> None:
        with self.assertRaises(ValueError):
            AestheticExperiment(branch_id="br_a", archetype="", capsule="", design_variance=5, variants=[])
        with self.assertRaises(ValueError):
            VariantSpec(variant_id="v", design_variance=11)

    def test_material_plan_roundtrip_preserves_experiment(self) -> None:
        experiment = AestheticExperiment(
            branch_id="br_abc",
            parent_branch_id="br_parent",
            archetype="editorial",
            capsule="warm-editorial-system-illustration",
            design_variance=6,
            variants=[
                VariantSpec(
                    variant_id="warm-editorial-system-illustration",
                    label="Warm editorial",
                    archetype="editorial",
                    capsule="warm-editorial-system-illustration",
                    design_variance=6,
                )
            ],
            selection_rationale="best material fit",
        )
        draft = plan_draft_from_dict(
            {
                "plan": {
                    "material_type": "social",
                    "mode": "hybrid",
                    "branch_id": experiment.branch_id,
                    "parent_branch_id": experiment.parent_branch_id,
                    "selected_direction_id": "warm-editorial-system-illustration",
                    "experiment": experiment.to_dict(),
                }
            },
            "wf",
        )
        self.assertIsInstance(draft.plan.experiment, AestheticExperiment)
        self.assertEqual(draft.plan.experiment.to_dict(), experiment.to_dict())


if __name__ == "__main__":
    unittest.main()
