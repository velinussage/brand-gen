"""M3 tests for scoring/dataset.py and scoring/calibration.py.

Concurrent-write stress test guards against the fcntl.flock invariant.
Deterministic partition test guards against PYTHONHASHSEED drift.
Kappa math tests guard against sign/weight regressions.
"""
from __future__ import annotations

import json
import tempfile
import threading
import unittest
from types import SimpleNamespace
from pathlib import Path

from brand_gen.commands.review import _maybe_log_disagreement
from brand_gen.scoring.calibration import (
    compute_agreement_stats,
    raw_agreement_rate,
    score_pairs_from_disagreement_records,
    weighted_cohen_kappa,
)
from brand_gen.scoring.dataset import (
    agreement_bucket,
    append_disagreement,
    compute_partition,
    disagreement_dataset_path,
    iter_disagreements,
    load_disagreements,
    partition_split_observed,
)


class TestComputePartition(unittest.TestCase):
    def test_deterministic(self):
        # Same input must always produce same output across calls (and
        # would need to across processes/hosts — that's why we use sha256
        # instead of Python's built-in hash()).
        self.assertEqual(compute_partition("v121"), compute_partition("v121"))
        self.assertEqual(compute_partition("v118"), compute_partition("v118"))

    def test_returns_one_of_two_tags(self):
        for vid in ("v001", "v123", "v456", "v789", "experimental-a"):
            tag = compute_partition(vid)
            self.assertIn(tag, ("scorer_training", "iteration_memory"))

    def test_roughly_balanced_over_many_ids(self):
        # sha256 mod 2 should give ~50/50 over a large sample
        counts = {"scorer_training": 0, "iteration_memory": 0}
        for i in range(1000):
            vid = f"v{i:04d}"
            counts[compute_partition(vid)] += 1
        # Should be within 40/60
        self.assertGreater(counts["scorer_training"], 400)
        self.assertGreater(counts["iteration_memory"], 400)

    def test_empty_version_id(self):
        # Safe default behavior: no crash on empty string
        self.assertIn(compute_partition(""), ("scorer_training", "iteration_memory"))


class TestAgreementBucket(unittest.TestCase):
    def test_bucket_boundaries(self):
        self.assertEqual(agreement_bucket(0), "strong_agreement")
        self.assertEqual(agreement_bucket(1), "mild_disagreement")
        self.assertEqual(agreement_bucket(2), "strong_disagreement")
        self.assertEqual(agreement_bucket(3), "calibration_failure")
        self.assertEqual(agreement_bucket(4), "calibration_failure")


