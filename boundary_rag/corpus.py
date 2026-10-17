import hashlib
import json
from pathlib import Path

DATA = Path(__file__).parent / 'data'


def read_json(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))


class Corpus:
    def __init__(self, directory: Path = DATA):
        self.directory = Path(directory)
        self.documents = read_json(self.directory / 'documents.json')
        self.profiles = read_json(self.directory / 'profiles.json')
        self.tasks = read_json(self.directory / 'tasks.json')
        self.by_id = {d['id']: d for d in self.documents}
        if len(self.by_id) != len(self.documents):
            raise ValueError('Duplicate document id')
        self.task_by_id = {t['id']: t for t in self.tasks}
        self.profile_by_id = {p['id']: p for p in self.profiles}
        for d in self.documents:
            if d['source'] not in self.profile_by_id:
                raise ValueError('Unknown source')
            for claim in d['claims']:
                if claim['task'] not in self.task_by_id or claim['quote'] not in d['text']:
                    raise ValueError(f'Unverifiable claim: {d["id"]}')
        for p in self.profiles:
            for task, ids in p['supports'].items():
                if task not in self.task_by_id or not ids:
                    raise ValueError('Invalid capability')
                for doc_id in ids:
                    d = self.by_id.get(doc_id)
                    if (not d or d['source'] != p['id'] or d['version'] != p['version']
                            or task not in [c['task'] for c in d['claims']]):
                        raise ValueError(f'Stale or unsupported profile: {p["id"]}/{task}')
            if set(p['supports']) & set(p['unsupported']):
                raise ValueError('Conflicting profile boundary')
        digest = hashlib.sha256()
        for name in ('documents.json', 'profiles.json', 'tasks.json'):
            digest.update((self.directory / name).read_bytes())
        self.snapshot = digest.hexdigest()

    def label(self, task: str) -> str:
        return self.task_by_id.get(task, {}).get('label', task.removeprefix('unknown:'))
