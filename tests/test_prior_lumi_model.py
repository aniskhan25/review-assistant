"""Opt-in Qwen prior-use regressions with synthetic proposal evidence."""
import os
import unittest

from app.configuration import review_registry, load_policy
from app.ingestion import document
from app.semantic_checks import assess


@unittest.skipUnless(os.environ.get('RUN_LOCAL_QWEN_TESTS') == '1',
                     'Requires staged local Qwen weights and Apple Metal')
class PriorLumiModelTests(unittest.TestCase):
    def test_prior_use_is_about_the_stack_not_completion_of_new_experiments(self):
        from app.local_mlx import model_fingerprint
        from app.mlx_backend import MLXBackend
        from app.security import install_network_guard

        install_network_guard()
        backend = MLXBackend('models/decision-4b/model', model_fingerprint('models/decision-4b'))
        registry = review_registry(os.environ.get('PRIOR_LUMI_TEST_PROFILE', 'FAST_LANE'))
        question = registry['questions']['code_previously_installed']
        cases = [
            ('The proposed PyTorch/PEFT stack is already proven on LUMI-G in our earlier '
             'Playground project using the LUMI AI Factory ROCm container. We measured '
             'inference throughput and LoRA training performance on LUMI. This new project '
             'will use that same stack for new datasets and model experiments.', 'YES'),
            ('This workflow completed a successful test on LUMI-G. '
             'We will tune performance and extend the experiments during this allocation.', 'YES'),
            ('We received a previous LUMI allocation but never installed or ran this '
             'application. Initial porting and validation on LUMI are planned.', 'NO'),
            ('Our workflow has run only on NVIDIA hardware. We plan to install and '
             'port it to LUMI-G using ROCm for the first time.', 'NO'),
        ]
        cases.extend([
            ('The proposed evaluation build v0.1 will be implemented and benchmarked on LUMI-G. '
             'Planned stack: Python, a PyTorch ROCm build, Transformers and scikit-learn; '
             'dependency versions will be pinned after LUMI compatibility testing. '
             'This build identifier is not a completed release. We will package the '
             'environment after compatibility tests.', 'NO'),
            ('An institutional AI system and local prototype already exist. This Playground '
             'project will develop an evaluation build for LUMI-G using a planned ROCm stack. '
             'The team will test LUMI compatibility and compare to the local baseline.', 'NO'),
        ])
        for index, (text, expected) in enumerate(cases):
            with self.subTest(case=index):
                state = {'registry': registry, 'policy': load_policy(), 'facts': {},
                         'document': document([{'page': 1, 'text': 'Code details\n' + text}])}
                decision = assess(state, backend, 'code_previously_installed', question, '')
                self.assertEqual(decision['answer'], expected)
                self.assertEqual(decision['status'], 'AGGREGATED')
                self.assertGreaterEqual(decision['confidence'], state['policy']['high_confidence'])
                self.assertGreaterEqual(decision['margin'], state['policy']['minimum_margin'])
