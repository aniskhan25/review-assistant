"""Optional, explicitly requested Aitta drafting; never a decision provider."""
import copy
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import ssl
import time
from datetime import datetime, timezone

from app.security import aitta_network_access

MODEL = 'Qwen/Qwen3.8-27B'
FORM_IDS = ('software_gpu_capable', 'code_previously_installed', 'workplan_sufficient')
PROMPT_VERSION = 'aitta-editor-2'
PRIVACY_VERSION = 'minimal-assessment-1'
SUMMARY_VALUES = {
    'access_mode': ('FAST_LANE', 'PLAYGROUND'),
    'classification': ('ACCEPT', 'REJECT'),
    'architecture_compatibility': ('SUPPORTED', 'NOT_DEMONSTRATED', 'NOT_ASSESSED'),
    'prior_installation': ('DEMONSTRATED', 'NOT_DEMONSTRATED', 'NOT_ASSESSED'),
    'workplan': ('FEASIBLE', 'INSUFFICIENT', 'NOT_ASSESSED'),
    'scaling_strategy': ('SUPPORTED', 'NOT_DEMONSTRATED', 'NOT_ASSESSED', 'NOT_REQUIRED'),
    'scaling_results': ('PROVIDED', 'NOT_PROVIDED', 'NOT_ASSESSED', 'NOT_REQUIRED'),
    'execution_pattern': ('INDEPENDENT_JOBS', 'DISTRIBUTED_JOB', 'MIXED_EXECUTION', 'NOT_SPECIFIED'),
    'resource_justification': ('ADEQUATE', 'NEEDS_CLARIFICATION', 'NOT_ASSESSED'),
    'capacity': ('WITHIN_EXPLICIT_LIMIT', 'EXCEEDS_EXPLICIT_LIMIT', 'NOT_ESTABLISHED'),
    'organization_eligibility': ('ELIGIBLE', 'INELIGIBLE', 'NOT_ASSESSED'),
    'country_eligibility': ('ELIGIBLE', 'INELIGIBLE', 'NOT_ASSESSED'),
    'tax_identifier': ('PROVIDED', 'ABSENT', 'NOT_ASSESSED'),
    'technical_fit': ('SUPPORTED', 'MATERIAL_CONCERN', 'CLARIFICATION_NEEDED', 'NOT_ASSESSED'),
    'resource_fit': ('SUPPORTED', 'MATERIAL_CONCERN', 'CLARIFICATION_NEEDED', 'NOT_ASSESSED'),
    'plan_credibility': ('SUPPORTED', 'MATERIAL_CONCERN', 'CLARIFICATION_NEEDED', 'NOT_ASSESSED'),
    'initial_validation': ('DEMONSTRATED', 'NOT_DEMONSTRATED', 'NOT_ASSESSED', 'NOT_REQUIRED'),
}
OPTION_FIELDS = ('scaling_results', 'execution_pattern')
COMMENT_FIELDS = {
    'software_gpu_capable': ('architecture_compatibility', 'technical_fit', 'initial_validation'),
    'code_previously_installed': ('prior_installation', 'initial_validation'),
    'workplan_sufficient': ('workplan', 'scaling_strategy', 'scaling_results', 'execution_pattern',
                            'resource_justification', 'capacity', 'resource_fit', 'plan_credibility'),
}
PROMPT = '''Edit the supplied generic technical review using ONLY the categorical assessment supplied.
You receive no proposal, project details or scientific idea. Do not infer them. Preserve the selected classification
and every finding; flag contradictions in issues. NOT_ASSESSED and NOT_ESTABLISHED do not mean absent or failed.
Scaling strategy support does not establish measured scaling results. An execution pattern is not a benchmark.
Write concise, coherent applicant-facing prose, without new factual claims, guarantees, numeric figures, named
software/models, names, identifiers, countries, datasets, evidence IDs, greetings or administrative boilerplate.
Use the classification reason as a standalone explanation. Global comments add supporting assessment detail.
Return ONLY JSON with exactly: comments (keyed software_gpu_capable, code_previously_installed,
workplan_sufficient), global_comment, rationale, issues (array of up to eight reviewer warnings).
Each comment, global_comment and rationale must have exactly text and assessment_fields. assessment_fields is a
nonempty array of supplied assessment key names supporting that text. Question comments use only their relevant
assessment fields. Limit each comment to fifty words, global comments to one hundred words, reason to one hundred
twenty words. Do not print field names or category codes in applicant prose. No invented clarification requests.
'''


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def binding(state):
    # Private provenance only: this digest and its source data never enter the request.
    return digest({'document': state['document'], 'registry_hash': state['registry_hash'],
                   'policy_hash': state['policy_hash'], 'extraction_resolved': state['extraction_resolved'],
                   'facts': {k: {a: b for a, b in f.items() if a != 'ready'} for k, f in state['facts'].items()},
                   'decisions': {k: {a: d.get(a) for a in ('answer', 'status', 'confirmed', 'reviewer_answer',
                       'reviewer_note', 'evidence_ids', 'reviewer_evidence_ids')} for k, d in state['decisions'].items()}})


