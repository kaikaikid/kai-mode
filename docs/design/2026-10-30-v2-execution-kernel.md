# V2 执行内核设计（单主会话 + 物理子会话）

2026-10-30

来源：与项目负责人的对话 ｜ 接收：主会话
关联票：无票
状态：设计草案，**尚未实现、未改任何现有模块**。

## 一句话现状

V2 是一条独立于机场体系的新执行体系：一个 issue 一个 run，主会话规划与验收，
物理子会话执行；默认并发 2 个 run；一次触发连续跑到门点才停；宿主可换。

## 一、目标与非目标

**目标**

1. **提效**：一次触发连续跑，人只在门点介入。
2. **降 token**：子会话自包含、报告限长、日志落盘不进上下文。
3. **保稳定**：状态落盘可续跑，写操作走门禁，冲突靠隔离而非运气。
4. **跨宿主**：不绑 Claude Code 的 subagent / 插件 / 定时器。

**非目标**

- 不替代机场体系（V1 保留，两套并存）。
- 不做多人协作调度（那是 V1 的事）。
- 不实现日表与定时唤醒；看板只做只读进度视图，不做调度。

## 二、三层架构

```
┌─ 策略层（可换）──────────────────────────────┐
│ tiering 档位 · 审查强度 · 交互阈值 · 角色皮肤   │
│ 预设：minimal / savvy / airport               │
└─────────────────────────────────────────────┘
┌─ 执行内核（V2 核心）─────────────────────────┐
│ run 状态机 · 任务图 · 子会话池 · 验收门 · 预算  │
└─────────────────────────────────────────────┘
┌─ 宿主适配层 ────────────────────────────────┐
│ claude-cli · codex-cli · qoder-cli ·         │
│ opencode-cli · generic（stdin/stdout）        │
└─────────────────────────────────────────────┘
```

依赖方向单向：策略层 → 内核 → 适配层。内核不认识具体宿主，适配层不认识任务语义。

## 三、run 生命周期

一个 issue = 一个 run。run 是状态机的最小可续跑单元。

```
created
  → queued          等槽位（并发满时停在这里，不占资源、不烧 token）
  → planning        主会话读 issue、拆任务图
  → design?         有可见 UI 才进，产出设计规格
  → delegating      派子会话执行
  → reviewing       逐任务验收
  → closing         汇总、发货
  → done

任一步 → blocked    需要人决策
任一步 → failed     不可恢复
任一步 → cancelled  人主动取消
queued ⇄ paused     被 urgent 抢占或让位
```

**paused 的恢复兜底**：加急完成、失败、取消、超时任一发生，脚本扫描
`paused` 的 run，按进入 paused 的时间最早优先恢复。**不依赖加急 run 主动通知**——
加急崩了也不会把别人永久挂起。

**门点（人只在这里停）**

| 门 | 触发条件 | 默认 | 可配 |
|---|---|---|---|
| G0 计划 | 任务图成型 | 开 | 可关（小任务跳过） |
| G1 设计 | 任务触碰可见 UI | 开 | 不可关（红线） |
| G2 发货 | commit / push / merge / 删除 | 开 | 不可关（红线） |

门以外的阶段全自动。这是「降低交互次数」的落点：一次触发，最多停 3 次。

**门的状态与回流**

| 门状态 | 含义 | 回流 |
|---|---|---|
| `pending` | 未处理 | 停在这里等人 |
| `approved` | 通过 | 进下一阶段 |
| `skipped` | 按规则跳过 | 进下一阶段 |
| `rejected` | 人否决 | G0 → `planning`；G1 → `design`；G2 → `reviewing` |

**门的顺序**：G0 → G1 → G2 严格串行，前一个没过不触发下一个。
所以「一次触发最多停 3 次」不会变成「同时弹 3 个窗」。

**门等待提醒**：门 `pending` 超过阈值（默认 30 分钟）发一次提醒，
只提醒不自动推进。人不在，run 就停着，不烧 token。

**blocked 的出口**（闭环必须有出口，否则卡死）

