# Codex 适配器（付费档备胎）

> 适用：Qoder 子会话不可用、opencode 不可用，或编排层明确要求 Codex。
> **付费档**：必须显式授权（如 `KAI_WATCHDOG_ALLOW_PAID=1`）；没有授权不许起。
> 与 opencode 同：**没有 `qoder_cron` 类定时口**，只能直接跑角色技能。

## 探测

```bash
Get-Command codex        # Windows 上常见 codex.cmd
codex --version          # 本机实测 0.163.0-alpha.10.2
```

没有入口 ⇒ 本档不可用，缺件如实登记（`no-launcher`）。

## 起角色（可写）

```bash
codex exec -C <仓库根> -s workspace-write --json -o <回执文件> \
  "读取并执行 skills/<角色>/SKILL.md 全文；你的角色是 codex-<角色>-<时间戳>；只做该文件写的动作。"
```

## 只读评审

```bash
codex exec -C <仓库根> -s read-only --json -o <回执文件> \
  "按票面 AC 评审 <票号>；只输出 verdict 与逐条证据路径。"
```

## 执行三职（ADR-0136 残留：researcher / implementer / reviewer）

- **Researcher**：`codex exec -s read-only`，产出 `research-<票>.md`；不写实现。
- **Implementer**（＝施工子代理）：`codex exec -s workspace-write`；必带派工卡（票号/AC/允许禁止修改/验证命令/环境口径）；独立 worktree 与分支；不 push、不合并。
- **Reviewer**（＝审查子代理）：`codex exec -s read-only`，**另起一次调用**（新上下文）；只拿 AC/diff/证据，输出 `verdict=pass|fail` ＋逐条证据；不得复用施工会话。
- 缺 reviewer 或 `reviewer==implementer` ⇒ 不算独立验收。

## 边界

- 付费前先取得用户/项目授权；未授权 ⇒ 记 `paid-not-authorized`，不降级偷偷跑。
- 不建/删其他宿主的定时任务；不替角色施工。
- 未实测的 flag 不许写进正本；版本与探针读数写进项目本机配置。
