---
name: designer
status: active
approved_by: human:kaikaikid
approved: 2026-11-09
sources:
  - resource: "../../../core/skills/gold/SKILL.md"
    note: "子代理纪律（默认零、先报数量）的正本在 gold"
description: >
  直接唤醒 泰兰德（designer）子代理的薄入口（角色名即命令，省去前缀）。
  视觉、插画、UI 设计。不自动派发；定好任务包后按宿主已配的方式起。
  触发：`/designer`、`/泰兰德`；如 `/reviewer`、`/崔希丝`。
version: 0.1.0
updated: 2026-11-09
allowed-tools: Read Grep
---

# 泰兰德（designer）—— 直接唤醒

> 角色身份、职责与边界住角色正本（装机时由 `set-kai-mode` 渲染成宿主 agent 文件）；本技能只管唤醒与任务包。
> 纪律正本在 `gold/SKILL.md`「子代理纪律」，本文件不复述。

## 唤醒

用宿主已配的方式起一个 `designer` 子代理：有原生子代理的宿主用 `subagent_type=designer`（或 agent 文件名）；
无原生子代理、本身是命令行 agent 工具的宿主，走本宿主自己的 CLI 进程，带角色提示词与 `可写（产出素材）` 档位。
具体命令样例住 `adapters/<宿主>.md` 与装机回执；本技能不复述。
禁止跨宿主借兵。

## 任务包（缺一项不派）

目标一句话 · 范围（含/不含）· AC 可机检 · 权限（只读/可写范围）· 交付格式与路径 · 预算（迭代/超时）。


## 纪律（摘自 gold）

默认 0；派之前报「几个、为什么、上限几」；机械/单一活 ≤1，标准施工 ≤3；深度固定 1 层。

**终点**：子代理拿到任务包并已起，或判定不派（记原因）。