| 出口 | 谁做 | 结果 |
|---|---|---|
| 补信息后继续 | 人给一句话 | 回到 blocked 前的阶段 |
| 重规划 | 主会话 | 回 `planning`，任务图重算 |
| 降级执行 | 主会话 | 换更低 tier 或改 brief 重试 |
| 解决 merge 冲突 | 主会话 | 在 worktree 内解冲突后重试 G2 |
| 取消 | 人 | 进 `cancelled`，保留 state 供复盘 |

`blocked` 不是终点，只是等人。人不在时 run 停在原地，不消耗 token。

## 四、任务图与调度

**节点**（task）

```json
{
  "id": "t1",
  "title": "短名，同时用作子会话 description",
  "brief": "自包含任务书：做什么、在哪、约束、完成定义、怎么验证",
  "tier": "light|medium|careful|heavy|fable",
  "deps": ["t0"],
  "touchset": ["src/auth/**", "tests/auth/**"],
  "ac": ["测试通过", "无新增 lint 错误"],
  "status": "pending|ready|running|review|accepted|returned|failed|blocked|abandoned",
  "attempts": 0,
  "session_id": null
}
```

**调度规则**

一个任务变 `ready` 需同时满足：

1. 所有 `deps` 都是 `accepted`（或 `abandoned`，视为不再阻塞）；
2. `touchset` 与在飞 run / 在飞任务的声明无重叠（重叠则排队）；
3. 运行时资源（端口 / DB / 服务）可用；
4. 全局子会话槽与 run 并发槽都有空位。

**检查与占位必须原子**

`coding spawn` 在一个文件锁内完成四步：touchset 复核 → 槽位预留 → 写 state → 起进程。
两个 run 同时 spawn 时，第二个会看到第一个的预留，排队而不是同时通过。
锁是 `.coding/lock`（OS 文件锁），进程崩溃时由内核自动释放，不留死锁。

没有这一步，两个 run 会同时通过「无冲突」检查，然后一起改同一个文件。

**run 间依赖**

`state.json` 加 `depends_on_runs: ["r-xxx"]`。被依赖的 run 未到 `done` 时，
本 run 停在 `queued`，**不占槽位**，也不算空槽。这补上了「相关任务排队」的落点。

**phase 推进条件**（脚本判定，不看 AI 心情）

| phase | 进入条件 | 离开条件 |
|---|---|---|
| `queued` | run 创建且无槽 | 拿到槽位 |
| `planning` | 拿到槽位 | 任务图成型 + G0 `approved`/`skipped` |
| `design` | 任务触碰可见 UI | 设计规格产出 + G1 `approved` |
| `delegating` | 至少一个 `ready` 任务 | 无 `pending`/`ready`/`running` |
| `reviewing` | 所有任务到终态 | 全部 `accepted`（或 `abandoned`） |
| `closing` | 全部 `accepted` | G2 `approved` + merge 完成 |
| `done` | merge 完成 | — |

**并发上限（默认）**

- 普通 run 槽：3
- 加急 run 预留槽：2
- 每 run 子会话并发：2
- 全局子会话并发：10（5 个 run 槽 × 2，加急槽也计入）

上限是配置项，超限的任务排队而不是失败。

**优先级与抢占**

run 与 task 都带 `priority: normal | urgent`，默认 `normal`。

**加急有专用预留槽**，不跟普通任务抢：

| 槽位 | 数量 | 给谁 |
|---|---|---|
| 普通槽 | 2 | `normal` run |
| 加急预留槽 | 1 | `urgent` run 专用，普通任务不能占 |

| 情况 | 处理 |
|---|---|
| 普通槽有空 | 直接开跑 |
| 普通槽满、加急到来 | **走预留槽，不抢占**，普通 run 不受影响 |
| 预留槽也满（同时两个加急） | 第二个排队；或抢占一个 `paused` 的普通 run 的树位 |
| 同优先级抢槽 | 排队，先到先得 |
| 加急与在飞任务 touchset 重叠 | **不抢文件**，等那个任务过验收再启动 |
| 都要发货 | G2 串行，一次一个 |

**底线**：抢占只抢槽位，不抢文件。touchset 重叠时加急也排队，
否则两个 run 改同一文件，合并必冲突。

