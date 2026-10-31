---
name: kai-mods
status: active
approved_by: human:kaikaikid
approved: 2026-10-31
sources: []
description: >
  CC 专属：登记、更新、管理已装插件/mod，记录个人向调整（如 UI 文字、补丁）。
  手动激活（disable-model-invocation: true），不自动触发；不替代 set-kai-mode 的装机。
  触发：用户明确说「登记插件」「更新 mod」「管理 mods」「调整 UI 文字」「个人向补丁」，
  或 /kai-mods。只在 CC 宿主下有效。
version: 0.1.0
updated: 2026-10-31
allowed-tools: Read Grep Bash
compatibility: Host-agnostic
disable-model-invocation: true
dependencies:
  skills: []
---

# Kai Mods —— CC 插件登记与个人向调整

> 只在 CC 宿主运行；其他宿主无 `/plugin` 命令，直接跳过。

## 这是什么

`/kai-mods` 是**个人向**的插件管理账本，区别于 `set-kai-mode`（装机/升级）和 `upgrade-kai-mode`（版本漂移）：

- `set-kai-mode` 管**框架**（技能、定时器、配置实例、门禁）；
- `/kai-mods` 管**插件/mod**（装了哪些、版本、个人补丁、UI 调整）。

**不自动触发**：必须用户明确喊 `/kai-mods` 或说「登记插件」等 trigger。

## 三类操作

### A. 登记（inventory）

列出宿主已装插件，与 `v2/mods/`、`scripts/mod-zh.py` 等个人补丁对账，登记到 `<项目根>/.mods/registry.md`。

```
/kai-mods inventory
```

做：`claude plugin list --json` → 对账 `v2/mods/` 与 `scripts/mod-*` → 写 `<项目根>/.mods/registry.md`。

### B. 更新（update）

把某个插件升到最新，跑 plugin-check，重跑个人补丁。

```
/kai-mods update <plugin-id>
```

做：`claude plugin update` → 重跑 `v2/mods/apply.py` 或对应 `scripts/mod-*.py` → 记录版本变化。

### C. 调整（patch）

记录一次个人向调整：UI 文字、补丁、配置 override，写入 `.mods/patches/<date>-<slug>.md`。

```
/kai-mods patch <slug> <描述>
```

## 状态落盘

```
.mods/
  registry.md          # 已装插件清单 + 版本 + 个人补丁指针
  patches/
    2026-10-31-zh-you-should-know.md   # 个人向调整记录
  overrides.json       # 配置 override（theme、language 等）
```

`.mods/` 是个人向数据，**不进仓库**（装时写进 `.gitignore`）。

## 与其它技能的关系

- `set-kai-mode`：装机/升级框架；`/kai-mods` 不重复它。
- `upgrade-kai-mode`：框架版本漂移；`/kai-mods` 管插件版本漂移。
- `v2/mods/apply.py`：V2 面板补丁；`/kai-mods update` 会调它。

## 铁律

1. **只在 CC 下运行**；其他宿主无 `/plugin`，直接报「不适用」。
2. **登记不等于安装**：registry 只记录，不自动装。
3. **补丁必须幂等**：`apply.py` / `mod-*.py` 重复跑无副作用。
4. **个人向数据不进仓库**：`.mods/` 写进 `.gitignore`。
5. **调整记录要可追溯**：每次 patch 写日期 + 原因 + 回滚命令。
