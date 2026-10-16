"""Advisory workload evidence and bounded scoring; never an approval gate."""
import hashlib
import json
import re

from app.decision import decide
from app.eligibility import reference_current
from app.retrieval import retrieve, substantive_text

SUMMARY_FIELDS = {
    'Task / method': r'\b(train\w*|fine.?tun\w*|inference|simulation|LoRA|RAG)\b',
    'Model / scale': r'\b(model|parameters?|LLM|transformer|billion)\b',
    'Data / availability': r'\b(dataset|data|samples?|tokens?|images?)\b',
    'Memory / precision': r'\b(memory|HBM|precision|BF16|FP16|FP32|quantiz\w*|shard\w*)\b',
    'Experiments / runtime': r'\b(experiments?|epochs?|steps?|throughput|runtime|hours?)\b',
    'Outputs / success': r'\b(deliver\w*|outputs?|accuracy|metric|success|benchmark|target|goal)\b',
}


def input_hash(state):
    payload = [state['document']['evidence'], state['facts'], state['extraction_resolved']]
    # Readiness is computed after analysis; exclude this derived UI property.
    payload[1] = {k: {a: b for a, b in v.items() if a != 'ready'} for k, v in state['facts'].items()}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def assess_workload(state, backend, context):
    config = state['registry'].get('workload')
    if not config:
        return None
    mode = state['facts']['access_mode']['value']
    supported = (mode in {'FAST_LANE', 'PLAYGROUND'} and state['registry'].get('profile') == mode and
                 str(state['facts']['target_machine']['value']).upper() in {'LUMI-G', 'LUMI G'})
    references = config['references']
    current = all(reference_current(r) for r in references)
    summary = []
    question = next(iter(config['questions'].values()))
    # All relevant sections, not just the model's top-five retrieval window.
    evidence = retrieve(state['document']['evidence'], question, limit=len(state['document']['evidence']))
    for label, pattern in SUMMARY_FIELDS.items():
        matches = []
        for ev in evidence:
            for line in substantive_text(ev['text']).splitlines():
                if re.search(pattern, line, re.I):
                    matches.append({'text': line, 'evidence_id': ev['id'], 'page': ev['page']})
                    break
        summary.append({'label': label, 'passages': matches[:2]})
    result = {'version': config['version'], 'input_hash': input_hash(state), 'stale': False,
              'summary': summary, 'references': references, 'findings': []}
    profile = ('Playground: a bounded pilot with a learning goal and success criterion suffices. '
               'Do not demand measured scaling, full training budgets or prior installation.' if mode == 'PLAYGROUND' else
               'Fast Lane: require an executable plan and workload sizing evidence; a pilot can justify estimates.')
    for key, original in config['questions'].items():
        q = dict(original)
        q['instructions'] += ' ' + profile
        passages = retrieve(state['document']['evidence'], q)
        status = ('UNSUPPORTED_PROFILE' if not supported else 'REFERENCE_EXPIRED' if not current else
                  'EXTRACTION_INCOMPLETE' if not state['extraction_resolved'] else None)
        if status:
            d = {'status': status, 'answer': 'UNKNOWN', 'evidence_ids': [e['id'] for e in passages]}
        else:
            reference_context = '\nDated LUMI reference facts (general guidance, not application certification):\n' + json.dumps(references)
            d = decide(backend, 'workload_' + key, q, passages, state['policy'], context + reference_context)
        reliable = (d['status'] == 'OK' and d.get('confidence', 0) >= state['policy']['high_confidence']
                    and d.get('margin', 0) >= state['policy']['minimum_margin'])
        finding = ('Plausible' if d['answer'] == 'YES' else 'Potential material concern') if reliable and d['answer'] != 'UNKNOWN' else 'Needs clarification'
        explanation = (q['criteria'][d['answer']] if reliable and d['answer'] != 'UNKNOWN' else q['clarification'])
        if d['status'] not in {'OK', 'LOW_CONFIDENCE', 'NO_EVIDENCE_FOUND'}:
            finding = 'Assessment unavailable'
            explanation = 'This advisory assessment could not run. Review the evidence manually or rerun suggestions after resolving the reported status.'
        result['findings'].append({'id': key, 'title': q['title'], 'finding': finding,
                                   'explanation': explanation, 'decision': d})
    return result


# Applicant-facing draft wording remains editable and subject to final approval.
REASONS = {
    'technical_fit': {
        'ACCEPT': 'The proposed computation and software provide a credible execution path on LUMI-G.',
        'REJECT': 'The proposal does not establish how the main computation will run on LUMI-G. Please identify the required software and suitable AMD/ROCm builds, explain the GPU memory needs, and describe how unsupported dependencies will be addressed.'},
    'resource_fit': {
        'ACCEPT': 'The proposed workload and sizing rationale support the requested allocation.',
        'REJECT': 'The requested GPU allocation is not sufficiently justified by the workload description. Please provide the model and data sizes, planned experiments and expected runtimes, and explain how these support the resource request.'},
    'plan_credibility': {
        'ACCEPT': 'The proposed method, available data and measurable outcomes form a credible plan for this allocation.',
        'REJECT': 'The proposal does not sufficiently explain how the available data and proposed method will achieve the project objectives. Please clarify the execution steps and how success will be measured.'},
}


def reason_options(workload):
    if not workload or workload.get('stale'):
        return []
    options = []
    for finding in workload['findings']:
        if finding['finding'] == 'Assessment unavailable' or finding['id'] not in REASONS:
            continue
        # A classifier abstention is not evidence that proposal details are missing.
        if finding['finding'] == 'Needs clarification' and finding['decision']['status'] != 'NO_EVIDENCE_FOUND':
            continue
        classification = 'ACCEPT' if finding['finding'] == 'Plausible' else 'REJECT'
        options.append({'id': finding['id'], 'title': finding['title'],
                        'classification': classification,
                        'text': REASONS[finding['id']][classification]})
    return options


def compose_reason(options, classification):
    """Compose matching findings as one paragraph, without internal diagnostics."""
    ids = {option['id'] for option in options if option['classification'] == classification}
    clauses = {
        'technical_fit': 'how the main computation will run on LUMI-G using suitable AMD/ROCm builds, within GPU memory limits and with any unsupported dependencies addressed',
        'resource_fit': 'how model and dataset sizes, planned experiments and expected runtimes justify the requested allocation',
        'plan_credibility': 'how the available data and proposed method lead to the project objectives and measurable success criteria',
    } if classification == 'REJECT' else {
        'technical_fit': 'a credible software and GPU execution path on LUMI-G',
        'resource_fit': 'a workload sizing rationale consistent with the requested allocation',
        'plan_credibility': 'a feasible connection between the method, available data and measurable project outcomes',
    }
    parts = [text for key, text in clauses.items() if key in ids]
    if not parts:
        return ''
    joined = parts[0] if len(parts) == 1 else ', '.join(parts[:-1]) + ', and ' + parts[-1] if len(parts) > 2 else ' and '.join(parts)
    if classification == 'ACCEPT':
        return 'The reviewed workload describes ' + joined + '.'
    return ('Further detail is needed to establish the feasibility of the proposed workload and its resource requirements. '
            'Please explain ' + joined + '.')
