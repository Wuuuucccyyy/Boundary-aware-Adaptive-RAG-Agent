"""Separate actual API billing tokens from local text processing proxies."""
import json
import time
from .text import token_proxy


def encoded(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'))


class BudgetExceeded(RuntimeError):
    pass


class Ledger:
    def __init__(self, config):
        self.config = config
        self.started = time.perf_counter()
        self.events = []

    def ensure(self, stage, input_value='', output_reserve=0):
        total = self.summary()
        if time.perf_counter() - self.started >= self.config.max_seconds:
            raise BudgetExceeded('time_budget')
        if len(self.events) >= self.config.max_module_calls:
            raise BudgetExceeded('module_call_budget')
        if stage == 'retrieval' and total['retrieval_calls'] >= self.config.max_retrieval_calls:
            raise BudgetExceeded('retrieval_call_budget')
        estimated = token_proxy(encoded(input_value)) + output_reserve
        if total['processed_token_proxy'] + estimated > self.config.max_work_tokens:
            raise BudgetExceeded('text_work_budget')

    def run(self, stage, input_value, fn, output_reserve=0):
        self.ensure(stage, input_value, output_reserve)
        start = time.perf_counter()
        value = fn()
        event = dict(stage=stage, elapsed_ms=(time.perf_counter()-start)*1000,
                     input_token_proxy=token_proxy(encoded(input_value)),
                     output_token_proxy=token_proxy(encoded(value)),
                     api_calls=0, api_prompt_tokens=0, api_completion_tokens=0)
        self.events.append(event)
        # Actual local work can exceed its reservation; record it, then stop before next operation.
        return value

    def summary(self):
        return dict(processed_token_proxy=sum(e['input_token_proxy']+e['output_token_proxy'] for e in self.events),
                    api_prompt_tokens=sum(e['api_prompt_tokens'] for e in self.events),
                    api_completion_tokens=sum(e['api_completion_tokens'] for e in self.events),
                    api_total_tokens=sum(e['api_prompt_tokens']+e['api_completion_tokens'] for e in self.events),
                    api_calls=sum(e['api_calls'] for e in self.events),
                    module_calls=len(self.events), retrieval_calls=sum(e['stage']=='retrieval' for e in self.events),
                    elapsed_ms=(time.perf_counter()-self.started)*1000,
                    by_stage={stage: dict(calls=sum(e['stage']==stage for e in self.events),
                                         elapsed_ms=sum(e['elapsed_ms'] for e in self.events if e['stage']==stage),
                                         token_proxy=sum(e['input_token_proxy']+e['output_token_proxy'] for e in self.events if e['stage']==stage))
                              for stage in sorted({e['stage'] for e in self.events})})
