---
name: 矮人工匠
status: active
approved_by: human:kaikaikid
approved: 2026-11-09
sources:
  - resource: "../../../core/skills/gold/SKILL.md"
    note: "子代理纪律（默认零、先报数量）的正本在 gold"
description: >
  唤醒 布莱恩·铜须（矮人工匠 · engineer）子代理的薄入口。中文默认：`/矮人工匠`（本技能名，命令面上可用）；
  「布莱恩·铜须」与「engineer」作自然语言唤醒词也认。
  代码实现、修复、测试。不自动派发；定好任务包后按宿主已配的方式起。
  触发：`/矮人工匠`（命令）；自然语言「叫布莱恩·铜须」「叫矮人工匠」也认；`engineer` 是工程标识（subagent_type）。
version: 0.3.0
updated: 2026-11-09
allowed-tools: Read Grep
---

# 矮人工匠（布莱恩·铜须）—— 直接唤醒

> 角色身份、职责与边界住角色正本（装机时由 `set-kai-mode` 渲染成宿主 agent 文件）；本技能只管唤醒与任务包。
> 纪律正本在 `gold/SKILL.md`「子代理纪律」，本文件不复述。

## 唤醒

用宿主已配的方式起一个 `engineer` 子代理：有原生子代理的宿主用 `subagent_type=engineer`（或 agent 文件名）；
无原生子代理、本身是命令行 agent 工具的宿主，走本宿主自己的 CLI 进程，带角色提示词与 `可写` 档位。
具体命令样例住 `adapters/<宿主>.md` 与装机回执；本技能不复述。禁止跨宿主借兵。

## 任务包（缺一项不派）

目标一句话 · 范围（含/不含）· AC 可机检 · 权限（只读/可写范围）· 交付格式与路径 · 预算（迭代/超时）。


## 纪律（摘自 gold）

默认 0；派之前报「几个、为什么、上限几」；机械/单一活 ≤1，标准施工 ≤3；深度固定 1 层。

**终点**：子代理拿到任务包并已起，或判定不派（记原因）。
