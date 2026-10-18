# 统计分析场景运行说明

这一轮研究来源选择和证据适用性。知识源是30项合成研究的方法/结果卡，包含可重算数据；程序检索这些已算好的结果，尚不负责对任意上传表格自动建模。

原有 `boundary_rag`、第一轮实验与复现命令保持不变；第二轮代码为 `stat_rag`。Python 3.11+，运行时仍只有标准库。

## 端到端运行

```bash
# 离线只作开发验证
python -m stat_rag --size 30 --output results/my_stat_demo.json
# 正式模型演示，使用本机已经授权的CC Switch配置
python -m stat_rag --size 30 --backend deepseek --ccswitch --output results/my_stat_online.json
python scripts/read_stat_trace.py --demo results/my_stat_online.json
```

其他环境使用 `DEEPSEEK_API_KEY`、`DEEPSEEK_MODEL`、`DEEPSEEK_BASE_URL`，去掉`--ccswitch`。与第一轮一致，凭据只进入进程环境，不记录到结果。

默认例子询问中国2026年成年人随机试验的效应估计与独立同分布验证方案。适用的两个研究给出模拟均值差2.459、随机留出MAE 0.457。美国研究或2022年研究虽主题相同，不能支持指定条件的结论。

四来源例子：

```bash
python -m stat_rag "中国2026年成年人研究：请组合预测结果、残差诊断、时间序列验证方案和MAR缺失处理。" --size 30 --backend deepseek --ccswitch --output results/stat_four_sources.json
python scripts/read_stat_trace.py --demo results/stat_four_sources.json
```

证据不足例子：`中国2026年成年人研究：仅有观察研究，因果效应是多少？`。系统应说明所给集合不能支持该因果结论，而非把关联斜率改名为因果效应。

## 正式对比

```bash
python scripts/run_stat_experiments.py --backend deepseek --ccswitch --split test --repeats 2 --output results/my_stat_experiment
```

默认10/20/30来源，6方法，12问题，2重复，共432次付费模型调用。可用 `--sizes 10` 做较小规模运行；使用新目录，或在配置/代码/数据一致时加 `--resume`。每次最多输出700tokens，无自动重试；失败保留实际usage，不静默切回离线。

方法：`all`、`positive`、`fixed`、`full_profile`、`dynamic`、`no_negative`。除全库外共享同一集合选择器；full_profile读取全部同样的条件，no_negative是dynamic移除两个惩罚项。

提交结果在 `results/stat_online`；主质量指标是结构化证据回答分，不等于自然语言统计解释的整体正确率。

```bash
python scripts/read_stat_trace.py --id stat-09 --size 30 --method dynamic
python scripts/verify_stat_results.py results/stat_online
```

## 数据与限制

`studies.json`包含来源画像、明确文档条件和原始数组；`benchmark.json`包含独立评价用的手工任务与支持文档金标。所有机构/总体标签及数字为合成。数值可用 `python -m stat_rag.fixtures` 重建；问题可用 `python -m stat_rag.benchmark` 重建。生产路由不读取问题gold。

来源范围有CN/US、2026/2022、adult以及研究设计/依赖结构/缺失机制等。预测画像故意缺少总体信息，正文明确为adult，用于验证“未知→检索核实”，而非未知即排除。每个来源目前只有一个文档，库内排序复杂度很低。

同主题不同条件的来源使用相同正向主题描述，这是受控混淆设置。它可能放大条件元数据的价值；必须与full_profile比较才能讨论显式负向表示的独立价值。规模与新增地区/时期条件耦合，不能把结果解释为纯来源数量效应。12个问题和合成规则覆盖有限，dev/test重用研究文档，没有独立自然数据或盲审。

设计依据是[NIST实验设计说明](https://itl.nist.gov/div898/handbook/ppc/section1/ppc136.htm)中的关联/因果区分，以及[scikit-learn验证指南](https://sklearn.org/stable/modules/cross_validation.html)对依赖数据验证方式的说明。资料仅使用自写摘要；统计原理不代表这些模拟数值有现实解释。

完整设置见[冻结协议](../experiments/STAT_PROTOCOL.md)，结果及失败分析见[第二轮报告](STAT_REPORT.md)。