def current(state):
    draft = state.get('writing_draft')
    return bool(draft and draft.get('privacy_version') == PRIVACY_VERSION
                and draft.get('prompt_version') == PROMPT_VERSION and draft['input_hash'] == binding(state))


def generic_review(assessment):
    compatibility = {
        'SUPPORTED': 'The proposed software has a supported execution path on the target architecture.',
        'NOT_DEMONSTRATED': 'A suitable software execution path is not demonstrated.',
        'NOT_ASSESSED': 'Architecture compatibility has not been assessed.'}
    prior = {
        'DEMONSTRATED': 'Prior installation or use on the target system is demonstrated.',
        'NOT_DEMONSTRATED': 'Prior installation or use on the target system is not demonstrated; initial setup may be needed.',
        'NOT_ASSESSED': 'Prior installation or use has not been assessed.'}
    plan = {
        'FEASIBLE': 'The workplan is considered feasible within the requested allocation.',
        'INSUFFICIENT': 'The workplan does not sufficiently establish feasibility within the requested allocation.',
        'NOT_ASSESSED': 'Workplan feasibility has not been assessed.'}
    return {'comments': {'software_gpu_capable': compatibility[assessment['architecture_compatibility']],
                        'code_previously_installed': prior[assessment['prior_installation']],
                        'workplan_sufficient': plan[assessment['workplan']]},
            'global_comment': 'The review considers compatibility, prior use, execution strategy, resource justification and feasibility.',
            'rationale': ('The selected classification is acceptance.' if assessment['classification'] == 'ACCEPT'
                          else 'The selected classification is rejection. Explain only the supplied adverse findings.')}


def validate_input(payload):
    if not isinstance(payload, dict) or set(payload) != {'assessment', 'generic_review'}:
        raise ValueError('Only the approved minimal assessment may be sent to Aitta.')
    assessment = payload['assessment']
    if not isinstance(assessment, dict) or set(assessment) != set(SUMMARY_VALUES):
        raise ValueError('Invalid minimal assessment fields.')
    for key, allowed in SUMMARY_VALUES.items():
        if not isinstance(assessment[key], str) or assessment[key] not in allowed:
            raise ValueError('Only fixed assessment categories may be sent to Aitta.')
    if payload['generic_review'] != generic_review(assessment):
        raise ValueError('Only locally composed generic review text may be sent to Aitta.')
    return payload


def build_input(state, classification, options=None):
    if classification not in ('ACCEPT', 'REJECT') or any(state['exceptions'].values()):
        raise ValueError('Resolve review exceptions and select a classification before drafting.')
    mode = state['facts']['access_mode']['value']
    if mode not in ('FAST_LANE', 'PLAYGROUND'):
        raise ValueError('Unsupported access mode for drafting.')
    options = {} if options is None else options
    if (not isinstance(options, dict) or set(options) - set(OPTION_FIELDS)
            or any(not isinstance(v, str) or v not in SUMMARY_VALUES[k] for k, v in options.items())):
        raise ValueError('Drafting options must use the fixed generic categories.')

    def answer(qid):
        d = state['decisions'].get(qid, {})
        value = d.get('reviewer_answer') if d.get('confirmed') else d.get('answer')
        return value if value in ('YES', 'NO') else None

    def category(qid, positive, negative, unknown='NOT_ASSESSED'):
        value = answer(qid)
        return positive if value == 'YES' else negative if value == 'NO' else unknown

    budget = state['decisions'].get('workplan_sufficient', {}).get('checks', {}).get('jobs_budgeted', {})
    budget_answer = budget.get('answer') if budget.get('status') == 'OK' else None
    capacity = next((f.get('severity') for f in state['rules']['findings']
                     if f.get('code') == 'resource_consumption'), None)

    def advisory(key):
        workload = state.get('workload')
        if not workload or workload.get('stale'):
            return 'NOT_ASSESSED'
        finding = next((f for f in workload.get('findings', []) if f.get('id') == key), {})
        if finding.get('decision', {}).get('status') == 'NO_EVIDENCE_FOUND':
            return 'CLARIFICATION_NEEDED'
        return {'Plausible': 'SUPPORTED', 'Potential material concern': 'MATERIAL_CONCERN'}.get(
            finding.get('finding'), 'NOT_ASSESSED')

    tax_status = state['facts'].get('vat_number', {}).get('status')
    assessment = {
        'access_mode': mode, 'classification': classification,
        'architecture_compatibility': category('software_gpu_capable', 'SUPPORTED', 'NOT_DEMONSTRATED'),
        'prior_installation': category('code_previously_installed', 'DEMONSTRATED', 'NOT_DEMONSTRATED'),
        'workplan': category('workplan_sufficient', 'FEASIBLE', 'INSUFFICIENT'),
        'scaling_strategy': category('scaling_strategy_adequate', 'SUPPORTED', 'NOT_DEMONSTRATED',
                                     'NOT_REQUIRED' if mode == 'PLAYGROUND' else 'NOT_ASSESSED'),
        # These categories require an explicit reviewer choice; never infer from text.
        'scaling_results': options.get('scaling_results', 'NOT_ASSESSED'),
        'execution_pattern': options.get('execution_pattern', 'NOT_SPECIFIED'),
        'resource_justification': ('ADEQUATE' if budget_answer == 'YES' else 'NEEDS_CLARIFICATION'
                                   if budget_answer == 'NO' else 'NOT_ASSESSED'),
        'capacity': ('WITHIN_EXPLICIT_LIMIT' if capacity == 'info' else 'EXCEEDS_EXPLICIT_LIMIT'
                     if capacity == 'blocker' else 'NOT_ESTABLISHED'),
        'organization_eligibility': category('organization_eligible', 'ELIGIBLE', 'INELIGIBLE'),
        'country_eligibility': category('country_eligible', 'ELIGIBLE', 'INELIGIBLE'),
        'tax_identifier': ('PROVIDED' if tax_status == 'PRESENT' else 'ABSENT'
                           if tax_status == 'ABSENT' else 'NOT_ASSESSED'),
        'technical_fit': advisory('technical_fit'),
        'resource_fit': advisory('resource_fit'),
        'plan_credibility': advisory('plan_credibility'),
        'initial_validation': category('fast_lane_validated', 'DEMONSTRATED', 'NOT_DEMONSTRATED',
                                       'NOT_REQUIRED' if mode == 'PLAYGROUND' else 'NOT_ASSESSED'),
    }
    return validate_input({'assessment': assessment, 'generic_review': generic_review(assessment)})


