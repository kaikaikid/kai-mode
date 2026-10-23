# Codex 子代理最终方案（2026-10）

> ⚠️ **口径基准（2026-10-23 统一，v3.2）**：本 README 是 2026-10-18 初版设计，§一/§五 的模型与窗口数字已过期。**当前生效口径**：`contracts/roles.yaml`（角色↔档↔推理，机器可读）+ `scripts/check-tiers.py`（五方对账，漂移即红）+ `~/.codex/config.toml` 的 `[agents]` 段。读本文时按以下更正理解：
> - **模型只能在六个 `group/tier-*` 档位里选**：R / C / P / V / G / W。角色↔档固定为 explorer·librarian→R、worker→C、planner→P、reviewer→V、visual-designer→G、archivist→W，已写进 `roles.yaml` 和 `delegation-prompts.md` 的必填行，**不再是"未来模板"**。
> - **推理档按成员实测能力定**：R=`none`（读档池刻意不带思考，已批准），C/P/V/G/W=`high`。依据是"该档全体成员共有的推理档"，不是声明——旧声明里 C 档写 `max`（成员其实共有 low/high，且 max 只有 2/6 支持）、P/V 写 `xhigh`/`max`（多数成员不支持），属于空头，已于 2026-10-23 改回真实交集。
> - **兜底已从 R 档 `low` 抬到 C 档 `high`**（`default_subagent_model = "group/tier-c"` + `default_subagent_reasoning_effort = "high"`）。理由：漏配代价不对称——兜底设 R 等于拿最便宜的无思考模型改代码，坏了看不出来；兜底设 C 只是多花几倍单价。分档靠派活模板显式带值，兜底只当保险丝。
> - **窗口实际值**：R=200K、C=400K、P=400K、V=400K、G=256K、W=1M。下文写的 128K/256K 是 2026-10-18 的旧快照。
> - `max_depth` **存在且已设为 1**（`agents.max_depth`）。下文 §四"本机当前 Codex 版本没有这个配置项"是错的，当时按旧版认知写的。
> - `reviewer` 不用 `group/kai-vasss`（该组已 disabled）。
> - 角色 **7 个全进 magpie library**，由「更新」从 `library.json` 重建；接管前的 `agents/*.toml` + `install.ps1` + `validate.ps1` + `VALIDATION.md` 已归档到 `_superseded/`（作废，勿用）。
> - **未决项**：只读角色的权限隔离目前真机仍是 `sandbox_policy=disabled`（子代理全继承父会话宽权限），§三 的"双重约束"实际只剩指令一层；`acceptance.md` 的行为验收一条没跑。


## 结论

采用 **6 个常规代理 + 1 个条件代理**：

```text
explorer → planner → reviewer（计划审查）→ worker → reviewer（代码审查）
                \→ librarian（外部事实）
                \→ visual-designer（视觉生产）
                \→ archivist（单一来源超 256K）
```

这套方案解决三个问题：

1. **隔离上下文**：噪声留在子代理，主会话只收结论。
2. **隔离权限**：分析类角色不拿写权限，执行类角色才改文件。
3. **集中推理预算**：规划与审查用较强模型和高推理，探索和检索用便宜模型和低推理。

不采用 DeepSeek 的 7 核心 + 1 可选，因为角色越多，派活判断、配置维护和失败面越大。
宽窗只给 `archivist` 一个角色，因为它只服务"单一来源超 256K"这个确定缺口，不是为了角色齐全。

---

## 一、最终角色

| 中文名 | `name` | 定位 | 推荐模型组（未来 per-role） | 推理 | 上下文预算 | 档 | 写入 |
|---|---|---|---|---|---|---|---|
| 探索者 | `explorer` | 定位代码、追调用链、汇总影响面 | `group/auto-deepseek-v4-1-flash-free` | `low` | 128K | R | 否 |
| 规划者 | `planner` | 澄清需求、拆任务、定义验收 | `group/auto-deepseek-v4-1-flash` | `high` | 256K | P | 否 |
| 执行者 | `worker` | 实现、修复、测试、构建 | `group/coding` | `high` | 256K | C | 是 |
| 审查者 | `reviewer` | 双模式：审计划、审 diff | `group/auto-deepseek-v4-1-flash`（**勿用已 disabled 的 `group/kai-vasss`**） | `high` | 256K | V | 否 |
| 资料官 | `librarian` | 外部文档、版本、时效事实 | `group/auto-deepseek-v4-1-flash-free` | `low` | 128K | R | 否 |
| 视觉设计师 | `visual-designer` | 设计系统对齐、UI 规格、视觉资产 | `group/vlm` | `high` | 256K | G | 否 |

