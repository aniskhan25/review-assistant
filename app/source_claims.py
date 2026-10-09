"""Narrow literal claims that can be resolved without a probabilistic classifier."""
import re

QUANTITY = re.compile(r'\b(?:\d[\d,.]*(?:\s?[kmb]|\s+(?:thousand|million|billion))?|(?:hundreds|thousands|millions)(?:\s+of\s+thousands)?|one|two|three|four|five|six|ten)\s+(?:of\s+)?(?:(?:extracted|video|training|independent|evaluation|benchmark|total|distinct|labeled|labelled|input|generated)\s+){0,3}(?:frames|images|videos|samples|tokens|jobs|runs)\b', re.I)
ACTION = re.compile(r'\b(?:process|execute|train|run|dataset|contains|training|benchmarking)\b', re.I)
OUTSIDE_SCOPE = re.compile(r'\b(?:future|previous|past|long-term)\b', re.I)
CORE = re.compile(r'\b(?:PyTorch|ROCm|JAX|DeepSpeed|FlashAttention|TensorFlow)\b', re.I)
DEFERRED = re.compile(r'\bversion\b.{0,180}\bpinned\s+after\b.{0,90}\b(?:validation|tests)\b', re.I)


def source_claim(question, evidence):
    matches = []
    if question.get('accounting_assumption_guard'):
        text = ' '.join(ev['text'] for ev in evidence)
        if (re.search(r'\b(?:assume[ds]?|assuming|assumption)\b.{0,160}\bMFU\b|\bMFU\b.{0,160}\b(?:assume[ds]?|assuming|assumption)\b', text, re.I | re.S)
                and re.search(r'\bGCDs?\b', text, re.I)) or (
                re.search(r'\bGCDs?\b.{0,80}\btheoretical\b|\btheoretical\b.{0,80}\bGCDs?\b', text, re.I | re.S)
                and re.search(r'\bMFU\b', text, re.I)):
            matches = [(ev, ev['text']) for ev in evidence if re.search(r'\bMFU\b|\bGCDs?\b', ev['text'], re.I)]
            return {'answer': 'UNKNOWN', 'evidence_ids': [ev['id'] for ev, _ in matches],
                    'quotes': [quote for _, quote in matches]}
    if question.get('quantity_evidence'):
        for ev in evidence:
            for line in ev['text'].splitlines():
                if QUANTITY.search(line) and ACTION.search(line) and not OUTSIDE_SCOPE.search(line):
                    matches.append((ev, line.strip()))
    elif question.get('explicit_version_deferral'):
        components = set()
        for ev in evidence:
            text = ' '.join(ev['text'].split())
            if 'Name and version of the code:' not in text:
                continue
            field = text.split('Name and version of the code:', 1)[1].split('Webpage and other references:', 1)[0]
            named = set(name.casefold() for name in CORE.findall(field))
            if named and DEFERRED.search(field):
                components.update(named)
                matches.append((ev, field.strip()))
        if len(components) < 2:
            return None
    if not matches:
        return None
    return {'answer': 'YES', 'evidence_ids': list(dict.fromkeys(ev['id'] for ev, _ in matches)),
            'quotes': list(dict.fromkeys(text for _, text in matches))}


def claim_decision(key, question, claim):
    return {'question_id': key, 'question_version': question['version'], 'inference_mode': 'source_claim',
            'model_answer': claim['answer'], 'answer': claim['answer'], 'probabilities': {},
            'confidence': 1., 'margin': 1., 'band': 'source-backed' if claim['answer'] != 'UNKNOWN' else 'reviewer required',
            'status': 'OK' if claim['answer'] != 'UNKNOWN' else 'ACCOUNTING_ASSUMPTION_REVIEW',
            'model': 'source-claim-rule', 'model_version': '1', 'latency_ms': 0.,
            'evidence_ids': claim['evidence_ids'], 'source_quotes': claim['quotes'],
            'reviewer_answer': None, 'reviewer_note': '', 'confirmed': False,
            'check_title': question['title']}


def claim_evidence(question, document_evidence, retrieved):
    if question.get('accounting_assumption_guard'):
        from app.retrieval import retrieve
        return retrieve(document_evidence, question, limit=len(document_evidence))
    return retrieved
