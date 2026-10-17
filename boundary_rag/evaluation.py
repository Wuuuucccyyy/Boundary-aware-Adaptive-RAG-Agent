"""Evaluation-only gold. Never imported by routing, parsing, retrieval or generation."""
import random
import re
import statistics

ANCHORS = {
    'leave': ['15', '3'], 'bonus_policy': ['绩效', '转正'], 'bonus_budget': ['1.12', '12'],
    'option_eligibility': ['12', '4'], 'option_tax': ['20%', '股数'],
    'travel_policy': ['经理', '经济舱'], 'travel_claim': ['30', '发票'],
    'portal_access': ['2', '认证'], 'vpn': ['网络', '认证', '工单'],
    'password': ['自助', '认证'], 'equipment_policy': ['3000', '试用'],
    'equipment_claim': ['5000', '发票'], 'equipment_setup': ['加密', '防护'],
    'offboarding_policy': ['30', '交接'], 'offboarding_account': ['18', '停用'],
    'invoice': ['DEMO-TAX-000', '星河'], 'training_policy': ['转正', '经理'],
    'training_claim': ['2000', '发票'], 'support_contact': ['helpdesk@example.invalid', '18'],
}


def score(sample, run):
    supported_tasks = [t for t, ids in sample['acceptable_documents'].items() if ids]
    retrieved = {h['document']['id'] for step in run['rounds'] for r in step['retrievals'] for h in r['hits']}
    cited = set(re.findall(r'\[([a-z][a-z0-9_-]+)\]', run['answer']))
    all_valid = {x['doc_id'] for evidence in run['evidence']['supports'].values() for x in evidence}
    sources = set(run['selected_sources'])
    initial = set(run['rounds'][0]['selected']) if run['rounds'] else set()
    recall = lambda selected: (sum(bool(selected & set(sample['acceptable_sources'][t])) for t in supported_tasks)
                              / len(supported_tasks) if supported_tasks else None)
    evidence_recall = (sum(bool(retrieved & set(sample['acceptable_documents'][t])) for t in supported_tasks)
                       / len(supported_tasks) if supported_tasks else None)
    fact_checks = {t: bool(cited & set(sample['acceptable_documents'][t])) and
                  all(anchor.lower() in run['answer'].lower().replace(' ', '') for anchor in ANCHORS[t])
                  for t in supported_tasks}
    fact_recall = statistics.mean(fact_checks.values()) if fact_checks else None
    abstained = bool(re.search(r'证据不足|无法确定|未提供|缺少|缺乏|无法.{0,8}(回答|确认|判断|提供)|没有.{0,8}证据|未能', run['answer']))
    # Partial-answer tasks need both known evidence and an explicit unknown statement.
    components = list(fact_checks.values())
    if not sample['fully_answerable']:
        components.append(abstained)
    quality = statistics.mean(components) if components else float(abstained)
    if run['generation_error']:
        quality = 0.0
    useful = {s for choices in sample['acceptable_sources'].values() for s in choices}
    calls = [r['source'] for step in run['rounds'] for r in step['retrievals']]
    return dict(quality_proxy=quality, fact_recall_proxy=fact_recall, fact_checks=fact_checks,
                necessary_source_recall=recall(sources), initial_source_recall=recall(initial),
                evidence_recall=evidence_recall, citation_validity=len(cited & all_valid)/len(cited) if cited else None,
                abstained=abstained, fully_answered=not abstained and not run['generation_error'],
                answerability_correct=(not abstained)==sample['fully_answerable'] and not bool(run['generation_error']),
                unnecessary_call_rate=sum(s not in useful for s in calls)/len(calls) if calls else 0,
                generation_success=not bool(run['generation_error']))


def quantile(values, p):
    ordered = sorted(values)
    index = (len(ordered)-1)*p
    low = int(index)
    high = min(low+1, len(ordered)-1)
    return ordered[low]+(ordered[high]-ordered[low])*(index-low)


def mean_present(values):
    valid = [v for v in values if v is not None]
    return statistics.mean(valid) if valid else None


def aggregate(records):
    groups = {}
    for r in records:
        for category in ('overall', r['category']):
            groups.setdefault((r['run']['method'], category), []).append(r)
    summaries = []
    for (method, category), members in groups.items():
        scores = [r['scores'] for r in members]
        costs = [r['run']['metrics'] for r in members]
        row = dict(method=method, category=category, n=len(members))
        for key in ('quality_proxy', 'fact_recall_proxy', 'necessary_source_recall', 'initial_source_recall',
                    'evidence_recall', 'citation_validity', 'unnecessary_call_rate', 'generation_success', 'answerability_correct'):
            row[key] = mean_present([s[key] for s in scores])
        row['answer_coverage'] = statistics.mean(s['fully_answered'] for s in scores)
        row['answered_quality_proxy'] = mean_present([s['quality_proxy'] for s in scores if s['fully_answered']])
        for key in ('processed_token_proxy', 'api_total_tokens_known', 'api_calls', 'retrieval_calls', 'module_calls'):
            row['mean_'+key] = mean_present([c[key] for c in costs])
        row['api_usage_complete_rate'] = statistics.mean(c['api_usage_complete'] for c in costs)
        row['p50_ms'] = quantile([c['elapsed_ms'] for c in costs], 0.5)
        row['p95_ms'] = quantile([c['elapsed_ms'] for c in costs], 0.95)
        summaries.append(row)
    return sorted(summaries, key=lambda r: (r['category'], r['method']))


def paired_intervals(records, draws=1000):
    """Bootstrap question clusters; repetitions are NOT independent samples."""
    grouped = {}
    for r in records:
        grouped.setdefault((r['sample_id'], r['run']['method']), []).append(r)
    ids = sorted({k[0] for k in grouped})
    output = []
    rng = random.Random(20261017)
    for baseline in ('all', 'positive', 'fixed'):
        for metric in ('quality_proxy', 'retrieval_calls', 'processed_token_proxy', 'api_total_tokens_known'):
            def value(member):
                return member['scores'][metric] if metric == 'quality_proxy' else member['run']['metrics'][metric]
            differences = []
            for sample_id in ids:
                a = mean_present([value(x) for x in grouped.get((sample_id, 'dynamic'), [])])
                b = mean_present([value(x) for x in grouped.get((sample_id, baseline), [])])
                if a is not None and b is not None:
                    differences.append(a-b)
            if differences:
                bootstrap = [statistics.mean(rng.choices(differences, k=len(differences))) for _ in range(draws)]
                output.append(dict(comparison='dynamic - '+baseline, metric=metric,
                                   mean_difference=statistics.mean(differences),
                                   ci95=[quantile(bootstrap, .025), quantile(bootstrap, .975)], n_questions=len(differences)))
    return output
