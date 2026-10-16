from copy import deepcopy
from app.configuration import load_config, load_policy
from app.decision import decide
from app.ingestion import document
from app.retrieval import retrieve
from tests.helpers import review


def test_supported_environment_retrieval_excludes_irrelevant_and_historical_sections():
    q = load_config('questions.json')['questions']['official_rocm_builds_available']
    doc = document([{'page':1, 'text': "Code Details and Feasibility\nWe use LUMI's supported PyTorch ROCm containers, FSDP and vLLM on ROCm. Additional Python packages will be installed during onboarding.\nPrivacy & Data Governance\nLUMI ROCm AMD build installed dependency environment"}])
    evidence = retrieve(doc['evidence'],q)
    assert evidence and all('Privacy' not in e['section'] for e in evidence)
    assert any('supported PyTorch' in e['text'] for e in evidence)
    assert q['evidence_first'] is False
    assert 'not required' in q['criteria']['YES']


def test_missing_environment_is_unknown_not_negative_and_saved_question_stays_old():
    q = load_config('questions.json')['questions']['official_rocm_builds_available']
    class Backend:
        name, version = 'fixture', '1'
        prompts = []
        def decide(self, text, question):
            self.prompts.append(question['instructions'])
            return {'YES':0., 'NO':0., 'UNKNOWN':1.}
    d = decide(Backend(), 'official_rocm_builds_available', q, [], load_policy())
    assert d['answer'] == 'UNKNOWN' and d['status'] == 'NO_EVIDENCE_FOUND'
    old = deepcopy(q)
    old['version']='4.4'
    old['instructions']='Verify every dependency build.'
    state=review()
    state['registry']['questions']['official_rocm_builds_available']=old
    assert state['registry']['questions']['official_rocm_builds_available']['instructions'] == 'Verify every dependency build.'
    from app.review import analyze
    backend = Backend()
    analyze(state, backend)
    assert 'Verify every dependency build.' in backend.prompts
    assert state['decisions']['official_rocm_builds_available']['question_version'] == '4.4'
    assert q['version']=='4.6'
