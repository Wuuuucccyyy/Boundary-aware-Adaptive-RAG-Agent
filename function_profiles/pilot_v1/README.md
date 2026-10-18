# 函数输入数据画像：首批5条待审样例

标注日期：2026-10-18（America/Los_Angeles）。范围由用户确认：`stats::t.test`、`stats::prcomp`、`stats::kmeans`、`base::scale`、`utils::read.csv`。每个函数只有一条记录，方法和参数差异保留在条目内部。当前仅供检查标注口径，**未开始批量处理、模型训练或新的在线实验**。

- [profiles.json](profiles.json)：便于展开阅读的5条记录数组。
- [profiles.jsonl](profiles.jsonl)：相同内容，每行一条记录，供程序读取。
- [schema.json](schema.json)：单条记录的JSON Schema（Draft 2020-12）。
- [source_manifest.json](source_manifest.json)：8个官方文档页面的URL、实际获取时间、页面标示版本和原始HTML SHA-256。
- [validation.json](validation.json)：结构关联、引用、未知/推断记录等校验结果。自动检查不证明统计解释正确。

## 与DARE及本项目的关系

参考[DARE论文](https://arxiv.org/abs/2603.04743)第3.1–3.2节及附录A（PDF第12页）：按函数筛选，结合文档与数据特征组织检索信息。参考[官方项目](https://github.com/AMA-CMFAI/DARE)。本样例是重新阅读R官方文档后的人工辅助标注，**不是DARE/RPKB原始记录，也不是DARE模型输出**。

沿用其六类数据属性和任务类型，但不直接复制扁平枚举：增加逐条依据、条件、推断、未知与冲突记录。尤其允许维度信息为unknown；不把示例中的分布或尺寸当作输入要求，不把稀疏性与概率分布混为一项统计假设。

本阶段只建立函数侧要求画像。后续可以把分析目标、实际数据画像和参数配置与本画像逐项比较，形成适用、冲突、未知的判断。该判断应另存运行轨迹，不回写成函数固有事实。画像没有证明某份数据已满足要求，也不是完整统计有效性证书。

## 五条记录的检查重点

| 函数 | 筛选 | 首要检查点 |
|---|---|---|
| stats::t.test | 保留 | 数值输入；配对模式要求、缺失处理、方差参数分别记录；分布族unknown |
| stats::prcomp | 保留 | 默认与公式接口分开；默认矩阵接口的NA处理unknown；参数拼写歧义未消解 |
| stats::kmeans | 保留 | 数值矩阵接口；NA处理unknown；初始化所需不同数据行数量为有理由的推断 |
| base::scale | 保留 | 数据变换有分析用途；忽略NA计算统计量不等于填补缺失值 |
| utils::read.csv | 排除 | 基础数据读取；保留筛选依据，画像字段标为未评估 |

具体依据均链接在各记录中；以上为审阅导航，不新增适用条件。所有“tabular”均为依据接口形式作出的模态归类，标为inferred、supported，不能用于排除其他经编码的数据来源。

## 字段规则

`data_profile`包含`data_modality`、`feature_type`、`distribution_assumption`、`dimensionality`、`missing_data_handling`、`specific_constraints`。`task_type`与它们使用相同的判断条目结构，避免把一整个维度压成含义不明的单个字符串。

每个判断条目：

| 字段 | 含义 |
|---|---|
| id / attribute | 记录内唯一ID及所判断的属性 |
| value | 文档支持的值；无依据时为字面量`unknown` |
| basis | `documented`文档明确；`inferred`根据文档推断；`unknown`未找到依据；`not_assessed`筛选排除后不标注；`conflict`未解决的冲突或歧义 |
| strength | 区分`required`要求、`supported`支持、`behavior`行为、`warning`警告、`recommendation`建议；不得将所有条目当成硬约束 |
| applies_when | 生效的接口或参数条件；数组内为AND。空数组仅表示本记录没有附加条件，不证明所有实现版本都成立 |
| evidence_ids | 对应`evidence`中的来源、章节、定位和短原文片段 |
| reason | 推断、未知及冲突必须说明理由；文档明确项可以为null |

`inferences`和`unknown_items`是可定位到条目ID的审阅索引。`conflicts`保留双方表述、证据及未解决状态。排除记录的`not_assessed`不会混入“文档未说明”的unknown统计。

`any`仅允许用于文档明确声明在该属性上没有限制的情形，并必须有明确依据和解释。本批没有使用any。`unknown`不意味着不适用，也不意味着没有限制。没有完整统计假设说明时，仍可能保留部分明确的参数行为。

`applies_when`目前是声明性条件，不是可直接执行的R检查器；例如`method=default`/`formula`应由后续调用层识别。没有运行R函数，也没有通过源代码、试运行或常识补充文档要求。

## 来源及冲突处理

逐条阅读包说明，以及函数Description、Usage、Arguments、Value、Examples；同时阅读与要求有关的Details。包级功能概述只提供背景，不自动继承为每个函数的约束。示例只能支持示例层面的使用，不能证明必要性或穷尽支持范围。只在本条函数/方法范围内标注，同页其他函数的要求不自动移入。

来源使用R官方维护的手册页面。`R-patched`是可变URL；记录的是实际获取到的页面版本，不声称是安装环境版本或当前最新版本。原始页面缓存在本机`local/function_profile_sources`，不随交付发布全文；公开记录保留短引文、版本和原始HTML哈希。以后重新下载若哈希不同，应新建版本，不覆盖本批。

发现并保留两项不同性质的问题：

1. `t.test`函数页标为4.5.1，`stats`包概述页标为4.5.0。属于来源版本不一致；保留两者，不假称统一版本。函数要求采用函数页本身的表述，包页没有提供额外适用条件。
2. `prcomp`的正式参数写作`scale.`，Details写作`scale = TRUE`。属于文字/参数归属歧义，不等同于已证实的运行行为矛盾；退化列缩放规则暂不绑定到正式参数，等待审阅，不借助语言常识自行消解。

同一函数不同接口的缺失值策略、或不同参数的条件行为，不算文档冲突。

## 复核与后续衔接

在仓库根目录运行（仅需Python标准库）：

```bash
python scripts/verify_function_profiles.py
```

若本地保留了本批原始HTML缓存，可额外核对页面哈希和短引文存在性：

```bash
python scripts/verify_function_profiles.py --sources-dir local/function_profile_sources
```

JSON Schema由支持Draft 2020-12的校验器逐条验证JSON数组或JSONL中的记录。标准库脚本做跨字段和引用检查，不冒充通用JSON Schema实现。两类检查都不能代替语义审阅。

本批共61条判断，5条推断、11条文档未知项、2项来源/文字问题，另有排除项的6个未评估字段。尚未采集真实数据或运行分析函数。建议先审阅三点：条件和方法划分是否合适、未知是否诚实、推断是否足够克制。用户确认5条口径后再扩批。

后续研究应让普通全信息路由与边界方法读取相同画像和依据，比较是否选错函数、是否误排可用函数、澄清/验证开销；不能再次把多提供条件信息的收益当成负向边界表示的独立贡献。
