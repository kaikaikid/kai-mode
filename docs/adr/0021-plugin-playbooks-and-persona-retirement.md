# 0021 插件化剧本：用 KWP 结构承载机场体系，人格层退役

## Status

accepted —— 2026-10-27 用户拍板「按这版插件化框架开工」。方案框架图见
[`docs/design/2026-10-27-kwp-plugin-architecture.svg`](../design/2026-10-27-kwp-plugin-architecture.svg)。

本文取代 [0007](0007-agents-layer-generic-contract.md)／[0008](0008-persona-model-config-and-host-adaptation.md) 的**载体形态**，
不改其中的判据（审查独立、只读/可写、宿主中立、模型不发明 slug）；0007／0008 保留为历史决策。

## Context

对 `anthropics/knowledge-work-plugins`（下称 KWP）的核对结论：它与 kai-mode 重合约一成，且全在知识层
（记忆、任务看板、ADR 模板、审查镜片、运维文档、插件装配）；kai-mode 的执法层——工作树隔离、塔台独占 push、
票状态机、五道门、审计账、红线、续跑指针、定时唤醒——KWP 一处都没有。因此可借的是**分发形态与技能写法**，
不是业务插件。

同期项目仓的治理票暴露了框架正本与项目实践的四处脱节：

| 证据 | 暴露的框架问题 |
|---|---|
| 项目仓 ADR-0145（一车道一树，一票一树废止） | 协议仍写「每票独立 worktree」，项目已按车道走 |
| 王牌 preflight 恒 `BLOCKED`、push 门不认 `-ace.md` | 协议没有写「王牌无对照道」与王牌日表归属 |
| 塔台每轮跑全历史普查、push 门常态超时 | 协议没有把「门自身成本不算被审对象的红」写成判据 |
| 推送临时树攒到 51 棵／9.7 GB | 塔台技能只有口头约定，没有登记式回收 |

KWP 的形态正好治这四类：**一个剧本一个插件、命令只做触发、技能写成可执行步骤、连接器缺什么就降级并登记**。

## Decision

### D1 目录形态：KWP 原生

仓根是市场，每个剧本是一个插件目录：

```text
.claude-plugin/marketplace.json          # 唯一分发清单：插件名／版本／来源／描述
<plugin>/
  .claude-plugin/plugin.json             # Claude Code 插件清单
  .qoder-plugin/plugin.json              # Qoder 插件清单（同一份内容）
  PLAYBOOK.md                            # 剧本总览：角色、阶段、记录面、红线指针
  CONNECTORS.md                          # 工具类别与降级（~~source control 等）
  commands/<role>.md                     # 角色触发口：只负责加载技能
  skills/<name>/SKILL.md                 # 可执行步骤（判据自解释）
```

- 本地插件的 `source` 是目录；将来引入上游插件时按 KWP 的做法用 sha 钉死。
- `registry.json` 退役。安装器从市场清单＋插件目录**派生**技能清单（内存中的旧形状只作兼容适配，
  不落第二份文件）。
- `manifests/install-profiles.json` 保留档位语义：`core` 是最小闭环，`full` 是全部自动件。

### D2 三层职责：剧本／角色／步骤

| 层 | 是什么 | 不许做什么 |
|---|---|---|
| 插件 | 一个剧本 | 不复制别家的判据 |
| 命令 | 角色口令，把剧本加载进来 | 不写长规则、不改判据 |
| 技能 | 剧本里的可执行步骤，每步带「过线判据」与「做不下去怎么办」 | 不复述协议数值，只留指针 |

判据正本仍只有一处：机场体系的 `airport/skills/loop/references/loop-protocol.md`。

### D3 五个剧本

| 插件 | 剧本 | 内容 |
|---|---|---|
| `airport` | 机场体系 | 命令：地勤／塔台／机长／副机长／王牌；技能：loop、pilot、copilot、tower、ground-crew、ace |
| `core` | 入口与安装 | 命令：kai-mode、set-kai-mode、handoff；技能：入口、安装、交接、审计、六条原则 |
| `board` | 看板 | `flight-info`（SQLite → `board.json`＋`index.html`） |
| `intake` | 想法池 | `kai-boom-idea-log` |
| `ops` | 事故与运维（新增） | `incident-response`、`runbook` |

- 机场五岗位一个不少：地勤、塔台、机长、副机长、王牌飞行员。只是从「人格文件」改成
  「角色命令＋角色技能」。
- `ops` 只进 `full` 档，不进 `core`。

### D4 人格层退役

- 删除 `agents/`（七个人格文件与 `dispatch.md`）、doctor 的 `agents-contract` 项、项目实例
  `models.agents.<人格>` 配置与初始化第 11 问。
- 派活规则（何时派、谁派谁、回执四要素、派生深度、上下文纪律）迁入协议 §五 与 §八，不再靠人格文件承载。
- **审查独立性仍由「另一段新上下文」保证**：Claude Code 用宿主原生子代理，Qoder 用原生 subagent，
  Codex／OpenCode 起独立进程。技能只写派什么、给什么、收回什么，不定义人格文件。
- 裁决不再有 `adjudicator` 人格：派一个只读裁决子代理，判据与 `ruling=` 三值住协议 §十一。

### D5 判据正本随技能安装