### 条件代理

只在触发条件成立时才派，不进默认链路。

| 中文名 | `name` | 定位 | 模型 | 推理 | 上下文预算 | 档 | 写入 |
|---|---|---|---|---|---|---|
| 档案员 | `archivist` | 超大单一来源 → 可回溯摘要 | `group/free-pool-1m` | `high` | 1M | W | 否 |

触发条件：**单一来源超过 256K，并且 rg、codegraph、局部读取都定位不了**。缺任何一条都别派。

### 为什么是这几个

- `explorer` 对应最高频的只读调查，用免费 Flash + `low` 推理，是全场最便宜的角色；贵的不是它的模型，是派它的次数。
- `planner` 用 Flash 做拆解。它不需要 1M：它读的是 explorer 压缩后的材料和关键文件，不是全仓库。
- `archivist` 是唯一宽窗角色，且严格只读。它不写代码、不判断方案好坏，只负责把超大输入压成可回溯的事实摘要。
- `worker` 使用 `group/coding`，只支持 `low/high`，固定 `high` 最稳。
- `reviewer` 合并计划审查和代码审查，避免 `momus` 与 `reviewer` 职责重叠。
- `librarian` 只在需要外部事实时启用，不进入每个任务的默认链路。
- `visual-designer` 只在 UI/视觉生产时启用，日常看图由主代理处理。

### 不建的角色

| 角色 | 处理 |
|---|---|
| `momus` | 并入 `reviewer` 的计划审查模式 |
| `worker-low` | 不建文件；主代理 spawn 时覆盖低成本模型/低推理 |
| `default` | 不覆盖内置兜底；模糊任务交回主代理重新路由 |
| `oracle` | 当前没有明确更强的可用模型；连续失败时再评估 |

---

## 二、路由规则

主代理先判断任务，再按下面的顺序派活。能自己完成的小任务不要为了“用上代理”而派活。

| 任务特征 | 路由 |
|---|---|
| 单文件、明确、小改动 | 主代理直接做；确实需要并行时派 `worker` 并降档 |
| 定位入口、追调用链、看影响面 | `explorer` |
| 外部文档、版本、最新事实 | `librarian` |
| 有歧义、多步骤、跨模块 | `planner` → `reviewer`（计划）→ `worker` → `reviewer`（diff） |
| 计划已明确，只需实现 | `worker` → `reviewer` |
| UI 设计、组件规格、视觉资产 | `visual-designer` |
| 单一来源超过 256K 且定位不了（巨型生成文件、超长日志、整份规范） | `archivist` |
| 超过 256K 的连续跨模块理解，但**可以**定位 | 先 `explorer` 分头定位，再 `worker` 分块做；不要用宽窗一把梭 |

### 硬规则

1. **低风险任务不强制计划审查**。单文件小修、文档改动由主代理或 `worker` 自验即可。
2. **中高风险任务必须计划审查**。涉及跨模块、权限、数据、发布、较大 UI 改版时，`worker` 不得绕过 `reviewer` 的计划审查。
3. **审查必须独立取证**。`reviewer` 自己看 diff、跑相关检查，不采信“已完成”的自报。
4. **`worker` 不得派生代理**。子代理只执行自己的任务，路由权留在主代理。
5. **`default` 不是模糊任务出口**。没有合适角色时交回主代理，不把任务丢给兜底。

详细决策树见 `contracts/routing.md`。

可直接复制的派活话术见 `contracts/delegation-prompts.md`。

---

## 三、权限模型

### 关键事实

