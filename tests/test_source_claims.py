from app.source_claims import source_claim


def ev(text):
    return {'id': 'ev', 'text': text}


def test_current_workload_quantity_is_literal_not_a_resource_total():
    q = {'quantity_evidence': True}
    assert source_claim(q, [ev('We will process hundreds of thousands of extracted video frames during training and benchmarking.')])['answer'] == 'YES'
    assert not source_claim(q, [ev('We request 50000 GPU hours over 3 months.')])
    assert not source_claim(q, [ev('Future deployment will process millions of video frames.')])
    assert not source_claim(q, [ev('Previous work processed 100 training samples.')])


def test_deferred_core_versions_need_two_distinct_components():
    q = {'explicit_version_deferral': True}
    torch = ev('Name and version of the code: PyTorch — version supplied by a selected release and pinned after functional training tests. Webpage and other references: docs')
    rocm = {'id': 'rocm', 'text': 'Name and version of the code: ROCm — version supplied by a selected release and pinned after environment validation. Webpage and other references: docs'}
    assert not source_claim(q, [torch])
    claim = source_claim(q, [torch, rocm])
    assert claim['answer'] == 'YES' and claim['evidence_ids'] == ['ev', 'rocm']
    assert not source_claim(q, [ev('Name and version of the code: PyTorch 2.5. We will tune the model after validation. Webpage and other references: docs')])


def test_token_multipliers_are_workload_quantities():
    assert source_claim({'quantity_evidence': True}, [ev('Training uses approximately 10 Billion tokens.')])['answer'] == 'YES'


def test_assumed_utilization_with_gcd_accounting_needs_review():
    q = {'accounting_assumption_guard': True}
    assert source_claim(q, [ev('We assume MFU of 32.5%, using 64 GCDs.')])['answer'] == 'UNKNOWN'
    assert not source_claim(q, [ev('Measured MFU is 32.5%, using 64 GCDs with verified module accounting.')])
    assert not source_claim(q, [ev('We assume MFU of 32.5%.')])


def software(kind):
    return {'software_source_check': kind, 'background_references': [{'claim': 'PyTorch and JAX support AMD.'}]}


def test_named_framework_is_not_proof_of_installation_or_exact_builds():
    evidence = [ev('Code(s) used: PyTorch 2.5') ]
    assert source_claim(software('dependencies_identified'), evidence)['answer'] == 'YES'
    assert source_claim(software('amd_path_supported'), evidence)['answer'] == 'YES'
    assert not source_claim({}, evidence)


def test_past_future_negated_or_unsupported_framework_is_not_positive_path():
    for text in ('Previous work used PyTorch.', 'Future deployment will use PyTorch.',
                 'We do not use PyTorch.', 'PyTorch cannot run on AMD.',
                 'PyTorch requires CUDA-only kernels.'):
        assert not source_claim(software('amd_path_supported'), [ev(text)])


def test_compatibility_restrictions_stay_with_model():
    for text in ('PyTorch requires CUDA-only kernels.', 'PyTorch uses custom CUDA-specific kernels.',
                 'PyTorch is not supported on AMD.', 'PyTorch uses cuDNN.',
                 'PyTorch does not require CUDA-only kernels.'):
        assert not source_claim(software('compatibility_blocker'), [ev(text)])


def test_benchmark_machine_alone_is_not_a_compatibility_restriction():
    claim = source_claim(software('compatibility_blocker'), [ev('Code: PyTorch. Benchmark measured on NVIDIA A100.')])
    assert claim['answer'] == 'NO' and claim['scope'] and not claim['quotes']


def test_current_training_steps_are_workload_evidence():
    assert source_claim({'quantity_evidence': True}, [ev('We will train for 10000 steps.')])['answer'] == 'YES'


def test_source_claim_search_is_not_limited_to_top_five_chunks():
    from app.source_claims import claim_evidence
    evidence = [dict(id=str(i), text='Technical notes ' + str(i), section='Code details', scope='proposal') for i in range(8)]
    evidence.append(dict(id='framework', text='Code(s) used: PyTorch', section='Code details', scope='proposal'))
    q = dict(software('dependencies_identified'), sections=['code'], keywords=['notes'], restrict_sections=True)
    claim = source_claim(q, claim_evidence(q, evidence, evidence[:5]))
    assert claim['evidence_ids'] == ['framework']


def test_model_parameter_size_alone_is_not_a_planned_workload():
    assert not source_claim({'quantity_evidence': True}, [ev('Execution scaled to models exceeding 30B parameters in our benchmark.')])
