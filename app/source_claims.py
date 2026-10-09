"""Narrow literal claims that can be resolved without a probabilistic classifier."""
import re

QUANTITY = re.compile(r'\b(?:\d[\d,.]*(?:\s?[kmb]|\s+(?:thousand|million|billion))?|(?:hundreds|thousands|millions)(?:\s+of\s+thousands)?|one|two|three|four|five|six|ten)\s+(?:of\s+)?(?:(?:extracted|video|training|independent|evaluation|benchmark|total|distinct|labeled|labelled|input|generated)\s+){0,3}(?:frames|images|videos|samples|tokens|jobs|runs|steps|epochs|models)\b', re.I)
ACTION = re.compile(r'\b(?:process(?:ing|ed)?|execut(?:e|ion)|train(?:ing|ed)?|runs?|dataset|contains|benchmark(?:ing|s)?)\b', re.I)
OUTSIDE_SCOPE = re.compile(r'\b(?:future|previous(?:ly)?|past|historical|long-term)\b', re.I)
CORE = re.compile(r'\b(?:PyTorch|ROCm|JAX|DeepSpeed|FlashAttention|TensorFlow)\b', re.I)
DEFERRED = re.compile(r'\bversion\b.{0,180}\bpinned\s+after\b.{0,90}\b(?:validation|tests)\b', re.I)
CUDA_ONLY = re.compile(r'\b(?:CUDA|NVIDIA)[ -]only\b|\b(?:requires?|must use|depends on)\b.{0,80}\b(?:CUDA|NVIDIA)\b', re.I)
UNSUPPORTED = re.compile(r'\b(?:does not|cannot|can\x27t|not supported|unsupported)\b.{0,50}\b(?:AMD|ROCm|HIP)\b|\b(?:AMD|ROCm|HIP)\b.{0,50}\b(?:unsupported|not supported)\b', re.I)
CONSTRAINT = re.compile(r'\b(?:TensorRT|cuDNN|NCCL|unsupported|unavailable|unpinned|unselected)\b|\bCUDA[ -](?:specific|custom|kernels?|extensions?)\b|\bcustom\s+CUDA\b|\bnot (?:supported|available|selected|pinned)\b|\bpinned after\b', re.I)


def software_claim(kind, evidence, question):
    """Literal presence and absence over the entire relevant proposal scope."""
    lines = [(ev, ' '.join(line.split())) for ev in evidence for line in ev['text'].splitlines() if line.strip()]
    if not lines:
        return None
    if kind in {'dependencies_identified', 'amd_path_supported'}:
        matches = [(ev, line) for ev, line in lines if CORE.search(line) and not OUTSIDE_SCOPE.search(line)
                   and not re.search(r'\b(?:do not|does not|not using|without)\b.{0,30}' + CORE.pattern, line, re.I)]
        if kind == 'amd_path_supported':
            # Use only framework support explicitly supplied as reference
            # background; this is not proof of installation or exact builds.
            references = ' '.join(ref['claim'] for ref in question.get('background_references', []))
            matches = [(ev, line) for ev, line in matches if not UNSUPPORTED.search(line) and not CUDA_ONLY.search(line) and any(
                re.search(r'\b' + name + r'\b', line, re.I) and name in references for name in ('PyTorch', 'JAX'))]
            matches += [(ev, line) for ev, line in lines if re.search(r'\b(?:ROCm|HIP)\b', line, re.I)
                        and re.search(r'\b(?:support|supports|backend|runtime|use|uses|using|target|targets|port|environment|stack)\b', line, re.I)
                        and not UNSUPPORTED.search(line) and not OUTSIDE_SCOPE.search(line)]
        if not matches:
            return None
        return {'answer': 'YES', 'evidence_ids': list(dict.fromkeys(ev['id'] for ev, _ in matches)),
                'quotes': list(dict.fromkeys(line for _, line in matches))}
    if kind == 'compatibility_blocker':
        deferred = source_claim({'explicit_version_deferral': True}, evidence)
        if deferred:
            return deferred
    blockers = [(ev, line) for ev, line in lines if UNSUPPORTED.search(line)]
    # A negated or qualified restriction is not an incompatibility. Complex
    # restrictions stay with the model rather than being decided by a regex.
    if kind == 'compatibility_blocker' and blockers:
        return None
    if any(CONSTRAINT.search(line) or CUDA_ONLY.search(line) for _, line in lines):
        return None
    return {'answer': 'NO', 'evidence_ids': [ev['id'] for ev in evidence], 'quotes': [],
            'scope': 'All relevant technical proposal passages searched; no explicit compatibility restriction was described.'}


def source_claim(question, evidence):
    matches = []
    if question.get('software_source_check'):
        return software_claim(question['software_source_check'], evidence, question)
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
            'evidence_scope': claim.get('scope', ''),
            'reviewer_answer': None, 'reviewer_note': '', 'confirmed': False,
            'check_title': question['title']}


def claim_evidence(question, document_evidence, retrieved):
    if question.get('accounting_assumption_guard') or question.get('software_source_check') or question.get('quantity_evidence') or question.get('explicit_version_deferral'):
        from app.retrieval import retrieve
        return retrieve(document_evidence, question, limit=len(document_evidence))
    return retrieved
