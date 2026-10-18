"""Describe frozen formal results; retain every trial and all unfavorable findings."""
import gzip
import json
from pathlib import Path
import statistics as st
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from stat_rag.fixtures import write
from stat_rag.core import METHODS


def main():
    directory=ROOT/'results/stat_online'
    with gzip.open(directory/'traces.jsonl.gz','rt',encoding='utf-8') as stream:records=[json.loads(line) for line in stream]
    summaries=json.loads((directory/'summary.json').read_text(encoding='utf-8'))
    intervals=json.loads((directory/'paired_ci.json').read_text(encoding='utf-8'))
    manifest=json.loads((directory/'manifest.json').read_text(encoding='utf-8'))
    overall={(r['size'],r['method']):r for r in summaries if r['category']=='overall'}
    paired={(r['sample_id'],r['run']['size'],r['run']['method'],r['repetition']):r for r in records}
    changes=[]
    for size in (10,20,30):
        for baseline in ('positive','fixed','full_profile','no_negative'):
            a=[r for r in records if r['run']['size']==size and r['run']['method']=='dynamic']
            first=sum(set(r['run']['rounds'][0]['selected'])!=set(paired[(r['sample_id'],size,baseline,r['repetition'])]['run']['rounds'][0]['selected']) for r in a)
            all_sources=sum(set(r['run']['selected_sources'])!=set(paired[(r['sample_id'],size,baseline,r['repetition'])]['run']['selected_sources']) for r in a)
            changes.append(dict(size=size,baseline=baseline,paired_runs=len(a),first_round_changed=first,total_source_set_changed=all_sources))
    write(directory/'decision_changes.json',changes)
    tokens=sum(r['run']['api']['total_tokens'] for r in records if r['run']['api']['usage_known'])
    known=sum(r['run']['api']['usage_known'] for r in records)
    failures=sum(not r['scores']['generation_success'] for r in records)
    paired_quality=[overall[(n,'dynamic')]['evidence_answer_score']-overall[(n,'full_profile')]['evidence_answer_score'] for n in (10,20,30)]
    lines=['# 第二轮统计分析领域在线实验报告','',
           '**本轮检验条件边界是否真正改变来源选择，以及在更多相似来源下是否有帮助。** 它不检验任意数据自动建模，也不把结构化摘录分当作完整统计建议正确率。','',
           f"正式运行完成{len(records)}次在线问答，模型请求为`{manifest['identity']['model']}`；{known}次有完整usage，已知实际用量共 **{tokens:,} tokens**，生成失败{failures}次。离线开发与单独演示不纳入正式结果。",'',
           '## 主要结果','',
           '| 来源数 | 方法 | 证据回答分 | 最终必要源召回 | 检索调用/题 | 不适用文档/题 | 实际API tokens/题 | p50 / p95秒 |',
           '|---:|---|---:|---:|---:|---:|---:|---:|']
    for size in (10,20,30):
        for method in METHODS:
            r=overall[(size,method)]
            lines.append(f"| {size} | {method} | {r['evidence_answer_score']:.3f} | {r['source_recall']:.1%} | {r['retrieval_calls']:.3f} | {r['inappropriate_documents']:.3f} | {r['api_tokens']:.2f} | {r['p50_ms']/1000:.3f} / {r['p95_ms']/1000:.3f} |")
    lines+=['','每行24次问答（12题×2重复），不是24个独立题目。必要源召回排除无来源的任务；错误条件文档会被共同验证器拒绝，因此它反映的是检索浪费，并不意味着错误内容已经进入回答。','']
    if all(abs(d)<1e-12 for d in paired_quality):
        lines.append('**动态与完整条件普通路由在三个规模上的主质量分相同。** 这支持“适用条件有价值”的解释，但不证明把条件显式写成负向边界优于一般兼容性路由。还需对比调用量与局限，而不能只对比弱主题基线。')
    else:
        lines.append('动态与完整条件普通路由存在分数差异，幅度和区间见后表；小型合成任务不足以确立一般优势。')
    d=overall[(30,'dynamic')];f=overall[(30,'fixed')];p=overall[(30,'full_profile')]
    lines+=['',f"30来源下，动态相对固定边界少检索{(1-d['retrieval_calls']/f['retrieval_calls']):.1%}，两者证据回答分均为{d['evidence_answer_score']:.3f}；相对完整条件普通路由仅少{p['retrieval_calls']-d['retrieval_calls']:.3f}次/题。后者的差异来自stat-12这一道部分可回答题少查一个来源，不能据此宣称稳定优势。",
            '', '30来源、四源问题stat-09中，动态与完整条件普通路由均一轮检索4个来源；固定边界需三轮8次，正向方法三轮11次仍只满足一半任务。它支持在这个混淆例子中减少试错的判断，尚未证明必要来源数增加本身带来优势。']
    lines+=['','主题基线或消融方法可能因为缺失可回答证据而输出更短的拒答，从而使用更少tokens。这样的token下降不能解释为在同等质量下更省成本。和全库比较时，无关内容已被共同验证器过滤，生成阶段输入也未必更短。','',
            '## 负向项是否实际生效','',
            '| 来源数 | 对比基线 | 配对问答数 | 首轮选源集合不同 | 最终访问集合不同 |',
            '|---:|---|---:|---:|---:|']
    for r in changes:lines.append(f"| {r['size']} | {r['baseline']} | {r['paired_runs']} | {r['first_round_changed']} | {r['total_source_set_changed']} |")
    lines+=['','这里比较的是同题、同规模、同重复编号的真实在线轨迹；路由为确定性规则，两次重复的选库并非独立样本。no_negative与dynamic共用同一个选择器和全部条件，仅惩罚系数变为0。这比第一轮的平局排序更能检验负向项是否影响行为。','',
            '## 规模与多源问题','',
            '| 来源数 | 类别 | 方法 | 证据回答分 | 检索调用/题 | 轮数/题 |',
            '|---:|---|---|---:|---:|---:|']
    for r in summaries:
        if r['category'] not in ('cross2','cross4'):continue
        lines.append(f"| {r['size']} | {r['category']} | {r['method']} | {r['evidence_answer_score']:.3f} | {r['retrieval_calls']:.3f} | {r['rounds']:.3f} |")
    lines+=['','双源和四源类别各只有一道问题，重复两次只反映生成波动，无法估计该问题类别的泛化效果。新增来源是同主题但地区/时期不同的独立合成研究；支持文档始终保留，规模与混淆条件耦合，因此结果不能直接推广为“知识库越多，动态方法必然越好”。','',
            '## 完整开销','',
            '| 来源数 | 方法 | 本地处理proxy/题 | 总模块调用/题 | 路由ms/题 | 验证ms/题 | 生成ms/题 |',
            '|---:|---|---:|---:|---:|---:|---:|']
    for size in (10,20,30):
        for method in METHODS:
            rs=[r for r in records if r['run']['size']==size and r['run']['method']==method]
            costs=[st.mean(sum(e['ms'] for e in r['run']['events'] if e['stage']==stage) for r in rs) for stage in ('routing','verification','generation')]
            s=overall[(size,method)]
            lines.append(f"| {size} | {method} | {s['processing_proxy']:.1f} | {s['module_calls']:.2f} | {costs[0]:.3f} | {costs[1]:.3f} | {costs[2]:.3f} |")
    lines+=['','规则分析、路由、检索与验证没有API tokens，但其处理量与耗时都在账本内。proxy是UTF-8字节/4的文本工作代理，不是模型tokens、CPU指令或货币费用。端到端包括计量和序列化，不包含初次加载/索引或落盘。API主导时延；按顺序轮换方法只能部分缓解服务端缓存、负载差异。','',
            '## 配对不确定性','',
            '按问题聚类bootstrap1000次；每规模只有12个题目。差值为dynamic减对应基线。','',
            '| 来源数 | 比较 | 指标 | 平均差 | 95%区间 |','|---:|---|---|---:|---|']
    for r in intervals:lines.append(f"| {r['size']} | {r['comparison']} | {r['metric']} | {r['mean']:.3f} | [{r['ci95'][0]:.3f}, {r['ci95'][1]:.3f}] |")
    lines+=['','## 失败、成功与评价边界','',
            '所有失败保存在`results/stat_online/failures.json`，原始轨迹完整保留。以下按每题每规模每方法第一次重复列出自动失败，不选择性删除：','',
            '| 题目 | 来源数 | 方法 | 证据回答分 | 未满足任务 | 生成错误 |','|---|---:|---|---:|---|---|']
    for r in records:
        if r['repetition'] or r['scores']['exact_task_success']:continue
        run=r['run'];lines.append(f"| {r['sample_id']} | {run['size']} | {run['method']} | {r['scores']['evidence_answer_score']:.3f} | {', '.join(run['state']['missing'])} | {run['generation_error'] or '无'} |")
    lines+=['','### 具体轨迹复核','',
            '以下固定查看30来源、第一次重复的双源/四源与未知总体问题。属于开发助手的轨迹复核，不是独立人类盲审。','',
            '| 题目 | 方法 | 分数 | 各轮检索数量 | 最终缺口 |','|---|---|---:|---|---|']
    for sid in ('stat-08','stat-09','stat-11'):
        for method in ('positive','fixed','full_profile','dynamic'):
            r=paired[(sid,30,method,0)];run=r['run']
            lines.append(f"| {sid} | {method} | {r['scores']['evidence_answer_score']:.3f} | {' → '.join(str(len(x['retrievals'])) for x in run['rounds'])} | {', '.join(run['state']['missing']) or '无'} |")
    lines+=['','stat-08要求随机试验效应与独立同分布验证。主题相同并不保证研究设计、地区和年份吻合；正向路由三轮后仍缺效应证据，固定路由需要三轮，完整条件普通路由和动态路由均一轮取齐。这个例子说明适用条件可避免试错，但未区分这两种条件路由。','',
            'stat-11询问老年人预测，而来源画像缺少总体字段、正文只支持成年人。动态先探索未知来源，核实后拒绝外推，最终正确拒答；但之后的保底探索仍可能选到无关主题。正确拒答分掩盖了这部分浪费，当前停止策略仍需改进。','']
    lines+=['','生成成功不等于问题被回答：部分主题路由在三轮内没取得适用证据，模型正确地拒绝补算，但对原本可回答的题仍是任务失败。共同验证器阻止了错误条件下的数值被作为正确答案。','',
            '结构化质量只检查任务级合法来源、完整原文与未知声明，不要求问题未询问的附加事实。自然语言answer字段未做完整蕴含或独立人类评价。严格摘录要求可能把合理改写判为格式失败，任何此类失败均原样保留。','',
            '## 对下一阶段的含义','',
            '本轮首先判断负向项是否真正影响了选择，其次用full_profile分离信息量与表示方式。即使动态胜过positive/no_negative，若full_profile达到相同质量及相近成本，当前证据仍不足以支持显式负向表示的独立贡献。','',
            '优先增加更自然的分析问题、独立任务标注、多文档来源、未知与错误元数据、冲突条件的可靠性，并让数量和混淆度独立变化。加入更强的全条件模型路由及校准概率，做质量约束下成本比较。暂不以本轮合成分数为依据直接开始训练。','',
            '## 复现','',
            '```bash','python scripts/verify_stat_results.py results/stat_online',
            'python scripts/read_stat_trace.py --id stat-08 --size 30 --method no_negative',
            'python scripts/run_stat_experiments.py --backend deepseek --ccswitch --split test --repeats 2 --output results/stat_new',
            '```','',
            '协议、数据生成、运行与局限见[统计场景指南](STAT_GUIDE.md)和[冻结协议](../experiments/STAT_PROTOCOL.md)。模型凭据、原始研究Word文档不在仓库中。','']
    (ROOT/'docs/STAT_REPORT.md').write_text('\n'.join(lines),encoding='utf-8',newline='\n')
    print(f'Report: {len(records)} online runs, {tokens} known tokens, {failures} generation failures')


if __name__=='__main__':main()