- `loops/loop-protocol.md` → `airport/skills/loop/references/loop-protocol.md`。
- 原因：安装面带不走仓根 `loops/`，旧版一直靠「读不到就按本仓副本」兜底，正是 ADR-0013 要治的死指针。
- 顶层 `loops/` 退役。项目仓若仍保留 `loops/loop-protocol.md`，它只是**镜像**，同步口改为从插件路径复制。

### D6 分发与体检

- `.claude-plugin/marketplace.json` 是唯一清单；每个 `plugin.json` 钉死自己的 `version`。
- 新增 `scripts/plugin-check.py`：校验市场↔插件目录↔`plugin.json`↔技能名／版本↔档位；内容摘要不一致即红，
  `--bump` 刷新摘要。接进 doctor，成为常规门。
- 新增最小 CI（`.github/workflows/plugin-check.yml`）：跑 `plugin-check` 与 `doctor`，红即停。
  与 KWP 的 `scan-plugins`／`bump-plugin-shas` 同形，但不引入外部安全扫描与 MCP 存活检查。

### D7 治理票写回正本（四处）

1. **一车道一树**：工作树从「一票一棵」改为「一车道一棵，票在树里换分支」；保留名
   `lane-main`／`lane-deputy`／`lane-ace`／`_push`；推送工位用完即拆，登记式回收。
   **2026-10-30 修订**：正常车道由「一车道一棵」改为两固定槽（`lane-<lane>-a`／`-b`），
   旧名 `lane-<lane>` 视为 `-a`；见 [0027](0027-lane-two-fixed-worktree-slots.md)。本条保留为历史。
2. **王牌车道**：王牌没有对照道（不因「另一张日表读不到」判 `BLOCKED`）；push 门的日表归属认 `-ace.md`；
   免票热修的提交信息必须带 `H-<日期>-<序号>`，否则门只能如实跳过、不许借别班槽位。
3. **门自身成本**：门超时／性能耗尽不算被审对象的红；塔台起手禁止每轮跑全历史普查，相交判定只走
   `git diff` 直出；门的耗时必须打印读数。
4. **树与工位回收**：临时推送工位建时登记、推完（成功／失败／中断）都回收；拆不掉要留痕，不许 `--force`。

### D8 宿主：先保两条腿

- **Claude Code**：读 `.claude-plugin/marketplace.json`／`plugin.json`；技能落
  `.claude/skills/<名>/SKILL.md` 或中央库副本；人格落点一节退役。
- **Qoder**（官方文档实测）：项目技能 `.qoder/skills/<名>/SKILL.md`；用户技能 `~/.qoder/skills/`；
  插件技能 `<plugin>/skills/<名>/SKILL.md`；规则 `.qoder/rules/**/*.md`＋`AGENTS.md`；
  子代理 `.qoder/agents/<名>.md`；定时任务 `.qoder/scheduled_tasks.json`／`/loop`。
  旧文写的 `qoder_cron` 在公开文档里查不到，按「运行时观测」标注，不当作公开 API。
- **Codex／OpenCode**：只补「技能从哪读、角色怎么起」两行，保留骨架。
- 唤醒围栏不变：角色命令之间不互相拉起，只有人工与定时器（仅塔台）能唤醒。

## Consequences

- 正面：一个剧本一个插件，新增／退役剧本只动一个目录；安装面自带判据正本，不再有仓外死指针；
  人格层退役后少七份需要同步的文件；分发有了版本钉与体检，漂移当场红。
- 负面／风险：
  - 这是一次**目录级迁移**，项目仓的镜像路径与既有装机都要跟着换（本轮只改框架仓，项目仓零字节改动）。
  - 命令带插件命名空间后，`/机长` 可能变成 `/airport:pilot`；中文自然语言触发由技能 `description`
    承担，宿主是否支持中文命令名需装机时实测，不支持就退回英文命令名。
  - 删除人格文件会丢掉一些「角色提示词」的稳定措辞；判据已迁入协议，但需要一轮实测确认审查独立性未退化。

## 明确不做

- 不引入 KWP 的 18 个业务插件、MCP 连接器内容、记忆／任务看板／dashboard。
- 不吸收 `tech-debt`（已有 `harness-audit`＋地勤开票）与 `testing-strategy`（已有 `tdd`＋审查门）。
- 不引入 KWP 的外部 PR 范围守卫与安全扫描（本仓没有外部投稿面）。
- 不自动拉起任何角色；不改唤醒围栏。
- 不改项目仓一个字节；镜像同步与项目侧门禁适配留作下一棒。

## 验证（判据级）

- `python scripts/plugin-check.py` 绿：市场↔插件↔技能↔版本↔档位一致。
- `python scripts/doctor.py --with-tests` 绿（含既有两红清零：安装面 ADR 引用、项目硬路径）。
- 仓根不再有 `registry.json`、`agents/`、`loops/`；`skills/` 不再是顶层技能目录。
- `airport/skills/loop/references/loop-protocol.md` 存在且被 `loop` 技能引用。
- `core`／`full` 档位都能从市场清单解析；`ops` 只在 `full`。
- Qoder 装机回执写明 `.qoder/skills/<名>/SKILL.md` 与命令退化路径；Claude Code 回执照旧。