**预留槽的意义**：加急永远有位置，不会因为「普通任务占了 2 个槽」而被卡住。
代价是磁盘上最多 5 棵树（3 普通 + 2 加急），换来加急零等待。

**验收**

每个任务返回后，主会话必须：

1. 读实际 diff，不只看报告；
2. 对照 `ac` 逐条核；
3. 检查越界（改了 touchset 外的文件）、遗漏、静默假设；
4. 便宜就自己重跑验证（build / test / preview）。

结果三选一：`accepted` / `returned`（附具体缺陷清单）/ `blocked`（转人）。

**task 级 blocked 的出口**

| 出口 | 谁做 | 结果 |
|---|---|---|
| 补 brief 重试 | 主会话 | 回 `pending`，`attempts+1` |
| 换 tier | 主会话 | 回 `pending`，换档重派 |
| 拆分 | 主会话 | 原任务拆成两个新任务 |
| 放弃该任务 | 人 | 标 `abandoned`，run 继续其余任务 |
| 取消 run | 人 | run → `cancelled` |

**重试上限**：`returned` 最多 2 轮；`failed` 重试 1 次；两者都超 → task `blocked`。

## 五、子会话协议

子会话是物理进程，不是宿主内 subagent。统一协议：

```
spawn(adapter, brief, opts) → session
  brief: 自包含，不含主会话历史
  opts:  { tier, cwd, timeout, budget, allowedTools }

wait(session, timeoutMs) → report
read(session) → log（落盘，默认不进上下文）
kill(session) → void
```

**报告格式（强制）**

子会话结束时必须输出结构化报告，字段限长：

```json
{
  "result": "done|partial|blocked",
  "files_changed": ["path — 一句话"],
  "verification": ["命令 → 结果摘要"],
  "open_questions": ["..."],
  "notes": "可选，≤100 字"
}
```

解析失败 = 视为 `partial`，主会话读 diff 自判。

**嵌套限制**：子会话**不得再开子会话**。深度固定为 2（主会话 + 子会话），防止失控和 token 爆炸。

**回收**：报告落盘后脚本立即 kill 子会话进程并清心跳，不留 zombie。
超时未报告 → 脚本 kill，按失败处理。

**权限默认**：子会话只拿只读工具 + `allowedTools` 白名单内的写工具。
删除类操作（`rm -rf`、`drop`、`force push`）一律拒绝，只能由主会话在 G2 后执行。
这是「子会话不能绕过发货门」的机械保证，不靠提示词约束。

**失败分类**（不同原因不同处理，不是一律重试）

| 原因 | 判定 | 处理 |
|---|---|---|
| 超时 | 心跳超过阈值 | kill，重试 1 次 |
| 崩溃 | 非零退出 | 重试 1 次 |
| 报告无法解析 | JSON 解析失败 | 不重试，主会话读 diff 自判 |
| 预算超 | token 超线 | kill，task `failed` |
| 权限拒绝 | 工具调用被拒 | 不重试，转 `blocked` |

**报告与 diff 必须对得上**

脚本校验 `files_changed` ⊆ `git diff --name-only`。不符 → 标 `partial`，
主会话必须读实际 diff。防「报告说改了 A，实际改了 B」。

## 六、状态落盘

```
.coding/runs/<run-id>/
  state.json        # 阶段、任务图、门状态、预算、续跑指针
  touchset.json     # 本 run 声明的文件/目录
  resources.json    # 端口/DB/服务占用
  sessions/<sid>/   # 子会话原始日志
  report.md         # 收口报告（人读）
```

`.coding/` 是运行期数据，**不进仓库**：装 V2 时写进 `.gitignore`。
这与工作区红线一致——开发期数据不落产品仓。

`state.json` 最小字段：

```json
{
  "run_id": "…",
  "issue": "…",
  "phase": "delegating",
  "budget": { "max_tokens": 0, "used_tokens": 0 },
  "gates": { "g0": "approved", "g1": "skipped", "g2": "pending" },
  "tasks": [ … ],
  "resume": { "last_accepted": "t2", "next_action": "spawn t3" }
}
```

