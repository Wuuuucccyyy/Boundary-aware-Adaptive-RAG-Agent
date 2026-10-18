"""Original synthetic studies; numeric findings recomputed from deterministic data."""
import hashlib
import json
from pathlib import Path
import random
import statistics as st

DATA = Path(__file__).parent / 'data'
LABELS = {'effect':'效应估计', 'validation':'验证方案', 'summary':'均值统计',
          'missing':'缺失处理', 'prediction':'预测结果', 'diagnostics':'残差诊断'}


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')


def build():
    specs = [
        ('trial','effect',{'design':'randomized','goal':'causal'}, '随机试验组间均值差', ['观察研究','相关关系']),
        ('observational','effect',{'design':'observational','goal':'association'}, '观察研究线性回归关联', ['因果']),
        ('iid','validation',{'dependence':'iid'}, '独立样本随机留出验证', ['时间序列','按月']),
        ('temporal','validation',{'dependence':'temporal'}, '时间顺序留出验证', ['独立同分布']),
        ('sample','summary',{'target':'sample'}, '当前样本描述均值', ['总体均值']),
        ('population','summary',{'target':'population'}, '已知抽样概率的加权总体均值', ['样本均值']),
        ('mcar','missing',{'mechanism':'mcar'}, 'MCAR条件下完整案例均值示例', ['MAR','MNAR']),
        ('mar','missing',{'mechanism':'mar'}, 'MAR条件下分层插补示例', ['MCAR','MNAR']),
        ('predict','prediction',{}, '冻结线性模型的预测结果', ['因果']),
        ('diagnose','diagnostics',{}, '线性模型残差描述', []),
    ]
    studies=[]
    for variant in range(3):
        for index,(kind,topic,extra,method,negative) in enumerate(specs):
            rng=random.Random(817+variant*100+index)
            x=list(range(1,21)); y=[2+0.7*t+rng.uniform(-1,1)+variant for t in x]
            slope,intercept=st.linear_regression(x,y)
            pred=[intercept+slope*t for t in x]
            residual=[a-b for a,b in zip(y,pred)]
            weights=[1 if t%2 else 3 for t in x]
            split=14
            train_slope,train_intercept=st.linear_regression(x[:split],y[:split])
            temporal_mae=st.mean(abs(v-(train_intercept+train_slope*t)) for t,v in zip(x[split:],y[split:]))
            order=list(range(20));rng.shuffle(order)
            train=order[:split];test=order[split:]
            rs,ri=st.linear_regression([x[j] for j in train],[y[j] for j in train])
            iid_mae=st.mean(abs(y[j]-(ri+rs*x[j])) for j in test)
            treatment=[1 if j%2 else 0 for j in order]
            outcome=[10+2*a+rng.uniform(-1,1) for a in treatment]
            difference=st.mean(v for v,a in zip(outcome,treatment) if a)-st.mean(v for v,a in zip(outcome,treatment) if not a)
            values={
                'trial':f'合成随机分配试验的处理组减对照组均值差为{difference:.3f}，该数值仅对应这项模拟试验。',
                'observational':f'合成观察数据的一元回归斜率为{slope:.3f}，仅描述关联，不建立因果识别。',
                'iid':f'合成独立样本采用随机留出验证，测试集MAE为{iid_mae:.3f}。',
                'temporal':f'合成时间序列采用过去14点训练、未来6点验证，测试集MAE为{temporal_mae:.3f}。',
                'sample':f'合成当前样本的未加权均值为{st.mean(y):.3f}，不据此保证总体代表性。',
                'population':f'按合成研究给定的逆抽样概率权重计算，总体均值估计为{sum(a*b for a,b in zip(y,weights))/sum(weights):.3f}。',
                'mcar':'此方法卡讨论MCAR条件下完整案例均值；缺失机制未核实时不能保证完整案例估计的适用性。',
                'mar':'此方法卡讨论MAR且插补模型合理时的分层插补；模型不确定性需要另外处理，不把单次插补当作完整推断。',
                'predict':f'冻结合成线性模型在x=25处的预测值为{intercept+slope*25:.3f}；这是外推示例，不是因果效应。',
                'diagnose':f'合成线性模型训练残差平均绝对值为{st.mean(abs(v) for v in residual):.3f}；该描述不能独自证明误差独立或模型正确。',
            }
            scope=dict(region='US' if variant==1 else 'CN',year='2022' if variant==2 else '2026',population='adult',**extra)
            sid='s'+hashlib.sha256(f'{kind}-{variant}'.encode()).hexdigest()[:8]
            quote=values[kind]
            profile_scope=dict(scope)
            if kind=='predict':profile_scope['population']=None
            # Conditions are documented facts about this study, not complements of task IDs.
            scope_text='；'.join(f'{k}={v}' for k,v in scope.items())
            studies.append(dict(id=sid,kind=kind,variant=variant,topic=topic,version='stats-v2-20261017',
                profile=dict(positive=LABELS[topic]+'：统计建模研究的方法、结果与局限。',
                             conditions=profile_scope,conditions_reference=sid+'-report',fixed_negative=negative),
                document=dict(id=sid+'-report',source=sid,title=method,text=quote+' 研究适用条件：'+scope_text,
                              quote=quote,conditions=scope,topic=topic,version='stats-v2-20261017'),
                computation=dict(x=x,y=y,weights=weights,treatment=treatment,outcome=outcome,
                                 random_train_indices=train,random_test_indices=test)))
    write(DATA/'studies.json',studies)


if __name__=='__main__':build()
