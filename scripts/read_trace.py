"""Inspect a published raw trace without external dependencies."""
import argparse
import gzip
import json
from pathlib import Path
import sys


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser()
    parser.add_argument('--archive', type=Path, default=Path('results/online/traces.jsonl.gz'))
    parser.add_argument('--id', required=True)
    parser.add_argument('--method', default='dynamic')
    parser.add_argument('--repetition', type=int, default=0)
    args = parser.parse_args()
    with gzip.open(args.archive, 'rt', encoding='utf-8') as stream:
        for line in stream:
            record = json.loads(line)
            if (record['sample_id'], record['run']['method'], record['repetition']) == (args.id, args.method, args.repetition):
                print(json.dumps(record, ensure_ascii=False, indent=2))
                return
    parser.exit(1, 'Trace not found\n')


if __name__ == '__main__':
    main()
