import copy
import json
import http.client
import threading

import pytest

from app.aitta import AittaWriter, FORM_IDS, SUMMARY_VALUES, binding, build_input, current, validate_output, validate_input, wire_request
from app.review import prepare_review, finalize
from app.server import create_server
from app.storage import Store
from app.decision import ManualBackend
from tests.helpers import review, confirmed, TEXT


def result(payload):
    entry = lambda text, fields: {'text': text, 'assessment_fields': fields}
    return {'comments': {
        'software_gpu_capable': entry('Specific reviewed architecture explanation.', ['architecture_compatibility']),
        'code_previously_installed': entry('Specific reviewed prior-use explanation.', ['prior_installation']),
        'workplan_sufficient': entry('Specific reviewed workplan explanation.', ['workplan'])},
        'global_comment': entry('The reviewed execution strategy supports feasible use.', ['workplan']),
        'rationale': entry('The reviewed compatibility and workplan support acceptance.', ['architecture_compatibility', 'workplan']),
        'issues': []}


def generate(writer, state, classification='ACCEPT', options=None):
    preview = writer.preview(state, classification, options)
    return writer.generate(state, classification, preview['preview_hash'], options)


class Writer(AittaWriter):
    def __init__(self):
        super().__init__('synthetic-token')
        self.calls = 0

    def completion(self, payload):
        self.calls += 1
        return result(payload)


def generated():
    s = confirmed(review())
    s['writing_draft'] = generate(Writer(), s)
    prepare_review(s)
    return s


def test_generated_text_reaches_all_export_fields_only_after_final_approval():
    s = generated()
    assert s['final'] is None and current(s)
    assert s['draft_rationale'] == s['writing_draft']['rationale']['text']
    assert 'Specific reviewed workplan explanation' in s['draft']
    comments = dict(s['draft_form_comments'])
    comments['software_gpu_capable'] = 'Reviewer-edited architecture assessment.'
    out = finalize(s, 'ACCEPT', 'Reviewer-edited reason.', True,
                   global_comment=s['draft_global_comment'], form_comments=comments)
    assert 'Reviewer-edited architecture assessment.' in out['text']
    assert 'Reviewer-edited reason.' in out['text']
    assert 'Specific reviewed workplan explanation' in out['text']
    assert 'ev-' not in out['text']
    assert out['drafting']['model'] == 'Qwen/Qwen3.8-27B'
    assert out['drafting']['evidence']['rationale']
    assert out['form_comments'] == comments


def test_changed_facts_or_classification_prevent_stale_generated_export():
    s = generated()
    s['facts']['total_storage_gb']['value'] += 1
    prepare_review(s)
    assert s['writing_draft']['stale'] and not s['draft_form_comments']
    with pytest.raises(ValueError, match='out of date'):
        finalize(s, 'ACCEPT', 'Old draft', True)
    s.pop('writing_draft')
    prepare_review(s)
    assert s['draft_classification'] == 'ACCEPT'
    s = generated()
    with pytest.raises(ValueError, match='another classification'):
        finalize(s, 'REJECT', 'Changed decision', True)


def test_technical_payload_excludes_team_assessments_contacts_and_tax_identifier():
    s = confirmed(review(TEXT.replace('Code details and feasibility',
        'Code details and feasibility\nE-mail: private@example.test\nOrganization VAT number: SECRET-TAX-ID')))
    s['document']['evidence'] += [dict(id='team', scope='team', page=1, section='Code details', text='Team secret'),
                               dict(id='assessment', scope='assessment', page=1, section='Code details', text='Old assessment')]
    payload = build_input(s, 'ACCEPT')
    sent = json.dumps(payload)
    assert 'private@example.test' not in sent and 'SECRET-TAX-ID' not in sent
    assert 'Team secret' not in sent and 'Old assessment' not in sent
    assert set(payload) == {'assessment', 'generic_review'}
    assert payload['assessment']['workplan'] == 'FEASIBLE'


def test_invalid_provider_text_or_sources_cannot_be_applied():
    payload = build_input(confirmed(review()), 'ACCEPT')
    good = result(payload)
    ids = set(SUMMARY_VALUES)
    for invalid in ('foreign-id', None):
        bad = copy.deepcopy(good)
        bad['rationale']['assessment_fields'] = [invalid]
        with pytest.raises(ValueError):
            validate_output(bad, ids)
    bad = copy.deepcopy(good)
    bad['rationale']['text'] = 'See ev-1 for evidence.'
    with pytest.raises(ValueError):
        validate_output(bad, ids)
    bad = copy.deepcopy(good)
    bad['classification'] = 'REJECT'
    with pytest.raises(ValueError):
        validate_output(bad, ids)
    s = review()
    with pytest.raises(ValueError, match='Resolve review exceptions'):
        generate(Writer(), s)


