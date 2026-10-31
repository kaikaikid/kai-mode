# Codex 适配器（付费档备胎）

> 本文只讲**怎么在这个宿主上起舰桥与施工子会话**。人格文件已退役；新上下文用独立 `codex exec` 进程。

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

## 执行三职

- **Researcher**：`codex exec -s read-only`，产出 `research-<票>.md`；不写实现。
- **Worker**（＝施工子会话）：`codex exec -s workspace-write`；brief 自包含（任务、AC、允许/禁止修改、验证命令、回执格式）；run 工作树与分支；不 push、不合并。
- **Gatekeeper**（＝门卫审查）：`codex exec -s read-only`，**另起一次调用**（新上下文）；只拿 AC/diff/证据，输出 accept/return ＋逐条证据；不得复用施工会话。
- 缺 reviewer 或 `reviewer==implementer` ⇒ 不算独立验收。

## 边界

- 付费前先取得用户/项目授权；未授权 ⇒ 记 `paid-not-authorized`，不降级偷偷跑。
- 不建/删其他宿主的定时任务；不替舰桥施工。
- 未实测的 flag 不许写进正本；版本与探针读数写进项目本机配置。
