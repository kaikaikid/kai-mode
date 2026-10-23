# 子代理模块优化调整方案

**日期：** 2026-10-23 · Asia/Shanghai
**对象：** 本模块（`subagents/codex/`，源出 magpie `codex-agents/final/` v3.2）+ kai-mode 机场体系
**依据文本：** ① `子代理设计对比与优化-2026-10-23.md`（magpie 侧，角色集与档位契约）②《Kai-vass 子代理系统改造指南》v1.0（你 10-23 提供，派发策略与评测方法）
**取证方式：** 本文所有数字由 `python scripts/measure-subagents.py` 现读 `~/.codex/state_5.sqlite`（只读）得出，不引用文档口径。

## 0. 结论先行

1. **两份上游文本在"角色集动不动"上是对立的，真机数据站在指南这边。** magpie 文本 §4 明确写"角色集不要动"；指南 §11 阶段 5 要求"对长期无调用的代理先停用观察"。**实测：7 个角色里只有 2 个被派过**（reviewer 5 次、worker 3 次），explorer / librarian / planner / visual-designer / archivist 在 v3.1 落地后**一次都没跑过**，全历史也从未出现。
2. **六档体系目前是 2/6 在用。** `tier-c` 8 次、`tier-v` 1 次；`tier-r`、`tier-p`、`tier-g`、`tier-w` **全历史 0 次调用**。所以 magpie 文本"待办"里那两个裁池口子（tier-r 5/11、tier-g 3/10 成员不支持声明的推理档）是**在优化一条没有车的道路**，优先级应降后。
3. **③"逐角色 model 覆盖"事实上没生效。** `roles.yaml` 声明 reviewer → `tier-v`，但 v3.1 落地后的 5 次 reviewer 里 **4 次跑在 `group/tier-c`**（全局默认），只有第一次（10-23 02:06）命中 `tier-v`。模板加了 `模型：` 行，主代理随后就不填了——这是提示词自律的必然衰减，不是偶发。
4. **①"收口三条"事实上没生效。** 写进 `routing.md` / `handoff.md` / `delegation-prompts.md` 的"必 close"之后，未关闭率从 **54% → 50%**（v3.1 前 16/29 open，之后 4/8 open）。`max_concurrent_threads_per_session = 3`，20 条 open 边意味着并发额度长期被名义占用。
5. **唯一真正生效的一条是角色打标。** v3.1 前 37 条里 28 条 `agent_role` 为空（76%），之后 8 条 **0 空**。说明"把字段写成模板必填项"有效，"把义务写成散文条款"无效——这条规律应当决定后续所有契约的写法。
6. **本模块与 kai-mode 之间有一处结构性撞车**：kai-mode 已有角色体系（机长 / 副机长 / 地勤 / 塔台，[0003](../../docs/adr/0003-airport-rebuild-four-roles.md) 四角色 + 30 分钟轮巡），本模块另有一套七角色 + 六档。**同一件事现在有两个正本**。不先定归属，模块就是第二套真相，正好犯 magpie 文本 §P2-6 自己诊断的病。
7. **子代理上限是本仓尚未裁决的第一个议题，不是外部冲突。** 本模块带进 `max_depth = 1` 与 `max_concurrent_threads_per_session = 3` 两道硬上限，而项目仓的 `ADR-0141-subagent-cap-removal.md`（"去掉子代理编制上限"；历史出处，判据待迁）**不约束本仓**——`docs/adr/0001-repo-independence.md` 已定：本仓裁决只记在 `docs/adr/`，不续接项目仓 `ADR-01xx`。所以正确读法不是"模块违反了某条 ADR"，而是"这两行是别人机器上的既成配置，本仓还没就上限做过自己的决定"。附带一个真风险：`max_depth = 1` 禁止子代理再派子代理，若塔台轮巡或机长→施工/审查依赖嵌套派发（`skills/塔台/SKILL.md:63`、`skills/地勤/SKILL.md:117`），它改变的是本仓闭环的形状。**未决前不要把这两行同步进任何宿主。**

## 1. 实测证据

`python scripts/measure-subagents.py --since 2026-10-23T01:38`（v3.1 落地时刻）

| 指标 | v3.1 前 | v3.1 后 | 门槛 | 判定 |
|---|---|---|---|---|
| 派发数 | 29 | 8 | — | 样本仍偏小 |
| 未关闭率 open/total | 55%（16/29） | 50%（4/8） | ≤10% | **红** |
| `agent_role` 空标率 | 76%（28/37 累计） | **0%** | 0% | **绿**（唯一达标） |
| 角色命中数 | worker ×1，其余空 | reviewer ×5、worker ×3 | 每角色可归因 | 5 个角色无数据 |
| reviewer 实际档位 | — | tier-c ×4 / tier-v ×1 | 声明档 = 实际档 | **红**（默认吞掉覆盖） |

