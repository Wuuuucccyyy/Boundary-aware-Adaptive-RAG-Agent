"""Build the report from both preserved online attempts, including failures."""
import gzip
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from verify_function_results import verify


def main():
    all_records=[];summaries={}
    for version in ('function_online','function_online_v2'):
        directory=ROOT/'results'/version
        all_records+=verify(directory)
        summaries[version]=json.loads((directory/'summary.json').read_text(encoding='utf-8'))
    calls=sum(r['generation']['api']['calls'] for r in all_records)
    tokens=sum(r['generation']['api']['total_tokens'] for r in all_records if r['generation']['api']['usage_known'])
    budget_failures=sum(r['generation']['error']=='api_token_budget' for r in all_records)
    final=[r for r in all_records if r['generation_payload'].get('evidence_catalog') is not None]
    pairs={}
    for r in final:pairs.setdefault(r['case_id'],[]).append(r)
    identical=sum(all(a['decision'][k]==b['decision'][k] for k in ('selected','state','action')) for a,b in pairs.values())
    lines=['# 函数画像适配层与配置路由验证报告','',
      '日期：2026-10-18。20条手工条件案例全部通过；新增适配层能读取原画像、绑定参数、比较显式输入事实，并输出判断、原文依据与读取来源。','',
      '**相同画像、事实和预算下，两种路由在12个配置问题上的决定全部一致，检查量也相同。本轮没有证明动态负向表示或自适应检查的独立收益。**','',
      '## 工程验证','',
      '- 20/20开发条件案例通过；与实现共同开发，不是独立准确率。',
      '- 14项新增单元测试覆盖预算、绑定、类型负例、原画像不变、事实溯源、配置对照和生成引用校验；连同原测试共62项通过。',
      '- package可安装；安装到独立目录后，从项目目录外运行20个案例通过，内置画像和案例可读取。',
      '- 原始5条画像仍为待审记录，未被修改或扩批。前两轮冻结代码未修改。','',
      '适用只表示本轮已实现的文档约束通过。独立性等设计事实需要调用方提供；未执行R、未拟合模型、未验证所有统计假设。','',
      '## 两轮在线记录及完整成本','',
      f'V1与V2共48次尝试，实际发起 **{calls}次DeepSeek API调用**，实际已知用量 **{tokens:,} tokens**。{budget_failures}次预算失败均在发送前发生，API calls为0。所有尝试均保留，没有用离线答案替换失败。','',
      '| 版本 | 方法 | 配置一致数 | 结构化解释通过数 | 检查/题 | 实际API调用 | 实际tokens | 端到端中位秒 |',
      '|---|---|---:|---:|---:|---:|---:|---:|']
    for version,groups in summaries.items():
        for r in groups:
            lines.append(f"| {'V1' if version=='function_online' else 'V2'} | {r['method']} | {round(r['configuration_score']*r['n'])}/{r['n']} | {round(r['rendering_score']*r['n'])}/{r['n']} | {r['checks_per_case']:.3f} | {r['api_calls']} | {r['api_tokens']:,} | {r['elapsed_ms_median']/1000:.3f} |")
    lines+=['','V1完整溯源字段重复进入模型输入，导致全部均值检验问题的两种方法都超过12000的保守输入/输出预留：12次预算失败、12次实际在线成功。此失败揭示生成上下文组织的成本问题，未改变本地路由的正确判断。','',
      'V2按证据ID去重模型上下文，保留全部判断及独立证据目录；完整原始哈希仍在轨迹中。所有12个输入在API调用前通过相同预算预检，最高预留8851。24次在线调用全部通过结构化检查。没有修改路由、案例、金标或校验规则。','',
      '模型仅解释公共检查器的结论，不负责路由；策略名称和分数对模型隐藏。两种策略的同题生成输入逐字相同。结构化检查只验证决定保持一致和引用ID存在，自由说明没有完整蕴含评分。两轮费用合计，V1失败没有从成本报告中删除。','',
      '## V2逐题结果','',
      f'12个配对决定中{identical}个完全一致；每对的预算与生成输入也经校验一致。','',
      '| 问题 | 选择/状态 | full_profile检查数 | dynamic检查数 |','|---|---|---:|---:|']
    for sid,rs in sorted(pairs.items()):
        by={r['decision']['method']:r for r in rs};a=by['full_profile'];b=by['dynamic']
        lines.append(f"| {sid} | {a['decision']['selected'] or a['decision']['state']} | {a['decision']['budget']['checks_used']} | {b['decision']['budget']['checks_used']} |")
    lines+=['','V2每方法平均读取输入32.75次/题。全文本处理proxy分别约10927与10923/题，含画像、检查轨迹与生成文本的UTF-8字节/4；它不是模型tokens或货币成本。实际API tokens分别21754与21712，输入相同但输出存在波动，不能把42 tokens差异解释成路由节省。服务缓存命中与负载影响时延，原始usage完整保存。','',
      '## 代表案例与失败边界','',
      '- condition-05 / route-04：指定配对调用，输入长度8与7；配对候选被阻止，非配对候选因改变用户目标也被拒绝。没有擅自切换统计任务。',
      '- condition-07：未启用配对时，配对长度条目inactive；不会因两组长度不等而误排。',
      '- condition-02/03：数值和复数都属于PCA默认接口明确支持的集合；公式接口仍按自己的数值要求判断。',
      '- condition-18 / route-12：不同数据行不足来自已标为推断的要求，输出unknown并请求核实，未直接当作确定文档冲突。',
      '- condition-20：PCA退化列缩放规则的文字歧义保持待核实，没有靠参数别名常识修补原画像。',
      '- V1中route-01至route-06均发生输入预留预算失败，完整数据保留于V1归档。','',
      '## 能得出的结论与下一步','',
      '工程接入已有实质进展：相同文档可随参数和事实产生满足、冲突、未知或分支不生效，并能解释原因。研究增益尚未证实。公共检查器和门槛已经解决了本轮大多数兼容性问题，候选通常只有一个可用配置，排序方法的独立作用很弱。','',
      '本轮没有实现按需获取新事实或动态停止检查，所以不能检验减少检查成本的假设。适配器是现有4个函数的受控词汇映射，不是任意R函数的通用自动编译器；部分输入类型转换仍需核实。用户提供的输入事实也尚未与真实数据自动核对。','',
      '后续应把画像构建质量、兼容性判断和信息获取策略分别评价。扩充同任务近邻前先审阅这些映射；若研究按需检查，须给普通完整信息路由同样的检查工具和预算，并引入可测的取数/核实成本、独立案例和多种有效候选。暂不据本轮开发分数启动训练。','',
      '## 复现','',
      '```bash','python -m function_guard --cases',
      'python scripts/read_function_trace.py --id route-04 --method dynamic',
      'python scripts/verify_function_results.py results/function_online',
      'python scripts/verify_function_results.py results/function_online_v2',
      'python scripts/run_function_comparison.py --ccswitch --output results/function_new',
      '```','',
      '在线命令会产生24次付费调用。V1与V2均保存源码快照和哈希，当前代码对应V2；新运行结果会受服务端波动影响。协议见[冻结协议](../experiments/FUNCTION_PROTOCOL.md)，输入及运行说明见[适配层指南](FUNCTION_ADAPTER_GUIDE.md)。','']
    (ROOT/'docs/FUNCTION_ADAPTER_REPORT.md').write_text('\n'.join(lines),encoding='utf-8',newline='\n')
    print(f'Report: 20 development cases, {calls} actual API calls, {tokens} total tokens across V1/V2')

if __name__=='__main__':main()
