# V1.0 设计基线吸收记录

> 来源：用户 2026-10-21 提供的《Kai-vass Autonomous Work Loop V1.0》。
> 结论：**吸收设计意图，不照抄实现形态。** 与本框架已有契约冲突的地方，按下表裁决；裁决理由写在同一行，避免下一个人再猜。
> 本文件是设计层唯一对照表。具体执行以 `skills/kai-mode/playbooks/` 与项目 ADR 为准。

## 一、总裁决

| V1.0 主张 | 本框架裁决 | 落在哪 |
|---|---|---|
| GitHub Issues/PR 是任务与协作中心 | **Issues 采纳为票面唯一事实源**；PR 不强制。默认 `ship_mode=direct`（门禁后直推 dev），需要人工审查的项目可切 `pr` 或 `hybrid` | `skills/kai-mode/playbooks/task-contract.md`、`skills/kai-mode/playbooks/approval.md`、项目配置 `ship_mode` |
| 调度器是流程控制者，不依赖 AI 记忆 | 采纳。任务账住 GitHub＋`plan.json`，运行态住本机状态文件，主会话不存任务账 | `playbooks/state-machine.md`、`skills/kai-mode/playbooks/audit.md` |
| Codex 是首选执行器 | **采纳“执行器可替换”，不采纳“Codex 唯一”**。项目配置 `execution.preferred`，按宿主探测结果选；本仓当前 Qoder 为主、Codex/opencode 为备 | `adapters/`、`templates/kai-mode.project.json` |
| 每任务独立会话、独立工作区 | 采纳。每张票一个 fresh context，工作树隔离，租约限定文件域 | `playbooks/shifts/group.md`、`skills/kai-mode/playbooks/context.md` |
| 自动修复有限次 | 采纳。默认最多 3 轮；同一错误签名出现 2 次提前停 | `skills/kai-mode/playbooks/reliability.md` |
| 所有任务必须有终止条件 | 采纳。状态机、超时、尝试上限、预算、停机牌共同构成终止条件 | `playbooks/state-machine.md`、`skills/kai-mode/playbooks/reliability.md` |
| 高风险操作走系统权限门禁，不靠提示词 | 采纳。风险分级矩阵＋不可自批规则 | `skills/kai-mode/playbooks/approval.md` |
| 本地 SQLite 保存运行状态、锁、尝试次数、检查点、事件 | **契约采纳，引擎暂缓。** 单机低维护场景用原子 JSON＋`events.jsonl` 已能覆盖；触发迁移条件见 §四 | `playbooks/state-machine.md`、`skills/kai-mode/playbooks/audit.md` |
| 执行角色只保留 Researcher／Implementer／Reviewer | 采纳为**组内执行角色**，不新增编排角色。编排层仍是 Tower／Ground／Coordinator／Group-A/B | `skills/kai-mode/playbooks/execution-roles.md` |
| `PR Ready` / `Merged` | 映射为 `ship_ready` / `landed`。启用 `pr` 模式时 `ship_ready` 的落地动作就是开 PR | `playbooks/state-machine.md` |
| 初始只允许 1 个编码任务并发 | **试点期采纳**：`pilot_global_wip=1`；24h 指标通过后按项目配置调到 2（组内）/4（全局） | `skills/kai-mode/playbooks/reliability.md`、项目配置 `limits` |
| 上下文 65% 准备交接、80% 停止堆积 | 采纳为检查点阈值。handoff 仍 ≤500 B；检查点是独立文件，只给接任者读 | `skills/kai-mode/playbooks/context.md` |
| 通知只针对有决策价值的事件 | 采纳。与既有“日报四类”合并：完成、待审批、连续失败、长期阻塞、预算阈值、安全拦截 | `skills/kai-mode/playbooks/audit.md` |
| 不引入另一个大型 Agent Harness | 采纳。不新建执行框架，只补契约与状态 | 本文件 §六 |

## 二、角色映射

| V1.0 角色 | 本框架落点 | 说明 |
|---|---|---|
| 用户 | 用户 | 目标、优先级、审批红线；不读运行日志 |
| 调度器 | Coordinator ＋ Tower 的确定性脚本 | Coordinator 只按异常；Tower 做排班与任务治理 |
| Researcher | Group 内的 `researcher` 子代理 | 只出调查结论与文件指针，不写实现 |
| Implementer | Group 内的 `implementer` 机长 | 新上下文、租约内施工、本地提交 |
| Reviewer | Group 内的 `reviewer` 子代理 | 独立上下文、逐条 AC、不得由作者自判 |
| Codex 执行适配器 | `adapters/codex.md` | 备选执行体；付费档需显式开关 |
| 发布/合并 | Ground | 并车、门、push、关票；PR 模式下开 PR |
| 任务治理 | Tower | 合同完整性、依赖、拆分、后续票；不做无限生成 |

