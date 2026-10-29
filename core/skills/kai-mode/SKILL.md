---
name: kai-mode
status: active
approved_by: human:kaikaikid
approved: 2026-10-21
sources: []
description: >
  kai-mode：所有剧本的统一入口与顶层抽象。用户一句话需求 → 判断 → 拷问（≤5 问，只问大方向，每题带推荐默认）
  → 定稿（清账 → ADR → 拆票草案 → 规划表）→ 用户拍一次板 → 路由给地勤开票 / 机长执行 / 王牌加急 / 塔台排班发货，
  只推荐唤醒命令，不自动起角色；剧本不限于这几个岗位。要全景/看进度时路由到看板（数据层 60-board ＋ 展示层 航班信息）。不执行具体活。
  触发：新想法、要开工、加急插单、kai 模式；熟活可直接喊角色口令（/ground-crew /tower /pilot /copilot /second-officer /ace；中文「地勤」「塔台」「机长」「二副」也认）。
version: 3.1.0
updated: 2026-10-27
allowed-tools: Read Grep
compatibility: Host-agnostic
dependencies:
  skills:
    - name: kai-domain-modeling
      reason: "定稿第 2 步（术语与 ADR）的方法（fork 自上游，微调记 deltas）"
    - name: kai-to-tickets
      reason: "定稿第 3 步（拆票草案）的方法（fork 自上游，微调记 deltas）"
---

# Kai Mode —— 所有剧本的统一入口

> **中立层**：规则住仓库里，任何 agent / 任何编辑器一进仓库即生效；斜杠命令只是可选别名。

## 这是什么

`/kai-mode` 是**所有剧本的统一入口与顶层抽象**：用户说一句话，它判断、拷问、定稿、路由。
**它不执行具体活**——不写代码、不开票、不排班、不 push；那些归各岗位和各剧本。

```
用户一句话
  → ① 判断（新想法 / 熟活 / 已有票）
  → ② 拷问 ≤5 问（只问大方向，每题带推荐默认）
  → ③ 定稿：清账 → ADR → 拆票草案 → 规划表
  → ④ 用户只在规划表上拍一次板   ◄── 全流程唯一必须她按的地方
  → ⑤ 路由：地勤开票 · 机长/副机长/二副执行 · 王牌加急 · 塔台排班发货 · 其它剧本
```

## 入口约定

| 你说什么 | 走哪 | 说明 |
|---|---|---|
| 新想法 / 方向未定 / 一句话需求 | `/kai-mode` | 默认入口；判断、拷问、定稿、路由 |
| 已定方案要开工 | `/tower` 排班，或熟活直喊 `/pilot`、`/copilot`、`/second-officer` | 机长只做日表里的票；表空就请塔台补 |
| 排班 / 发货 / 关票 | `/tower` | 也可等 60 分钟轮巡自动跑 |
| 临时加急 / 直接让某个角色马上做 | `/ace` | 用户直连的加急通道；简单可免票热修，复杂必须开票 |
| 聊规划、开票、记想法 | `/ground-crew` | 开票权归地勤；开票后可三选一：拉起王牌 / 进王牌队列 / 等塔台 |
| 「loop」 | **不是口令** | 历史叫法；单票闭环是机长/副机长/二副共用协议 |

六个岗位只是默认的机场剧本；**剧本不限于这几个岗位**——新增剧本在项目配置实例 `registry.playbooks[]` 登记一行即可
（一行四格：`name` 剧本名／`trigger` 怎么被唤醒／`route` 路由到哪支技能／`notes` 一句边界；项目仓 router.md 已退役），入口不必改。

## 六个角色（职责与正本）

