"""Evaluate structured evidence use; free-text entailment is not claimed."""
import random
import statistics as st


def score(sample,run):
    gold=sample['acceptable_documents'];answer=run['output']
    claims=answer.get('claims',[]) if isinstance(answer,dict) else []
    unknown=answer.get('unknown',[]) if isinstance(answer,dict) else []
    documents={h['document']['id']:h['document'] for step in run['rounds'] for call in step['retrievals'] for h in call['hits']}
    valid={}
    for claim in claims:
        if not isinstance(claim,dict):continue
        t=claim.get('requirement_id');doc=claim.get('document_id')
        if t in gold and doc in gold[t] and doc in documents and claim.get('quote')==documents[doc]['quote']:
            valid[t]=doc
    checks=[t in valid if ids else t in unknown and not any(isinstance(c,dict) and c.get('requirement_id')==t for c in claims) for t,ids in gold.items()]
    quality=st.mean(checks) if checks else 0
    if run['generation_error']:quality=0
    supported=[ids for ids in gold.values() if ids]
    recall=lambda selected: st.mean(any(doc.removesuffix('-report') in selected for doc in ids) for ids in supported) if supported else None
    requested=[call['source'] for step in run['rounds'] for call in step['retrievals']]
    useful={d.removesuffix('-report') for ids in gold.values() for d in ids}
    output_precision=len(valid)/len(claims) if claims else None
    return dict(evidence_answer_score=quality,exact_task_success=all(checks) and not run['generation_error'],
                source_recall=recall(set(requested)),initial_source_recall=recall(set(run['rounds'][0]['selected']) if run['rounds'] else set()),
                evidence_recall=st.mean(any(d in documents for d in ids) for ids in supported) if supported else None,
                claim_precision=output_precision,unnecessary_calls=sum(s not in useful for s in requested),
                inappropriate_documents=len({r['document_id'] for r in run['state']['rejections'] if r['state']=='conflict'}),
                generation_success=not bool(run['generation_error']))


def percentile(values,p):
    x=sorted(values);i=(len(x)-1)*p;lo=int(i);hi=min(lo+1,len(x)-1)
    return x[lo]+(x[hi]-x[lo])*(i-lo)


def average(xs):
    values=[v for v in xs if v is not None]
    return st.mean(values) if values else None


def summarize(records):
    groups={}
    for r in records:
        for category in ('overall',r['category']):groups.setdefault((r['run']['size'],r['run']['method'],category),[]).append(r)
    results=[]
    for (size,method,category),items in sorted(groups.items()):
        out=dict(size=size,method=method,category=category,n=len(items))
        for key in items[0]['scores']:out[key]=average([x['scores'][key] for x in items])
        for key in ('retrieval_calls','module_calls','rounds','processing_proxy'):out[key]=average([x['run']['metrics'][key] for x in items])
        out['api_tokens']=average([x['run']['api']['total_tokens'] if x['run']['api']['usage_known'] else None for x in items])
        out['api_usage_known_rate']=average([x['run']['api']['usage_known'] for x in items])
        out['p50_ms']=percentile([x['run']['metrics']['elapsed_ms'] for x in items],.5)
        out['p95_ms']=percentile([x['run']['metrics']['elapsed_ms'] for x in items],.95)
        results.append(out)
    return results


def bootstrap(records):
    rng=random.Random(817);results=[]
    for size in sorted({r['run']['size'] for r in records}):
        for base in ('positive','full_profile','no_negative'):
            for metric in ('evidence_answer_score','retrieval_calls','api_tokens'):
                grouped={}
                for r in records:
                    if r['run']['size']!=size or r['run']['method'] not in ('dynamic',base):continue
                    value=r['scores'][metric] if metric=='evidence_answer_score' else r['run']['metrics'][metric] if metric=='retrieval_calls' else r['run']['api']['total_tokens'] if r['run']['api']['usage_known'] else None
                    grouped.setdefault((r['sample_id'],r['run']['method']),[]).append(value)
                diffs=[]
                for sid in sorted({k[0] for k in grouped}):
                    a=average(grouped.get((sid,'dynamic'),[]));b=average(grouped.get((sid,base),[]))
                    if a is not None and b is not None:diffs.append(a-b)
                if diffs:
                    values=[st.mean(rng.choices(diffs,k=len(diffs))) for _ in range(1000)]
                    results.append(dict(size=size,comparison='dynamic - '+base,metric=metric,mean=st.mean(diffs),ci95=[percentile(values,.025),percentile(values,.975)],question_clusters=len(diffs)))
    return results
