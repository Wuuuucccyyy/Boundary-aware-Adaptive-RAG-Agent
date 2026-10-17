"""Recompute published metrics from raw traces without making API calls."""
import argparse
import gzip
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from boundary_rag.evaluation import aggregate, score


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('directory', nargs='?', type=Path, default=ROOT/'results/online')
    args = parser.parse_args()
    metadata = json.loads((args.directory/'archive.json').read_text(encoding='utf-8'))
    archive = args.directory/metadata['filename']
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == metadata['sha256'], 'Archive checksum mismatch'
    with gzip.open(archive, 'rt', encoding='utf-8') as stream:
        records = [json.loads(line) for line in stream]
    assert len(records) == metadata['records']
    samples = {s['id']:s for s in json.loads((ROOT/'experiments/queries.json').read_text(encoding='utf-8'))}
    identity = json.loads((args.directory/'manifest.json').read_text(encoding='utf-8'))['identity']
    expected = {(s['id'], m, rep) for s in samples.values() if s['split']==identity['split']
                for m in ('all','positive','fixed','dynamic') for rep in range(identity['repeats'])}
    actual = {(r['sample_id'],r['run']['method'],r['repetition']) for r in records}
    assert len(actual) == len(records) and actual == expected, 'Missing or duplicated trial'
    for r in records:
        run = r['run']
        assert score(samples[r['sample_id']], run) == r['scores'], 'Evaluation drift'
        assert run['corpus_sha256'] == identity['corpus_sha256']
        assert run['config'] == identity['config']
        assert run['metrics']['retrieval_calls'] <= run['config']['max_retrieval_calls']
        assert run['metrics']['module_calls'] <= run['config']['max_module_calls']
        actual_tokens = sum(e['api_prompt_tokens'] + e['api_completion_tokens'] for e in run['events'])
        assert actual_tokens == run['metrics']['api_total_tokens']
    recomputed = aggregate(records)
    saved = json.loads((args.directory/'summary.json').read_text(encoding='utf-8'))
    assert len(saved) == len(recomputed)
    for a,b in zip(recomputed,saved):
        for k in a:
            if isinstance(a[k], (float,int)) and isinstance(b[k], (float,int)):
                assert math.isclose(a[k],b[k],rel_tol=1e-10,abs_tol=1e-10), k
            else:
                assert a[k] == b[k], k
    print(f'PASS: {len(records)} traces, scores, aggregate metrics, token accounting and archive checksum')


if __name__ == '__main__':
    main()
