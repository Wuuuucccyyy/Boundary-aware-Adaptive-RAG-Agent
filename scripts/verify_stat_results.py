"""Offline verification of the published online experiment and its provenance."""
import argparse
import gzip
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
from stat_rag.core import Corpus,canonical,METHODS,Settings,select
from stat_rag.fixtures import DATA
from stat_rag.evaluation import score,summarize
from run_stat_experiments import code_hash


def verify(directory):
    manifest=json.loads((directory/'manifest.json').read_text(encoding='utf-8'));identity=manifest['identity']
    metadata=json.loads((directory/'archive.json').read_text(encoding='utf-8'));archive=directory/'traces.jsonl.gz'
    assert hashlib.sha256(archive.read_bytes()).hexdigest()==metadata['sha256'],'Archive checksum mismatch'
    with gzip.open(archive,'rt',encoding='utf-8') as f:records=[json.loads(line) for line in f]
    samples=json.loads((DATA/'benchmark.json').read_text(encoding='utf-8'))
    assert hashlib.sha256(canonical(samples).encode()).hexdigest()==identity['benchmark_sha256'],'Benchmark changed'
    assert code_hash()==identity['code_sha256'],'Frozen code changed'
    gold={s['id']:s for s in samples if s['split']==identity['split']}
    expected={(sid,size,method,rep) for sid in gold for size in identity['sizes'] for method in METHODS for rep in range(identity['repeats'])}
    actual={(r['sample_id'],r['run']['size'],r['run']['method'],r['repetition']) for r in records}
    assert actual==expected and len(actual)==len(records)==metadata['records'],'Missing/duplicate trial'
    for size in identity['sizes']:assert Corpus(size).snapshot==identity['corpus_sha256'][str(size)],'Data changed'
    for r in records:
        run=r['run'];assert score(gold[r['sample_id']],run)==r['scores'],'Score drift'
        assert run['settings']==identity['settings']
        assert run['metrics']['retrieval_calls']<=run['settings']['max_retrieval_calls']
        assert run['metrics']['rounds']<=run['settings']['max_rounds']
        assert run['metrics']['module_calls']==len(run['events'])
        assert run['metrics']['processing_proxy']==sum(e['processing_proxy'] for e in run['events'])
        if run['api']['usage_known']:assert run['api']['total_tokens']==run['api']['prompt_tokens']+run['api']['completion_tokens']
    saved=json.loads((directory/'summary.json').read_text(encoding='utf-8'));fresh=summarize(records)
    assert len(saved)==len(fresh)
    for a,b in zip(saved,fresh):
        for k,v in a.items():
            if isinstance(v,(int,float)) and isinstance(b[k],(int,float)):assert math.isclose(v,b[k],rel_tol=1e-10,abs_tol=1e-10),k
            else:assert v==b[k],k
    print(f'PASS: {len(records)} online traces, complete schedule, source/code hashes, scores, token ledger and summaries')
    return records


def main():
    p=argparse.ArgumentParser();p.add_argument('directory',type=Path,nargs='?',default=ROOT/'results/stat_online')
    args=p.parse_args();verify(args.directory)


if __name__=='__main__':main()
