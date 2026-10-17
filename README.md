# Boundary-aware Adaptive RAG Agent

边界感知自适应 RAG 智能体：面对职责交叉的 HR、财务、技术支持知识库，解释每个来源能支持当前问题的哪些子任务，按证据缺口追加检索，并记录成本和停止原因。

第一阶段原型使用规则动态边界，无需训练、无需数据库或前端。**离线演示用于开发验证；正式对比实验使用 DeepSeek 在线回答。** 数据全部自建，原始研究文档和密钥不在仓库中。按项目所有者后续要求，本仓库公开。

## 安装

需要 Python 3.11+。运行时只使用标准库。

```bash
git clone https://github.com/Wuuuucccyyy/Boundary-aware-Adaptive-RAG-Agent.git
cd Boundary-aware-Adaptive-RAG-Agent
python -m venv .venv
```

Windows PowerShell：`.venv\Scripts\Activate.ps1`。macOS/Linux：`source .venv/bin/activate`。

直接从仓库目录运行以下命令即可，无需安装额外包。可选 `python -m pip install .` 安装 `boundary-rag` 命令。`requirements.txt` 说明无运行时依赖；安装构建本身需要 setuptools。

## 先运行端到端示例

```bash
python -m boundary_rag "员工期权的授予资格是什么，期权税务怎么算？" --method dynamic --output results/my_demo.json
```

预期第一轮选择 `hr` 和 `finance`：HR提供入职满12个月、委员会批准和4年归属期；财务提供本合成案例的税基公式和20%模拟扣缴规则。答案分别引用 `[hr-option_eligibility]` 与 `[finance-option_tax]`。IT不提供这两个子任务的依据，日志解释本轮未选原因。

输出还包括每个库的正向分、任务级冲突、画像版本、实际检索文档、缺失证据、轮数、调用、耗时及停止原因。原始轨迹示例见 [离线开发演示](results/demo_extractive.json) 和 [DeepSeek 在线演示](results/demo_deepseek.json)。

```bash
python -m boundary_rag "VPN连接失败，员工门户密码如何重置？"
python -m boundary_rag "明天上海天气如何？"
python -m boundary_rag "期权税务怎么算，明天股价是多少？"
python -m boundary_rag "员工期权资格和期权税务怎么算？" --max-retrieval-calls 1
```

## 使用 DeepSeek

通过环境变量配置。`.env.example` 仅是模板，程序不会自动加载 `.env`。不要将实际 key 写入代码、命令历史或配置提交；可在本机环境设置界面配置，或使用交互式输入。

PowerShell：

```powershell
$secret = Read-Host "DeepSeek API key" -AsSecureString
$env:DEEPSEEK_API_KEY = [System.Net.NetworkCredential]::new('', $secret).Password
$env:DEEPSEEK_MODEL = 'deepseek-v4-pro'
$env:DEEPSEEK_BASE_URL = 'https://api.deepseek.com'
python -m boundary_rag --backend deepseek --output results/my_online_demo.json
```

macOS/Linux（bash）：

```bash
read -rsp 'DeepSeek API key: ' DEEPSEEK_API_KEY; echo
export DEEPSEEK_API_KEY
export DEEPSEEK_MODEL=deepseek-v4-pro
export DEEPSEEK_BASE_URL=https://api.deepseek.com
python -m boundary_rag --backend deepseek
```

已配置 CC Switch 的本机可显式选择 `--ccswitch`：只读 `~/.cc-switch/cc-switch.db` 中名为 DeepSeek 的当前提供商，凭据仅注入本进程环境，转换官方 Anthropic 兼容地址为官方 Chat Completions 地址，并移除模型名的 `[1m]` 客户端后缀。此方式不修改 CC Switch，也不导出数据库。

```bash
python -m boundary_rag --backend deepseek --ccswitch
```

接口依据 [DeepSeek Chat Completions 官方文档](https://api-docs.deepseek.com/api/create-chat-completion/)，使用关闭 thinking 的统一生成设置并保存实际 `usage`。模型 ID 可通过环境变量更换；复现提交结果请保持模型一致。API失败或截断会明确失败，不冒充离线成功。

## 复现正式在线对比

先阅读 [冻结评价协议](experiments/PROTOCOL.md)。完整运行会产生 320 次付费 API 请求（40题 × 4方法 × 2重复），每次最多输出800 tokens，默认不自动重试。

```bash
python scripts/run_experiments.py --backend deepseek --repeats 2 --output results/my_online
# 或使用本机 CC Switch：追加 --ccswitch
python scripts/pack_traces.py results/my_online
```

中断后加 `--resume`；代码、配置、模型、数据哈希都必须一致，已有轨迹不重复收费。换参数请使用新输出目录。结果含 `manifest.json`、`summary.csv/json`、配对 bootstrap 区间、所有失败样例、每题轨迹。在线模型和网络存在波动，可复现流程及数据，不能保证逐字答案或时延相同。

提交的正式结果位于 [results/online](results/online)，原始轨迹压缩为 `traces.jsonl.gz`，完整内容未删减。查看任一问题：

阅读 [在线实验报告与失败分析](docs/EXPERIMENT_REPORT.md)。原始自动评分有已披露的格式及粒度偏差，需结合报告中的人工复核，不应直接解释为真实准确率。

已完成的正式运行共320次在线问答、65,225个实际API tokens。动态方案平均1.975次检索，全库5.10次、正向2.025次、固定2.00次；四种方案约203–205个API tokens/题，本轮未证明动态方案显著节省模型tokens。内容复核由开发助手完成，并非独立人类盲审。

```bash
python scripts/read_trace.py --id test-11 --method dynamic --repetition 0
python scripts/verify_results.py results/online
```

离线开发验证和必要测试：

```bash
python -m unittest discover -s tests -v
python scripts/run_experiments.py --backend extractive --split dev --repeats 1 --output results/my_dev
```

四方法为 `all` 全库、`positive` 正向画像、`fixed` 固定负向软惩罚、`dynamic` 当前缺口条件下的动态任务边界。检索、证据检查、回答模型、预算统一；各方法都可追加检索。指标包括答案事实/拒答代理分、必要源召回、证据召回、实际API tokens、规则处理量、调用量及p50/p95时延。规则路由和检查的API tokens为0，其CPU工作和耗时仍计入。不要把本地 `processed_token_proxy` 当成模型tokens或费用。

## 项目结构

```text
boundary_rag/      分析、路由、BM25、证据检查、生成、计量和命令行
  data/            合成文档、P/Q/N画像、任务本体
scripts/           数据重建、实验、原始轨迹归档/读取
experiments/       冻结协议与独立评价金标
tests/             核心流程与API故障测试
results/online/    正式在线结果与压缩原始轨迹
docs/              计划、架构、数据卡、已知问题与后续研究
```

详见 [架构](docs/ARCHITECTURE.md)、[数据来源与限制](docs/DATA_CARD.md)、[已知问题及下一阶段](docs/KNOWN_ISSUES.md) 和仓库 [Issues](https://github.com/Wuuuucccyyy/Boundary-aware-Adaptive-RAG-Agent/issues)。动态方法同时使用任务覆盖矩阵与集合选择，合成实验不单独证明负向边界的研究贡献。
