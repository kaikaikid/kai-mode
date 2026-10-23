> 状态（2026-10-22 同步）：按机场体系重做残留表保留（判据出处：项目仓 框架仓旧裁决，历史，已由本仓 [0003](../../../框架仓旧裁决) 重述接管）；文中租约/班次/按铃/五角色等已退役机制以 0003 为准（日表＋Issue＋分支三件记录面、塔台独占 push）。

# 组内执行三职：Researcher / Implementer / Reviewer

> 编排角色（Tower/Ground/Coordinator/Group）不变；这三个是 Group 内部的**执行角色**，不是编排角色。
> 简单票可以只用一个 implementer + 一个 reviewer；复杂票才加 researcher。不要为每张票机械地凑三个角色。
> **但 reviewer 不能省**：凡有代码/schema/高风险改动，必须有独立 reviewer；docs-only 且有机检的票可由组主上下文复核，并在状态卡写 `self-check`。reviewer 必须是另一次调用，id 不得与 implementer 相同。

## 一、职责与禁区

| 角色 | 只做 | 产出 | 绝不做 |
|---|---|---|---|
| Researcher | 查代码/文档/外部资料，给事实、选项、风险 | `research-<票>.md`（路径/行号/来源） | 写实现、改代码、替 Tower 拍方案 |
| Implementer | 在租约内实现、写测、跑定向命令、本地提交 | 分支＋commit＋回执 ≤25 行 | 自判验收、并车、push、扩租约 |
| Reviewer | 独立复核 diff 与 AC，跑验证，写验收 | `acceptance-<票>.json` | 改实现、替作者修代码、凭作者结论放行 |

## 二、什么时候用谁

- **简单票**（单文件、低风险）：1 个 implementer + 1 个 reviewer；只改文档且有机检时可 `self-check`，不硬派 reviewer。
- **复杂票**（跨模块、方案不明）：researcher 先出调查，再 implementer + reviewer。
- **高风险票**：上述三角色 + 用户审批；reviewer 可加安全/性能专项检查。
- **纯调查票**：只 researcher，产出结论与后续票建议，不写代码。
- **修复轮**：新 implementer（或同一角色新上下文）+ 同一 reviewer 标准；不允许作者自己判修复通过。

## 三、派工卡（每个子代理必带）

```text
你是 <researcher|implementer|reviewer>，只做本票。
票号：<n>；租约：<逐枚文件/目录>；禁改：<清单>。
合同哈希：<sha256>；若票面变化，停手写 blocked。
止损：主体 60/30 分钟；差量 35/20 分钟；只读 15–20 次。
回执 ≤25 行：改了什么/证据/卡点/下一步。
implementer 额外：scope-check check；commit --only -F <文件> -- <路径>；不 push/不并车。
reviewer 额外：不得读作者结论当证据；逐条 AC 跑命令；判不了写 unverified，不许猜 pass。
```

## 四、并行规则

- 同一文件域同一时刻只一个 implementer；不同票文件域不重叠才可并行。
- researcher 可以与 implementer 并行（只读），但不得改同一文件。
- reviewer 必须在 implementer 提交后启动；不得边写边审同一份未提交内容。
- 组内并行上限取 `limits.per_group`；全局取 `limits.global`。
- 每个执行体一个工作树；不在主树改；不在车道里跑会污染共享依赖的命令。

## 五、独立性与真度

- **写代码的人不能给自己出 pass**；组主上下文也不能代替 reviewer。
- reviewer 只拿：票面 AC、diff/commit、运行方式、证据；不拿作者“已经好了”的结论。
- reviewer 的每条 AC 必须有方法（test/run/browser/vlm/measure）与证据路径。
- 不可执行的检查（账号、真机、支付、对外发布、法律/安全审批）⇒ 写 `unverified`，不假装判过。
- 同一票 reviewer 与 implementer 最多 3 轮；第 4 轮转 Tower 重排/拆票，不再原地打转。

## 六、失败与交接

- implementer 卡住：写回执＋检查点，交回 Group；不无限重试。
- reviewer 判不过：写清未过项与原因；Group 决定 repair 或 blocked。
- researcher 结论不足：明确写“缺什么证据”，不编来源。
- 任何角色发现票面/租约冲突：停手写 `blocked`，不自行扩权。

## 七、宿主落地与计量

- **Qoder**：researcher=`Explore`（或多步 `general-purpose`）；implementer=`general-purpose`（有 `isolation=worktree` 时优先独立树）；reviewer=**新起** `general-purpose` 只读。`Plan` 不做验收，`Explore` 不做全文审查。
- **Codex**：researcher/reviewer=`codex exec -s read-only`；implementer=`codex exec -s workspace-write`。
- **其他宿主**：按 `adapters/<host>.md` 探测；没有 `Agent` 工具就开 fresh 子会话，不能拿组主上下文自判。
- **状态卡记** `subagents: [{role,id,ticket}]`；有代码/schema 改动而 `subagents` 缺 reviewer，或 `reviewer == implementer` ⇒ 不算独立验收，Ground 不接 ship handoff。
- **指标（每周看）**：reviewer 独立率（`reviewer != implementer` 的票 / 有代码改动的票）、每票子代理数、子代理回执超 25 行的比例。没有读数写 `unknown`，不猜。
