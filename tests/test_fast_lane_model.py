"""Opt-in real Qwen regressions; no private proposal content is committed."""

import os

import unittest

from app.configuration import load_policy, review_registry
from app.decision import decide


CASES = [
    ("Our preliminary scientific results outperform earlier models. The code currently runs "
     "on NVIDIA GPUs and Intel Gaudi. Official PyTorch ROCm builds exist. We will adapt the "
     "workflow to LUMI-G. The budget includes installation, ROCm validation and measurement "
     "of throughput and scaling. The project will produce a validated AMD configuration.", "NO"),
    ("This workflow has been tested successfully on Intel Gaudi. ROCm support is planned.", "NO"),
    ("This workflow has been tested successfully on NVIDIA. ROCm support is planned.", "NO"),
    ("We have never used LUMI or Try and Buy. We will first validate the workload on AMD "
     "using the supported PyTorch ROCm container during this project.", "NO"),
    ("We have never used LUMI. This same pipeline completed a 100-step run on a local AMD "
     "MI210 with ROCm, measuring 120 samples per second.", "YES"),
    ("The proposed training pipeline completed 200 steps successfully on LUMI-G. "
     "We will still tune performance during the requested allocation.", "YES"),
    ("During Try and Buy, this same workflow ran successfully on LUMI-G; "
     "500 steps completed at 80 samples per second.", "YES"),
    ("Our CTO ran an unrelated model on unspecified CSC hardware. The proposed workload "
     "has never run on LUMI or AMD/ROCm; first validation is planned for this allocation.", "NO"),
    ("The proposal says this workflow has never run on AMD and also says it ran successfully "
     "on LUMI-G yesterday. These claims conflict and cannot be reconciled.", "UNKNOWN"),
]


@unittest.skipUnless(os.environ.get("RUN_LOCAL_QWEN_TESTS") == "1",
                     "Requires the staged local Qwen model and Apple Metal")
class FastLaneModelTests(unittest.TestCase):
    def test_completed_run_and_platform_must_belong_to_same_test(self):
        from app.local_mlx import model_fingerprint
        from app.mlx_backend import MLXBackend
        from app.security import install_network_guard

        install_network_guard()
        backend = MLXBackend("models/decision-4b/model", model_fingerprint("models/decision-4b"))
        question = review_registry("FAST_LANE")["questions"]["fast_lane_validated"]
        policy = load_policy()
        for index, (text, expected) in enumerate(CASES):
            with self.subTest(case=index, expected=expected):
                decision = decide(backend, "fast_lane_validated", question,
                                  [{"id": "synthetic", "page": 1, "section": "Code details", "text": text}], policy)
                self.assertEqual(decision["status"], "OK")
                self.assertEqual(decision["answer"], expected)
                if expected != "UNKNOWN":
                    self.assertGreaterEqual(decision["confidence"], policy["high_confidence"])
                    self.assertGreaterEqual(decision["margin"], policy["minimum_margin"])
