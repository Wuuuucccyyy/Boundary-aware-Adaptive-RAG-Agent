import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from boundary_rag.accounting import BudgetExceeded, Ledger
from boundary_rag.agent import Agent
from boundary_rag.corpus import Corpus, DATA
from boundary_rag.evaluation import score
from boundary_rag.evidence import check
from boundary_rag.generation import DeepSeek, ModelError
from boundary_rag.query import decompose
from boundary_rag.routing import route
from boundary_rag.schema import Config


class PipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.corpus = Corpus()

    def test_cross_source_query_keeps_hr_despite_tax(self):
        r = Agent().answer('期权授予资格和期权税务怎么算？')
        self.assertTrue(r['sufficient'])
        self.assertEqual(set(r['selected_sources']), {'hr', 'finance'})
        self.assertIn('[hr-option_eligibility]', r['answer'])
        self.assertIn('[finance-option_tax]', r['answer'])

    def test_tax_only_avoids_hr(self):
        r = Agent().answer('员工期权税务怎么算？')
        self.assertEqual(r['selected_sources'], ['finance'])

    def test_three_sources(self):
        r = Agent().answer('电脑补贴资格、电脑资产入账和电脑加密配置分别怎么处理？')
        self.assertEqual(set(r['selected_sources']), {'hr', 'finance', 'it'})
        self.assertTrue(r['sufficient'])

    def test_evidence_state_changes_boundary(self):
        config = Config()
        first, _ = route('期权资格和税务', ['option_eligibility','option_tax'], self.corpus, 'dynamic', config, {})
        second, reasons = route('期权税务', ['option_tax'], self.corpus, 'dynamic', config, {'hr':1})
        self.assertEqual(set(first), {'hr','finance'})
        self.assertEqual(second, ['finance'])
        self.assertEqual(next(r for r in reasons if r['source']=='hr')['applicable'], [])

    def test_unknown_query_abstains_and_terminates(self):
        r = Agent().answer('明天上海天气如何？')
        self.assertFalse(r['sufficient'])
        self.assertIn('无法确定', r['answer'])
        self.assertLessEqual(len(r['rounds']), 3)
        self.assertLessEqual(r['metrics']['retrieval_calls'], 9)

    def test_partial_unknown_not_hidden(self):
        r = Agent().answer('期权税务怎么算，明天股价是多少？')
        self.assertFalse(r['sufficient'])
        self.assertIn('20%', r['answer'])
        self.assertIn('股价', r['answer'])
        self.assertTrue(any(t.startswith('unknown:') for t in r['tasks']))

    def test_retrieval_budget_is_hard(self):
        r = Agent(config=Config(max_retrieval_calls=1)).answer('年假有几天？', 'all')
        self.assertEqual(r['metrics']['retrieval_calls'], 1)
        self.assertEqual(r['stop_reason'], 'retrieval_call_budget')
        # Unchecked hits must not become verified evidence on budget exhaustion.
        self.assertFalse(r['sufficient'])

    def test_module_budget_is_hard(self):
        r = Agent(config=Config(max_module_calls=2)).answer('年假有几天？')
        self.assertLessEqual(r['metrics']['module_calls'], 2)
        self.assertEqual(r['backend'], 'unavailable')

    def test_text_budget_blocks_before_first_operation(self):
        r = Agent(config=Config(max_work_tokens=1)).answer('年假有几天？')
        self.assertEqual(r['metrics']['module_calls'], 0)
        self.assertEqual(r['stop_reason'], 'text_work_budget')

    def test_append_retrieval_in_same_source(self):
        r = Agent(config=Config(top_k=1)).answer('VPN连接失败，员工门户密码如何重置？')
        self.assertTrue(r['sufficient'])
        self.assertGreater(len(r['rounds']), 1)
        ids = [h['document']['id'] for step in r['rounds'] for entry in step['retrievals'] for h in entry['hits']]
        self.assertEqual(len(ids), len(set(ids)))

    def test_round_limit_stops_incomplete_answer(self):
        r = Agent(config=Config(top_k=1, max_rounds=1)).answer('VPN连接失败，员工门户密码如何重置？')
        self.assertFalse(r['sufficient'])
        self.assertEqual(r['stop_reason'], 'max_rounds')

    def test_similar_distractor_is_not_evidence(self):
        hit = {'document': self.corpus.by_id['hr-tax_notice'], 'score': 99}
        self.assertFalse(check(['option_tax'], [hit])['sufficient'])

    def test_forged_quote_rejected(self):
        doc = copy.deepcopy(self.corpus.by_id['hr-leave'])
        doc['claims'][0]['quote'] = '年假100天'
        self.assertFalse(check(['leave'], [{'document':doc}])['sufficient'])

    def test_stale_profile_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            for path in DATA.glob('*.json'):
                Path(tmp, path.name).write_bytes(path.read_bytes())
            path = Path(tmp, 'profiles.json')
            profiles = json.loads(path.read_text(encoding='utf-8'))
            profiles[0]['version'] = 'old'
            path.write_text(json.dumps(profiles), encoding='utf-8')
            with self.assertRaises(ValueError):
                Corpus(Path(tmp))

    def test_all_methods_share_index_and_answerer(self):
        agent = Agent()
        results = [agent.answer('年假有几天？', m) for m in ('all','positive','fixed','dynamic')]
        self.assertEqual(len({r['corpus_sha256'] for r in results}), 1)
        self.assertTrue(all(r['backend']=='extractive' for r in results))

    def test_no_profiles_mutated_after_failed_search(self):
        before = copy.deepcopy(self.corpus.profiles)
        Agent(corpus=self.corpus).answer('火星有哪些员工？')
        self.assertEqual(before, self.corpus.profiles)

    def test_empty_query_rejected(self):
        with self.assertRaises(ValueError):
            Agent().answer(' ')

    def test_invalid_budget_rejected(self):
        with self.assertRaises(ValueError):
            Config(max_rounds=0)


class ProviderTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {'DEEPSEEK_API_KEY':'test-only-not-a-real-key',
                                           'DEEPSEEK_MODEL':'fixture-model'}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)
        self.corpus = Corpus()
        self.state = check(['leave'], [{'document':self.corpus.by_id['hr-leave']}])

    def response(self, content, finish='stop'):
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self): return json.dumps({'choices':[{'message':{'content':content},'finish_reason':finish}],
                                               'usage':{'prompt_tokens':100,'completion_tokens':20},'model':'fixture-model'}).encode()
        return Response()

    def test_api_usage_accounted(self):
        ledger = Ledger(Config())
        with patch('urllib.request.urlopen', return_value=self.response('15天 [hr-leave]')):
            DeepSeek().generate('年假几天？', self.state, self.corpus, ledger)
        self.assertEqual(ledger.summary()['api_total_tokens'], 120)
        self.assertTrue(ledger.events[0]['usage_known'])

    def test_truncated_response_is_failure_and_tokens_retained(self):
        ledger = Ledger(Config())
        with patch('urllib.request.urlopen', return_value=self.response('15天', 'length')):
            with self.assertRaises(ModelError):
                DeepSeek().generate('年假几天？', self.state, self.corpus, ledger)
        self.assertEqual(ledger.summary()['api_total_tokens'], 120)

    def test_api_budget_blocks_request(self):
        with patch('urllib.request.urlopen') as network:
            with self.assertRaises(BudgetExceeded):
                DeepSeek().generate('年假几天？', self.state, self.corpus, Ledger(Config(max_llm_tokens=1)))
            network.assert_not_called()

    def test_invalid_citation_is_rejected(self):
        with patch('urllib.request.urlopen', return_value=self.response('答案 [fake-document]')):
            with self.assertRaises(ModelError):
                DeepSeek().generate('年假几天？', self.state, self.corpus, Ledger(Config()))

    def test_http_error_never_leaks_response_body(self):
        import urllib.error
        ledger = Ledger(Config())
        error = urllib.error.HTTPError('https://api.deepseek.com',401,'secret-body',{},None)
        with patch('urllib.request.urlopen', side_effect=error):
            with self.assertRaisesRegex(ModelError, '^http_401$'):
                DeepSeek().generate('年假几天？', self.state, self.corpus, ledger)
        self.assertEqual(ledger.summary()['api_calls'], 1)
        self.assertFalse(ledger.events[0]['usage_known'])
        self.assertNotIn('secret-body', json.dumps(ledger.events))


if __name__ == '__main__':
    unittest.main()
