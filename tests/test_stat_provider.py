import json
import os
import time
import unittest
from unittest.mock import patch
from stat_rag.core import Settings
from stat_rag.provider import generate


class StatisticalProviderTests(unittest.TestCase):
    def setUp(self):
        self.env=patch.dict(os.environ,{'DEEPSEEK_API_KEY':'not-a-real-key','DEEPSEEK_MODEL':'fixture-model'},clear=True)
        self.env.start();self.addCleanup(self.env.stop)
        self.requirements=[dict(id='effect',topic='effect',conditions={})]
        self.state=dict(supports={'effect':[dict(document_id='s1',quote='结果为2.459')]},missing=[])

    def response(self,finish='stop',content=None):
        value=content or {'claims':[dict(requirement_id='effect',document_id='s1',quote='结果为2.459')],'unknown':[],'answer':'已给出合成结果。'}
        class Response:
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self):return json.dumps(dict(usage=dict(prompt_tokens=100,completion_tokens=50,total_tokens=150),model='fixture-model',choices=[dict(finish_reason=finish,message=dict(content=json.dumps(value)))] )).encode()
        return Response()

    def test_real_usage_retained(self):
        with patch('urllib.request.urlopen',return_value=self.response()):
            _,api,error,_=generate('q',self.requirements,self.state,Settings(),time.perf_counter())
        self.assertIsNone(error);self.assertEqual(api['total_tokens'],150)

    def test_truncation_preserves_usage_and_fails(self):
        with patch('urllib.request.urlopen',return_value=self.response('length')):
            _,api,error,_=generate('q',self.requirements,self.state,Settings(),time.perf_counter())
        self.assertEqual(error,'incomplete_generation');self.assertEqual(api['total_tokens'],150)

    def test_token_budget_prevents_network(self):
        with patch('urllib.request.urlopen') as network:
            _,api,error,_=generate('q',self.requirements,self.state,Settings(max_api_tokens=1),time.perf_counter())
        network.assert_not_called();self.assertEqual(api['calls'],0);self.assertEqual(error,'api_token_budget')

    def test_http_error_has_unknown_usage_and_no_secret(self):
        import urllib.error
        failure=urllib.error.HTTPError('https://api.deepseek.com',401,'private body',{},None)
        with patch('urllib.request.urlopen',side_effect=failure):
            result=generate('q',self.requirements,self.state,Settings(),time.perf_counter())
        self.assertEqual(result[2],'http_401');self.assertFalse(result[1]['usage_known'])
        self.assertNotIn('private body',json.dumps(result));self.assertNotIn('not-a-real-key',json.dumps(result))


if __name__=='__main__':unittest.main()
