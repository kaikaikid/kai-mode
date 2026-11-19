# 人格层（persona layer）

> 三层分工：**canon**＝职责四块（宿主中立，逐字共用）· **skin**＝名字/身份/性格 · **persona**＝人格分层与记忆接口。
> 正本住 `roles/persona/<role>.json`，校验器 `scripts/persona.py`，机器门 `doctor.py` 的 `persona-layer`。
>
> **别和「人格层激活」混为一谈**：装配技能里那节（`core/skills/set-kai-mode/references/default-entry.md`）
> 管的是**把 canon＋skin 渲染成会话提示词**这件装配动作，口语里也简称「人格层」；
> 本文件讲的是**第三层 persona 块本身**（成长与记忆接口）。当前渲染器只拼 canon＋skin，
> **persona 块暂不进渲染**（`scripts/rolelib.py` 的 `render_body` 不含它），留给未来记忆系统接。

## 为什么单开一层

canon 只写「做什么、不做什么」，skin 只写「叫什么、什么脾气」。两者都**静态**。
人格层补的是**可变但受控**的部分：哪些不可改（原初内核）、什么可成长（自我）、成长从哪里来（记忆）。
这样以后接记忆系统时，不用改 canon/skin，也不必把成长事实写进仓库。

## 五个块

| 块 | 语义 | 可写性 |
|---|---|---|
| `identity_core` | 原初内核：来历、职业、身份、世界观 | **只读基线**；改要团长批准 + 追加版本 + 保留旧版 |
| `id` | 本我：天性与欲望（从 skin.personality 提炼） | 可成熟，不可被记忆抹除 |
| `ego` | 自我：现实判断与成长层 | **只放引用**（`refs[]`），不内联事实 |
| `superego` | 超我：价值与行为准则 | 核心底线不自动反转 |
| `memory` | 记忆接口声明 | 只声明，不装数据 |

## 记忆接口（留给未来记忆系统）

记忆本体**不进仓**，`memory.storage = external`；只有 `archivist` 能写，其他角色只提候选。
未来记忆系统实现这四个操作即可接上：

```text
retrieve(role_id, task)            -> [memory]      # 按任务相关注入，禁止整库注入
propose(role_id, experience)       -> candidate     # 任何角色可提候选
commit(candidate)                  -> memory        # 仅 archivist；带来源/时间/版本/冲突
rollback(memory_id)                -> receipt       # 回滚也留审计
```

约束（写进校验器）：

- `memory.write_policy` 必须是 `candidate_only`；直接写入一律拒绝。
- `memory.conflict_policy = isolate_then_escalate`：与内核冲突的记忆隔离，不注入，交团长裁定。
- `scope` 只允许 `task_fact / preference / skill / relationship / failure_lesson`。
- 注入顺序：安全规则 → 原初内核 → 职责边界 → 任务契约 → 与本任务相关的 ego 摘要。

## 记忆读写矩阵（v1）

v1 只落三类：`task_fact` / `failure_lesson` / `preference`。所有角色都只能 `propose`；
`commit` / `rollback` / `veto` 只有 `archivist` 能做（含 coordinator 的私有记忆入账）。

| 角色 | 按需读（namespace / kind） | propose | 私有记忆 |
|---|---|---|---|
| coordinator | 全部 ＋ `coordinator-private`；全部 kind | `preference` / `relationship` / `task_fact` | 有 |
| engineer | `project` / `task` / `shared`；`skill` / `task_fact` / `failure_lesson` | `task_fact` / `failure_lesson` / `skill` | 无 |
| reviewer | 任务卡 ＋ 实际 diff ＋ 测试/CI ＋ `project` / `shared`；工程师报告只当 claim | `failure_lesson` | 无 |
| archivist | 全部 | `commit` / `rollback` / `veto` | 无（治理全部） |
| researcher | `project` / `shared`；`task_fact` / `failure_lesson` | `task_fact` | 无 |
| architect | `project` / `shared`；`task_fact` / `relationship` | `task_fact` / `relationship` | 无 |
| designer | `user` / `project` / `shared`；`preference` / `skill` | `preference` / `skill` | 无 |
| writer | `user` / `project` / `shared`；`preference` / `skill` | `preference` / `skill` | 无 |

设计 / 写作的偏好只在「用户明确说过或项目规范有证据」时 propose；researcher 只提事实，
结论归 architect / coordinator；reviewer 的独立性锚定 diff 与测试，不锚定工程师叙述。

## 指纹

`python scripts/persona.py fingerprint <role>` 输出 `identity_core` 的 sha256。
用途：记忆注入前核对内核未变；迁移/压缩后仍可复算；改内核必然换指纹。

## 改动纪律

- 改 `identity_core`：团长批准 + `version` 递增 + 旧文件留在 git 历史，不静默改。
- 改 `id`/`superego` 的核心条：同上。
- `ego.refs` 由记忆系统写引用；仓库里保持空或只放指针。
