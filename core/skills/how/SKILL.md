---
name: how
status: active
approved_by: human:kaikaikid
approved: 2026-11-19
sources:
  - resource: "../role-entry/SKILL.md"
    note: "专家入口：由它按 role_id 加载 profile 并注入配对方法技能路径"
  - resource: "../principles/SKILL.md"
    note: "四类词与一次一问等通用判据的单一住处，本技能不复述"
description: >
  只读代码导航：解释一段代码怎么运作、该放哪层、谁拥有这块，给可点证据建心智模型。
  不写代码、不改设计、不开票、不自动写记忆。
  触发：/how、「这段怎么运作」「走一遍调用链」「这该放哪层」「谁拥有这块」。
version: 0.1.0
updated: 2026-11-19
allowed-tools: Read Grep Glob Bash
metadata:
  owner_role: architect
  allowed_roles: [coordinator]
---

# how —— 这段代码怎么运作

> 回答「它是什么、怎么跑、住哪、谁拥有」，不回答「该怎么改」。
> 结论先行；事实带 `file:line`，推断与未知分开写。

## 何时用

- 接手一块陌生代码，要先建心智模型。
- 判断一个改动该放哪层、归哪个模块。
- 走一遍调用链，看数据从哪来、到哪去。
- 不适用：要设计新方案（归 architect 的方案工作）、要改代码（施工派 worker）。

## 输入

- 目标：文件 / 符号 / 子系统 + 一句话问题。
- 仓根：在哪个仓里找。缺任一项先问一句，不猜。

## 步骤

1. **定题**：问题模糊就先写一句自己的解释（「你是说 X 这条链吗」），再开始探。
2. **判复杂度**：
   - 单模块：一趟读完，直接成文。
   - 跨文件：拆 2–4 个视角（入口 / 核心逻辑 / 数据与存储 / 外部边界），逐个取证。
3. **取证**：
   - 有 `.codegraph/` 的仓先用 `codegraph explore "<符号或问题>"`，一次拿符号源码与调用路径。
   - 没有就 Grep 定位 + Read 读全上下文；别只看函数名猜语义。
   - 用 `git log -L` / `git blame -L` 取最近改动，说明这段为什么长这样。
   - 每条结论落 `file:line`；命令读数原样引用。
4. **五段成文**（见下）。
5. **放置与归属**：给出候选层与各自代价（改哪里、影响谁、回滚成本），**不替用户拍板**。

## 输出（五段，固定顺序）

1. **Overview**：一段话讲清这块做什么、为谁服务。
2. **Key Concepts**：出现的领域词与关键类型，各一句话。
3. **How It Works**：按调用顺序走链，每步带 `file:line`。
4. **Where Things Live**：目录/模块/表/配置各在哪，谁读谁写。
5. **Gotchas**：坑、隐式约定、历史包袱——每条注明是 fact 还是 inference。

末尾单列 **unknown**：没查到的、查不动的、需要人确认的，逐条写缺什么证据。

## 证据与用词

- 只用四类词：`fact`（带证据）/ `inference`（标依据）/ `unknown`（缺什么）/ `recommendation`（谁决策）。
- 事实的证据：`file:line`、commit sha、PR/issue 号、命令读数。四样都没有的，不算 fact。
- 共享证据契约由调用角色的上下文提供；本技能只使用 fact/inference/unknown/recommendation 四类词，不重复判据。

## 边界

- **只读**：禁 Edit / Write，不跑服务，不 commit，不改配置与状态。
- Bash 仅只读命令：`git log/show/blame`、`rg`、`ls`、读取类查询；写文件、装包、启进程一律不做。
- 只解释现状，不设计、不改代码、不提改法清单——除非用户明确要 recommendation。
- 不复制别的技能正文；需要别的判据时给兄弟技能指针。

## 自检

```text
五段齐全，末尾有 unknown
每条 fact 都有 file:line 或读数
没有任何 Edit/Write 动作；git status 干净
```
