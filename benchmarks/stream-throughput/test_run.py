#!/usr/bin/env python3
"""Small contract tests for benchmark acceptance aggregation."""

import runpy
import unittest
from pathlib import Path


summarize = runpy.run_path(str(Path(__file__).with_name("run.py")))["summarize"]


def sample(**changes):
    result = {
        "status": "pass",
        "backend": "rustdv-direct",
        "transactions": 1000,
        "cycles": 1210,
        "digest": "abc",
        "trace_digest": "def",
        "cycles_per_s": 100.0,
        "elapsed_s": 12.1,
    }
    result.update(changes)
    return result


class SummaryTests(unittest.TestCase):
    def test_repeated_results_must_match(self):
        for changed in (
            {"transactions": 999},
            {"cycles": 1209},
            {"digest": "bad"},
            {"trace_digest": "bad"},
        ):
            with self.subTest(changed=changed), self.assertRaisesRegex(
                RuntimeError, "repeat 2 changed"
            ):
                summarize([sample(), sample(**changed)])

    def test_timing_variation_is_allowed(self):
        result = summarize(
            [sample(cycles_per_s=100.0), sample(cycles_per_s=120.0)]
        )
        self.assertEqual(result["median_cycles_per_s"], 110.0)


if __name__ == "__main__":
    unittest.main()
