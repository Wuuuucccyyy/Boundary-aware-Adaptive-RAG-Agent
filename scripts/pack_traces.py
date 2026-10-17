"""Archive raw runs deterministically; one JSON object per line, gzip mtime=0."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    paths = sorted((args.directory/'traces').glob('*.json'))
    if not paths:
        parser.error('No traces found')
    output = args.directory/'traces.jsonl.gz'
    with output.open('wb') as raw:
        with gzip.GzipFile(filename='', fileobj=raw, mode='wb', mtime=0) as stream:
            for path in paths:
                obj = json.loads(path.read_text(encoding='utf-8'))
                stream.write((json.dumps(obj, ensure_ascii=False, separators=(',', ':'))+'\n').encode('utf-8'))
    metadata = dict(records=len(paths), sha256=hashlib.sha256(output.read_bytes()).hexdigest(),
                    format='gzip compressed UTF-8 JSON Lines', filename=output.name)
    (args.directory/'archive.json').write_text(json.dumps(metadata, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(metadata))


if __name__ == '__main__':
    main()
