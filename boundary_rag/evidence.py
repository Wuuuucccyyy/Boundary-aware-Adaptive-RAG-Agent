"""Synthetic claim support check, NOT a general-purpose entailment model."""


def check(tasks: list[str], hits: list[dict]) -> dict:
    supports = {}
    for task in tasks:
        for hit in hits:
            doc = hit['document']
            for claim in doc['claims']:
                if claim['task'] == task and claim['quote'] in doc['text']:
                    supports.setdefault(task, []).append({'doc_id': doc['id'], 'source': doc['source'],
                                                          'quote': claim['quote'], 'version': doc['version']})
    return {'supports': supports, 'missing': [t for t in tasks if t not in supports],
            'sufficient': all(t in supports for t in tasks)}
