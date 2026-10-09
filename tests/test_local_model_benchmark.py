"""The candidate adapter must preserve binary direction and unknown semantics."""
from tools.benchmark_local_models import kev_record, RecordedBackend


def test_binary_maps_false_to_no_and_preserves_the_rubric():
    question = {"instructions": "Is installation reported?", "binary_evidence": True,
                "criteria": {"YES": "Installation reported", "NO": "Not reported", "UNKNOWN": "Conflicting"}}
    record, keys = kev_record("Untrusted proposal", question)
    assert keys == ["NO", "YES"]
    assert record["questions"][0]["options"] == ["no: Not reported", "yes: Installation reported"]
    assert record["state"] == "Untrusted proposal"


def test_choice_keeps_the_unknown_option():
    question = {"instructions": "Assess", "criteria": {"YES": "Supported", "NO": "Unsupported", "UNKNOWN": "Conflicting"}}
    record, keys = kev_record("Evidence", question)
    assert keys == ["YES", "NO", "UNKNOWN"]
    assert record["questions"][0]["options"][-1] == "UNKNOWN: Conflicting"


def test_input_fingerprint_excludes_outputs_and_includes_wording():
    class Backend:
        name, version = "test", "1"
        def decide(self, state, question):
            return {"YES": 1., "NO": 0., "UNKNOWN": 0.}
    backend = RecordedBackend(Backend())
    backend.decide("Evidence", {"instructions": "Question one"})
    backend.decide("Evidence", {"instructions": "Question two"})
    assert backend.calls[0]["input_sha256"] != backend.calls[1]["input_sha256"]


def test_more_prefills_cannot_offset_incorrect_prefills():
    from tools.compare_corrected_models import quality_gate
    base=dict(total=48,matching=34,wrong=2,unknown=12,ready=30,wrong_ready=1)
    other=dict(base,ready=36,wrong_ready=3)
    assert not quality_gate(dict(overall=base,per_question={'q':base}),dict(overall=other,per_question={'q':other}))


def test_overall_gain_cannot_hide_a_question_regression():
    from tools.compare_corrected_models import quality_gate
    base=dict(total=48,matching=34,wrong=2,unknown=12,ready=30,wrong_ready=1)
    improved=dict(base,matching=35,unknown=11,ready=31)
    worse=dict(base,matching=33,wrong=3)
    assert not quality_gate(dict(overall=base,per_question={'workplan':base}),dict(overall=improved,per_question={'workplan':worse}))


def test_equal_quality_can_qualify_a_faster_model():
    from tools.compare_corrected_models import quality_gate
    base=dict(total=48,matching=34,wrong=2,unknown=12,ready=30,wrong_ready=1)
    report=dict(overall=base,per_question={'q':base})
    assert quality_gate(report,report)


def test_unknown_count_is_distinct_from_review_requirements():
    from tools.compare_corrected_models import counts
    cases=[{'application_id':'synthetic','answers':{
        'software':{'gold':'YES','predicted':'YES','ready':True},
        'installed':{'gold':'YES','predicted':'NO','ready':False},
        'workplan':{'gold':'NO','predicted':'UNKNOWN','ready':False}}}]
    result=counts(cases)['overall']
    assert result == dict(total=3,matching=1,wrong=1,unknown=1,ready=1,wrong_ready=0)
