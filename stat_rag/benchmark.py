"""Hand-authored task gold, separate from production parser and routing."""
from .fixtures import DATA,write
import json


def build():
    common='中国2026年成年人研究：'
    definitions=[
      ('single', '随机试验的因果效应估计是多少？',{'effect':'trial'}),
      ('single', '观察研究的关联估计是多少？',{'effect':'observational'}),
      ('single', '时间序列的验证方案和误差是什么？',{'validation':'temporal'}),
      ('single', '独立同分布数据的验证设计是什么？',{'validation':'iid'}),
      ('single', '已知逆抽样概率权重时总体均值是多少？',{'summary':'population'}),
      ('single', '只描述当前样本，样本均值是多少？',{'summary':'sample'}),
      ('single', '假设MAR，缺失处理需要什么条件？',{'missing':'mar'}),
      ('cross2', '随机试验的因果效应估计是多少，同时独立同分布数据的验证方案是什么？',{'effect':'trial','validation':'iid'}),
      ('cross4', '请组合预测结果、残差诊断、时间序列验证方案和MAR缺失处理。',{'prediction':'predict','diagnostics':'diagnose','validation':'temporal','missing':'mar'}),
      ('unsupported', '仅有观察研究，因果效应是多少？',{'effect':None}),
      ('unsupported', '请给出预测结果。',{'prediction':None}),
      ('partial', '随机试验的因果效应估计是多少，以及公司的实际营业收入是多少？',{'effect':'trial','unknown':None}),
    ]
    sources=json.loads((DATA/'studies.json').read_text(encoding='utf-8'))
    samples=[]
    for i,(category,text,gold) in enumerate(definitions,1):
        query=common+text
        if i==11:query=query.replace('成年人','老年人')
        acceptable={task:[s['document']['id'] for s in sources if s['kind']==kind and s['variant']==0] if kind else [] for task,kind in gold.items()}
        samples.append(dict(id=f'stat-{i:02}',category=category,query=query,split='test',acceptable_documents=acceptable,
                            necessary_source_count=sum(bool(ids) for ids in acceptable.values())))
    # Development uses different phrasing, same small synthetic domain, disclosed non-independent documents.
    for i,(text,gold) in enumerate([
      ('随机试验效应估计，请附原文。',{'effect':'trial'}),
      ('时间序列验证设计，请解释训练与测试顺序。',{'validation':'temporal'}),
      ('MCAR缺失处理有哪些条件？',{'missing':'mcar'}),
      ('预测值与残差情况是什么？',{'prediction':'predict','diagnostics':'diagnose'}),
      ('缺失机制是MNAR，缺失处理如何进行？',{'missing':None}),
      ('独立同分布验证方案和样本均值分别是什么？',{'validation':'iid','summary':'sample'})],1):
        samples.append(dict(id=f'dev-stat-{i:02}',category='dev',query=common+text,split='dev',
          acceptable_documents={t:[s['document']['id'] for s in sources if s['kind']==kind and s['variant']==0] if kind else [] for t,kind in gold.items()}))
    write(DATA/'benchmark.json',samples)


if __name__=='__main__':build()