复现口径：`state_5.sqlite` 的 `thread_spawn_edges ⋈ threads`，字段 `status / agent_role / model / reasoning_effort / created_at`（epoch 秒，本仓按 UTC+8 解读）。

## 2. 角色与档位的重新定位

指南 §3.2 的"通常不值得派发"清单，加上上面的实测数据，得到本模块的默认策略调整。定位从"每个角色都是一条常设岗位"改为"每个角色都是一个**可选能力**"。

| 模块角色 | 声明档 | 实测调用 | 调整后默认 | 理由 |
|---|---|---|---|---|
| `worker`（受限实现） | tier-c | 3 | **按需保留** | 唯一有真实使用证据的执行角色 |
| `reviewer`（独立审查） | tier-v | 5 | **按需保留**，并强制 `tier-v` | 独立性成立（不是实现者自审） |
| `planner` | tier-p | 0 | **折叠进主代理** | 指南 §3.3：连续推理与跨步骤决策归主循环 |
| `explorer` / `librarian` | tier-r | 0 | **保留能力，改为显式申请才派** | 只有"大量读档 + 主上下文装不下"才成立 |
| `visual-designer` | tier-g | 0 | **休眠**，接 kai-mode 设计侧时再启 | 与 `soft-design-system` 技能重叠 |
| `archivist` | tier-w | 0 | **降级为 Skill/Tool**（写检查点） | 指南 §8.2：状态属"写入 Issue / handoff"，不需专岗 |

档位侧：`tier-r` / `tier-p` / `tier-g` / `tier-w` 四档在角色折叠后**没有消费者**。建议显式标记为 `reserved`（保留定义、不承诺成本、不进入 check-tiers 的告警面），而不是继续修池。

与 kai-mode 角色的对应（这套映射定了，两个正本才能合一）：机长 = 主代理（对端到端负责，禁止只做转发器，指南 §4）；副机长 = `reviewer`；地勤 = `worker`；塔台 = **外部任务循环**，不是子代理（指南 §2 表格与 §12 都把排程/重试/超时/恢复划给循环，而非某个 Agent 的聊天上下文）。

## 3. 调整方案

### P0 · 把散文义务变成必填字段或机器闸（本周）

**只做一件事：凡是要求"必须"的条款，改成本地可校验的字段。** 依据是 §1 的规律——必填字段达标（0 空标），散文条款不达标（54%→50%）。

- **落点：** `contracts/delegation-prompts.md` 每个模板首行的 `模型：` 改为**逐角色硬编码具体 slug**（reviewer 行写死 `group/tier-v`），去掉"由主代理填写"的空间；`contracts/routing.md` 收口三条后追加一行"本条由 `scripts/measure-subagents.py` 度量，open_rate > 10% 视为契约失效"。
- **验收线：** 连续 10 次派发后跑 `measure-subagents.py --since <本次开工时刻>`，`model_per_role` 里 reviewer 只能出现 `tier-v`，open_rate ≤ 10%。达不到就承认"提示词路线无效"，转 P1 的外部闸，不要再加第三条散文。

### P0-bis · 上限由本仓自己裁决，落成 ADR-0002（在 P0 之前）

上限问题不该由提示词层裁决，也不该沿用别仓结论。本仓需要一条自己的 ADR，三条候选：

- **(a) 不设上限，只设度量**：删掉 `max_depth` / `max_concurrent` 的承诺，把"并发是否成问题"交给 §1 的度量——若 `measure-subagents.py` 的 open_rate 长期高且派发确实排队，再以"实测证据 + ADR-0002"的形式恢复上限。与 `skills/set-kai-mode/SKILL.md:213`"不得写死个数"的既有口径同向，但那是引用，不是依据。
- **(b) 设上限并说明理由**：若 P1 证明僵尸边真在吃额度，则正式写"编制可无限，生命周期必须收口"，上限以闸门形式存在而非配置文件。
- **(c) 分层**：`max_depth = 1` 单独裁决（禁嵌套与"编制数量"是两件事，ADR-0001 之后没有外部条款替我们合并它们），`max_concurrent` 交给 P1 的软闸。

裁决写成 `docs/adr/0002-*.md`。在此之前，`config.template.toml` 顶部已注明这两行属"来源机器的既成值、本仓未裁决"，别有人照模板配宿主。

### P1 · 外部生命周期闸（两周内）