Codex 官方文档明确：**子代理继承父会话的 sandbox 和 approval 设置，agent TOML 里的 `sandbox_mode` 不能覆盖父会话**。

所以只读角色必须满足两条：

- TOML 和指令声明“不写文件”；
- 父会话在该轮使用 `read-only`，或审查在独立只读会话中执行。

本机当前主配置是 `danger-full-access`。这意味着：

- 直接在当前会话 spawn `explorer` / `reviewer`，它们在权限上仍是可写的；
- 只有在指令层面自律，不能当作强制隔离；
- 需要强隔离时，先把父会话权限切到 `read-only`，再派分析任务。

当前 `[agents]` 默认值已写入本机（`default_subagent_model` = R 档 flash-free、`default_subagent_reasoning_effort` = `low`、`max_concurrent_threads_per_session` = 3），7 个子代理由 magpie 从 `library.json` 重建到 `~/.codex/agents/`（不带 model 字段）。但**没有**把主会话全局权限改成 `read-only`，因为那会阻断正常编码。只读调查和审查仍需在派活前切换父会话权限。

### 推荐操作

| 场景 | 父会话权限 | 说明 |
|---|---|---|
| 只读调查、计划、审查 | `read-only` | `explorer` / `planner` / `reviewer` / `librarian` |
| 实现、修 bug、测试 | `workspace-write` | `worker` 可改工作区 |
| 需要跨目录或系统级操作 | `danger-full-access` | 仅用户明确授权时 |

UI 自动化或独立验证可在只读会话中用 `codex -s read-only` 执行，避免被主会话的宽权限覆盖。

---

## 四、配置

已按本方案写入本机：

```text
C:\Users\Administrator\.codex\agents\
```

`~/.codex/agents/` 现由 magpie 从 `library.json` 重建 **7 个** toml（**不带** model 字段）；接管前的手写 `agents/*.toml` + `install.ps1` 已作废归档到 `_superseded/`，**不要再跑安装脚本、不要手写带 model 的 toml**（会与 library.json 冲突弹黄条）。落盘口径：

`~/.codex/config.toml` 的 `[agents]` 已更新为：

```toml
[agents]
default_subagent_model = "group/auto-deepseek-v4-1-flash-free"
default_subagent_reasoning_effort = "low"
max_concurrent_threads_per_session = 3
```

说明：

- `default_subagent_model` 是漏配保险丝，不是常规路径。现值 `group/tier-c` + `high`：漏配时最坏是"读档的活多花几倍单价"，而不是"拿无思考的便宜模型改代码且看不出来"。
- `max_concurrent_threads_per_session = 3` 控制并发。**注意额度按"未 close 的 agent"计数**，不是按正在跑的计数；实测 2026-10-17~21 的 29 条 spawn 边里 16 条停在 open，等于长期占坑，症状是"派不动"。收口三条见 `contracts/routing.md` §4。
- `max_depth = 1`：本机 Codex（0.163.0-alpha.11.1）支持该字段，已显式锁死一层，子代理不能再开子代理。（本行原文曾写"本机没有这个配置项"，是 2026-10-18 按旧版认知的误判，2026-10-23 用二进制字段表与实测配置复核后改正。）
- 不写 `enabled = true`，它本来就是默认值。

修改前的原配置已备份到：

```text
C:\Users\Administrator\.codex\agent-backups\20261018-final-plan\config.toml
```

应用后的完整配置快照在 `final/config.current.toml`，便于对照和回滚。Magpie 可能在重启或保存设置时回写配置，改动后需重启 Codex 并在 Magpie 中复核。

现在的应用方式是走 magpie，不再手工安装：

1. 在 magpie「资源库 → 子代理」配好 7 个角色的 name / 描述 / 指令 / skills。
2. 点右上「**更新**」——magpie 见 `~/.codex/agents/` 状态后从 `library.json` 重建，不写 model 字段，黄条消失。
3. `[agents]` 三行若没自动生效，手动补进 `~/.codex/config.toml`（值见上），再重启 Codex。

> 接管前的 `install.ps1` / `validate.ps1`（会复制带 model 的 toml、且用过期 effort=high）已移到 `_superseded/`，仅留档，勿执行。

