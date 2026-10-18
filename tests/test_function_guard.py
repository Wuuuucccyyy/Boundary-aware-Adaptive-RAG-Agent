import copy
from importlib.resources import files
import json
import unittest
from function_guard import ProfileStore,evaluate
from function_guard.__main__ import run_cases
from function_guard.routing import route,METHODS
from function_guard.provider import payload_for,validate


class FunctionGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store=ProfileStore()
        cases=json.loads(files('function_guard').joinpath('data/condition_cases.json').read_text(encoding='utf-8'))
        cls.pca=cases[1]['request']
        cls.scale=cases[12]['request']

    def test_hand_specified_cases(self):
        result=run_cases(self.store)
        self.assertEqual(result['cases'],20)
        self.assertEqual(result['passed'],20)

    def test_budget_cannot_silently_certify_partially_checked_call(self):
        result=evaluate(self.pca,self.store,max_checks=1)
        self.assertEqual(result['state'],'unknown')
        self.assertEqual(result['action'],'budget_exhausted')
        self.assertEqual(result['budget']['checks_used'],1)

    def test_unrecognized_interface_is_not_inactive_everywhere(self):
        r=copy.deepcopy(self.pca);r['parameters']['method']='unsupported'
        result=evaluate(r,self.store)
        self.assertEqual(result['state'],'unknown')
        self.assertTrue(result['binding_issues'])

    def test_numeric_scalar_parameter_is_length_one_not_boolean(self):
        r=copy.deepcopy(self.scale);r['parameters']['center']=1
        before=copy.deepcopy(r)
        result=evaluate(r,self.store)
        self.assertEqual(result['state'],'conflict')
        self.assertEqual(result['parameters']['center'],[1])
        self.assertEqual(r,before)

    def test_unverified_vector_coercion_requires_review(self):
        r=copy.deepcopy(self.scale);r['parameters']['center']=['a','b','c']
        self.assertEqual(evaluate(r,self.store)['state'],'unknown')

    def test_union_type_has_negative_case(self):
        r=copy.deepcopy(self.pca);r['facts']['x_type']='categorical'
        result=evaluate(r,self.store)
        self.assertEqual(result['state'],'conflict')

    def test_evidence_and_fact_provenance_survive_adapter(self):
        r=copy.deepcopy(self.pca);r['fact_provenance']={'x_type':'schema.csv:column_types'}
        result=evaluate(r,self.store)
        row=next(c for c in result['checks'] if c['claim_id']=='feature_type.1')
        observed=next(o for o in row['observations'] if o['kind']=='fact' and o['key']=='x_type')
        self.assertEqual(observed['source'],'schema.csv:column_types')
        self.assertTrue(row['evidence'][0]['sha256'])
        self.assertTrue(row['evidence'][0]['url'].startswith('https://'))

    def test_documentation_unknown_is_not_global_rejection(self):
        result=evaluate(self.pca,self.store)
        self.assertEqual(result['state'],'applicable')
        row=next(c for c in result['checks'] if c['claim_id']=='distribution_assumption.1')
        self.assertEqual(row['status'],'unknown')
        self.assertFalse(row['critical'])

    def test_unknown_focus_cannot_be_silently_ignored(self):
        r=copy.deepcopy(self.pca);r['focus_claim_ids']=['invented']
        with self.assertRaises(ValueError):evaluate(r,self.store)

    def test_profile_annotations_are_not_mutated(self):
        before=copy.deepcopy(self.store.records)
        evaluate(self.pca,self.store)
        self.assertEqual(self.store.records,before)

    def test_configuration_cases_and_information_budgets(self):
        cases=json.loads(files('function_guard').joinpath('data/routing_cases.json').read_text(encoding='utf-8'))
        for case in cases:
            a,b=[route(case['request'],m,self.store) for m in METHODS]
            for r in (a,b):
                self.assertEqual({k:r[k] for k in ('state','selected')},case['expected'],case['id'])
                self.assertLessEqual(r['budget']['checks_used'],80)
            self.assertEqual(a['budget'],b['budget'])
            self.assertEqual(payload_for(case['request'],a),payload_for(case['request'],b))

    def test_routing_budget_records_actual_checks_and_defers(self):
        case=json.loads(files('function_guard').joinpath('data/routing_cases.json').read_text(encoding='utf-8'))[0]
        r=route(case['request'],'dynamic',self.store,max_checks=1)
        self.assertEqual(r['state'],'unknown')
        self.assertEqual(r['budget']['checks_used'],0)
        self.assertTrue(r['budget']['exhausted'])

    def test_renderer_cannot_change_verified_configuration(self):
        case=json.loads(files('function_guard').joinpath('data/routing_cases.json').read_text(encoding='utf-8'))[0]
        d=route(case['request'],'dynamic',self.store);p=payload_for(case['request'],d)
        output=dict(selected='pooled',state=d['state'],action=d['action'],explanation='x',evidence=[])
        with self.assertRaisesRegex(ValueError,'decision_changed'):validate(output,p)

    def test_renderer_rejects_fabricated_claim_reference(self):
        case=json.loads(files('function_guard').joinpath('data/routing_cases.json').read_text(encoding='utf-8'))[0]
        d=route(case['request'],'dynamic',self.store);p=payload_for(case['request'],d)
        output=dict(selected=d['selected'],state=d['state'],action=d['action'],explanation='x',
                    evidence=[dict(candidate_id='welch',claim_id='invented')])
        with self.assertRaisesRegex(ValueError,'unknown_evidence_reference'):validate(output,p)
