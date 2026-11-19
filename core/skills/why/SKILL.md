---
name: why
status: active
approved_by: human:kaikaikid
approved: 2026-11-19
sources:
  - resource: "../role-entry/SKILL.md"
    note: "专家入口：researcher 的派发与配对技能注入口径"
description: >
  只读溯源：回答一段代码或一个决策为什么长这样，七类证据源逐类盘点后给置信度。
  不改 issue/PR、不写文件、不自动写记忆。
  触发：/why、「为什么这样」「当时为什么选它」「这阈值哪来的」「回归/复盘根因」。
version: 0.1.0
updated: 2026-11-19
allowed-tools: Read Grep Glob Bash
metadata:
  owner_role: researcher
  allowed_roles: [coordinator]
---

# why —— 为什么这样

> 回答「当时为什么这么定」，不是「现在该怎么定」。
> 空结果也是发现：某个源查过、没有，也是结论的一部分。

## 何时用

- 一段奇怪的代码/阈值/分支，想知道它防的是什么。
- 决策复盘：当时有哪些选项、为什么选了这个。
- 回归或事故的根因溯源（只找原因，不修）。
- 不适用：要新方案（归 architect）、要修代码（施工派 worker）。

## 输入

- 目标：代码块 / 常量 / 决策 + 一句话问题。
- 可用的证据源清单：哪些工单系统、文档仓、聊天记录、监控面板在这台机器上可读。

## 步骤

1. **代码锚点**：定位 `file:line` 与符号；`git blame -L` 找到引入 commit；`git log --follow -p` 看演化；merge subject 里的 `(#N)` 取 PR 号。
2. **七类证据源盘点**（每类标：有 / 无 / 不可用）：
   源码管理、工单系统、长文档、聊天记录、可观测数据、错误跟踪、分析仓。
3. **逐源取证**：
   - 有就查，引用必须可点（文件、行号、编号、命令读数）。
   - 空就记「查过、无记录」——这是发现，不是失败。
   - 不可用就记「不可用 + 原因」，不假装查过。
4. **综合八段**（见下）。
5. **若为改动前奏**：把结论收敛成约束集 Preserve / Change / Avoid / Risk，各 2–5 条，交回调度方决定是否开工。

## 输出（八段，固定顺序）

1. **The Question**：一句话，原样复述要回答什么。
2. **The Code in Question**：`file:line` + 关键片段摘要（不整段复制）。
3. **What We Found**：逐源证据；空结果写「查过、无」。
4. **What We Can Reasonably Infer**：标 inference，写依据。
5. **Competing Hypotheses**：若有多个解释，各自支持/反证。
6. **What We Don't Know**：unknown，逐条写缺什么。
7. **Sources Consulted**：七类源各一行：有/无/不可用 + 具体引用。
8. **Confidence Summary**：高/中/低 + 一句话理由（证据覆盖度）。

## 用词与证据

- 只用四类词：`fact` / `inference` / `unknown` / `recommendation`。
- fact：文件+行号、commit sha、PR/issue 号、命令读数，四者之一。
- 引用可点：给路径与行号；远程条目给编号与标题，不给会烂的链接。
- 共享证据契约由调用角色的上下文提供；本技能只使用 fact/inference/unknown/recommendation 四类词，不重复判据。

## 边界

- **只读**：不改 issue / PR / 工单状态，不写任何文件，不 commit。
- Bash 仅只读：`git log/show/blame`、`gh` 的只读子命令、`rg`、`ls`。
- 不 spawn 子代理；需要并行时由调度方按证据源拆任务。
- 只回答「为什么」，不夹带「应该怎么改」；改法最多进 recommendation 并写明决策人。

## 自检

```text
八段齐全；Sources Consulted 七类都有状态
每条 fact 可点；unknown 与 inference 没有混写
没有写文件、没有改任何外部状态
```