---

## 五、模型与推理约束

本机真实模型目录（`~/.codex/magpie-models.json`）确认（2026-10-18 实测）：

| 模型 | 可用推理 | 上下文 |
|---|---|---|
| `group/free-pool-1m` | `high` | 1M |
| `group/vlm` | `low`, `high` | 1M |
| `group/coding` | `low`, `high` | 512K |
| `group/kai-vasss` | `high` | 1M | ⚠️ 已 disabled，**不要用** |
| `group/auto-deepseek-v4-1-flash` | `low`, `high`, `max` | 1M |
| `group/auto-deepseek-v4-1-flash-free` | `low`, `high`, `max` | 200K |

因此：

**这段已按 2026-10-18 的目录实测修正，原表有两处过期。**

- `group/coding` 实际是 512K，不是 1M；
- `group/auto-deepseek-v4-1-flash-free` 的 `max_context_window` 在该目录里为空值，README 原写的 200K 来自更早的快照，换配池后必须重新核对。

分组与成本杠杆：

- **分组不是省钱手段，是限制手段。** 同一个任务，窗口开大不会让 token 变少，只会让代理"敢"把更多东西塞进去，实际花费反而上升。所以不要为了"宽一点舒服"就升档。
- **最大的成本杠杆是路由到哪一档。** 把 `worker` 的活派给 R 档，是最贵的错；把定位活派给 P/V 档，是白烧钱。
- **第二杠杆是推理强度。** `high` 比 `low` 贵数倍；纯读角色用 `high` 没有收益，所以 `explorer` / `librarian` 已降到 `low`。
- **第三杠杆是派几次。** 重试、串行探测、多个代理并行找同一件事，这里最容易悄悄漏钱。
- **角色固定绑一个模型（静态映射）有利于 prompt cache 命中**，比每次动态选模型更省。

### 档位契约

档位与具体模型解耦。**当前** 7 个全共用 `default_subagent_model`（R 档 + `low`）；下表的「推理 / 上下文」是**推荐档 / 未来 per-role 生效后的目标**。重规划模型池后只换推荐组（`模型组框架.md` §3），档位语义不变。

| 档 | 角色 | 上下文预算 | 推理 | 成本量级 | 为什么 |
|---|---|---|---|---|---|
| R 读档 | `explorer`, `librarian` | 128K | `low` | 1× | 定位与检索，输出短，不需要深推理 |
| C 编码档 | `worker` | 256K | `high` | 3–6× | 要读多个文件、改代码、自测 |
| P/V 规划·审查档 | `planner`, `reviewer` | 256K | `high` | 10–20× | 输出短但错不起，值得买深度 |
| G 图档 | `visual-designer` | 256K | `high` | 5–10× | 视觉推理 |
| W 宽页档 | `archivist` | 1M | `high` | 按量 | 只用于单一来源超 256K，且无法定位 |
| 主会话 | 你直接对话 | 由你定 | 由你定 | — | 人愿意付的场景 |

### 关键事实：`medium` 不可用

本机在用组**没有一个支持 `medium`**（全是 `low`/`high`/`max`）。所以：

- 不要给任何角色写 `medium`；写了可能静默回退到 `low`，会让 C/P/V 档的质量莫名变差。
- 读档就老实写 `low`，判断档老实写 `high`。
- 困难任务可在 spawn 时把 `planner` 显式提到 `max`。

### 关键事实：上下文预算不是硬配置

agent TOML **没有 `context_window` 字段**。所以预算写成三层约束：

1. `contracts/roles.yaml` 的 `context_budget` 字段（契约与审计用）；
2. 角色 `developer_instructions` 里的一行预算规则（执行约束）；
3. `contracts/routing.md` 的升级规则（路由约束）。

不写 128K/256K 的虚拟模型组，直接用真实存在的组；档位差异靠 effort 和角色边界实现。

> 模型组是当前机器的事实，不是永久结论。换机器或换 Magpie 配池后，先重新核对 `magpie-models.json`。