**预算到线**：`used_tokens ≥ max_tokens` → run 转 `blocked`，附「已用 / 上限」，
等人决定加预算或收尾。子会话级预算超线 → 该子会话 kill，task 标 `failed`。
预算只停不崩，已完成的产出不丢。

**续跑**：进程崩溃 / 会话被杀后，重启只读 `state.json` 与 `resume`，
不要求人重新描述任务。这是「保稳定」的落点。

**谁写状态**：只有控制平面脚本写 `state.json`，AI 主会话与子会话都不直接写。
写操作是原子的（写临时文件再 rename），避免半截文件。子会话崩溃只影响它自己
那条 `sessions/<sid>/` 记录，不会污染任务图。

**崩溃语义**：主会话崩溃 → 脚本从 `state.json` 续跑；子会话崩溃 → 脚本在
`wait` 超时或非零退出时判定，重试 1 次后标 `failed`。任何情况下都不
「猜」已完成，只认落盘状态。

**schema 版本**：`state.json` 带 `schema_version`。脚本启动时若版本不匹配，
先跑迁移再操作；迁移失败 → 拒绝操作并报错，不拿旧格式硬跑。

**惰性清扫（不引入常驻进程）**：每条 `coding` 命令启动时顺带做一次清扫——
过期心跳、超 24h 的残留 worktree、孤儿子会话进程。所以只要你还在用，
残留就不会积；不用时也不占资源。这是对「没有 daemon」的取舍。

**状态与 git 对账**：`coding doctor` 检查 state 记录的 worktree / 分支是否还存在、
commit 是否打上、merge 是否完成。不一致以 git 为准，报告漂移并给修复命令。
防止「state 说 done，git 里其实没合」。

### 控制平面脚本化（能脚本就脚本）

V2 的可靠性不靠 AI 的记忆，靠脚本。**确定性的事全部脚本化，AI 只做判断。**

| 职责 | 谁做 | 为什么 |
|---|---|---|
| 状态机推进 | 脚本 | 确定性、可测、可重放 |
| 任务调度与槽位分配 | 脚本 | 确定性 |
| worktree 建 / 删 / 冻结 | 脚本 | 幂等 |
| touchset 冲突检查 | 脚本 | 确定性 |
| 子会话 spawn / wait / kill / 超时 | 脚本 | 生命周期 |
| 预算计数 | 脚本 | 精确 |
| 断点续跑 | 脚本 | 读 `state.json` 即可 |
| 门禁校验（G2 前） | 脚本 | 机器门先于人工门 |
| 规划 / 拆任务 | AI | 判断 |
| 写 brief | AI | 判断 |
| 验收判断 | AI | 判断 |
| 设计决策 | AI | 判断 |

**CLI（控制平面）**

```
coding run <issue>       # 建 state + worktree，开 run
coding next [run-id]     # 算下一个 ready 任务；不带参数算全局
coding spawn <task-id>   # 起子会话，登记 pid / 心跳（幂等键 task_id+attempt）
coding report <task-id>  # 收报告，落盘，kill 子会话，清心跳
coding accept <task-id>  # AI 验收通过 → 写 accepted，推进 resume
coding return <task-id>  # AI 验收不通过 → 写 returned，附缺陷清单
coding gate <g0|g1|g2>   # 校验门，写 gate 状态（approved/rejected/skipped）
coding resume <run-id>   # 从 state.json 续跑
coding reopen <task-id>  # 撤销已 accepted 的任务，回 pending
coding doctor            # 状态与 git 对账，报漂移
coding gc                # 清理已收尾资源
coding status            # 读 state 出表
```

AI 通过调用这些命令推进，**不直接改 `state.json`**。命令是幂等的：
`spawn` 以 `task_id + attempt` 为键，重复调用返回同一 session，不重复起进程；
`accept` / `return` 对已终态任务无副作用。

**中断续跑靠三样东西**

1. **原子写**：`state.json` 先写 `.tmp` 再 rename，断电不留半截。
2. **心跳**：每个子会话写 `sessions/<sid>/heartbeat`，脚本按时间判定僵死。
3. **恢复点**：`resume.last_accepted` + `next_action`，重启后脚本从这一点接着做，
   不需要人重新描述任务。

