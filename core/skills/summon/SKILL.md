---
name: summon
status: active
approved_by: human:kaikaikid
approved: 2026-11-09
sources:
  - resource: "../../../core/skills/guild/SKILL.md"
    note: "子代理纪律（默认零、先报数量）的正本在 guild，本技能不复述"
description: >
  手动唤醒一个专业角色子代理的方法论入口（酒馆名「召集」）。
  不自动派发、不写代码、不开票；只决定「派谁、给什么上下文、上限几个」，
  然后按本宿主已配置的唤醒方式交给宿主起。
  跨宿主没有统一的「派子代理」API——有的宿主有原生子代理，有的只能拉自己的 CLI 进程；
  所以本技能是方法论，不是适配器。宿主细节住 adapters，本文件只给判据。
  触发：`/summon <角色>`、`/召集 <角色>`；角色＝researcher/architect/engineer/designer/writer/archivist/reviewer。
version: 0.1.1
updated: 2026-11-09
allowed-tools: Read Grep
compatibility: 需宿主能起新上下文；起不了按 adapters 缺件登记，不退化成主会话自己写
---

# 召集（summon）—— 手动唤醒一个角色

> 这是方法论，不是适配器：本技能不直接派进程，只把「派谁、给什么、上限几个」定清楚，
> 然后交给宿主已配好的唤醒方式。纪律正本在 `guild/SKILL.md`「子代理纪律」，本文件不复述。

## 什么时候用

- 想在**不开 fleet run** 的情况下，单独要一个角色看一眼（调查、出方案、审一段代码）。
- 已开 run 但想临时加一个角色（如让 `reviewer` 预审）。
- 创作类用武器集（`producer` 等），不走本技能。

**不该用**：能当前会话直接做完的（默认 0 子代理）；要做成有验收标准的事（开 `fleet`，走 claim/report/verdict）。

## 七个角色（认 `role_id`）

| role_id | 酒馆名 | 一句话 | 升级条件 |
|---|---|---|---|
| researcher | 崔希丝 | 外部调查、资料与证据 | 来源>3 或要把广告与事实分开 |
| architect | 瑞兹 | 架构、取舍、根因 | 架构选择／模块边界／不可逆技术选择 |
| engineer | 布莱恩 | 代码实现、修复、测试 | 改动文件>3 或需迁移/回滚 |
| designer | 泰兰德 | 视觉、插画、UI | 交付物是视觉方案 |
| writer | 周卓 | 文档、教程、报告 | 要可对外交付的长文档 |
| archivist | 克罗米 | 记忆治理、复盘 | 写跨任务记忆或改流程 |
| reviewer | 提里奥 | 独立审查（只读、新上下文） | Risk≥HIGH 或正式交付 |

## 怎么唤醒（按宿主能力分两条路）

宿主走哪条、具体命令样例，住 `adapters/<宿主>.md` 与装机回执；本技能只给判据：

1. **有原生子代理的宿主**：用宿主派发，`subagent_type` 或 agent 文件名＝角色名（角色文件由 `set-kai-mode` 渲染）。
2. **无原生子代理、本身是命令行 agent 工具的宿主**：走 `fleet auto` 的 `worker_cmd`/`reviewer_cmd` 拉本宿主自己的 CLI 进程；不在 run 里时由康娜起一次本宿主 CLI，带角色提示词与只读／可写档位。

两条都起不了 ⇒ 按 adapters 缺件登记 `no-new-context`，不退化成「主会话自己写代码」。
**禁止跨宿主借兵**：在 A 宿主里不拉 B 宿主的 CLI。

## 任务包（缺一项不派）

目标一句话 · 范围（含/不含）· AC 可机检 · 权限（只读/可写范围）· 交付格式与路径 · 预算（迭代/超时）。
审查类强制新上下文、只读、不继承执行者完整历史。

## 纪律（摘自 guild，详见 guild/SKILL.md）

默认 0；派之前报「几个、为什么、上限几」；机械/单一活 ≤1，标准施工 ≤3；深度固定 1 层（子代理不派子代理）。

**终点**：子代理拿到任务包并已起，或判定不派（记原因）。