## 三、新增与已有

**已有、只需引用（不重复造）：**

- 租约与文件域互斥：`scope-check declare/check/clear`
- 跑道牌与全局出货牌：`on-duty-check`
- handoff ≤500 B、验收摘要、状态卡四格
- AI 全判验收（新上下文 reviewer，不抽样）
- 停机牌、按铃适配器、代际上限 1
- 并车门、push-preflight、close-gate、两路回读

**本次新增（V1.0 补齐）：**

1. 三循环：治理 / 执行 / 反馈维护
2. 票状态机与转移守卫
3. 任务合同（10 字段）与 Definition of Ready / Done
4. 组内执行三职与派工卡契约
5. 可靠性：租约过期、重试上限、同错早停、去重、崩溃恢复、熔断、预算
6. 审批矩阵与“不得自批”
7. 检查点与上下文阈值
8. 审计事件与通知策略
9. 六阶段迁移验收

## 四、有意偏离（连同理由）

### 4.1 SQLite 暂缓，不取消契约

V1.0 要的是**崩溃可恢复、锁可过期、尝试可计数、事件可追溯**，不是某个具体数据库。当前单机、单仓、事件量小，JSON 原子写＋追加日志已经满足，且不引入新依赖、不需要迁移工具。**迁移触发条件（任一命中就重开这张账）：**

- 事件量 > 5,000 条/日，或状态文件 > 200 张票同时活跃；
- 出现需要跨进程事务的场景（多个调度器实例、远程执行体共享状态）；
- 现有 JSON 原子写在真实崩溃演练中丢过一次状态。

在此之前，禁止同时维护 JSON 与 SQLite 两套真相。若迁移，SQLite 只做**运行态**，票面仍以 GitHub 为准。

### 4.2 PR 不强制，按项目选 `ship_mode`

V1.0 假定有 CI 与 PR 审查。本仓当前 CI 只剩手动触发，真正的强门在 pre-push；强制 PR 会把“门”换成“等人点按钮”，反而降低真度。因此：

- `direct`（默认）：并车→收尾门→push→close-gate；低/中风险自动，高风险仍须人。
- `pr`：验证通过→推分支→开 PR→等人/自动合并；适合有 CI 与外部审查的项目。
- `hybrid`：低/中风险 direct，高风险 pr。

三种模式的**验收证据与状态机相同**，只换落地动作。

### 4.3 执行器不锁定 Codex

“首选执行器”是项目配置，不是框架常量。宿主中立是本框架的验收判据：换一家 agent 仍能按同一剧本飞。Qoder 当前推荐“只按铃子会话”，Codex/opencode 是备胎，未来可加新适配器。

### 4.4 GitHub 标签只做粗状态，细状态住本机

V1.0 的 11 个状态不全部映射成标签，否则每张票都要频繁改标签，且标签本身无法防“AI 自称状态”。做法：

- 本机 `task-state-<票>.json` 是细状态正本，转移由脚本校验；
- GitHub 只保留少量耐久标签：`ready-for-agent`、`blocked`、`awaiting-acceptance`，以及关闭状态；
- 冲突时以 GitHub 票面内容 + 本机事件日志 + git 事实三方对账，不以标签自称。

### 4.5 试点并发 1，不等于永远 1

V1.0 的“初始 1 个”是稳定性选择，不是产品目标。试点 24h 通过后按实测调到组内 2、全局 4；再高必须先解掉“同一工作区/同一端口”类共享状态。

## 五、六阶段落地

