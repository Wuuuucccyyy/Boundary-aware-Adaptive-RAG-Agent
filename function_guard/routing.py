"""Two ranking policies sharing all information, guard checks and budgets."""
import json
import time
from .engine import ProfileStore,evaluate,unknown

METHODS=('full_profile','dynamic')


def route(request,method,store=None,max_checks=80,max_candidates=4):
    if method not in METHODS:raise ValueError('Unknown routing method')
    if type(max_checks) is not int or max_checks<1:raise ValueError('Invalid check budget')
    candidates=request['candidates']
    if not 1<=len(candidates)<=max_candidates:raise ValueError('Candidate budget exceeded')
    if len({c['id'] for c in candidates})!=len(candidates):raise ValueError('Duplicate candidate IDs')
    store=store or ProfileStore();started=time.perf_counter();remaining=max_checks;rows=[];exhausted=False
    for candidate in candidates:
        goals=[]
        parameters=candidate['parameters']
        behavior=request.get('required_behavior',{})
        reserved=len(request.get('required_parameters',{}))+len(behavior)+1
        if remaining<=reserved:
            rows.append(dict(id=candidate['id'],state='unknown',goal_checks=[],
                             guard=None,reason='shared_check_budget_exhausted'))
            exhausted=True;continue
        for key,wanted in request.get('required_parameters',{}).items():
            actual=parameters.get(key)
            goals.append(dict(kind='requested_parameter',key=key,wanted=wanted,actual=actual,
                              status='unknown' if unknown(actual) else 'satisfied' if type(actual) is type(wanted) and actual==wanted else 'conflict',
                              source='explicit_user_requirement'))
        guard=evaluate(dict(function_id=candidate['function_id'],parameters=parameters,
                            facts=request.get('facts',{}),fact_provenance=request.get('fact_provenance',{})),
                       store,max_checks=remaining-reserved)
        profile=store.records[candidate['function_id']]
        tasks={c['value'] for c in profile['task_type'] if c['basis']=='documented'}
        goals.append(dict(kind='requested_task',key='task',wanted=request['task'],actual=sorted(tasks),
                          status='satisfied' if request['task'] in tasks else 'conflict',source='explicit_user_requirement_and_profile_task'))
        for attr,wanted in behavior.items():
            matches=[c for c in guard['checks'] if c['attribute']==attr and c['active']=='true' and c['status']=='informational']
            values=[c['value'] for c in matches]
            goals.append(dict(kind='requested_behavior',key=attr,wanted=wanted,actual=values,
                              status='satisfied' if wanted in values else 'conflict' if values else 'unknown',
                              source='explicit_user_requirement_and_conditional_profile_behavior',
                              claim_ids=[c['claim_id'] for c in matches]))
        remaining-=guard['budget']['checks_used']+reserved
        exhausted=exhausted or guard['budget']['exhausted']
        state=guard['state']
        if any(g['status']=='conflict' for g in goals):state='conflict'
        elif any(g['status']=='unknown' for g in goals) and state=='applicable':state='unknown'
        rows.append(dict(id=candidate['id'],state=state,goal_checks=goals,guard=guard,reason='shared_guard_and_goal_checks'))
    eligible=[r for r in rows if r['state']=='applicable']
    for row in rows:
        checks=row['guard']['checks'] if row['guard'] else []
        required=[c for c in checks if c['critical'] and c['active']!='false']
        matched=sum(c['status']=='satisfied' for c in required)
        warnings=sum(c['status']=='warning' for c in checks)
        # Both policies enforce the SAME confirmed-conflict and unknown guards.
        row['ranking_score']=(matched/max(1,len(required))) if method=='full_profile' else -sum(c['status']=='conflict' for c in checks)-sum(c['critical'] and c['status'] in ('unknown','documentation_conflict') for c in checks)-0.1*warnings
    best=sorted(eligible,key=lambda r:(-r['ranking_score'],r['id']))[0] if eligible else None
    state='applicable' if best else 'unknown' if any(r['state']=='unknown' for r in rows) else 'conflict'
    action='proceed_with_documented_scope' if best else 'clarify_or_review' if state=='unknown' else 'no_compatible_configuration'
    # Same full profiles supplied to both policies; no gold labels are read here.
    profile_bytes=len(json.dumps([store.records[c['function_id']] for c in candidates],ensure_ascii=False).encode())
    return dict(method=method,selected=best['id'] if best else None,state=state,action=action,candidates=rows,
                profile_snapshot=store.snapshot,budget=dict(max_checks=max_checks,checks_used=max_checks-remaining,
                max_candidates=max_candidates,candidates_evaluated=sum(r['guard'] is not None for r in rows),exhausted=exhausted),
                metrics=dict(profile_bytes=profile_bytes,input_reads=sum(r['guard']['metrics']['fact_reads'] for r in rows if r['guard']),
                             elapsed_ms=(time.perf_counter()-started)*1000),
                scope='configuration_compatibility_not_execution_or_complete_statistical_validity')
