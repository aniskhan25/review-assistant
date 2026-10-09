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