def wire_request(payload, model=MODEL):
    validate_input(payload)
    return {'model': model, 'messages': [{'role': 'system', 'content': PROMPT},
            {'role': 'user', 'content': json.dumps(payload)}], 'temperature': 0.7,
            'max_completion_tokens': 6000, 'stream': True, 'reasoning_effort': 'low'}


def validate_output(result, allowed_fields):
    if not isinstance(result, dict) or set(result) != {'comments', 'global_comment', 'rationale', 'issues'}:
        raise ValueError('Aitta returned an invalid review structure; no draft was applied.')
    if not isinstance(result['comments'], dict) or set(result['comments']) != set(FORM_IDS):
        raise ValueError('Aitta did not return all three assessment comments.')
    fields = [(v, 2000, set(COMMENT_FIELDS[k])) for k, v in result['comments'].items()]
    fields += [(result[k], 4000, set(allowed_fields)) for k in ('global_comment', 'rationale')]
    for value, limit, permitted in fields:
        if (not isinstance(value, dict) or set(value) != {'text', 'assessment_fields'}
                or not isinstance(value['text'], str) or not value['text'].strip() or len(value['text']) > limit
                or re.search(r'\d|https?://|@|<think>|\[proposal evidence:', value['text'], re.I)
                or not isinstance(value['assessment_fields'], list) or not value['assessment_fields']
                or any(not isinstance(key, str) or key not in permitted for key in value['assessment_fields'])):
            raise ValueError('Aitta returned new details or invalid assessment references; no draft was applied.')
    issues = result['issues']
    if not isinstance(issues, list) or len(issues) > 8 or any(not isinstance(x, str) or len(x) > 1000 for x in issues):
        raise ValueError('Aitta returned invalid review warnings.')
    return copy.deepcopy(result)


def local_sources(state, fields):
    """Attach internal provenance after generation; never send passage IDs to Aitta."""
    mapping = {'architecture_compatibility': 'software_gpu_capable', 'prior_installation': 'code_previously_installed',
               'workplan': 'workplan_sufficient', 'resource_justification': 'workplan_sufficient',
               'scaling_strategy': 'scaling_strategy_adequate', 'initial_validation': 'fast_lane_validated',
               'organization_eligibility': 'organization_eligible', 'country_eligibility': 'country_eligible'}
    ids = []
    for field in fields:
        d = state['decisions'].get(mapping.get(field), {})
        ids += d.get('reviewer_evidence_ids', []) if d.get('confirmed') else d.get('evidence_ids', [])
        if field in ('technical_fit', 'resource_fit', 'plan_credibility'):
            workload = state.get('workload') or {}
            finding = next((f for f in workload.get('findings', []) if f.get('id') == field), {})
            ids += finding.get('decision', {}).get('evidence_ids', [])
        if field == 'tax_identifier':
            from app.readiness import fact_evidence
            ids += fact_evidence(state, state['facts']['vat_number'])
    return list(dict.fromkeys(ids))

