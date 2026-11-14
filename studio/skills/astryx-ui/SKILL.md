---
name: astryx-ui
status: active
approved_by: human:kaikaikid
approved: 2026-11-14
sources: []
description: >
  只在「新建 React 19+ 界面／原型／内部工具」或「项目已依赖 @astryxdesign/*」时使用本地 Astryx 设计系统；
  不接 Vue、不改造既有 Kai-vass 页面、不做全局安装。触发：新建 React 页面、React 原型、内部工具页面、Astryx 组件库、astryx 设计系统、找设计组件、新前端页面、用组件库搭页面、设计手册。
version: 0.1.0
updated: 2026-11-14
allowed-tools: Read Grep Bash
compatibility: Host-agnostic
metadata:
  alias: Astryx 进场
  audience: 泰兰德·语风（designer）、布莱恩·铜须（engineer）
---

# astryx-ui —— 新 React 界面才进场的组件库

> 本机在 `D:\kaikaikid\tools\astryx` 部署了 Meta 开源设计系统 Astryx（v0.7.16，React 19+ ＋ StyleX）。
> 这份技能只管「什么时候进场、怎么走 CLI」；组件文档、主题、模板一律由 CLI 现场回答，不在此复制。

## 角色定位

这是**组件库与设计系统的进场判据**，不是 UI 设计方法，也不是 Kai-vass 前端规范。
Kai-vass 现有前端是 Vue 3 ＋ Tailwind，Astryx 要 React 19＋：**现有前端一律不接**，继续走项目自己的设计系统。

## 进场闸门（先过，再动手）

同时满足才用本技能：

1. 任务是**新建 React 19+ 页面／原型／内部工具**，或目标项目已依赖 `@astryxdesign/*`。
2. 目标不是 Vue／现有 Kai-vass 前端，也不是「只评审既有界面」。
3. 用户没有指定其它组件库或手写 HTML/CSS。

任一不满足 ⇒ 不调用 Astryx，按项目既有栈与团队技能走（泰兰德用 design-critique／design-handoff 等，布莱恩按项目工程规范）。**不为 Vue 活引入 Astryx，不把通用 UI 触发词当进场许可。**

## 怎么走

1. **确认落点** —— 在目标项目目录读 `package.json`：React ≥19 或已有 `@astryxdesign/core`。**终点**：确认是 React 项目并记下包管理器；不是就停。
2. **装依赖与接线** —— `pnpm add @astryxdesign/core @astryxdesign/theme-neutral @stylexjs/stylex`（npm/yarn 按项目已有），`pnpm add -D @astryxdesign/cli`；入口引 `reset.css` 与 `astryx.css`。目标项目里一律用 `pnpm exec astryx …`（或 `npx`）；Astryx 仓内才可直接 `pnpm astryx`（monorepo 转发）。**终点**：`pnpm exec astryx component Button` 有响应。
3. **从模板起页** —— `pnpm exec astryx build "<需求>"` 选模板，`pnpm exec astryx template <name> <path>` 落骨架，缺的块用 `template <Block>` 补；用组件前先 `component <Name>` 读 props。**终点**：页面框架来自模板，不是裸 `<div>` 拼装。
4. **查文档／省 token** —— 全量命令看 `astryx manifest --json`；查组件／文档用 `--json`、`--dense`，需要中文试 `--zh`（无翻译会回落英文）。`--json/--dense/--zh` 是全局旗标（各读命令通用，`component --help` 不列出但可用）。**终点**：引用的是当前版本 CLI 的答案，不是记忆中的 API。
5. **交付前自检** —— `pnpm exec astryx doctor --built <dir>`；复查裸 `div`／`className`／硬编码 hex/px 并换成组件或 token；再跑项目构建。**终点**：doctor 0 fail、构建通过、交付的是可跑产物。
6. **看实物** —— 本机已构建好的 Storybook：`pnpm -C D:\kaikaikid\tools\astryx dev` → http://localhost:6006（首次预览慢，Vite 预 bundling，等或重载预览 iframe）。**终点**：组件外观有真渲染证据。

## 硬规则

- 不全局安装 CLI、不改 kai-mode 正本、不装 Claude/Codex 插件；项目内版本优先。
- 不替用户做观感取舍；主题定制走主题包／主题编辑器，不写 `:root` 覆盖。
- 目标项目缺 React 19＋或包管理器异常 ⇒ 按三格登记（缺什么／卡在哪步／要谁拍），不降级硬上。
- 只引本机已部署的 v0.7.16 事实；组件数量、props、模板名一律以 CLI 现场输出为准。
- 队友使用范围：泰兰德（界面与体验）与布莱恩（实现与验证）；其它角色需要时由康娜转派，不自行扩散触发。
