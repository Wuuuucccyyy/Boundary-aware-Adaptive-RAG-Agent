import copy
from dataclasses import replace
import json
import unittest
from stat_rag.core import Agent,Corpus,Settings,compare,parse,select,verify
from stat_rag.provider import validate,citations


class StatisticalRoutingTests(unittest.TestCase):
    def test_applicable_conflict_unknown_distinct(self):
        self.assertEqual(compare({'year':'2026'},{'year':'2026'})['state'],'applicable')
        self.assertEqual(compare({'year':'2022'},{'year':'2026'})['state'],'conflict')
        self.assertEqual(compare({'year':None},{'year':'2026'})['state'],'unknown')

    def test_same_source_changes_with_context(self):
        c=Corpus(10);s=next(s for s in c.sources if s['kind']=='observational')
        a=parse('中国2026年成年人观察研究的关联估计是多少？')[0]
        b=parse('中国2026年成年人观察研究的因果效应是多少？')[0]
        self.assertEqual(compare(s['profile']['conditions'],a['conditions'])['state'],'applicable')
        self.assertEqual(compare(s['profile']['conditions'],b['conditions'])['state'],'conflict')

    def test_dynamic_cross_domain_preserves_both(self):
        r=Agent(30).run('中国2026年成年人随机试验因果效应估计，以及独立同分布验证方案？','dynamic')
        self.assertEqual(set(r['state']['supports']),{'effect','validation'})
        self.assertEqual(r['metrics']['retrieval_calls'],2)

    def test_unknown_profile_resolved_by_document(self):
        r=Agent(30).run('中国2026年成年人研究的预测结果？','dynamic')
        self.assertIn('prediction',r['state']['supports'])
        self.assertTrue(any(d['boundaries']['prediction']['state']=='unknown' and d['selected'] for d in r['rounds'][0]['decisions']))

    def test_observational_data_does_not_supply_causal_evidence(self):
        r=Agent(30).run('中国2026年成年人观察研究的因果效应是多少？','all')
        self.assertEqual(r['state']['missing'],['effect'])
        self.assertFalse(r['state']['supports'])

    def test_negative_term_can_change_decision(self):
        c=Corpus(30)
        queries=['中国2026年成年人时间序列验证方案？','中国2026年成年人随机试验因果效应估计？','中国2026年成年人MAR缺失处理？']
        changes=0
        for q in queries:
            req=parse(q)
            a,_=select(q,req,c,'dynamic',set(),Settings())
            b,_=select(q,req,c,'no_negative',set(),Settings())
            changes+=a!=b
        self.assertGreater(changes,0)

    def test_full_profile_receives_same_conditions(self):
        c=Corpus(10);q='中国2026年成年人随机试验因果效应估计？'
        _,a=select(q,parse(q),c,'dynamic',set(),Settings())
        _,b=select(q,parse(q),c,'full_profile',set(),Settings())
        self.assertEqual([r['boundaries'] for r in a],[r['boundaries'] for r in b])

    def test_no_negative_is_dynamic_with_zero_penalty(self):
        c=Corpus(30);q='中国2026年成年人时间序列验证方案？';req=parse(q)
        a,_=select(q,req,c,'no_negative',set(),Settings())
        b,_=select(q,req,c,'dynamic',set(),Settings(risk_weight=0,unknown_weight=0))
        self.assertEqual(a,b)

    def test_source_budget(self):
        r=Agent(30,Settings(max_retrieval_calls=2)).run('中国2026年成年人时间序列验证方案？','all')
        self.assertEqual(r['metrics']['retrieval_calls'],2)
        self.assertEqual(r['stop'],'retrieval_budget')

    def test_no_repeated_source_calls(self):
        r=Agent(30).run('中国2026年老年人预测结果？','positive')
        seen=[x['source'] for step in r['rounds'] for x in step['retrievals']]
        self.assertEqual(len(seen),len(set(seen)))

    def test_citation_variants(self):
        self.assertEqual(citations('[doc_id: s1-report] [s2-report]'),['s1-report','s2-report'])

    def test_fabricated_number_fails_quote_validation(self):
        req=[dict(id='effect')];state={'supports':{'effect':[dict(document_id='s1',quote='结果为2.459')]}}
        output={'claims':[dict(requirement_id='effect',document_id='s1',quote='结果为99')],'unknown':[],'answer':''}
        with self.assertRaises(ValueError):validate(output,req,state)

    def test_hidden_unknown_citation_rejected(self):
        with self.assertRaises(ValueError):validate({'claims':[],'unknown':[],'answer':'[doc_id: fake]'},[],{'supports':{}})

    def test_four_source_demo(self):
        r=Agent(30).run('中国2026年成年人研究：预测结果、残差诊断、时间序列验证方案和MAR缺失处理？','dynamic')
        self.assertFalse(r['state']['missing'])
        self.assertEqual(len(r['state']['supports']),4)

    def test_no_profile_mutation_on_failure(self):
        a=Agent(30);before=copy.deepcopy(a.corpus.sources)
        a.run('中国2026年老年人预测结果？','dynamic')
        self.assertEqual(before,a.corpus.sources)


if __name__=='__main__':unittest.main()
