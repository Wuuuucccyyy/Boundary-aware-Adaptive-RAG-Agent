"""Check pilot annotation invariants; this does not judge statistical correctness."""
import argparse
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
FIELDS={'data_modality','feature_type','distribution_assumption','dimensionality','missing_data_handling','specific_constraints'}

class Plain(HTMLParser):
    def __init__(self):super().__init__();self.parts=[]
    def handle_data(self,data):self.parts.append(data)

def verify(directory, sources_dir=None):
    records=json.loads((directory/'profiles.json').read_text(encoding='utf-8'))
    lines=[json.loads(s) for s in (directory/'profiles.jsonl').read_text(encoding='utf-8').splitlines()]
    assert records==lines,'JSON/JSONL differ'
    assert len(records)==5 and len({r['record_id'] for r in records})==5,'Expected five distinct pilot records'
    assert sum(r['selection']['keep'] for r in records)==4,'Expected four retained and one excluded'
    manifest={s['id']:s for s in json.loads((directory/'source_manifest.json').read_text(encoding='utf-8'))}
    quote_words={};claim_count=0
    for r in records:
        assert r['profile_target']=='function_input_requirements' and r['review_status']=='pending_user_review'
        assert set(r['data_profile'])==FIELDS
        assert set(r['documentation_review'].values())=={'read'}
        src={s['id']:s for s in r['document_sources']}
        for sid,s in src.items():
            assert {k:v for k,v in s.items() if k!='role'}==manifest[sid]
            if sources_dir:
                raw=(sources_dir/(sid+'.html')).read_bytes()
                assert hashlib.sha256(raw).hexdigest()==s['sha256'],f'Source changed: {sid}'
        evidence={e['id']:e for e in r['evidence']}
        assert len(evidence)==len(r['evidence'])
        for e in evidence.values():
            assert e['source_id'] in src and e['section'] and e['quote']
            quote_words.setdefault(e['source_id'],set()).add(e['quote'])
            if sources_dir:
                parser=Plain();parser.feed((sources_dir/(e['source_id']+'.html')).read_text(encoding='utf-8'))
                plain=' '.join(' '.join(parser.parts).split())
                assert e['quote'] in plain,f'Quote not found: {r["record_id"]}/{e["id"]}'
        assert set(r['selection']['evidence_ids'])<=set(evidence)
        claims=[c for field in r['data_profile'].values() for c in field]+r['task_type']
        assert all(r['data_profile'].values()) and r['task_type']
        ids={c['id'] for c in claims};assert len(ids)==len(claims)
        conflict_ids={cid for x in r['conflicts'] for cid in x['affected_claim_ids']}
        for c in claims:
            assert set(c['evidence_ids'])<=set(evidence)
            if c['basis'] in ('documented','inferred','conflict'):assert c['evidence_ids']
            if c['basis'] in ('unknown','not_assessed','conflict'):assert c['value']=='unknown' and c['reason']
            if c['basis']=='inferred':assert c['reason']
            if c['basis']=='conflict':assert c['id'] in conflict_ids
            if c['value']=='any':assert c['basis']=='documented' and c['reason'] and c['evidence_ids']
        assert r['inferences']==[dict(claim_id=c['id'],reason=c['reason']) for c in claims if c['basis']=='inferred']
        assert r['unknown_items']==[dict(claim_id=c['id'],reason=c['reason']) for c in claims if c['basis']=='unknown']
        for conflict in r['conflicts']:
            assert conflict['resolution']=='unresolved' and len(conflict['alternatives'])>=2
            assert set(conflict['evidence_ids'])<=set(evidence) and set(conflict['affected_claim_ids'])<=ids
        if not r['selection']['keep']:
            assert all(c['basis']=='not_assessed' for v in r['data_profile'].values() for c in v)
        for o in r['output_summary']:assert set(o['evidence_ids'])<=set(evidence)
        claim_count+=len(claims)
    for sid,quotes in quote_words.items():assert sum(len(q.split()) for q in quotes)<=25,f'Quote budget: {sid}'
    result=dict(records=len(records),retained=4,excluded=1,claims=claim_count,
        inference_count=sum(len(r['inferences']) for r in records),unknown_count=sum(len(r['unknown_items']) for r in records),
        conflict_count=sum(len(r['conflicts']) for r in records),checks='passed',
        original_source_hashes_and_quote_presence_checked=bool(sources_dir),
        semantic_accuracy='requires_human_review',bulk_processing='not_started')
    return result

def main():
    p=argparse.ArgumentParser();p.add_argument('directory',type=Path,nargs='?',default=ROOT/'function_profiles/pilot_v1')
    p.add_argument('--sources-dir',type=Path);p.add_argument('--write-report',action='store_true')
    args=p.parse_args();result=verify(args.directory,args.sources_dir)
    if args.write_report:(args.directory/'validation.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':main()
