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
