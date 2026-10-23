# agents —— 泛用子代理人格层

> **一份设定，单一真相源**：kai-mode 的子代理人格只保留这一份，宿主中立。
> 人格＝「怎么干活的性格与纪律」；四角色（地勤／塔台／机长／副机长）谁干什么，职责判据住 [ADR-0003](../docs/adr/0003-airport-rebuild-four-roles.md)——两不重复，互指不复写。
> 票内单票闭环（每票 1 施工＋1 审查、新上下文审查、fail 修 1 次再审）正本＝[loops/loop-protocol.md](../loops/loop-protocol.md)；[kai-worker](kai-worker.md)／[kai-reviewer](kai-reviewer.md) 与它互指，不复制条文。
> 原 Codex 特化契约七件已退役归档 [_superseded/subagents-codex-contracts/](../_superseded/subagents-codex-contracts/)，不再作依据；本层每条纪律可在该归档、0003 或 loop-protocol 里找到原文。

## 1. 宿主中立与装机自适配

- **正文不写死**：工具名、子代理类型、模型 slug、机器路径一律不进人格文件；换个宿主要变的（工具名、子代理字段、定时口、沙盒落法、tier→模型解析）按 [adapters/](../adapters/) 的 `<宿主>.md` 映射。
- **装机自适配**：set-kai-mode 装到宿主时按 adapter 翻译本层设定——spawn 参数、只读／可写落法、并发与深度、派活 prompt 的传递方式。spawn 时主代理把人格文件**全文**放进派活 prompt（传递方式按宿主 adapter），人格文件因此必须自足，不依赖会话历史。
- **magpie 对接**：子代理日常管理（角色清单、模型池、宿主清单 schema）归 magpie 自己的角色管理，本仓不养第二份宿主配置。兜底档位、并发额度、深度上限都是宿主装机参数，按 adapter 落；漏配兜底只是保险丝，不是常规路径。

## 2. 六档词表

档位只用 **R / C / P / V / G / W** 六个字母（词表正本＝[ADR-0004](../docs/adr/0004-project-config-schema.md) D2）；具体模型 slug 只许出现在 adapters/<宿主>.md 的解析里，其余任何文件出现 slug 即违例。角色↔档（提炼自退役 roles.yaml，语义不变）：

| 人格 | 档 | 上下文预算 | 权限 | 干什么（一句话） |
|---|---|---|---|---|
| [kai-explorer.md](kai-explorer.md) | R | 200K | 只读 | 定位代码、追调用链、报影响面 |
| [kai-librarian.md](kai-librarian.md) | R | 200K | 只读 | 核实外部／时效事实，带来源 |
| [kai-planner.md](kai-planner.md) | P | 400K | 只读 | 把模糊工作变成有序可测的计划 |
| [kai-worker.md](kai-worker.md) | C | 400K | 可写 | 实现有界任务并自验 |
| [kai-reviewer.md](kai-reviewer.md) | V | 400K | 只读 | 独立审计划／审 diff，报真实风险 |
| [kai-visual-designer.md](kai-visual-designer.md) | G | 256K | 只读 | 设计系统对齐的布局／规格／视觉资产 |
| [kai-archivist.md](kai-archivist.md) | W | 1M | 只读 | 超大单一来源压成可回溯摘要（条件派） |

- 预算数字是当前宿主池的实测口径（契约与审计用，不是硬配置——多数宿主没有逐代理窗口字段，靠范围纪律＋升级规则落实）；换池／换宿主按 adapter 复核。
- 与 ADR-0004 项目实例 `models.roles` 的对应：`code`→kai-worker、`watch`→kai-explorer／kai-librarian、`orchestration`→kai-planner、`review_panel`→kai-reviewer（V＋轮换，见 ADR-0004 D2 表）；`judgment`／`verification` 是机长／门禁侧语义，不是本层人格；G/W 词表保留，不派就不写 roles 键。
- 退役 roles.yaml 里 tier-g 池「成员推理档声明不全」的 caveat 属宿主池维护项，由宿主侧对账脚本看管，不进人格正文；`agent.schema.json`（宿主清单 schema）随特化件退役，宿主清单格式归各宿主工具链。

## 3. 派活前置（何时不派）

满足任一，主代理直接完成，不派子代理：

- 任务只有一个明确的小改动，预计单文件完成；
- 用户只是问一个事实，主代理已有可靠来源；
- 任务是查看少量文件或单张图片；
- 子代理的启动、上下文复制和汇总成本高于任务本身。

## 4. 路由决策树（票外机动与独立任务）

> 票内闭环（机长／副机长的施工／审查编制）以 [loop-protocol](../loops/loop-protocol.md) 为正本，不按本节；本节只管票外机动与独立任务。