def test_token_file_permissions_and_environment_do_not_enter_provenance(tmp_path, monkeypatch):
    monkeypatch.delenv('AITTA_API_KEY', raising=False)
    path = tmp_path / 'aitta.token'
    path.write_text('private-synthetic-token')
    path.chmod(0o644)
    with pytest.raises(ValueError, match='owner-only'):
        AittaWriter.from_environment(tmp_path)
    path.chmod(0o600)
    w = AittaWriter.from_environment(tmp_path)
    assert w.model == 'Qwen/Qwen3.8-27B'
    monkeypatch.setenv('AITTA_API_KEY', 'environment-synthetic-token')
    assert AittaWriter.from_environment(tmp_path)._token == 'environment-synthetic-token'


def test_generation_api_requires_explicit_send_and_preserves_decisions(tmp_path):
    store = Store(tmp_path / 'data')
    state = confirmed(review())
    store.insert(state)
    writer = Writer()
    server = create_server(store, ManualBackend(), state['policy'], 'secret', 'test-reviewer', 0, writer=writer)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    def post(action, payload):
        c = http.client.HTTPConnection('127.0.0.1', server.server_port)
        c.request('POST', '/api/reviews/' + state['id'] + '/' + action, json.dumps(payload),
                  {'Authorization': 'Bearer secret', 'Content-Type': 'application/json'})
        r = c.getresponse(); code, body = r.status, json.loads(r.read()); c.close()
        return code, body

    try:
        c = http.client.HTTPConnection('127.0.0.1', server.server_port)
        c.request('GET', '/api/config', headers={'Authorization': 'Bearer secret'})
        config = json.loads(c.getresponse().read()); c.close()
        assert config['drafting'] == {'enabled': True, 'model': 'Qwen/Qwen3.8-27B', 'privacy_version': 'minimal-assessment-1'}
        assert 'synthetic-token' not in json.dumps(config) and writer.calls == 0
        before = store.get(state['id'])
        status, _ = post('preview-review', {'revision': 0, 'classification': 'ACCEPT', 'review_text': 'Private idea'})
        assert status == 400 and writer.calls == 0 and store.get(state['id']) == before
        status, _ = post('preview-review', {'revision': 0, 'classification': 'ACCEPT',
                                           'assessment_options': {'execution_pattern': 'Private method'}})
        assert status == 400 and writer.calls == 0
        status, _ = post('draft-review', {'revision': 0, 'classification': 'ACCEPT'})
        assert status == 400 and writer.calls == 0 and store.get(state['id']) == before
        status, _ = post('draft-review', {'revision': 0, 'classification': 'ACCEPT', 'send_to_aitta': True})
        assert status == 400 and writer.calls == 0
        status, preview = post('preview-review', {'revision': 0, 'classification': 'ACCEPT'})
        assert status == 200 and writer.calls == 0 and store.get(state['id']) == before
        assert preview['request'] == wire_request(build_input(before, 'ACCEPT'), writer.model)
        status, _ = post('draft-review', {'revision': 0, 'classification': 'ACCEPT', 'send_to_aitta': True, 'preview_hash': 'wrong'})
        assert status == 400 and writer.calls == 0
        status, data = post('draft-review', {'revision': 0, 'classification': 'ACCEPT', 'send_to_aitta': True, 'preview_hash': preview['preview_hash']})
        assert status == 200 and writer.calls == 1
        assert data['decisions'] == before['decisions'] and data['final'] is None
        assert data['draft_rationale'].startswith('The reviewed compatibility')
        status, _ = post('draft-review', {'revision': 0, 'classification': 'ACCEPT', 'send_to_aitta': True})
        assert status == 409 and writer.calls == 1
        status, cleared = post('standard-wording', {'revision': 1})
        assert status == 200 and 'writing_draft' not in cleared
        assert not cleared['draft_form_comments']
        before = store.get(state['id'])
        def unavailable(payload):
            raise ValueError('Aitta is busy.')
        writer.completion = unavailable
        _, preview = post('preview-review', {'revision': 2, 'classification': 'ACCEPT'})
        status, _ = post('draft-review', {'revision': 2, 'classification': 'ACCEPT', 'send_to_aitta': True, 'preview_hash': preview['preview_hash']})
        assert status == 400 and store.get(state['id']) == before
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=5)