`max_depth = 1` 已经把嵌套堵死，但没人堵"未 close"。指南 §2 把这类职责划给外部循环，所以：

- 新增 `scripts/gate-before-spawn.py`：派发前读 `state_5.sqlite`，open 边 ≥ `max_concurrent` 即拒绝并列出待 close 的 `child_thread_id`，把"额度被僵尸吃掉"从隐性变为显性阻塞。
- 先验证前提：**open 边是否真的占用并发额度**。若不占用（并发照样起得来），P0/P1 的成本账要重算，此条降级为卫生问题。
- **验收线：** 制造 open ≥ 3 的状态，闸必须拒绝并给出可执行处置。

### P2 · 建评测集，然后再谈任何角色重构（两周起）

两份上游文本共同缺的那一步——magpie 文本 §P1-4"acceptance.md 一条没跑"，指南 §10 要 8–10 个固定任务。落到 kai-mode 的具体化：

| 编号 | 任务（用本仓真实物件） | 判定指标 |
|---|---|---|
| E1 | 改 `schemas/` 里一个字段描述 | 主代理是否**没有**派发（期望 0 次） |
| E3 | 追 `scripts/doctor.py` 的调用链 | 派 explorer 是否真省下主上下文，报告是否带路径行号 |
| E5 | 定"塔台轮巡该不该用 spawn 嵌套" | reviewer/Oracle 是否改变结论，还是只是背书 |
| E7 | 让 `registry.json` 测试转红再修 | 是否发生代理间反复交接 |
| E9 | 杀掉会话后凭 `loops/loop-protocol.md` 检查点续跑 | 能否不读全史恢复 |
| E10 | 给一个必然超时的派活 | 是否被记 `unreconciled` 而非 `completed` |

每次记录 `measure-subagents.py --json` 的输出 + 成功率 + 返工数。**一次只改一个因素**（指南 §10.3）。

### P3 · 归属与漂移（P0 同期决定）

- 正本二选一：**magpie 为写本、kai-mode 为读本**（每次改完同步过来，`check-tiers.py` + `measure-subagents.py` 在本仓跑），或**kai-mode 为正本**（magpie 侧改为消费方）。不允许双向手改。
- 定一条红线：**只有跨项目通用的角色契约进本仓**（README 已声明本仓不受任何项目仓票据约束）。magpie 的模型池、tier slug、成本口径属主机专属，需要抽象成"档位于本机 = X"的映射层，否则本仓会随 magpie 配置漂移。
- 两份上游文本目前都不在任何版本控制里（散在 `D:\kaikaikid\tools\magpie\`）。建议把本方案与两份文本一并纳入 `subagents/codex/`，否则三个月后又是一轮碎片化考古。

## 4. 明确不做

- 不做 council / observer（指南 §4 默认不参与、magpie 文本 §3 第三档"别急"）。7 个角色里 5 个零调用时扩角色是自欺。
- 不修 `tier-r` / `tier-g` 池成员（§0.2）。
- 不重排角色提示词、不换模型（指南 §0"不建议做的事"2、§11 阶段 1"暂时不要"）。
- 不为"看起来像团队"补链路（指南 §3.2 末条）。
- 不新增编排框架或新依赖（指南 §13 末注）。
- 不把可靠性职责（重试、超时、预算、锁）继续写进角色提示词；它属外部循环。

## 5. 需要你拍板

1. **`planner` / `archivist` 折叠、`visual-designer` 休眠**——这是与 magpie 文本"不要动角色集"直接冲突的一票，我按数据建议动。
2. **`tier-r/p/g/w` 四档是标 `reserved` 还是留作池待用**。
3. **正本归属**：magpie 写 / kai-mode 读，还是反过来。
4. **上限怎么定**：P0-bis 的 (a) / (b) / (c) 选一，我写成 `docs/adr/0002-*.md`。ADR-0001 之后这已是本仓自己的问题，项目仓结论只能当参考。
5. **既有"以项目仓 ADR 为准"的条款清到哪一步**：ADR-0001 宣布项目仓 ADR 不约束本仓，但仓里仍有多处正面让权——`MIGRATION.md:39`「ADR 正本在项目仓；本仓只引用」、`MIGRATION.md:56`「机场体系裁决仍以项目仓 ADR 为准」、`loops/loop-protocol.md:5`、若干 `skills/*/SKILL.md` 的 `resource: 项目仓 docs/artifacts/adrs/...`。这些是**本仓技能的正本**，改了会经 `registry.json` 下发到 8 个宿主，属于我没有动你的部分。要么现在逐处改写，要么先只改 `MIGRATION.md` 那两条总纲、技能内的引用等各自轮到用时再收。