**验收**：脚本跑一遍 `coding next` 能算出正确的下一个任务，且 kill 掉进程后
`coding resume` 能续上，才算「脚本化闭环」成立。

## 七、冲突避免（四层）

| 层 | 机制 | 拦住什么 |
|---|---|---|
| 1 物理隔离 | 每 run 独立 git worktree + 独立分支 | 文件互相覆盖 |
| 2 声明式 touchset | run / 任务启动前声明触碰范围，重叠则排队 | 同文件并发修改 |
| 3 资源登记 | 端口 / DB / 外部服务写进 `resources.json` | 运行时抢占 |
| 4 写入门 | commit / push / merge / 删除走 G2 | 主干被并发写坏 |

**worktree 生命周期（防堆积，这是 V1 的痛点）**

V1 的 worktree 是「每票一个、人工 merge、人工清理」，跑久了就是一堆树。
V2 把 worktree 绑死在 run 上，自动收尾：

| 时点 | 动作 |
|---|---|
| run 启动 | 建 worktree + 分支，登记到 `state.json` |
| run `done` + G2 批准 | 自动 merge 回主干 → 自动删除 worktree 与分支 |
| run `cancelled` / `failed` | worktree 保留 24h 供复盘，之后自动删；`coding gc` 可立即清 |
| 只读任务（审查 / 分析） | **不建 worktree**，直接在主干读 |
| merge 冲突 | 转 `blocked`，不硬合，等人决定 |

**worktree 位置**：`.coding/worktrees/<run-id>/`，在仓库工作区之外，
不污染 `git status`，也不进 `.gitignore` 的判断范围。分支名 `coding/<run-id>`，
run-id 全局唯一，不会撞。

**diff base 与 merge 目标**：验收读的 diff 是
`git diff $(git merge-base <base> coding/<run-id>)`，不是拿整棵树比。
merge 目标是配置的 base 分支（默认 `main`）。多个 run 按 **G2 批准时间**顺序合，
先批准先合；后合的若冲突，转 `blocked` 解冲突，不自动重排。

**硬上限**：活跃 worktree ≤ 5 棵 = 3 个普通槽 + 2 个加急预留槽。
`paused` 的 run 保留自己的树，占的是它原来的槽位，不额外加树。
超过就排队，不再建新树。这样最多 5 棵，不会「一堆」，加急也永远有位。

**兜底命令**：`coding gc` 一条清掉所有已收尾的 worktree、分支与残留状态；
`coding status` 里每个 run 都标出 worktree 路径和是否已回收。

**执行期间开新任务**：

- 无关新 issue → 新 run，独立 worktree，并行；
- 相关但依赖当前产出 → 新 run，任务图声明依赖，排队；
- 对当前任务的修正 → 追加到当前任务图，同 run 消化。

当前 run 不被打断，冲突在第 2 层被拦下。

## 八、降 token 清单

1. 子会话 brief 自包含，不复制主会话历史。
2. 子会话报告限长（约 200–300 字或 JSON 字段限长）。
3. 主会话只读 diff + 报告摘要，不读子会话全文。
4. 子会话原始日志落盘，默认不进上下文，需要时才 `read`。
5. 总控（多 run 时）只做路由与资源分配，不读任务内容。
6. 上下文到阈值自动压缩 / 交棒（继承 handoff 思路）。
7. 任务图增量更新，不重发全量。
8. 已完成任务的 brief 与报告归档，不再参与上下文。

## 九、跨宿主适配接口

```ts
interface HostAdapter {
  name: string;
  probe(): Promise<Capabilities>;
  spawn(brief: string, opts: SpawnOpts): Promise<SessionHandle>;
  send(h: SessionHandle, msg: string): Promise<void>;
  wait(h: SessionHandle, timeoutMs: number): Promise<Report>;
  read(h: SessionHandle): Promise<string>;
  kill(h: SessionHandle): Promise<void>;
}

interface Capabilities {
  models: string[];
  maxConcurrent: number;
  supportsTools: boolean;
  supportsStructuredOutput: boolean;
}
```

**首批适配器**