def test_network_exception_is_limited_to_aitta_https_request_context():
    import subprocess, sys
    code = '''
import socket,sys,threading
from app.security import install_network_guard,aitta_network_access
install_network_guard()
def denied(fn):
 try: fn()
 except PermissionError: return
 raise AssertionError('External connection was allowed')
sock=socket.socket()
denied(lambda: sys.audit('socket.getaddrinfo','example.org',443,0,1,0))
socket.getaddrinfo=lambda *a,**k:[(socket.AF_INET,socket.SOCK_STREAM,6,'',('93.184.216.34',443))]
with aitta_network_access():
 sys.audit('socket.connect',sock,('93.184.216.34',443))
 denied(lambda: sys.audit('socket.connect',sock,('93.184.216.34',80)))
 denied(lambda: sys.audit('socket.connect',sock,('8.8.8.8',443)))
 denied(lambda: sys.audit('socket.getaddrinfo','example.org',443,0,1,0))
 denied(lambda: sys.audit('socket.getaddrinfo','aitta-api.csc.fi',80,0,1,0))
 errors=[]
 def other_thread():
  try: sys.audit('socket.connect',sock,('93.184.216.34',443))
  except PermissionError: errors.append(True)
 t=threading.Thread(target=other_thread);t.start();t.join()
 assert errors==[True]
denied(lambda: sys.audit('socket.connect',sock,('93.184.216.34',443)))
sock.close()
'''
    run = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True)
    assert run.returncode == 0, run.stderr


def test_aitta_wire_format_uses_supported_parameters_and_never_follows_redirects(monkeypatch):
    import app.aitta as module
    from contextlib import nullcontext
    payload = build_input(confirmed(review()), 'ACCEPT')
    requests = []
    response = {'status': 200, 'finish_reason': 'stop'}

    class Reply:
        @property
        def status(self): return response['status']
        def getheader(self, name, default=''): return 'application/json'
        def read(self, maximum):
            return json.dumps({'choices': [{'finish_reason': response['finish_reason'],
                               'message': {'content': json.dumps(result(payload))}}]}).encode()[:maximum]

    class Connection:
        def __init__(self, host, **kwargs):
            assert host == 'aitta-api.csc.fi'
        def request(self, method, path, body, headers):
            requests.append((method, path, json.loads(body), headers))
        def getresponse(self): return Reply()
        def close(self): pass

    monkeypatch.setattr(module, 'aitta_network_access', nullcontext)
    monkeypatch.setattr(module.http.client, 'HTTPSConnection', Connection)
    writer = AittaWriter('private-test-token')
    assert writer.completion(payload)['rationale']['text']
    method, path, body, headers = requests[0]
    assert method == 'POST' and path == '/openai/v1/chat/completions'
    assert body['reasoning_effort'] == 'low'
    assert body['stream'] is True
    assert body['max_completion_tokens'] == 6000
    assert 'chat_template_kwargs' not in body
    assert headers['Authorization'] == 'Bearer private-test-token'
    response['finish_reason'] = 'length'
    with pytest.raises(ValueError, match='incomplete'):
        writer.completion(payload)
    response['status'] = 302
    with pytest.raises(ValueError, match='could not return'):
        writer.completion(payload)
    assert len(requests) == 3
    response['status'] = 401
    with pytest.raises(ValueError, match='authentication failed'):
        writer.completion(payload)