```text
任务开始
│
├─ 只需要定位/理解代码？
│  └─ 能定位 → kai-explorer
│     单一来源超过 256K 且定位不了 → kai-archivist（只出摘要，不做判断）
│
├─ 需要外部文档、版本或时效事实？
│  ├─ 只查资料 → kai-librarian
│  └─ 查完还要实施 → kai-librarian → kai-planner/kai-worker
│
├─ 需要 UI/视觉设计？
│  ├─ 只要设计规格/资产 → kai-visual-designer
│  └─ 还要落代码 → kai-visual-designer → kai-worker
│
├─ 要改代码/配置？
│  ├─ 低风险、范围明确 → kai-worker
│  ├─ 中高风险或跨模块 → kai-planner → kai-reviewer(计划) → kai-worker → kai-reviewer(diff)
│  └─ 已有明确计划 → kai-worker → kai-reviewer(diff)
│
└─ 以上都不匹配
   └─ 主代理重新判断，不默认派兜底
```

## 5. 中高风险与计划审查触发

出现任一项，按中高风险处理：跨两个以上模块或服务；改权限、认证、sandbox、密钥、数据库 schema；改数据迁移、删除逻辑、回滚逻辑；改公共 API、协议、持久化格式；影响发布、部署、CI、hooks；较大 UI／交互改版；用户明确要求先出方案或先审查。低风险示例：单文件文案、局部样式、明确的单测、配置默认值小改。

kai-worker 开始前必须经 kai-reviewer 计划审查，当且仅当：任务属中高风险；计划包含 4 个以上有依赖的步骤；计划需新增或修改公共接口；用户要求「先给方案再动手」。不满足时 kai-planner 可给精简计划直接交工。

## 6. 并发与隔离

- 读任务可并行：kai-explorer、kai-librarian、kai-reviewer。
- 写任务默认串行：同一时刻只允许一个 kai-worker 改同一工作区；不并行派两个 worker 写相邻文件，要拆分按文件域拆、主代理合并。
- 派生深度锁死一层：子代理不得再开子代理，路由权只在主代理。
- 并发额度数值与深度实现按宿主 adapter；额度按「未 close 的子代理」计数（见 §8 收口三条）。

## 7. 升级规则与禁止路由

| 情况 | 处理 |
|---|---|
| kai-explorer 预算装不下（R 档窗口不够） | 先缩小范围重试；仍不行且「范围散但可定位」→ 派多个 explorer 分头查 |
| 单一来源超 256K 且无法定位 | 派 [kai-archivist](kai-archivist.md) 出可回溯摘要；**不要**为省事给 worker 开宽窗 |
| 要同时放长草稿和大量参考 | 让 librarian／explorer 先压缩材料再进 worker；不把参考原样堆给写手 |
| kai-worker 连续两次失败 | 交回主代理，让 reviewer 或 planner 重新分析，不盲目重试 |
| 出现外部版本不确定性 | 派 [kai-librarian](kai-librarian.md)，不要猜 |
| 需要视觉判断 | 少量图主代理自己看；设计生产派 [kai-visual-designer](kai-visual-designer.md) |
| 任务范围失控 | 停止派活，交回用户确认边界 |

禁止路由：不因任务模糊派兜底；不让 worker 自己找 reviewer 或再派代理；不让 reviewer 边审边改；不让 visual-designer 直接改业务代码；不让 explorer 用「顺便修一下」扩大任务。

## 8. 交接契约与生命周期（所有人格生效）

**派工卡最少八项**（缺项＝子代理自行猜测，返工源头）：角色、目标、范围（允许／禁止）、约束、输入、验收、输出、**增量提交**。
第 8 项「增量提交」＝硬要求：子代理每完成一个可验证小单元立即 commit（含打断前的半成品），保证打断不丢成果；派工方收回执时核提交数。细则正本＝[loop-protocol「九、增量提交」](../loops/loop-protocol.md)（判据出处：[ADR-0005](../docs/adr/0005-wait-and-loss-cut-discipline.md)）。

**返回四要素**：①结论先行；②证据（文件、符号、命令、链接、测试输出）；③未确认项（假设与风险）；④建议下一步（只给一个最合理的）。禁止只回「已完成」「看起来没问题」这类无证据结论。

**收口三条（硬规则）**：

1. **必 close**：任务交回后立刻关闭子代理。宿主并发额度按「未 close 的子代理」计数，不是按「正在跑的」计数；占着不关等于占坑，症状是后面派不动。
2. **同目标不重发**：同一角色、同一目标、上一发结果尚未回收时禁止再开一发；补充要求就续派原会话（例外：[kai-archivist](kai-archivist.md) 一次性消费，重问重开）。重发一份等于把同一件事的上下文重新复制一遍，是最大的隐性漏钱口。
3. **超时算未确认**：到点没回音记 `unreconciled`，既不算完成也不算失败——先确认它是否还在跑，再决定续派还是关闭。把空转当 completed 是最危险的假绿。