| 角色 | 口令 | 管什么 | 正本 |
|---|---|---|---|
| 地勤 | `/ground-crew` | 跟用户对话、规划、开票、收 BOOM 想法 | [`airport/skills/ground-crew/SKILL.md`](../../../airport/skills/ground-crew/SKILL.md) |
| 塔台 | `/tower` | 独立岗位；默认每 60 分钟被唤醒，也可人工唤醒；kai-mode 只推荐命令；先发货、后补排班（排班放最后）；合并、push、关票 | [`airport/skills/tower/SKILL.md`](../../../airport/skills/tower/SKILL.md) |
| 机长 | `/pilot` | goal 模式读 `-main` 日表并滚到跑空（在飞名额按协议正本，待发货不占位）；取舍默认派裁决子代理 | [`airport/skills/pilot/SKILL.md`](../../../airport/skills/pilot/SKILL.md) |
| 副机长 | `/copilot` | 同一条 loop 的另一分支，读 `-deputy` 日表 | [`airport/skills/copilot/SKILL.md`](../../../airport/skills/copilot/SKILL.md) |
| 二副 | `/second-officer` | 同一条 loop 的第三条机长道，读 `-second` 日表 | [`airport/skills/second-officer/SKILL.md`](../../../airport/skills/second-officer/SKILL.md) |
| 王牌飞行员 | `/ace` | 用户直连的加急通道；读加急队列标签票（标签字符串见地勤技能），在自己的 `-ace.md` 车道滚动消费（执行帽口径见协议 §一）；简单免票热修、复杂自补票 | [`airport/skills/ace/SKILL.md`](../../../airport/skills/ace/SKILL.md) |

**权限硬线**：塔台独占 push 与关票；机长/副机长/二副/王牌只管理不写码（王牌热修是受控例外）、不 push；地勤只开票不施工；kai-mode 只做入口。

## 拷问规则 —— 流程位＋指针

- **流程位**：拷问＝流程第②步（见上），交互顺序与入口判断咬死，留在流程里。
- **判据细则唯一正本**：[`skills/principle-ask-one-question-at-a-time/`](../principle-ask-one-question-at-a-time/SKILL.md)（何时进场/判据/反例/验证）；本节不复述细则。

## 定稿规则 —— 清账 → ADR → 拆票草案 → 规划表

1. **清账**：上游决策已被推翻 / 重复票 → 关；不属于本里程碑 → 转走；超 30 天没动 → **只列清单交用户，不自动关**。
2. **ADR**：大方向决策落项目 ADR 目录，落点从项目配置实例 `registry.adrs.dir` 读（缺实例即报缺件，不猜落点）。
   方法用 `kai-domain-modeling`（术语挑战、ADR 三条件、GLOSSARY 落点；fork 自上游）。
3. **拆票草案**：按里程碑拆成可执行工单草案（目标、AC、允许/禁止修改、验证命令）。
   方法用 `kai-to-tickets`（垂直切片、阻塞边、宽重构 expand–contract；fork 自上游）；**只出草案，开票归地勤**。
4. **规划表**：汇总成一张表——她**只在规划表上拍一次板**；批准后路由**地勤开票**。

## 审批边界 —— 流程位＋指针

- **流程位**：拍板前每次「要问她吗」的判断，以及各岗位、各剧本的审批点，都吃这一条。
- **判据细则唯一正本**：[`skills/principle-visible-and-redline-only/`](../principle-visible-and-redline-only/SKILL.md)（何时进场/判据/反例/验证）；本节不复述细则。

## 路由：拍板之后

| 需求形态 | 路由给 | 交付物 |
|---|---|---|
| 需要开票 / 改票面 | 地勤 | Issue（挂里程碑、`ready-for-agent`、AC 与禁区） |
| 有票要执行 | 机长 / 副机长 / 二副 | 按日表开工；每票 1 施工 + 1 审查 |
| 临时加急 / 用户直连 | 王牌飞行员 | 加急队列标签票或自补票；热修四件记录；发货仍归塔台 |
| 要排班 / 发货 / 关票 | 塔台 | 日表、一次合并 push、关票回执 |
| 不属于这些岗位 | 对应剧本 | 登记行收进项目配置实例 `registry.playbooks[]` |
| 要全景 / 看进度 | **看板**（三层：数据 ＋ 展示 ＋ 触发） | 数据层 `handoff/60-board/` 卡片；展示层 [`flight-info`](../../../board/skills/flight-info/SKILL.md)（口令 `/航班信息`）的 `board.json`（AI 读）与 `index.html`（人读） |