| 阶段 | 交付 | 验收 | 状态 |
|---|---|---|---|
| 1 任务治理 | Issue 模板、风险分级、DoR/DoD、PR 模板 | 一个执行器只看票面就能开工，不需回看聊天 | 本次落地 |
| 2 单任务自动执行 | 状态机、执行器适配、隔离工作区、门禁、出货 | 从 Ready 票到本地提交全自动 | 已有大半，补状态机 |
| 3 可靠性与恢复 | 检查点、租约过期、重试、去重、崩溃恢复 | 强杀进程后恢复且不重复领票/不重复创建 PR | 待实现 |
| 4 反馈闭环 | CI/PR 意见处理、有限修复、阻塞通知 | 失败触发新尝试，到上限正确停止并留证 | 待实现 |
| 5 任务链 | 依赖图、后续票生成、周期巡检、优先级 | 前置完成能解锁后续；不可执行任务不堵队列 | 部分已有（`plan.json`） |
| 6 受控自主 | 分级审批、受保护合并、预算、审计报告 | 低风险自动推进；高风险无法绕过审批 | 待实现 |

阶段 2/3 的实现票在 #1829 落地、框架迁移 P2 之后开；在此之前只落契约，不改直播面。

> **2026-10-21 独立 reviewer 修正**：运行态文件改用 `task-state-<票>.json`（与 scope-check 的 `current-task-<票>.json` 分开）；PR 模板改为合并后回填；文件域租约 TTL 标为未实现（45 分钟只适用跑道牌/出货牌）；P2 座位映射、`acceptance` 的 `implementer` 必填与 reviewer 独立性、任务 schema 的 `null`/`approval_required`/`deadline` 已补齐。判据出处：项目仓 ADR-0136「评审修正」（历史出处，判据待迁）。

## 六、闭环完成的十条（本框架口径）

V1.0 §十二的十条完成定义，逐条落到本框架的判据：

| # | V1.0 完成定义 | 本框架判据 | 现状 |
|---|---|---|---|
| 1 | 用户能规划并开票 | `/kai-mode`＋任务合同 Issue 模板；票面十字段 | 本次落地 |
| 2 | 调度器独立发现并领取任务 | Tower 读 `plan.json`/队列；Coordinator 异常兜底；租约领取 | 已有，补状态机 |
| 3 | 执行器隔离工作区完成任务 | Group 一票一会话/一树；租约限文件域 | 已有 |
| 4 | 真实验收决定下一阶段 | reviewer 逐条 AC＋`acceptance` schema；状态机不许跳步 | 已有，补状态 |
| 5 | 失败有限重试且能中断恢复 | ≤3 轮、同错 2 次停、检查点、崩溃恢复 | 待实现（阶段 3） |
| 6 | PR/审批/合并受实际规则约束 | `approval.md` 风险矩阵；`ship_mode`；门禁与 close-gate | 已有，补审批记录 |
| 7 | 结果触发下一任务或正确终止 | Loop A 补票/拆分；状态机 `closed`/`failed`/`blocked` | 本次落契约 |
| 8 | 关键状态可追溯 | `events.jsonl`＋追溯链；关票回读 | 本次落契约 |
| 9 | 不依赖长期对话维持上下文 | `context.md`＋`task-state-<票>.json`＋检查点 | 本次落契约 |
| 10 | 无任务时安全等待，新任务继续 | Coordinator `idle`；队列/信箱触发；不空转 | 已有 |

**判据原则：** 十条里每一条都必须有“文件/命令/事件”三选一的证据形态；只有叙述、没有证据的条目不算完成。

## 七、明确不做

- 不引入另一个大型 Agent Harness 取代现有执行体。
- 不让主控会话长期承载所有任务历史。
- 不允许无限重试。
- 不允许模型自行决定测试是否算通过。
- 不把聊天记忆当唯一任务状态。
- 不默认多个编码代理并发修改同一工作区。
- 不在基础闭环稳定前开启生产自动发布。

## 八、与既有 ADR 的关系

（以下均为项目仓历史出处注记，判据待迁；本仓不引项目仓裁决为现行事实——见 [0001](adr/0001-repo-independence.md)。）

- 角色拆分、按铃适配器、AI 全判：项目仓 ADR-0135（历史出处，判据待迁；已 accepted）。
- 租约与出货单点：项目仓 ADR-0133（历史出处，判据待迁；D2 的“出货单点归塔台”已被 ADR-0135 改归 Ground）。
- 机场体系与剧本层：项目仓 ADR-0132（历史出处，判据待迁）；机场体系现行正本＝本仓 [0003](adr/0003-airport-rebuild-four-roles.md)。
- 本文件的裁决 originally 在项目仓以 ADR-0136 登记（判据出处：项目仓 ADR-0136，历史）；本仓接管后判据以本文件为准，项目仓那份不再约束本仓（见 [0001](adr/0001-repo-independence.md)）。