class AittaWriter:
    privacy_version = PRIVACY_VERSION

    def __init__(self, token, model=MODEL):
        if not token or any(c.isspace() for c in token) or not re.fullmatch(r'[\w.-]+/[\w.-]+', model):
            raise ValueError('Aitta needs a valid access token and model identifier.')
        self._token = token
        self.model = model

    @classmethod
    def from_environment(cls, data_dir, model=MODEL):
        token = os.environ.get('AITTA_API_KEY', '').strip()
        if not token:
            path = Path(data_dir) / 'aitta.token'
            if not path.is_file() or path.stat().st_mode & 0o077:
                raise ValueError('Set AITTA_API_KEY or provide an owner-only data/aitta.token file.')
            token = path.read_text().strip()
        return cls(token, model)

    def completion(self, payload):
        validate_input(payload)
        try:
            context = ssl.create_default_context()
            try:
                import certifi
                context = ssl.create_default_context(cafile=certifi.where())
            except ImportError:
                pass
            # No configurable destination, proxy, redirect, tools or automatic retry.
            with aitta_network_access():
                connection = http.client.HTTPSConnection('aitta-api.csc.fi', context=context, timeout=180)
                try:
                    body = json.dumps(wire_request(payload, self.model))
                    connection.request('POST', '/openai/v1/chat/completions', body=body,
                        headers={'Authorization': 'Bearer ' + self._token, 'Content-Type': 'application/json'})
                    response = connection.getresponse()
                    status = response.status
                    if status == 200 and 'text/event-stream' in response.getheader('Content-Type', ''):
                        chunks, finish, size = [], None, 0
                        deadline = time.monotonic() + 300
                        while time.monotonic() < deadline:
                            line = response.readline(100001)
                            if not line:
                                break
                            size += len(line)
                            if size > 4000000 or len(line) > 100000:
                                raise ValueError('Aitta response exceeded the drafting limit.')
                            if not line.startswith(b'data:'):
                                continue
                            data = line[5:].strip()
                            if data == b'[DONE]':
                                break
                            event = json.loads(data)
                            for choice in event.get('choices', []):
                                text = choice.get('delta', {}).get('content')
                                if text:
                                    chunks.append(text)
                                finish = choice.get('finish_reason') or finish
                        raw = json.dumps({'choices': [{'finish_reason': finish,
                            'message': {'content': ''.join(chunks)}}]}).encode()
                    else:
                        raw = response.read(100001)
                finally:
                    connection.close()
            if status in (401, 403):
                raise ValueError('Aitta authentication failed. Renew the locally configured access token.')
            if status == 429:
                raise ValueError('Aitta is busy or rate-limited. Your existing review is unchanged; retry later.')
            if status != 200 or len(raw) > 100000:
                raise ValueError('Aitta could not return a review. Your existing review is unchanged; retry later.')
            completion = json.loads(raw)['choices'][0]
            if completion.get('finish_reason') != 'stop':
                raise ValueError('Aitta review was incomplete; no draft was applied.')
            content = completion['message']['content'].strip()
            if content.startswith('```json') and content.endswith('```'):
                content = content[7:-3].strip()
            return json.loads(content)
        except ValueError as exc:
            if str(exc).startswith('Aitta '):
                raise
            raise ValueError('Aitta returned an unreadable review; no draft was applied.') from None
        except Exception:
            raise ValueError('Aitta is unavailable or still loading the model; no draft was applied. Retry later.') from None

    def preview(self, state, classification, options=None):
        payload = build_input(state, classification, options)
        request = wire_request(payload, self.model)
        return {'request': request, 'assessment': payload['assessment'], 'preview_hash': digest(request),
                'privacy_version': PRIVACY_VERSION, 'model': self.model}

    def generate(self, state, classification, preview_hash=None, options=None):
        payload = build_input(state, classification, options)
        request = wire_request(payload, self.model)
        if preview_hash != digest(request):
            raise ValueError('Preview the current minimal assessment before sending it to Aitta.')
        result = validate_output(self.completion(payload), set(SUMMARY_VALUES))
        for value in list(result['comments'].values()) + [result['global_comment'], result['rationale']]:
            value['evidence_ids'] = local_sources(state, value['assessment_fields'])
        result.update(model=self.model, provider='Aitta', prompt_version=PROMPT_VERSION,
                      privacy_version=PRIVACY_VERSION, assessment=payload['assessment'],
                      outbound_preview_hash=preview_hash, input_hash=binding(state), classification=classification,
                      generated_at=datetime.now(timezone.utc).isoformat())
        return result