**kai-mode 只做路由与推荐**：打印/写出 `/tower`、`/pilot`、`/copilot`、`/second-officer`、`/ace`、`/ground-crew` 等命令，交人工执行；
**不调用会话创建口，不自动起角色**。宿主缺能力时写进
`/set-kai-mode` 的缺件登记，不猜路径、不硬起。
**唤醒塔台的人名单（现阶段）**：人工口令、60 分钟唤醒定时器两路；
kai-mode 只推荐命令，不在唤醒名单；唤醒围栏见协议 §一（后续可评审放开）——
它们需要塔台时写进交付/播报，由人工或定时器处理。

## 正本地图（入口不复述判据，只给路径）

判据一条只住一个家：本文件只做路由，不复制条文。

| 要判什么 | 正本 |
|---|---|
| 一张票从领到发、名额、审查门、回执、红线 | 兄弟技能 `loop` |
| 派子代理：何时不派、谁能派谁、并发、上下文纪律 | 兄弟技能 `loop` 的 `dispatch.md` |
| 六个岗位与角色命令 | 机场剧本 `airport/PLAYBOOK.md` |
| 开票与 Definition of Ready | 地勤技能 ＋ 项目仓的 issue 读取口径 |
| 交接文档与跨 agent 看板 | 项目 `handoff/README.md`（装机骨架自带） |
| 技能目录与字段契约 | 框架仓 `docs/skill-layout.md` |
| 宿主差异：怎么装插件、技能放哪、角色命令怎么起 | 框架仓 `adapters/README.md` |

> 「框架仓」那几行指 clone 里的正本，不随技能安装；技能正文已写全现行判据，读不到那些文件不影响执行。

## 分层与硬互斥线

| 层 | 管什么 | 正本 |
|---|---|---|
| 入口层 | 判断、拷问、定稿、路由 | 本文件 |
| 方法层 | 怎么干（六岗位技能 ＋ 单票闭环） | 框架仓的角色技能与单票闭环正本 |
| 调度层 | 谁在飞、排班、并发、发货 | 塔台技能 ＋ 六岗位正文 ＋ 项目配置 `paths.day_tables_dir` 日表 |
| 记录层 | 票状态与证据 | GitHub Issue（唯一事实源）＋ 日表 |
| 展示层 | 人看的全景（不改状态） | 数据 `handoff/60-board/` ＋ 展示 [`flight-info`](../../../board/skills/flight-info/SKILL.md) |

- 入口**不复述**任何一层的判据；剧本**不写**谁在飞 / 并发 / 发货；调度**不改**剧本判据。
- 一个语义只许一个家：判据见 [`principle-one-semantics-one-home`](../principle-one-semantics-one-home/SKILL.md)。

## 设计取舍

全权授予 · 一句路由 · **翻人话**；另加「拷问只问大方向 ＋ 定稿一条龙 ＋ 拍板只一次」。

- **正文不常驻**：治理正本「索引一行常驻 ＋ 叶子按需读」，派活前先问这一发要不要整读。
- **传指针不传全文**：给子代理文件路径与票号，不粘正文；回收只收回执上限内的结论（见协议正本 §五）。
- **仪式随规模塌缩**：判据见 [`principle-ceremony-collapses-with-scale`](../principle-ceremony-collapses-with-scale/SKILL.md)。
- **默认往前走**：判据见 [`principle-measure-dont-ask`](../principle-measure-dont-ask/SKILL.md)。
- **不搬**并行舰队那套机器（与「单写手／隔离」那套并行舰队口径相反）。

## 历史

旧机场机器（2026-10-21 前那套）已退役，角色、并发、任务面与发货边界一律以六岗位技能正文为准；
配置与安装走 [`/set-kai-mode`](../set-kai-mode/SKILL.md)。
