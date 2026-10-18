"""Frozen 12-case, two-policy online engineering comparison; no R execution."""
import argparse
from datetime import datetime,timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import random
import statistics
import sys
import time

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from boundary_rag.credentials import load_ccswitch
from function_guard import ProfileStore
from function_guard.routing import METHODS,route
from function_guard.provider import payload_for,generate


def canonical(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'))


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')


def identity(store,model):
    paths=sorted((ROOT/'function_guard').glob('*.py'))+[Path(__file__),ROOT/'boundary_rag/credentials.py']
    digest=hashlib.sha256()
    for p in paths:digest.update(p.relative_to(ROOT).as_posix().encode());digest.update(p.read_text(encoding='utf-8').encode())
    data={p.name:hashlib.sha256(canonical(json.loads(p.read_text(encoding='utf-8'))).encode()).hexdigest() for p in sorted((ROOT/'function_guard/data').glob('*.json'))}
    return dict(code_sha256=digest.hexdigest(),profile_snapshot=store.snapshot,data_sha256=data,model=model,
                methods=list(METHODS),seed=901,max_checks=80,max_candidates=4,max_output_tokens=350,max_api_tokens=12000,
                timeout_seconds=45,repeats=1,temperature=0,thinking='disabled',backend='deepseek')


def summarize(records):
    result=[]
    for method in METHODS:
        rs=[r for r in records if r['decision']['method']==method]
        known=[r['generation']['api']['total_tokens'] for r in rs if r['generation']['api']['usage_known']]
        result.append(dict(method=method,n=len(rs),configuration_score=statistics.mean(r['scores']['configuration_correct'] for r in rs),
            rendering_score=statistics.mean(r['scores']['rendering_valid'] for r in rs),
            end_to_end_score=statistics.mean(r['scores']['end_to_end'] for r in rs),
            checks_per_case=statistics.mean(r['decision']['budget']['checks_used'] for r in rs),
            input_reads_per_case=statistics.mean(r['decision']['metrics']['input_reads'] for r in rs),
            api_calls=sum(r['generation']['api']['calls'] for r in rs),known_usage=len(known),
            api_tokens=sum(known),processing_proxy_per_case=statistics.mean(r['processing_proxy'] for r in rs),
            elapsed_ms_median=statistics.median(r['elapsed_ms'] for r in rs)))
    return result


def main():
    p=argparse.ArgumentParser();p.add_argument('--ccswitch',action='store_true');p.add_argument('--output',type=Path,required=True);p.add_argument('--resume',action='store_true')
    args=p.parse_args()
    if args.ccswitch:load_ccswitch()
    if not all(os.environ.get(k) for k in ('DEEPSEEK_API_KEY','DEEPSEEK_MODEL')):p.error('Missing DeepSeek configuration')
    store=ProfileStore();ident=identity(store,os.environ['DEEPSEEK_MODEL']);manifest=args.output/'manifest.json'
    if manifest.exists():
        old=json.loads(manifest.read_text(encoding='utf-8'))
        if not args.resume or old['identity']!=ident:p.error('Output exists; resume requires identical frozen inputs')
    else:write(manifest,dict(identity=ident,started_utc=datetime.now(timezone.utc).isoformat()))
    cases=json.loads((ROOT/'function_guard/data/routing_cases.json').read_text(encoding='utf-8'))
    random.Random(901).shuffle(cases);records=[]
    for i,case in enumerate(cases):
        methods=METHODS if i%2==0 else METHODS[::-1]
        for method in methods:
            path=args.output/'traces'/f'{case["id"]}-{method}.json'
            if args.resume and path.exists():record=json.loads(path.read_text(encoding='utf-8'))
            else:
                start=time.perf_counter();decision=route(case['request'],method,store)
                payload=payload_for(case['request'],decision);generation=generate(payload)
                correct=all(decision[k]==v for k,v in case['expected'].items())
                valid=not generation['error']
                record=dict(case_id=case['id'],request=case['request'],decision=decision,generation_payload=payload,generation=generation,
                            scores=dict(configuration_correct=correct,rendering_valid=valid,end_to_end=correct and valid),
                            processing_proxy=(decision['metrics']['profile_bytes']+len(canonical(case['request']).encode())+len(canonical(decision).encode())+3)//4+generation['processing_proxy'],
                            elapsed_ms=(time.perf_counter()-start)*1000)
                write(path,record)
            records.append(record)
            print(f"{len(records)}/24 {case['id']} {method} state={record['decision']['state']} selected={record['decision']['selected']} error={record['generation']['error']}",flush=True)
    write(args.output/'summary.json',summarize(records))
    write(args.output/'failures.json',[r for r in records if not r['scores']['end_to_end']])
    archive=args.output/'traces.jsonl.gz'
    with archive.open('wb') as raw:
        with gzip.GzipFile(filename='',fileobj=raw,mode='wb',mtime=0) as f:
            for r in sorted(records,key=lambda r:(r['case_id'],r['decision']['method'])):f.write((canonical(r)+'\n').encode())
    write(args.output/'archive.json',dict(records=len(records),sha256=hashlib.sha256(archive.read_bytes()).hexdigest()))
    saved=json.loads(manifest.read_text(encoding='utf-8'));saved.update(completed_utc=datetime.now(timezone.utc).isoformat(),records=len(records));write(manifest,saved)

if __name__=='__main__':main()