class TestAppendAndLoad(unittest.TestCase):
    def test_append_creates_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            brand_dir = Path(tmpdir)
            path = disagreement_dataset_path(brand_dir)
            self.assertFalse(path.exists())
            record = {"version_id": "v001", "agent_score": 4, "user_score": 1,
                      "delta": 3, "agreement_bucket": "calibration_failure",
                      "partition_tag": compute_partition("v001")}
            append_disagreement(brand_dir, record)
            self.assertTrue(path.exists())

    def test_append_adds_schema_version(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            brand_dir = Path(tmpdir)
            append_disagreement(brand_dir, {"version_id": "v001"})
            loaded = load_disagreements(brand_dir)
            self.assertEqual(loaded[0]["schema_version"], 1)
            self.assertEqual(loaded[0]["partition_algo"], "sha256-mod2")

    def test_load_recent_first(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            brand_dir = Path(tmpdir)
            for i in range(5):
                append_disagreement(brand_dir, {"version_id": f"v{i:03d}"})
            loaded = load_disagreements(brand_dir)
            # Most recent first
            self.assertEqual(loaded[0]["version_id"], "v004")
            self.assertEqual(loaded[-1]["version_id"], "v000")

    def test_load_with_limit(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            brand_dir = Path(tmpdir)
            for i in range(10):
                append_disagreement(brand_dir, {"version_id": f"v{i:03d}"})
            loaded = load_disagreements(brand_dir, limit=3)
            self.assertEqual(len(loaded), 3)

    def test_filter_by_partition_tag(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            brand_dir = Path(tmpdir)
            append_disagreement(brand_dir, {"version_id": "v1", "partition_tag": "scorer_training"})
            append_disagreement(brand_dir, {"version_id": "v2", "partition_tag": "iteration_memory"})
            append_disagreement(brand_dir, {"version_id": "v3", "partition_tag": "scorer_training"})
            training = load_disagreements(brand_dir, partition_tag="scorer_training")
            self.assertEqual(len(training), 2)
            for r in training:
                self.assertEqual(r["partition_tag"], "scorer_training")

    def test_filter_by_material_type(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            brand_dir = Path(tmpdir)
            append_disagreement(brand_dir, {"version_id": "v1", "material_type": "landing-hero"})
            append_disagreement(brand_dir, {"version_id": "v2", "material_type": "brand-scene"})
            loaded = load_disagreements(brand_dir, material_type="landing-hero")
            self.assertEqual(len(loaded), 1)
            self.assertEqual(loaded[0]["version_id"], "v1")

    def test_filter_by_bucket(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            brand_dir = Path(tmpdir)
            append_disagreement(brand_dir, {"version_id": "v1", "agreement_bucket": "strong_disagreement"})
            append_disagreement(brand_dir, {"version_id": "v2", "agreement_bucket": "strong_agreement"})
            loaded = load_disagreements(brand_dir, bucket="strong_disagreement")
            self.assertEqual(len(loaded), 1)

    def test_malformed_line_skipped(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            brand_dir = Path(tmpdir)
            path = disagreement_dataset_path(brand_dir)
            path.parent.mkdir(parents=True, exist_ok=True)
            # Write one valid line, one malformed line, one valid line
            path.write_text('{"version_id": "v1"}\nnot json\n{"version_id": "v2"}\n')
            loaded = load_disagreements(brand_dir)
            # Should have loaded 2 records, skipped the malformed line
            self.assertEqual(len(loaded), 2)

    def test_partition_split_observed(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            brand_dir = Path(tmpdir)
            for i in range(10):
                append_disagreement(brand_dir, {
                    "version_id": f"v{i:03d}",
                    "partition_tag": compute_partition(f"v{i:03d}"),
                })
            records = load_disagreements(brand_dir)
            split = partition_split_observed(records)
            total = split["scorer_training"] + split["iteration_memory"] + split["unknown"]
            self.assertEqual(total, 10)

    def test_feedback_disagreement_preserves_reflection_ready_fields(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            brand_dir = Path(tmpdir)
            critique = {
                "rubric_version": "v2.1",
                "scorer_version": "dspy-gepa-candidate-7",
                "provider": "test-vlm",
                "overall_score": 4,
                "axis_scores": {"brand_fit": 4, "product_truth": 3},
                "axis_rationales": {
                    "brand_fit": "Palette and restraint align with the identity.",
                    "product_truth": "Readable product proof is present but too small.",
                },
                "disqualifier_triggered": True,
                "disqualifier_rule": "invented-copy",
                "why_user_might_dislike_if_polished": "It looks finished but invents a headline the user never approved.",
                "before_after_diffs": [
                    {
                        "principle": "copy fidelity",
                        "before": "invented visible headline",
                        "after": "use deterministic approved copy only",
                    }
                ],
            }
            entry = {
                "score": 2,
                "status": "rejected",
                "material_type": "social-card",
                "mode": "hybrid",
                "model": "test-model",
                "workflow_id": "wf-gepa",
                "vlm_critique": critique,
            }

            _maybe_log_disagreement(
                brand_dir,
                "v123",
                entry,
                SimpleNamespace(notes="Text is wrong even though the layout is polished."),
            )

            loaded = load_disagreements(brand_dir)
            self.assertEqual(len(loaded), 1)
            record = loaded[0]
            self.assertEqual(record["axis_scores"], critique["axis_scores"])
            self.assertEqual(record["axis_rationales"], critique["axis_rationales"])
            self.assertTrue(record["disqualifier_triggered"])
            self.assertEqual(record["disqualifier_rule"], "invented-copy")
            self.assertEqual(
                record["why_user_might_dislike_if_polished"],
                "It looks finished but invents a headline the user never approved.",
            )
            self.assertEqual(record["before_after_diffs"], critique["before_after_diffs"])


class TestConcurrentAppend(unittest.TestCase):
    """The critical test: fcntl.flock must guard against line interleaving.

    10 threads × 50 appends each = 500 valid JSONL lines. Without the
    lock this would frequently produce corrupted lines under load.
    """

    def test_concurrent_writes_no_corruption(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            brand_dir = Path(tmpdir)
            n_threads = 10
            n_per_thread = 50
            errors: list[Exception] = []

            def worker(thread_id: int):
                try:
                    for i in range(n_per_thread):
                        append_disagreement(brand_dir, {
                            "version_id": f"t{thread_id}-{i:03d}",
                            "thread_id": thread_id,
                            "sequence": i,
                            # Big-ish record to increase chance of tearing
                            "padding": "x" * 200,
                        })
                except Exception as exc:
                    errors.append(exc)

            threads = [threading.Thread(target=worker, args=(t,)) for t in range(n_threads)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            self.assertEqual(errors, [], f"thread errors: {errors}")
            records = load_disagreements(brand_dir)
            # Every line must parse as a full dict — if fcntl failed,
            # we'd see corrupt partial lines that json.loads() rejects
            # and load_disagreements silently skips. The count tells us.
            self.assertEqual(len(records), n_threads * n_per_thread,
                             f"expected {n_threads * n_per_thread} records, got {len(records)}")


class TestIterDisagreements(unittest.TestCase):
    def test_empty_brand(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            records = list(iter_disagreements(Path(tmpdir)))
            self.assertEqual(records, [])

    def test_yields_in_write_order(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            brand_dir = Path(tmpdir)
            for i in range(5):
                append_disagreement(brand_dir, {"version_id": f"v{i:03d}"})
            ids = [r["version_id"] for r in iter_disagreements(brand_dir)]
            self.assertEqual(ids, ["v000", "v001", "v002", "v003", "v004"])


class TestRawAgreementRate(unittest.TestCase):
    def test_perfect_agreement(self):
        self.assertEqual(raw_agreement_rate([1, 2, 3, 4, 5], [1, 2, 3, 4, 5]), 1.0)

    def test_no_agreement(self):
        self.assertEqual(raw_agreement_rate([1, 2, 3, 4, 5], [5, 4, 3, 2, 1]), 0.2)

    def test_empty_inputs(self):
        self.assertEqual(raw_agreement_rate([], []), 0.0)

    def test_length_mismatch_raises(self):
        with self.assertRaises(ValueError):
            raw_agreement_rate([1, 2], [1, 2, 3])


class TestWeightedKappa(unittest.TestCase):
    def test_perfect_agreement(self):
        kappa = weighted_cohen_kappa([1, 2, 3, 4, 5], [1, 2, 3, 4, 5])
        self.assertAlmostEqual(kappa, 1.0)

    def test_inverse_agreement(self):
        kappa = weighted_cohen_kappa([1, 2, 3, 4, 5], [5, 4, 3, 2, 1])
        self.assertLess(kappa, -0.5)

    def test_partial_agreement(self):
        # Minor disagreement on a couple points — should be positive but < 1
        kappa = weighted_cohen_kappa([1, 2, 3, 4, 5], [1, 2, 4, 4, 5])
        self.assertGreater(kappa, 0)
        self.assertLess(kappa, 1.0)

    def test_empty_inputs(self):
        self.assertEqual(weighted_cohen_kappa([], []), 0.0)

    def test_length_mismatch_raises(self):
        with self.assertRaises(ValueError):
            weighted_cohen_kappa([1, 2], [1, 2, 3])

    def test_out_of_range_values_skipped(self):
        # Scores outside 1-5 should be silently dropped, not crash
        kappa = weighted_cohen_kappa([1, 2, 99, 4, 5], [1, 2, 3, 4, 5])
        # With the out-of-range pair dropped, kappa on the rest is still high
        self.assertGreater(kappa, 0.8)


class TestScorePairsFromRecords(unittest.TestCase):
    def test_extracts_paired_scores(self):
        records = [
            {"agent_score": 4, "user_score": 4},
            {"agent_score": 3, "user_score": 1},
            {"agent_score": 5, "user_score": 5},
        ]
        agent, user = score_pairs_from_disagreement_records(records)
        self.assertEqual(agent, [4, 3, 5])
        self.assertEqual(user, [4, 1, 5])

    def test_skips_records_missing_either_score(self):
        records = [
            {"agent_score": 4, "user_score": 4},
            {"agent_score": 3},  # missing user
            {"user_score": 2},  # missing agent
            {"agent_score": 5, "user_score": 5},
        ]
        agent, user = score_pairs_from_disagreement_records(records)
        self.assertEqual(len(agent), 2)
        self.assertEqual(len(user), 2)


class TestComputeAgreementStats(unittest.TestCase):
    def test_empty_records(self):
        stats = compute_agreement_stats([])
        self.assertEqual(stats["n_total"], 0)
        self.assertEqual(stats["n_scored"], 0)
        self.assertEqual(stats["raw_agreement"], 0.0)
        self.assertEqual(stats["weighted_kappa"], 0.0)

    def test_mixed_records(self):
        records = [
            {"agent_score": 4, "user_score": 4, "agreement_bucket": "strong_agreement", "material_type": "landing-hero"},
            {"agent_score": 4, "user_score": 1, "agreement_bucket": "calibration_failure", "material_type": "landing-hero"},
            {"agent_score": 3, "user_score": 2, "agreement_bucket": "mild_disagreement", "material_type": "brand-scene"},
        ]
        stats = compute_agreement_stats(records)
        self.assertEqual(stats["n_total"], 3)
        self.assertEqual(stats["n_scored"], 3)
        self.assertEqual(stats["n_per_bucket"]["strong_agreement"], 1)
        self.assertEqual(stats["n_per_bucket"]["calibration_failure"], 1)
        self.assertEqual(stats["n_per_material"]["landing-hero"], 2)
        self.assertEqual(stats["n_per_material"]["brand-scene"], 1)


if __name__ == "__main__":
    unittest.main()
