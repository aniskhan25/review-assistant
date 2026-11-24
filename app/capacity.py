"""Project-wide capacity bounds require project-wide concurrency evidence."""


def resource_capacity(state):
    facts = state['facts']

    def value(key):
        fact = facts.get(key, {})
        return fact.get('value') if fact.get('status') == 'PRESENT' else None

    hours, months = value('requested_gpu_hours'), value('project_duration_months')
    gpus = value('maximum_number_of_gpus')
    source = (facts.get('maximum_number_of_gpus', {}).get('source') or {}).get('text', '').casefold()
    fields = ['requested_gpu_hours', 'project_duration_months']
    total = None
    scope = 'unspecified'
    if 'total concurrent' in source or 'across all jobs' in source:
        total, scope = gpus, 'project_total'
        fields.append('maximum_number_of_gpus')
    elif value('maximum_gpus_per_job') and value('maximum_simultaneous_jobs'):
        total = value('maximum_gpus_per_job') * value('maximum_simultaneous_jobs')
        scope = 'per_job_times_concurrent_jobs'
        fields.extend(['maximum_gpus_per_job', 'maximum_simultaneous_jobs'])
    calculation = {'requested_gpu_hours': hours, 'maximum_number_of_gpus': gpus,
                   'project_duration_months': months, 'maximum_total_concurrent_gpus': total,
                   'concurrency_scope': scope,
                   'assumption': '30-day months; project-wide concurrency and GPU-hours use consistent accounting units',
                   'evidence_fields': fields}
    result = {'code': 'resource_consumption', 'severity': 'attention', 'calculation': calculation}
    if hours is None or months is None or hours <= 0 or months <= 0:
        result['message'] = 'Resource feasibility needs valid GPU-hours and duration.'
        return result
    calculation['required_average_gpus'] = hours / (24 * 30 * months)
    if total is None or total <= 0:
        result['message'] = ('No project-wide GPU concurrency limit is established. A per-job GPU or node limit '
                             'does not limit the number of concurrent jobs. Clarify the maximum total GPUs '
                             'across all jobs; no hard capacity ceiling has been calculated.')
        return result
    calculation['minimum_months'] = hours / (total * 24 * 30)
    calculation['maximum_gpu_hours'] = total * 24 * 30 * months
    exceeds = hours > calculation['maximum_gpu_hours']
    result.update(severity='blocker' if exceeds else 'info', message=(
        'Allocation cannot be consumed within the declared duration at the explicit project-wide concurrency limit.'
        if exceeds else 'Allocation fits the explicit project-wide capacity limit; queue availability is not guaranteed.'))
    return result
