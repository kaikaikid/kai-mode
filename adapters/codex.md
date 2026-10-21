# Codex 适配器（付费档备胎）

> 适用：Qoder 子会话不可用、opencode 不可用，或编排层明确要求 Codex。
> **付费档**：必须显式授权（如 `KAI_WATCHDOG_ALLOW_PAID=1`）；没有授权不许起。
> 与 opencode 同：**不能按 Qoder 定时任务**，只能直接跑角色剧本。

## 探测

```bash
Get-Command codex        # Windows 上常见 codex.cmd
codex --version          # 本机实测 0.163.0-alpha.10.2
```

没有入口 ⇒ 本档不可用，登记 `no-launcher`。

## 起角色（可写）

```bash
codex exec -C <项目根> -s workspace-write --json -o <回执文件> \
  "读取并执行 <项目根>/.ai/scope/shifts/<role>.md；你的班次名是 codex-<role>-<时间戳>；只做该文件写的动作。"
```

## 只读评审

```bash
codex exec -C <项目根> -s read-only --json -o <回执文件> \
  "按 <验收规则> 评审 <票号>；只输出 acceptance JSON 与证据路径。"
```

## 边界

- 付费前先取得用户/项目授权；未授权 ⇒ 记 `paid-not-authorized`，不降级偷偷跑。
- 不建/删 Qoder 定时任务；不替角色施工。
- 未实测的 flag 不许写进正本；版本与探针读数写进项目注册档。
