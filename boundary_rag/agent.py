from collections import Counter
from .accounting import BudgetExceeded, Ledger
from .corpus import Corpus
from .evidence import check
from .generation import DeepSeek, ModelError, extractive
from .query import decompose
from .retrieval import Retriever
from .routing import route
from .schema import Config


class Agent:
    def __init__(self, corpus=None, config=None, backend='extractive'):
        self.corpus = corpus or Corpus()
        self.config = config or Config()
        self.retriever = Retriever(self.corpus)
        if backend not in ('extractive', 'deepseek'):
            raise ValueError('Unknown backend')
        self.backend = backend
        self.generator = DeepSeek() if backend == 'deepseek' else None

    def answer(self, query, method='dynamic'):
        ledger = Ledger(self.config)
        tasks, hits, rounds, seen, visits = [], [], [], set(), Counter()
        state = {'supports': {}, 'missing': [], 'sufficient': False}
        stop, generation_error = 'max_rounds', None
        try:
            tasks = ledger.run('decomposition', {'query': query, 'task_definitions': self.corpus.tasks},
                               lambda: decompose(query, self.corpus.tasks))
            state['missing'] = tasks[:]
            for number in range(1, self.config.max_rounds+1):
                missing = state['missing']
                search_query = query if number == 1 else '；'.join(self.corpus.label(t) for t in missing)
                # Pass exactly what each router reads; P/Q-only does not pay for N serialization.
                profiles = self.corpus.profiles if method == 'dynamic' else [
                    {k: p[k] for k in ('id', 'positive', 'examples', 'fixed_negative_patterns')
                     if k != 'fixed_negative_patterns' or method == 'fixed'} for p in self.corpus.profiles]
                route_input = {'query': search_query, 'missing': missing, 'profiles': profiles, 'visits': dict(visits)}
                if method == 'all':
                    route_input = {'sources': list(self.corpus.profile_by_id)}
                selected, decisions = ledger.run('routing', route_input,
                    lambda: route(search_query, missing, self.corpus, method, self.config, visits))
                trace = dict(round=number, missing_before=missing[:], search_query=search_query,
                             selected=selected, decisions=decisions, retrievals=[])
                rounds.append(trace)
                for source in selected:
                    found = ledger.run('retrieval', {'source': source, 'query': search_query, 'top_k': self.config.top_k},
                        lambda: self.retriever.search(source, search_query, self.config.top_k, seen))
                    visits[source] += 1
                    seen.update(h['document']['id'] for h in found)
                    hits.extend(found)
                    trace['retrievals'].append({'source': source, 'hits': found})
                state = ledger.run('evidence_check', {'tasks': tasks, 'hits': hits}, lambda: check(tasks, hits))
                trace['evidence_check'] = state
                if state['sufficient']:
                    stop = 'sufficient_evidence'
                    break
                if all(visits.get(p['id'], 0) for p in self.corpus.profiles) and not any(
                        r['hits'] for r in trace['retrievals']):
                    stop = 'no_new_evidence'
                    break
        except BudgetExceeded as exc:
            stop = str(exc)
        if not tasks:
            tasks = ['unknown:' + query]
            state = {'supports': {}, 'missing': tasks, 'sufficient': False}
        answer = ''
        answer_backend = self.backend
        try:
            if self.generator:
                answer = self.generator.generate(query, state, self.corpus, ledger)
            else:
                answer = ledger.run('generation', state, lambda: extractive(state, self.corpus))
        except (BudgetExceeded, ModelError) as exc:
            generation_error = str(exc)
            # Explicit degraded response; never count as a successful model call.
            answer = '本次未完成回答生成。停止原因：' + generation_error + '。'
            answer_backend = 'unavailable'
        metrics = ledger.summary()
        metrics['api_usage_complete'] = all(e.get('usage_known', True) for e in ledger.events)
        metrics['api_total_tokens_known'] = metrics['api_total_tokens'] if metrics['api_usage_complete'] else None
        return dict(query=query, method=method, backend=answer_backend, requested_backend=self.backend,
                    corpus_sha256=self.corpus.snapshot, config=self.config.to_dict(), tasks=tasks,
                    answer=answer, sufficient=state['sufficient'], evidence=state,
                    selected_sources=list(visits), rounds=rounds, stop_reason=stop,
                    generation_error=generation_error, metrics=metrics, events=ledger.events)