| 宿主 | 调用形态 | 备注 |
|---|---|---|
| claude-cli | `claude -p <brief> --output-format json` | 参考实现 |
| codex-cli | `codex exec …` | 探测可用性 |
| qoder-cli | 对应 CLI | 探测可用性 |
| opencode-cli | 对应 CLI | 探测可用性 |
| generic | stdin 写 brief，stdout 读报告，exit code 表结果 | 兜底 |

能力不足时降级：无结构化输出 → 用标记段解析；无工具 → 子会话只产文本建议，主会话执行。

**全部不可用**：所有 adapter 的 `probe` 都失败 → run 转 `blocked`，报「无可用宿主」。
不崩溃、不静默降级到无工具模式——那会让子会话产出无法验证的文本，等于假完成。

## 十、闭环验证矩阵

设计「能闭环」的判据是下面每一行都能跑通，缺一行不算闭环。

| 场景 | 输入 | 期望 | 验证方式 |
|---|---|---|---|
| 正常路径 | 单个小 issue | 跑到 done，AC 全过 | 真实小任务 |
| 失败重试 | 子会话崩溃 | 重试 1 次；再失败进 blocked | 注入 kill |
| 断点续跑 | 进程被杀后重启 | 从 `state.json` 续跑，不重述任务 | kill -9 后重启 |
| 并发冲突 | 两 run 声明重叠 touchset | 第二个排队，不撞车 | 构造重叠声明 |
| 门禁 | 未批准 G2 | 拒绝 push / merge | 尝试越门写 |
| 跨宿主 | 换一个 adapter 重跑同一 run | 结果一致 | codex adapter 重跑 |
| 预算 | 设小 token 预算 | 到线停并报告，不超支 | 设 1k 预算 |
| 加急抢占 | 两槽占满时来 urgent | 挂起一个 normal，加急跑完自动恢复 | 构造占满 + urgent |
| 加急撞文件 | urgent 与在飞 touchset 重叠 | 不抢文件，排队到该任务验收 | 构造重叠 touchset |
| worktree 收尾 | 连续跑 5 个 run | 每个 done 后自动回收，最多 5 棵 | 跑 5 个并查 `coding status` |
| gc 兜底 | 残留 paused/cancelled | `coding gc` 一次清干净 | 构造残留后跑 gc |
| 晚激活 | 已有未提交改动才敲 `/coding` | 询问接管/丢弃，接管后从当前状态跑 | 造脏工作区再激活 |
| 脚本调度 | 任务图有多种依赖 | `coding next` 算出正确 ready 任务，幂等 | 重复调用对比结果 |
| 心跳僵死 | 子会话进程挂起 | 脚本按心跳超时判定并重试 | 暂停子进程再等超时 |
| 加急预留槽 | 普通槽 2 个占满时来 urgent | 走预留槽，普通 run 不受影响 | 占满普通槽后开 urgent |
| 交互次数 | 一次触发 | 中途只在 G0/G1/G2 停 | 计数人机往返 |
| 门被否决 | G2 选 rejected | 回 `reviewing`，不发货 | 拒绝一次 G2 |
| task 放弃 | 一个 task 反复失败 | 标 `abandoned`，其余任务继续 | 注入持续失败 |
| 预算到线 | 超 max_tokens | run 转 blocked，产出保留 | 设小预算跑超 |
| 宿主全不可用 | 所有 adapter probe 失败 | run 转 blocked，报「无可用宿主」 | 改坏 adapter 配置 |
| 加急崩溃 | urgent 跑一半崩溃 | paused 的 run 被脚本自动恢复 | kill 加急进程 |
| 并发 spawn 竞态 | 两 run 同时抢同一文件 | 文件锁串行化，第二个排队 | 并发调 spawn |
| 报告与 diff 不符 | 报告写 A、实际改 B | 标 partial，强制读 diff | 伪造报告 |
| 状态漂移 | 手动删 worktree / 漏 merge | `coding doctor` 报漂移并给修复 | 手动破坏后跑 doctor |
| merge 冲突 | 两 run 改动冲突 | 转 blocked，解冲突后重试 G2 | 构造冲突合并 |
| schema 迁移 | 旧版 state.json | 先迁移再操作，失败拒绝 | 造旧版 state |
| 撤销验收 | accepted 任务要回退 | `coding reopen` 回 pending | 验收后 reopen |

