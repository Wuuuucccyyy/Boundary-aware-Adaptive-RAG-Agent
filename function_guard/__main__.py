"""Run one structured request, or replay the development condition cases."""
import argparse
from importlib.resources import files
import json
from pathlib import Path
from .engine import ProfileStore, evaluate


def run_cases(store=None):
    store=store or ProfileStore()
    cases=json.loads(files('function_guard').joinpath('data/condition_cases.json').read_text(encoding='utf-8'))
    results=[]
    for case in cases:
        actual=evaluate(case['request'],store)
        statuses={c['claim_id']:c['status'] for c in actual['checks']}
        passed=actual['state']==case['expected']['state'] and all(statuses.get(k)==v for k,v in case['expected']['checks'].items())
        results.append(dict(id=case['id'],purpose=case['purpose'],passed=passed,expected=case['expected'],actual=actual))
    return dict(kind='offline_development_condition_cases',cases=len(results),passed=sum(r['passed'] for r in results),results=results)


def main():
    p=argparse.ArgumentParser(description='Check documented function input constraints; does not execute R')
    p.add_argument('--request',type=Path);p.add_argument('--cases',action='store_true');p.add_argument('--profiles',type=Path)
    p.add_argument('--output',type=Path);p.add_argument('--max-checks',type=int,default=80)
    args=p.parse_args()
    if bool(args.request)==args.cases:p.error('Choose exactly one of --request or --cases')
    store=ProfileStore(args.profiles)
    result=run_cases(store) if args.cases else evaluate(json.loads(args.request.read_text(encoding='utf-8')),store,args.max_checks)
    text=json.dumps(result,ensure_ascii=False,indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(text+'\n',encoding='utf-8',newline='\n')
    if args.cases:
        print(f"{result['passed']}/{result['cases']} condition cases passed")
        for r in result['results']:
            if not r['passed']:print(r['id'],r['expected'],r['actual']['state'],{c['claim_id']:c['status'] for c in r['actual']['checks']})
        if result['passed']!=result['cases']:raise SystemExit(1)
    else:print(text)

if __name__=='__main__':main()