> 表中保留 `group/free-pool-1m` 是为了说明通用兜底存在；本方案的角色没有使用它。

---

## 六、时间与外部事实

代理文件不硬编码日期，避免过期。父会话负责提供当前日期和时区：

```text
当前日期：2026-10-18（Asia/Shanghai）。
对版本、模型、价格、政策等时效事实，不要凭记忆回答；先查当前最新来源。
```

具体规则：

- `librarian` 查询使用“当前最新”，不要写“2025 年最新”。
- 结果标注发布日期、版本、来源。
- 旧资料必须标注可能过时。
- `planner` / `reviewer` 遇到版本判断时，移交 `librarian` 或明确列为假设。

详见 `contracts/time.md`。

---

## 七、最小验收

### 静态检查（v3 口径）

接管前的 `validate.ps1`（对手写 toml 跑 doctor、且用过期 effort）已归档 `_superseded/`，不再作为验收路径。现役静态验收：

1. magpie 资源库配好 7 个角色后点「更新」，让 magpie 从 `library.json` 重建 `~/.codex/agents/*.toml`。
2. **黄条警告消失** = 没有手写 model 字段与 library 冲突。
3. 重建出的 toml **不含** `model =` / `model_reasoning_effort =` 行（模型走父配置 `default_subagent_model`）。
4. `~/.codex/config.toml` 的 `[agents]` 三行（model / effort=low / max_concurrent=3）解析通过、无启动 warning。

### 行为检查

1. 只读测试：让 `explorer` 尝试写一个临时文件，必须失败；如果成功，说明父会话权限没有被设为只读。
2. 审查测试：让 `reviewer` 尝试改一行代码，必须失败或明确拒绝。
3. 闭包测试：`planner` 出计划 → `reviewer` 找缺陷 → `worker` 执行 → `reviewer` 看 diff。
4. 诚实性测试：故意让一个测试失败，`worker` 必须如实报告失败，不能把失败说成通过。
5. 时间测试：问“当前最新版本是什么”，检查查询没有出现旧年份锚定。

完整验收表见 `contracts/acceptance.md`。

---

## 八、与 DeepSeek 方案的差异

| DeepSeek 方案 | 本方案 | 原因 |
|---|---|---|
| 7 核心 + 1 可选 | 4 核心 + 2 条件 | 降低角色维护和路由复杂度 |
| 新建 128K/256K 组 | 使用现有真实组 | 当前机器没有这些组，先跑通再拆 |
| 只读靠 `sandbox_mode` | 父会话权限 + 指令双重约束 | 官方明确子代理继承父会话权限 |
| 全部 `high` | 读档 `low`、判断档 `high` | `medium` 本机不存在；读角色用 `high` 是纯浪费 |
| 每个角色都想要大窗口 | 窗口与任务范围匹配，宽窗只给 `archivist` | 窗口是限制手段，不是省钱手段 |
| 强制计划审查 | 按风险触发 | 低风险任务不该被流程拖慢 |
| 三层时间基建 | 父会话注入 + 角色规则 + 验收 | 保留原则，不做额外服务 |

一句话：**先跑通 4 个核心闭环，再用真实缺口决定是否增加第 5 个角色。**

---

## 九、当前状态

静态层已经可用（v3 magpie 接管口径）：

- 7 个子代理在 magpie `library.json`，由「更新」重建到 `~/.codex/agents/`（不带 model 字段）；
- 推荐档与真实模型目录已核对（`模型组框架.md` §3）；
- `[agents]` 默认值已写入（`default_subagent_model` = R 档 flash-free、`effort` = `low`、`max_concurrent` = 3）；
- 本机配置严格解析通过。

还差真实行为验收：只读写入拦截、计划/代码双审查、worker 诚实报告、时间反向测试。按 `contracts/acceptance.md` 跑完这些项目后，才能把"框架可用"升级为"框架已验证"。

> 接管前（2026-10-18 手工安装流）的验证记录已归档在 `_superseded/VALIDATION.md`，其"6 个文件 / effort=high / reviewer=kai-vasss / 靠 toml sandbox_mode 隔离"等结论按本文顶部更正，不作现役口径。