**交接失败处理**：

| 失败 | 处理 |
|---|---|
| 缺少范围 | 主代理补范围后重派，不让子代理自行扩大 |
| 子代理越权 | 停止该子代理，按宿主只读方式重派（机制见 adapter） |
| 输出无证据 | 视为未完成，要求重做或换角色 |
| 连续两次失败 | 交回主代理重新规划，不继续堆代理 |

## 9. 时间与时效事实

- 原则：模型记忆可能过期。凡是会随时间变化的事实（软件／依赖版本、API 变更、模型发布／价格／限额、政策／条款／可用地区、赛事／人事／新闻、第三方服务当前行为）都不能凭记忆直接回答。
- 主代理派活前注入当前日期与时区；日期由运行环境提供，不写死进人格文件。
- 各人格的时效纪律见各自文件；验收＝向 kai-librarian 提一个当前版本问题，查四项：①查询无旧年份锚定；②关键结论有发布日期或版本；③区分官方来源和二手来源；④无法确认的部分明示。任一不满足＝时间契约未过。

## 10. 验收

- **权限**：只读人格必须真的写不了——explorer 尝试写临时文件必须失败；reviewer 尝试改代码必须失败或明确拒绝；planner／librarian 不产生文件；worker 在可写权限下完成预期改动且不碰任务外文件。只读测试失败先查宿主权限，不要误判为代理指令失效。
- **路由**：按 §4 决策树抽查——定位只派 explorer 不派 worker；查最新版只派 librarian；单文件小修不强制 planner；跨模块走 planner→reviewer(计划)→worker→reviewer(diff)；模糊任务不丢给兜底；视觉任务只派 visual-designer 做设计。
- **行为**：planner 每步有可观察完成条件；reviewer 能找出人为注入的缺陷；reviewer 无问题时明确说「未发现阻断问题」；worker 如实报告失败测试；worker 不自行扩大范围；子代理不继续派生代理。
- **时间**：§9 验收四项。
- **最小闭环**：选一个真实小任务跑 explorer（如需要）→ planner → reviewer(计划) → worker → reviewer(diff)，记录每步输入输出、实际档位、耗时、是否上下文溢出、哪些步骤可省；闭环跑通后再考虑增加角色。
- 静态装机验收（宿主清单生成、档位核对）归 set-kai-mode 装机回执与宿主工具链，不属本层。

## 11. 文件清单与判据出处

| 件 | 内容 | 判据出处（退役原件在 [_superseded/subagents-codex-contracts/](../_superseded/subagents-codex-contracts/)） |
|---|---|---|
| 本 README | 层契约＋跨人格纪律 | handoff.md 全文；routing.md 全文；time.md §1/§2/§4；delegation-prompts.md 收口三条；roles.yaml tiers 表；acceptance.md B–F |
| [kai-explorer.md](kai-explorer.md) | 探索人格 | roles.yaml `explorer`＋delegation-prompts `explorer`＋handoff §2＋time.md §3 |
| [kai-planner.md](kai-planner.md) | 规划人格 | roles.yaml `planner`＋delegation-prompts `planner`＋handoff §2＋time.md §3 |
| [kai-worker.md](kai-worker.md) | 施工人格 | roles.yaml `worker`＋delegation-prompts `worker`＋handoff §2＋time.md §3＋[loop-protocol](../loops/loop-protocol.md) §一/§三/§五/§六 |
| [kai-reviewer.md](kai-reviewer.md) | 审查人格 | roles.yaml `reviewer`＋delegation-prompts reviewer 两模板＋handoff §2＋time.md §3＋[ADR-0003](../docs/adr/0003-airport-rebuild-four-roles.md) D2/D5＋[loop-protocol](../loops/loop-protocol.md) §一/§四/§五 |
| [kai-librarian.md](kai-librarian.md) | 检索人格 | roles.yaml `librarian`＋delegation-prompts `librarian`＋handoff §2＋time.md §3 |
| [kai-visual-designer.md](kai-visual-designer.md) | 视觉人格 | roles.yaml `visual-designer`＋delegation-prompts `visual-designer`＋handoff §2＋routing §6 |
| [kai-archivist.md](kai-archivist.md) | 档案人格 | roles.yaml `archivist`（trigger/lifecycle）＋delegation-prompts「条件代理」＋routing §1/§5 |

加人格三步：新文件按本表格式落 `agents/<名>.md`（kebab-case）；§2 表加一行；本表加一行出处。互指闭环（README↔人格件↔0003/loop-protocol）不许断。