def test_streaming_uses_final_content_only_and_rejects_partial_json(monkeypatch):
    import app.aitta as module
    from contextlib import nullcontext
    import io
    payload = build_input(confirmed(review()), 'ACCEPT')
    text = json.dumps(result(payload))
    events = [
        {'choices': [{'delta': {'reasoning': 'Internal reasoning must never become review prose.'}}]},
        {'choices': [{'delta': {'content': text[:80]}}]},
        {'choices': [{'delta': {'content': text[80:]}, 'finish_reason': 'stop'}]},
    ]
    stream = b''.join(b'data: ' + json.dumps(e).encode() + b'\n\n' for e in events) + b'data: [DONE]\n\n'

    class Reply:
        status = 200
        def __init__(self): self.body = io.BytesIO(stream)
        def getheader(self, name, default=''): return 'text/event-stream'
        def readline(self, maximum): return self.body.readline(maximum)

    class Connection:
        def __init__(self, *a, **kw): pass
        def request(self, *a, **kw): pass
        def getresponse(self): return Reply()
        def close(self): pass

    monkeypatch.setattr(module, 'aitta_network_access', nullcontext)
    monkeypatch.setattr(module.http.client, 'HTTPSConnection', Connection)
    writer = AittaWriter('synthetic-token')
    assert writer.completion(payload) == result(payload)
    stream = b'data: {"choices":[{"delta":{"content":"{"},"finish_reason":"length"}]}\n\ndata: [DONE]\n\n'
    with pytest.raises(ValueError, match='incomplete'):
        writer.completion(payload)


def test_outbound_request_is_identical_for_same_assessment_with_different_private_data():
    first = confirmed(review())
    second = copy.deepcopy(first)
    secret = 'PRIVATE-INVENTION-ALPHA-987654321'
    second['document'] = {'document_id': secret, 'pages': [{'page': 1, 'text': secret}],
                          'evidence': [{'id': secret, 'text': secret, 'section': secret, 'scope': 'proposal'}]}
    for key, fact in second['facts'].items():
        if key != 'access_mode': fact['value'] = secret
        fact['reviewer_note'] = secret
        if fact.get('source'): fact['source']['text'] = secret
    for d in second['decisions'].values():
        d['reviewer_note'] = secret
        d['evidence_ids'] = [secret]
        d['reviewer_evidence_ids'] = [secret]
        d['aggregation_reason'] = secret
    for finding in second['rules']['findings']:
        finding['message'] = secret
        finding['source_ref'] = secret
        finding['calculation'] = {'secret': secret}
    if second.get('workload'):
        second['workload']['summary'] = secret
        for finding in second['workload'].get('findings', []):
            finding['explanation'] = secret
            finding['decision']['evidence_ids'] = [secret]
    second.update(draft=secret, draft_rationale=secret, draft_global_comment=secret,
                  registry_hash=secret, policy_hash=secret, final={'text': secret})
    a = wire_request(build_input(first, 'ACCEPT'))
    b = wire_request(build_input(second, 'ACCEPT'))
    assert a == b
    assert secret not in json.dumps(b)
    assert 'PyTorch' not in json.dumps(b) and 'Finland' not in json.dumps(b)
    assert '50000' not in json.dumps(b) and 'ev-' not in json.dumps(b)


def test_payload_and_options_cannot_accept_free_text_or_existing_review_text():
    s = confirmed(review())
    good = build_input(s, 'ACCEPT')
    assert good['assessment']['scaling_strategy'] == 'SUPPORTED'
    assert good['assessment']['scaling_results'] == 'NOT_ASSESSED'
    for options in ({'scaling_results': 'SecretProject result'}, {'reviewer_note': 'Secret idea'},
                    {'execution_pattern': 'our custom private algorithm'}):
        with pytest.raises(ValueError):
            build_input(s, 'ACCEPT', options)
    bad = copy.deepcopy(good)
    bad['generic_review']['rationale'] = 'Private current review text.'
    with pytest.raises(ValueError): validate_input(bad)
    bad = copy.deepcopy(good)
    bad['assessment']['country'] = 'Private country'
    with pytest.raises(ValueError): validate_input(bad)
    assert build_input(s, 'ACCEPT', {'scaling_results': 'PROVIDED'})['assessment']['scaling_results'] == 'PROVIDED'


def test_old_excerpt_based_drafts_require_regeneration():
    s = generated()
    s['writing_draft'].pop('privacy_version')
    prepare_review(s)
    assert s['writing_draft']['stale'] and not current(s)
    with pytest.raises(ValueError, match='out of date'):
        finalize(s, 'ACCEPT', 'Old review', True)


def test_new_numbers_and_references_are_rejected_in_minimal_mode():
    good = result(build_input(confirmed(review()), 'ACCEPT'))
    for text in ('The project needs 32 GPUs.', 'Write to person@example.test.', 'Use https://example.test.', 'See ev-4.'):
        bad = copy.deepcopy(good)
        bad['rationale']['text'] = text
        with pytest.raises(ValueError): validate_output(bad, set(SUMMARY_VALUES))
