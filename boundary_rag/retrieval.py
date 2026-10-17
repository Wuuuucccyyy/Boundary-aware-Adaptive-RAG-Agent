"""BM25 over title + text; annotations are never included in retrieval scores."""
import math
from collections import Counter
from .text import terms


class Retriever:
    def __init__(self, corpus):
        self.documents = corpus.documents
        self.tf = {d['id']: Counter(terms(d['title'] + ' ' + d['text'])) for d in self.documents}
        self.df = Counter(term for tf in self.tf.values() for term in tf)
        self.average = sum(sum(tf.values()) for tf in self.tf.values()) / len(self.tf)

    def search(self, source: str, query: str, k: int, seen: set[str]) -> list[dict]:
        candidates = []
        for doc in self.documents:
            if doc['source'] != source or doc['id'] in seen:
                continue
            tf = self.tf[doc['id']]
            score = 0.0
            for token in set(terms(query)):
                n = tf[token]
                if n:
                    idf = math.log(1 + (len(self.documents) - self.df[token] + 0.5) / (self.df[token] + 0.5))
                    score += idf * n * 2.5 / (n + 1.5 * (0.25 + 0.75 * sum(tf.values()) / self.average))
            if score > 0:
                candidates.append({'document': doc, 'score': round(score, 6)})
        return sorted(candidates, key=lambda h: (-h['score'], h['document']['id']))[:k]