## 十一、与 V1 机场体系的关系

- **V1 不动**：机场体系留在 `main` / `dev`，不删不改。
- **V2 独立分支、独立目录**（拟 `v2/`），与 `airport/` 并列。
- **共享契约**：AC 写法、发货权分离、续跑指针格式。
- **不共享**：角色调度、日表、定时器、看板。
- 两套文档不互指为正本，只在必要处留指针。

### 安装时 V1 是否保留

**默认保留。** 装 V2 不动 V1 的任何文件、命令、状态。

| 安装选项 | 行为 | 适用 |
|---|---|---|
| `共存`（默认） | V1 + V2 都可用，命令、目录、状态各自独立 | 想继续用机场体系 |
| `仅 V2` | 不装 / 不启用 V1 的命令与定时器 | 想要纯净 V2 |

规则：

1. **装 V2 不顺手卸 V1**。卸载是单独动作，必须人明确要求。
2. **两套状态不共享**：V1 用 `handoff/`、日表；V2 用 `.coding/runs/`。
3. **命令不冲突**：V1 是 `/pilot` `/tower` `/ace` 等，V2 是 `/coding`。
4. **共享契约只读**：AC 写法、发货权分离、续跑指针格式可以互相参考，但不互相写。
5. **升级互不影响**：`upgrade-kai-mode` 只升 V1；V2 有自己的升级路径。
6. **卸载不删数据**：卸 V2 保留 `.coding/` 供复盘；要删得单独跑 `coding gc --all`。
7. **升级不中断在飞 run**：升级 V2 时若有 run 在跑，先让它到门点或 `paused`，再换版本。

## 十二、激活命令与体系边界

V2 只有一个交互角色，但必须有独立入口，否则跟创作体系
（`/producer` `/writer` `/artist` `/director` `/review` `/marketing`）混在一起。

| 命令 | 作用 |
|---|---|
| `/coding <任务>` | 进入 V2 主会话，开一个 run |
| `/coding status` | 看板（见下节） |
| `/coding resume <run-id>` | 从 `state.json` 续跑 |
| `/coding stop <run-id>` | 停一个 run，保留状态 |
| `/coding gc` | 清掉已收尾的 worktree、分支与残留状态 |
| `/coding adopt` | 把当前工作区的未提交改动接管为一个 run 的 baseline |

**激活语义**：一次 `/coding <任务>` 激活管一个 run 的全生命周期——规划、派工、
验收、发货都在同一 run 内，不需要反复激活。中途加任务 = 再敲一次 `/coding`
开新 run，不打断当前的；`/coding resume` 也算一次激活。

**issue 来源**：`/coding <任务>` 直接给文本；`/coding --issue <url>` 关联 GitHub
issue，AC 从 issue 正文抽。两种都落成 `state.json` 的 `issue` 字段。
**AC 归属**：AI 规划时写 AC，G0 时人可以改；G0 通过后 AC 锁定，验收按锁定的版本核。

**忘了先激活（晚激活）**：不会出错，但会丢三样东西——任务图、token 预算计数、
G0 计划门。补救办法：

- `/coding` 检测到工作区有未提交改动时，先问一句「接管为 baseline 还是丢弃」；
- 选接管 → 把现有改动快照成 `baseline`，开 run 时首个任务从当前状态开始，
  不追溯前期；
- 晚激活的 run 没有 G0（计划已过），只剩 G1（若碰 UI）和 G2（发货）。

所以晚激活不是错误路径，只是少了几道门和一份任务图。**建议还是先激活**，
因为前期拆的任务图、预算、门禁记录补不回来。

**边界**：`/coding` 管代码开发；创作体系管作品交付。两套命令不互相调用，
也不共用角色名。机场体系的 `/pilot` `/tower` `/ace` 等留在 V1，V2 不提供。
激活命令是体系路由的锚点：没有它，「做个落地页」无法判断走开发还是创作。

## 十三、看板

