# Codex 适配器（付费档备胎）

> 本文只讲**怎么在这个宿主上起舰桥**。舰队施工不适用：Codex 没有宿主原生子代理，
> 而 框架已明确只调用宿主自己的子代理，不拉 `codex exec` 子进程。

> 适用：Qoder 子会话不可用、opencode 不可用，或编排层明确要求 Codex。
> **付费档**：必须显式授权（如 `KAI_WATCHDOG_ALLOW_PAID=1`）；没有授权不许起。
> 与 opencode 同：不依赖宿主定时口；舰桥按需起会话。

## 探测

```bash
Get-Command codex        # Windows 上常见 codex.cmd
codex --version          # 本机实测 0.164.0-alpha.11.1
```

没有入口 ⇒ 本档不可用，缺件如实登记（`no-launcher`）。

## 宿主工具探测

- **Builder（施工）**：`codex exec -s workspace-write`（沙箱给写权）；探测不到 `codex` 入口 ⇒ 本档不可用，缺件如实登记。
- **Reviewer（评审）**：`codex exec -s read-only`，**另起一次调用**（新上下文）；复用施工会话 ⇒ 不算独立验收。
- **Researcher（检索/探索）**：`codex exec -s read-only`，只产出研究稿，不写实现。
## 内置子代理

- 无 agent 定义文件这一层 ⇒ **覆盖不适用**：不装 `.md`，子代理按下面的独立进程腿执行，
  装机时三格登记 `no-agent-surface`，不假装已装。

- **降级**：无 Task 类子代理字段 ⇒ 三个角色都用独立 `codex exec` 进程顶替，各带各的 sandbox；付费未授权 ⇒ 记 `paid-not-authorized`，不偷偷跑。

## 起舰桥（可写，仅人工执行）

```bash
codex exec -C <仓库根> -s workspace-write --json -o <回执文件> \
  "读取并执行 core/skills/bridge/SKILL.md 全文；只做该文件写的动作。"
```

## 只读评审

```bash
codex exec -C <仓库根> -s read-only --json -o <回执文件> \
  "按票面 AC 评审 <票号>；只输出 verdict 与逐条证据路径。"
```

## 执行三职（舰队不适用）

- 框架只用宿主原生子代理；Codex 当前没有这一层 ⇒ `travel claim/report/review/verdict` 派活链不适用。
- 按缺件三格登记 `no-new-context`，如实告诉用户「这个宿主跑不了舰队执行内核」；不退化去拉 `codex exec`。
- 舰桥本身仍可用：它只做对话、开票、发货，不依赖宿主子代理。
- 若 Codex 未来提供原生子代理，再在这里补「怎么起、怎么锁只读、报告落哪」三条。

## 边界

- 付费前先取得用户/项目授权；未授权 ⇒ 记 `paid-not-authorized`，不降级偷偷跑。
- 不建/删其他宿主的定时任务；不替舰桥施工。
- 未实测的 flag 不许写进正本；版本与探针读数写进项目本机配置。

## 原生子代理（舰队必需）

- Codex **没有**宿主内建的原生子代理（当前实测）；舰队内核的 `travel claim` / `report` /
  `review` / `verdict` 派活链因此不适用。
- 不退化去拉 `codex exec` 子进程：用户已明确框架只调用宿主自己的子代理。
- 起不了新上下文 ⇒ 按 §6 登记 `no-new-context`，如实告诉用户「这个宿主跑不了舰队执行内核」。
- 若未来 Codex 提供原生子代理，再在本节补「怎么起、怎么锁只读、报告落哪」三条。
