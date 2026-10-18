"""Frozen round-two online experiment. Offline runs are development-only."""
import argparse
from dataclasses import asdict
from datetime import datetime,timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import platform
import random
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from stat_rag.core import Agent,Settings,METHODS,canonical
from stat_rag.fixtures import DATA,write
from stat_rag.evaluation import score,summarize,bootstrap
from boundary_rag.credentials import load_ccswitch


def code_hash():
    digest=hashlib.sha256()
    paths=sorted((ROOT/'stat_rag').glob('*.py'))+[Path(__file__),ROOT/'boundary_rag/text.py',ROOT/'boundary_rag/retrieval.py',ROOT/'boundary_rag/credentials.py']
    for path in paths:
        digest.update(path.relative_to(ROOT).as_posix().encode())
        digest.update(path.read_text(encoding='utf-8').replace('\r\n','\n').encode())
    return digest.hexdigest()


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    p=argparse.ArgumentParser()
    p.add_argument('--backend',choices=('offline','deepseek'),default='offline')
    p.add_argument('--ccswitch',action='store_true');p.add_argument('--split',choices=('dev','test'),default='dev')
    p.add_argument('--repeats',type=int,default=1);p.add_argument('--sizes',type=int,nargs='+',default=[10,20,30])
    p.add_argument('--output',type=Path,required=True);p.add_argument('--resume',action='store_true')
    args=p.parse_args()
    if args.repeats<1 or len(set(args.sizes))!=len(args.sizes) or any(s not in (10,20,30) for s in args.sizes):p.error('Invalid sizes or repeats')
    if args.ccswitch:load_ccswitch()
    if args.backend=='deepseek' and not all(os.environ.get(k) for k in ('DEEPSEEK_API_KEY','DEEPSEEK_MODEL')):p.error('Missing DeepSeek configuration')
    agents={size:Agent(size,backend=args.backend) for size in args.sizes}
    all_samples=json.loads((DATA/'benchmark.json').read_text(encoding='utf-8'))
    samples=[s for s in all_samples if s['split']==args.split]
    identity=dict(backend=args.backend,model=os.environ.get('DEEPSEEK_MODEL') if args.backend=='deepseek' else 'offline-extractive',
                  split=args.split,repeats=args.repeats,sizes=args.sizes,methods=METHODS,code_sha256=code_hash(),
                  corpus_sha256={str(s):a.corpus.snapshot for s,a in agents.items()},
                  benchmark_sha256=hashlib.sha256(canonical(all_samples).encode()).hexdigest(),
                  settings=asdict(Settings()),seed=817,temperature=0,thinking='disabled',concurrency=1)
    # Round trip tuples to lists for stable manifest equality.
    identity=json.loads(json.dumps(identity));manifest_path=args.output/'manifest.json'
    if manifest_path.exists():
        old=json.loads(manifest_path.read_text(encoding='utf-8'))
        if not args.resume or old['identity']!=identity:p.error('Existing output requires --resume with identical frozen inputs')
    else:write(manifest_path,dict(identity=identity,started_utc=datetime.now(timezone.utc).isoformat(),python=platform.python_version(),platform=platform.platform()))
    schedule=[(rep,size,sample) for rep in range(args.repeats) for size in args.sizes for sample in samples]
    random.Random(817).shuffle(schedule)
    records=[];total=len(schedule)*len(METHODS)
    for i,(rep,size,sample) in enumerate(schedule):
        offset=i%len(METHODS)
        for method in METHODS[offset:]+METHODS[:offset]:
            path=args.output/'traces'/f'{sample["id"]}-{size}-{method}-{rep}.json'
            if args.resume and path.exists():r=json.loads(path.read_text(encoding='utf-8'))
            else:
                run=agents[size].run(sample['query'],method)
                r=dict(sample_id=sample['id'],category=sample['category'],repetition=rep,scores=score(sample,run),run=run)
                write(path,r)
            records.append(r)
            print(f"{len(records)}/{total} {sample['id']} N={size} {method} score={r['scores']['evidence_answer_score']:.2f} tokens={r['run']['api']['total_tokens'] if r['run']['api']['usage_known'] else 'unknown'} error={r['run']['generation_error']}",flush=True)
    write(args.output/'summary.json',summarize(records));write(args.output/'paired_ci.json',bootstrap(records))
    failures=[dict(sample_id=r['sample_id'],size=r['run']['size'],method=r['run']['method'],repetition=r['repetition'],scores=r['scores'],
                   error=r['run']['generation_error'],missing=r['run']['state']['missing'],output=r['run']['output']) for r in records if not r['scores']['exact_task_success']]
    write(args.output/'failures.json',failures)
    archive=args.output/'traces.jsonl.gz'
    with archive.open('wb') as raw:
        with gzip.GzipFile(filename='',fileobj=raw,mode='wb',mtime=0) as stream:
            for r in sorted(records,key=lambda r:(r['sample_id'],r['run']['size'],r['run']['method'],r['repetition'])):
                stream.write((canonical(r)+'\n').encode())
    write(args.output/'archive.json',dict(records=len(records),sha256=hashlib.sha256(archive.read_bytes()).hexdigest()))
    manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
    manifest.update(completed_utc=datetime.now(timezone.utc).isoformat(),records=len(records),failures=len(failures))
    write(manifest_path,manifest)
    print('Completed '+str(args.output))


if __name__=='__main__':main()
