---
name: role-entry
status: active
approved_by: human:kaikaikid
approved: 2026-11-19
sources: []
description: >
  按需加载专家角色 profile：只做触发与指针，不复制契约。
  触发：点名专家角色，或要调研、架构、设计、写作。
version: 0.1.0
updated: 2026-11-19
allowed-tools: Read Grep
compatibility: Host-agnostic
metadata:
  alias: 专家入口
---

# role-entry —— 专家角色入口

> 本技能只回答一件事：**这次该按需加载哪位专家**。
> 它不复制任何角色契约；契约正文在项目的 `.ai/roles/profiles/<role_id>.md`。

## 角色定位

专家 4 按需加载，不进宿主常驻 agent 目录：

| role_id | 触发（用户要什么） | profile |
|---|---|---|
| `researcher` | 证据、来源、调研、对比资料 | `.ai/roles/profiles/<role_id>.md` |
| `architect` | 方案、结构、接口、根因 | `.ai/roles/profiles/<role_id>.md` |
| `designer` | 界面、观感、原型、设计规格 | `.ai/roles/profiles/<role_id>.md` |
| `writer` | 成稿、文案、长文档 | `.ai/roles/profiles/<role_id>.md` |

核心 3（`engineer`／`reviewer`／`archivist`）走宿主 agent 目录，主 AI 是会话级 prompt；
它们都不由本技能触发，别在这里重复加载。

## 怎么走

1. **认角色** —— 从用户话里取 role_id；对不上专家 4 就停，不硬套。
   **终点**：拿到一个 role_id。
2. **读 profile** —— 读 `.ai/roles/profiles/<role_id>.md`；文件不在 ⇒ 按缺件停下报「profile 未渲染」。
   **终点**：拿到该专家的完整契约正文。
3. **交给派发** —— 把 profile 正文作为该次任务的角色提示词，按内核派活规则带任务卡执行。
   **终点**：该角色在自己的上下文里开工；主 AI 只调度与验收。

## 硬规则

- **不复制契约**：本技能只留触发与指针，契约唯一家在 profile 文件。
- **不放 agent 目录**：专家 profile 不进宿主的常驻 agent 目录，防宿主自动派活。
- **不唤醒主 AI**：主 AI 是会话入口，不是可派发角色。
- **记忆只提候选**：任何角色都不直接写长期记忆；入账只走 `archivist`。
- 缺件按三格登记（缺什么／卡在哪一步／要谁拍补），不猜默认、不假装已加载。

## 验证

```text
profile 是否齐全：本技能指向的 4 个文件都在 .ai/roles/profiles/
缺件演练：删掉一个 profile，再触发对应角色 → 必须报「profile 未渲染」
```