轻量、只读、直观。数据源是各 run 的 `state.json`，不引入 SQLite、定时刷新或服务进程。

`coding status` 终端表：

```
RUN      ISSUE              PHASE        TASKS  GATE  AGE
r-7f2a   修复登录超时        delegating   3/7    G2    12m
r-9c1d   加导出 CSV          queued       -      -     3m
r-4e8b   重构 auth 模块       blocked      2/5    G0    1h
```

`coding status --html` 生成单文件 `v2/board.html`：

- 三列：**在做 / 在等 / 已完成**；
- 列映射：在做 = `planning/design/delegating/reviewing/closing`；
  在等 = `queued/paused/blocked`；已完成 = `done/cancelled/failed`；
- 点 run 展开任务图与门状态；
- 数据全部来自落盘的 `state.json`，页面不写任何状态。

看板只读；所有写操作仍走主会话与门禁。规模到了「十几个 run 跨周」，
再考虑接 V1 的航班信息，不在 V2 内先做。

## 十四、已知取舍（明确接受，不再补）

| 取舍 | 为什么接受 | 代价 |
|---|---|---|
| 只读任务直接读主干 | 建树成本高于收益 | 主干正被 merge 时可能读到中间态；读前 pin commit 缓解 |
| `.coding/` 里日志明文 | 本地运行期数据 | 可能含 secrets；目录权限 700，日志脱敏，不上传 |
| 跨宿主 token 不可比 | 各宿主计数口径不同 | 预算只做上限告警，不做跨宿主比较 |
| 宿主不支持 resume | 子会话级无法续 | 该子会话降级为重跑，run 级仍可续 |
| 惰性清扫而非 daemon | 不引常驻进程 | 长期不用时残留不清，下次命令触发时清 |
| 一个 repo 一个 `.coding/` | 避免多项目串状态 | 多项目要分别管 |

## 十五、未决问题

1. 子会话报告用严格 JSON 还是标记段？（建议 JSON，解析失败降级为 partial）
2. 预算单位用 token、调用次数还是墙钟？（建议 token 为主，墙钟兜底）
3. 多 run 时是否需要常驻总控？（已定：不需要常驻。脚本 `coding next` 负责槽位与资源分配，总控只在人工排查时按需拉起）
4. 跨宿主的工具名与 tier 如何映射到具体模型？（建议先只做 claude-cli + generic，tier 映射表随 adapter 走，其余按需）
5. V2 目录落 `v2/` 还是 `core/v2/`？（建议顶层 `v2/`，表明是新体系）
6. 激活命令已定为 `/coding`（用户 2026-10-30 拍板）。
7. 控制平面脚本用什么写？（建议 Python 3 标准库，零第三方依赖，跨宿主都能跑）

## 十六、跃迁模式（V2 autopilot）

`/jump` 是 V2 的全自动挡：G0/G1/G2 由门卫子代理自批，人只在红线与异常时被叫醒。

- **命令**：`/jump <issue> [--tasks f.json]`；`/PRI-jump` 走加急预留槽。
- **并发**：普通槽 3 + 加急槽 2；每 run 2 个子代理；全局 10。排队 run 在槽位空出后由
  `promote_queued` 自动提升。
- **门卫**：`coding review` 起一个独立上下文、只读工具的子代理，读实际 diff 对照 AC，
  输出 `accept|return`；`--apply` 把裁决写回任务状态。
- **发货（全脚本化）**：切到 base（默认 `dev`）→ merge → 收尾门（`.coding/config.json`
  的 `finish_cmd`）→ `git push origin <base>` → 自动识别 `#123` / GitHub issue URL 并关票。
- **无人值守驱动**：`coding drive` 循环 `spawn → report → review → accept`，直到所有 run
  终态或 blocked；不依赖 AI 主会话逐步敲命令。
- **打断条件**：红线写操作、连续 return 3 轮、merge 冲突（自动 rebase 一次后仍冲突）、
  收尾门失败、push 被拒、无可用宿主。预算门不启用。
- **与 V1 的关系**：权限等价于塔台（合并/push/关票），但状态不共享；V2 的 run 仍落
  `.coding/runs/`，V1 的日表与 Issue 评论不受影响。
