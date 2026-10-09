"""Compare corrected-workflow development reports without exporting proposal text."""
import argparse
import hashlib
import json
from pathlib import Path
import statistics


def counts(cases, readiness=None):
    rows = []
    for case in cases:
        for qid, answer in case['answers'].items():
            ready = readiness[(case['application_id'], qid)] if readiness is not None else answer['ready']
            rows.append(dict(question=qid, gold=answer['gold'], predicted=answer['predicted'], ready=ready))
    def summarize(selected):
        return dict(total=len(selected), matching=sum(r['predicted'] == r['gold'] for r in selected),
                    wrong=sum(r['predicted'] not in {r['gold'], 'UNKNOWN'} for r in selected),
                    unknown=sum(r['predicted'] == 'UNKNOWN' for r in selected),
                    ready=sum(r['ready'] for r in selected),
                    wrong_ready=sum(r['ready'] and r['predicted'] != r['gold'] for r in selected))
    return dict(overall=summarize(rows), per_question={qid:summarize([r for r in rows if r['question']==qid])
                for qid in sorted({r['question'] for r in rows})})


def quality_gate(baseline, candidate):
    def passes(base, other):
        return (other['total'] == base['total'] and other['matching'] >= base['matching']
                and other['wrong'] <= base['wrong'] and other['unknown'] <= base['unknown']
                and other['ready'] >= base['ready'] and other['wrong_ready'] <= base['wrong_ready'])
    return passes(baseline['overall'],candidate['overall']) and all(
        passes(base,candidate['per_question'][qid]) for qid,base in baseline['per_question'].items())


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory',type=Path)
    args=parser.parse_args()
    frozen=json.loads((args.directory/'frozen-comparison.json').read_text())
    baseline_path=Path(frozen['baseline'])
    if hashlib.sha256(baseline_path.read_bytes()).hexdigest()!=frozen['baseline_sha256']:
        raise ValueError('Baseline changed after comparison was frozen')
    readiness_path=baseline_path.parent/'development-readiness.json'
    if hashlib.sha256(readiness_path.read_bytes()).hexdigest()!=frozen['baseline_readiness_sha256']:
        raise ValueError('Baseline readiness changed')
    baseline=json.loads(baseline_path.read_text())
    candidate=json.loads((args.directory/'kev-08b-development.json').read_text())
    timing=json.loads((args.directory/'baseline-timing.json').read_text())
    if baseline['registry_hash']!=frozen['registry_sha256']:
        raise ValueError('Baseline criteria do not match')
    for report in [candidate,timing]:
        if report['split']!='development' or any(report[key]!=frozen[key] for key in
                ['registry_sha256','policy_sha256','dataset_sha256']):
            raise ValueError('Evaluation inputs changed')
    if [c['application_id'] for c in candidate['cases']]!=frozen['development_ids']:
        raise ValueError('Candidate cases changed')
    if [c['application_id'] for c in timing['cases']]!=frozen['timing_ids']:
        raise ValueError('Timing cases changed')
    if timing['model_version']!=baseline['model_version']:
        raise ValueError('Timing used another baseline model')
    if any(c['model_errors'] for report in [baseline,timing] for c in report['cases']):
        raise ValueError('Baseline inference errors invalidate the comparison')
    base_cases={c['application_id']:c for c in baseline['cases']}
    for case in timing['cases']:
        if any(a['predicted']!=base_cases[case['application_id']]['answers'][q]['predicted']
               for q,a in case['answers'].items()):
            raise ValueError('Fresh baseline answers differ from the exact replay baseline')
    readiness={(r['application_id'],r['question_id']):r['ready'] for r in json.loads(readiness_path.read_text())}
    base=counts(baseline['cases'],readiness)
    other=counts(candidate['cases'])
    ids=set(frozen['timing_ids'])
    base_seconds=statistics.median(c['elapsed_seconds'] for c in timing['cases'])
    other_seconds=statistics.median(c['elapsed_seconds'] for c in candidate['cases'] if c['application_id'] in ids)
    errors=sum(c['model_errors'] for c in candidate['cases'])
    quality=quality_gate(base,other) and errors==0
    summary=dict(split='development',applications=len(candidate['cases']),baseline=base,candidate=other,
                 passes_quality_gate=quality,passes_selection_gate=quality and other_seconds<base_seconds,
                 model_errors=errors,timing_cases=frozen['timing_ids'],baseline_median_seconds=base_seconds,
                 candidate_median_seconds=other_seconds,speed_ratio=base_seconds/other_seconds,
                 candidate_memory=candidate['inference_memory'],baseline_memory=timing['inference_memory'],
                 production_qualified=False,
                 limits='Provisional historical labels; 16 exposed development proposals. Qwen accuracy/readiness uses exact replay; four selected Qwen reviews were freshly scored and timed. No fresh held-out validation. Final classification and eligibility are not evaluated.')
    output=args.directory/'summary.json'
    if output.exists():raise ValueError('Preserve existing comparison output')
    output.write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':
    main()
