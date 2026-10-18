"""Verify source snapshots, all attempts, policy fairness and accounting offline."""
import argparse
import gzip
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
from function_guard import ProfileStore
from function_guard.routing import route,METHODS
from function_guard.provider import validate
from run_function_comparison import canonical,summarize


def verify(directory):
    manifest=json.loads((directory/'manifest.json').read_text(encoding='utf-8'));ident=manifest['identity']
    snapshot=json.loads((directory/'source_snapshot.json').read_text(encoding='utf-8'))
    paths=sorted(p for p in snapshot if p.startswith('function_guard/'))+['scripts/run_function_comparison.py','boundary_rag/credentials.py']
    digest=hashlib.sha256()
    for p in paths:digest.update(p.encode());digest.update(snapshot[p].encode())
    assert digest.hexdigest()==ident['code_sha256'],'Frozen source snapshot changed'
    for name,expected in ident['data_sha256'].items():
        data=json.loads((ROOT/'function_guard/data'/name).read_text(encoding='utf-8'))
        assert hashlib.sha256(canonical(data).encode()).hexdigest()==expected,'Case data changed'
    store=ProfileStore();assert store.snapshot==ident['profile_snapshot'],'Profile data changed'
    metadata=json.loads((directory/'archive.json').read_text(encoding='utf-8'));archive=directory/'traces.jsonl.gz'
    assert hashlib.sha256(archive.read_bytes()).hexdigest()==metadata['sha256'],'Archive changed'
    with gzip.open(archive,'rt',encoding='utf-8') as f:records=[json.loads(line) for line in f]
    cases={r['id']:r for r in json.loads((ROOT/'function_guard/data/routing_cases.json').read_text(encoding='utf-8'))}
    actual={(r['case_id'],r['decision']['method']) for r in records}
    assert actual=={(sid,m) for sid in cases for m in METHODS} and len(actual)==len(records)==metadata['records']==manifest['records']
    paired={}
    for r in records:
        case=cases[r['case_id']];d=r['decision'];g=r['generation']
        assert r['request']==case['request']
        assert r['scores']['configuration_correct']==all(d[k]==v for k,v in case['expected'].items())
        assert r['scores']['rendering_valid']==(g['error'] is None)
        assert r['scores']['end_to_end']==(r['scores']['configuration_correct'] and r['scores']['rendering_valid'])
        assert d['budget']['checks_used']<=ident['max_checks'] and d['budget']['candidates_evaluated']<=ident['max_candidates']
        if g['api']['usage_known']:assert g['api']['total_tokens']==g['api']['prompt_tokens']+g['api']['completion_tokens']
        if not g['error']:validate(g['output'],r['generation_payload'])
        if g['error']=='api_token_budget':assert g['api']['calls']==0 and g['api']['total_tokens']==0
        # Replay only when the current guard/routing code matches the snapshot.
        if all((ROOT/p).read_text(encoding='utf-8')==snapshot[p] for p in ('function_guard/engine.py','function_guard/routing.py')):
            fresh=route(case['request'],d['method'],store)
            for k in ('selected','state','action','budget'):assert fresh[k]==d[k]
            for a,b in zip(fresh['candidates'],d['candidates']):
                assert a['goal_checks']==b['goal_checks']
                if a['guard']:assert a['guard']['checks']==b['guard']['checks']
        paired.setdefault(r['case_id'],[]).append(r)
    for rs in paired.values():
        assert len(rs)==2 and rs[0]['generation_payload']==rs[1]['generation_payload'],'Policy receives different generation information'
        assert rs[0]['decision']['budget']==rs[1]['decision']['budget'],'Policy receives different budgets'
    saved=json.loads((directory/'summary.json').read_text(encoding='utf-8'));fresh=summarize(records)
    for a,b in zip(saved,fresh):
        for k,v in a.items():
            if type(v) in (int,float):assert math.isclose(v,b[k],rel_tol=1e-10,abs_tol=1e-10),k
            else:assert v==b[k],k
    print(f'PASS: {directory.name}, {len(records)} attempts, frozen sources/data, decisions, equal policy inputs/budgets and token ledger')
    return records


def main():
    p=argparse.ArgumentParser();p.add_argument('directory',type=Path,nargs='?',default=ROOT/'results/function_online_v2')
    args=p.parse_args();verify(args.directory)

if __name__=='__main__':main()
