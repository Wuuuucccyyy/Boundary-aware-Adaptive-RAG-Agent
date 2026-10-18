"""Shared parser, selector, retriever and verifier. No benchmark labels imported."""
from dataclasses import asdict, dataclass
import hashlib
import json
import re
import time
from .fixtures import DATA,LABELS
from boundary_rag.text import similarity,token_proxy
from boundary_rag.retrieval import Retriever

METHODS=('all','positive','fixed','full_profile','dynamic','no_negative')


def canonical(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'))


@dataclass(frozen=True)
class Settings:
    max_rounds:int=3
    max_retrieval_calls:int=30
    top_k:int=1
    max_output_tokens:int=700
    max_api_tokens:int=12000
    max_seconds:float=60
    max_processing_proxy:int=150000
    risk_weight:float=0.85
    unknown_weight:float=0.2
    def __post_init__(self):
        if min(self.max_rounds,self.max_retrieval_calls,self.top_k,self.max_output_tokens,self.max_api_tokens,self.max_seconds,self.max_processing_proxy)<=0:
            raise ValueError('Budgets must be positive')
        if not 0<=self.risk_weight<=1 or not 0<=self.unknown_weight<=1:raise ValueError('Invalid risk weights')


class Corpus:
    def __init__(self,size=10):
        if size not in (10,20,30):raise ValueError('Source count must be 10, 20 or 30')
        self.sources=json.loads((DATA/'studies.json').read_text(encoding='utf-8'))[:size]
        self.documents=[s['document'] for s in self.sources]
        self.by_id={s['id']:s for s in self.sources}
        self.docs={d['id']:d for d in self.documents}
        self.snapshot=hashlib.sha256(canonical(self.sources).encode()).hexdigest()
        for s in self.sources:
            if s['document']['version']!=s['version']:raise ValueError('Stale source profile')
            if s['document']['quote'] not in s['document']['text']:raise ValueError('Unsupported quotation')
            if s['profile']['conditions_reference']!=s['document']['id']:raise ValueError('Invalid boundary reference')


def parse(query):
    if not query.strip():raise ValueError('Empty question')
    common={'region':'CN' if '中国' in query else 'US' if '美国' in query else None,
            'year':(re.search(r'20\d\d',query).group() if re.search(r'20\d\d',query) else None),
            'population':'senior' if '老年人' in query else 'adult' if '成年人' in query else None}
    patterns={'effect':'效应估计|关联估计|因果效应', 'validation':'验证方案|验证设计',
              'summary':'总体均值|样本均值', 'missing':'缺失处理|插补方案',
              'prediction':'预测结果|预测值', 'diagnostics':'残差诊断|残差情况'}
    requirements=[]
    for topic,pattern in patterns.items():
        if not re.search(pattern,query):continue
        scope=dict(common)
        if topic=='effect':scope.update(design='observational' if '观察研究' in query else 'randomized' if '随机试验' in query else None,
                                        goal='association' if '关联估计' in query else 'causal')
        if topic=='validation':scope['dependence']='temporal' if '时间序列' in query else 'iid' if '独立同分布' in query else None
        if topic=='summary':scope['target']='population' if '总体均值' in query else 'sample'
        if topic=='missing':scope['mechanism']='mcar' if 'MCAR' in query else 'mar' if re.search(r'(?<![A-Z])MAR(?![A-Z])',query) else 'mnar' if 'MNAR' in query else None
        requirements.append(dict(id=topic,topic=topic,conditions=scope))
    if '实际营业收入' in query or not requirements:
        requirements.append(dict(id='unknown',topic='unknown',conditions=common))
    return requirements


def compare(scope,requested):
    matches=[];conflicts=[];unknown=[]
    for field,value in requested.items():
        if value is None or scope.get(field) is None:unknown.append(field)
        elif scope[field]==value:matches.append(field)
        else:conflicts.append(dict(field=field,requested=value,available=scope[field]))
    return dict(state='conflict' if conflicts else 'unknown' if unknown else 'applicable',
                matches=matches,conflicts=conflicts,unknown=unknown)


def select(query,missing,corpus,method,seen,settings):
    if method not in METHODS:raise ValueError('Unknown router')
    candidates=[s for s in corpus.sources if s['id'] not in seen]
    if method=='all':return [s['id'] for s in candidates],[]
    rows=[]
    for source in candidates:
        lexical=similarity(query,source['profile']['positive'])
        tasks={};details={}
        for req in missing:
            base=(0.8+0.15*lexical) if source['topic']==req['topic'] else 0
            probability=base
            if method in ('dynamic','no_negative','full_profile'):
                relation=compare(source['profile']['conditions'],req['conditions'])
                details[req['id']]=relation
                if method=='full_profile':
                    # Ordinary all-information compatibility, shared fields; no hidden metadata advantage.
                    denominator=max(1,len(req['conditions']))
                    probability=base*(len(relation['matches'])+0.5*len(relation['unknown']))/denominator
                elif method=='dynamic':
                    probability=max(0,base-settings.risk_weight*bool(relation['conflicts'])-settings.unknown_weight*bool(relation['unknown']))
                # no_negative keeps the same code path and candidate metadata, but both penalties are zero.
            elif method=='fixed':
                hits=[p for p in source['profile']['fixed_negative'] if re.search(p,query)]
                probability=max(0,base-0.55*bool(hits))
                details[req['id']]={'static_conflicts':hits}
            tasks[req['id']]=probability
        rows.append(dict(source=source['id'],expected_support=tasks,boundaries=details,
                         boundary_reference=source['profile']['conditions_reference'] if method in ('dynamic','no_negative','full_profile') else None))
    # SAME greedy expected union-coverage selector for every non-all method.
    uncovered={r['id']:1.0 for r in missing}; selected=[];pool=rows[:]
    for _ in range(max(1,len(missing))):
        if not pool:break
        def utility(row):return sum(uncovered[t]*p for t,p in row['expected_support'].items())-0.08
        best=max(pool,key=lambda row:(utility(row),hashlib.sha256((query+row['source']).encode()).hexdigest()))
        gain=utility(best)
        if gain<=0:break
        selected.append(best['source']);pool.remove(best)
        for task,p in best['expected_support'].items():uncovered[task]*=1-p
        if all(v<=0.2 for v in uncovered.values()):break
    if not selected and candidates:
        # Unknown is explored rather than asserted to be permanently unsupported.
        exploratory=max(rows,key=lambda row:(sum(row['expected_support'].values()),hashlib.sha256((query+row['source']).encode()).hexdigest()))
        selected=[exploratory['source']]
    for row in rows:row['selected']=row['source'] in selected
    return selected,rows


def verify(requirements,hits):
    supports={};rejections=[]
    for req in requirements:
        for hit in hits:
            d=hit['document']
            if d['topic']!=req['topic']:continue
            state=compare(d['conditions'],req['conditions'])
            if state['state']=='applicable' and d['quote'] in d['text']:
                supports.setdefault(req['id'],[]).append(dict(document_id=d['id'],quote=d['quote'],source=d['source']))
            else:rejections.append(dict(requirement=req['id'],document_id=d['id'],**state))
    return dict(supports=supports,missing=[r['id'] for r in requirements if r['id'] not in supports],rejections=rejections)


class Agent:
    def __init__(self,size=10,settings=None,backend='offline'):
        self.corpus=Corpus(size);self.settings=settings or Settings();self.retriever=Retriever(self.corpus)
        if backend not in ('offline','deepseek'):raise ValueError('Unknown backend')
        self.backend=backend

    def run(self,query,method):
        start=time.perf_counter();events=[];trace=[];seen=set();hits=[];calls=0;stop='max_rounds'
        def timed(stage,inp,fn):
            if time.perf_counter()-start>self.settings.max_seconds:raise TimeoutError('time_budget')
            if sum(e['processing_proxy'] for e in events)+token_proxy(canonical(inp))>self.settings.max_processing_proxy:raise TimeoutError('processing_budget')
            at=time.perf_counter();out=fn();events.append(dict(stage=stage,ms=(time.perf_counter()-at)*1000,
                processing_proxy=token_proxy(canonical(inp))+token_proxy(canonical(out))))
            return out
        requirements=timed('analysis',query,lambda:parse(query))
        state={'supports':{},'missing':[r['id'] for r in requirements],'rejections':[]}
        try:
            for round_id in range(self.settings.max_rounds):
                missing=[r for r in requirements if r['id'] in state['missing']]
                profiles=[dict(id=s['id'],topic=s['topic'],positive=s['profile']['positive'],
                               **({'conditions':s['profile']['conditions']} if method in ('dynamic','no_negative','full_profile') else {}),
                               **({'fixed_negative':s['profile']['fixed_negative']} if method=='fixed' else {})) for s in self.corpus.sources]
                selected,decisions=timed('routing',dict(query=query,missing=missing,profiles=profiles if method!='all' else list(self.corpus.by_id)),
                                         lambda:select(query,missing,self.corpus,method,seen,self.settings))
                step=dict(round=round_id+1,missing_before=state['missing'][:],selected=selected,decisions=decisions,retrievals=[])
                trace.append(step)
                if not selected:stop='sources_exhausted';break
                for source in selected:
                    if calls>=self.settings.max_retrieval_calls:stop='retrieval_budget';break
                    found=timed('retrieval',dict(source=source,query=query),lambda:self.retriever.search(source,query,self.settings.top_k,set()))
                    calls+=1;seen.add(source);hits.extend(found);step['retrievals'].append(dict(source=source,hits=found))
                state=timed('verification',dict(requirements=requirements,hits=hits),lambda:verify(requirements,hits))
                step['verification']=state
                if not state['missing']:stop='sufficient';break
                if calls>=self.settings.max_retrieval_calls:stop='retrieval_budget';break
        except TimeoutError as exc:stop=str(exc)
        if self.backend=='offline':
            output=timed('generation',state,lambda:dict(claims=[dict(requirement_id=t,**entries[0]) for t,entries in state['supports'].items()],
                           unknown=state['missing'],answer='开发验证：从已验证原文摘录。'))
            api=dict(calls=0,prompt_tokens=0,completion_tokens=0,total_tokens=0,usage_known=True)
            error=None
        else:
            from .provider import generate
            output,api,error,event=generate(query,requirements,state,self.settings,start)
            events.append(event)
        return dict(query=query,method=method,size=len(self.corpus.sources),backend=self.backend,settings=asdict(self.settings),
                    snapshot=self.corpus.snapshot,requirements=requirements,state=state,rounds=trace,
                    selected_sources=sorted(seen),stop=stop,output=output,generation_error=error,api=api,events=events,
                    metrics=dict(retrieval_calls=calls,module_calls=len(events),rounds=len(trace),
                                 elapsed_ms=(time.perf_counter()-start)*1000,processing_proxy=sum(e['processing_proxy'] for e in events)))
