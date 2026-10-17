"""Reproducible four-way experiment with balanced order and resumable raw traces."""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import random
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from boundary_rag.agent import Agent
from boundary_rag.credentials import load_ccswitch
from boundary_rag.evaluation import aggregate, paired_intervals, score
from boundary_rag.routing import METHODS
from boundary_rag.schema import Config


def dump(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser()
    parser.add_argument('--backend', choices=['extractive', 'deepseek'], default='extractive')
    parser.add_argument('--ccswitch', action='store_true')
    parser.add_argument('--split', choices=['dev', 'test'], default='test')
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--output', type=Path, default=ROOT/'results/offline')
    parser.add_argument('--max-rounds', type=int, default=3)
    parser.add_argument('--positive-top-k', type=int, default=1)
    parser.add_argument('--resume', action='store_true')
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error('--repeats must be positive')
    if args.ccswitch:
        load_ccswitch()
    config = Config(max_rounds=args.max_rounds, positive_top_k=args.positive_top_k)
    agent = Agent(config=config, backend=args.backend)
    query_path = ROOT/'experiments/queries.json'
    samples = [s for s in json.loads(query_path.read_text(encoding='utf-8')) if s['split'] == args.split]
    samples.sort(key=lambda s: s['id'])
    random.Random(20261017).shuffle(samples)
    code_hash = hashlib.sha256()
    for path in sorted((ROOT/'boundary_rag').glob('*.py')) + [Path(__file__), ROOT/'scripts/build_benchmark.py']:
        code_hash.update(path.name.encode())
        code_hash.update(path.read_bytes())
    identity = dict(backend=args.backend, model=os.environ.get('DEEPSEEK_MODEL') if args.backend=='deepseek' else 'extractive-v1',
                    corpus_sha256=agent.corpus.snapshot, query_sha256=hashlib.sha256(query_path.read_bytes()).hexdigest(),
                    code_sha256=code_hash.hexdigest(), config=config.to_dict(), split=args.split, repeats=args.repeats,
                    seed=20261017, temperature=0, thinking='disabled', concurrency=1)
    manifest_path = args.output/'manifest.json'
    if manifest_path.exists():
        previous = json.loads(manifest_path.read_text(encoding='utf-8'))
        if not args.resume or previous['identity'] != identity:
            parser.error('Output exists. Use a fresh output folder, or --resume with identical code/config/data.')
    else:
        dump(manifest_path, dict(identity=identity, started_at=datetime.now(timezone.utc).isoformat(),
                                python=platform.python_version(), platform=platform.platform(),
                                note='No application cache; provider cache usage is retained. Timings exclude startup, index build and disk writes.'))
    records = []
    total = len(samples)*len(METHODS)*args.repeats
    for repetition in range(args.repeats):
        for index, sample in enumerate(samples):
            # Rotate order to spread API cache / provider drift across methods.
            offset = (index+repetition) % len(METHODS)
            order = METHODS[offset:]+METHODS[:offset]
            for method in order:
                path = args.output/'traces'/f'{sample["id"]}-{method}-{repetition}.json'
                if args.resume and path.exists():
                    record = json.loads(path.read_text(encoding='utf-8'))
                else:
                    run = agent.answer(sample['query'], method)
                    record = dict(sample_id=sample['id'], category=sample['category'], repetition=repetition,
                                  scores=score(sample, run), run=run)
                    dump(path, record)
                records.append(record)
                print(f"{len(records)}/{total} {sample['id']} {method} quality={record['scores']['quality_proxy']:.2f} "
                      f"api_tokens={record['run']['metrics']['api_total_tokens_known']}", flush=True)
    summary = aggregate(records)
    dump(args.output/'summary.json', summary)
    dump(args.output/'paired_ci.json', paired_intervals(records))
    with (args.output/'summary.csv').open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(summary[0]))
        writer.writeheader()
        writer.writerows(summary)
    failures = [dict(sample_id=r['sample_id'], method=r['run']['method'], repetition=r['repetition'],
                     query=r['run']['query'], answer=r['run']['answer'], tasks=r['run']['tasks'],
                     missing=r['run']['evidence']['missing'], scores=r['scores'],
                     trace=f"traces/{r['sample_id']}-{r['run']['method']}-{r['repetition']}.json")
                for r in records if r['scores']['quality_proxy'] < 1 or not r['scores']['answerability_correct']]
    dump(args.output/'failures.json', failures)
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    manifest.update(completed_at=datetime.now(timezone.utc).isoformat(), runs=len(records), failure_records=len(failures))
    dump(manifest_path, manifest)
    print('Completed: '+str(args.output), flush=True)


if __name__ == '__main__':
    main()
