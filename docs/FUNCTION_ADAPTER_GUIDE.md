# 函数画像适配层运行说明

Python 3.11+，运行时仅标准库。仓库根目录可直接运行，或用`python -m pip install .`安装。构建安装可能需要联网获取setuptools等构建工具；运行条件案例不需要R或API。

## 开发案例与单次判断

```bash
python -X utf8 -m function_guard --cases --output results/my_conditions.json
python -X utf8 -m function_guard --request function_guard/data/example_request.json --output results/my_function_decision.json
```

默认示例指定配对检验，输入长度8和7，结果为conflict、block_configuration。输出包含生效的参数分支、逐条状态、文档章节/短片段/URL/哈希、输入事实来源与检查预算。条件不生效标为inactive；未绑定或未知参数不能自动视作false。

输入是结构化调用意图，当前没有自然语言解析器或自动数据事实抽取。最小请求示例：

```json
{
  "function_id": "stats::prcomp",
  "parameters": {"method": "default", "center": true, "scale.": false},
  "facts": {
    "x_type": "numeric", "x_structure": "matrix", "ncol": 3,
    "has_missing": false, "zero_columns": false, "constant_columns": false
  },
  "fact_provenance": {"x_type": "调用方的数据结构检查"}
}
```

省略、null和字面量unknown/any都不能作为实际事实的确定值。未给来源的事实标为caller_supplied，不假称程序已经从数据验证。`parameters.method`是适配器接口标签default/formula，不是传给R的同名参数；所有生效参数显式提供，不从模型常识猜默认值。

数值参数标量表示长度1的R数值向量，与true/false分开；向量使用JSON数组。不能确认的字符串向量转换进入unknown，不静默强转。`x_type`使用numeric/integer/double/complex/categorical/binary/logical/text；结构使用vector/matrix/data_frame/matrix_like。公式调用的x事实描述参与分析的响应或变量，仍须单独提供公式结构事实。

## 结果语义与范围

| 总状态 | 含义 | 处置 |
|---|---|---|
| applicable | 本轮实现的文档输入条件通过 | 在已说明范围内继续，可附警告 |
| conflict | 已确认的文档要求或用户目标冲突 | 阻止当前配置 |
| unknown | 关键事实/参数/文档未明确，或预算不足 | 澄清或复核 |
| excluded | 画像筛选已排除 | 不进入统计函数路由 |

每条检查另有satisfied、conflict、unknown、inactive、informational、warning、documentation_conflict状态。required是要求；supported不是排他限制；behavior是行为，通常不作为硬门槛。推断条目失败只形成unknown，来源文字歧义不自动编译为阻断规则。

无关的文档未知不自动阻断全部任务。`focus_claim_ids`可要求本次必须回答某条未知要求，例如分布适用性；该项仍未知时，整体不能报告通过。applicable不保证所有统计假设成立或R函数一定成功，完整性受原画像和适配器覆盖范围限制。

画像加载用`importlib.resources`，安装后可读取打包的画像及案例；原始`pilot_v1`记录及review_status不变。规则是显式受控映射，未实现任意函数自动编译。结构关系由明确比较操作处理，不执行文档中的代码或字符串表达式。

## 同配置路由对照

12个案例在`function_guard/data/routing_cases.json`，每个有同一函数的两个配置。完整画像普通路由与动态边界路由使用相同输入、兼容性检查和80个检查单元预算。用户明确目标也参与检查，例如指定paired=true后不能自动换成非配对分析。

```bash
python scripts/read_function_trace.py --id route-04 --method dynamic
python scripts/read_function_trace.py --id route-12 --method full_profile --json
python scripts/verify_function_results.py results/function_online_v2
```

以上只读已提交结果，不产生API调用。重新运行在线小样本：

```bash
python scripts/run_function_comparison.py --ccswitch --output results/function_new
```

共24次DeepSeek调用；也可用环境变量`DEEPSEEK_API_KEY`、`DEEPSEEK_MODEL`、`DEEPSEEK_BASE_URL`并去掉`--ccswitch`。凭据不写日志，无自动重试；中断后加`--resume`要求代码、画像、案例与配置哈希完全一致。

结果保存manifest、源码快照、summary、失败记录和完整压缩轨迹。V1全部保留；V2仅对生成输入做证据去重，成本报告包括两次运行。检查单元、输入读取次数、文本proxy与实际API tokens分别计量；路由和检查是本地规则，模型只生成带引用的解释。

详见[实验报告](FUNCTION_ADAPTER_REPORT.md)和[冻结协议](../experiments/FUNCTION_PROTOCOL.md)。
