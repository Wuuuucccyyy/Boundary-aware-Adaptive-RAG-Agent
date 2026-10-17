import unittest
from boundary_rag.agent import Agent
from boundary_rag.evaluation import score


class EvaluationTests(unittest.TestCase):
    def test_valid_alternative_source_not_penalized(self):
        sample = dict(acceptable_documents={'support_contact':['it-support_contact','hr-support_contact']},
                      acceptable_sources={'support_contact':['it','hr']}, fully_answerable=True)
        result = Agent().answer('服务台联系邮箱是什么？')
        metric = score(sample,result)
        self.assertEqual(metric['necessary_source_recall'],1)

    def test_no_answer_has_no_source_recall_denominator(self):
        sample = dict(acceptable_documents={},acceptable_sources={},fully_answerable=False)
        metric = score(sample,Agent().answer('火星人口是多少？'))
        self.assertIsNone(metric['necessary_source_recall'])
        self.assertEqual(metric['quality_proxy'],1)

    def test_failed_generation_never_counts_as_correct(self):
        sample = dict(acceptable_documents={},acceptable_sources={},fully_answerable=False)
        result = Agent().answer('火星人口是多少？')
        result['generation_error']='timeout'
        metric = score(sample,result)
        self.assertEqual(metric['quality_proxy'],0)
        self.assertFalse(metric['answerability_correct'])


if __name__ == '__main__':
    unittest.main()
