# Agent 全局数据根：非项目数据集中，项目数据自管

一句话：**跨项目的配置/认证/会话/日志/缓存进 `KAI_AGENT_DATA_ROOT`；项目内的 agent 配置留在项目仓。**
裁决：[ADR-0012](adr/0012-global-agent-data-root.md)。本机实际根值只存在用户环境变量里，框架仓不写盘符。

## 1. 当前映射

| Agent | 全局数据落点 | 设置方式 | 项目数据（留在项目仓） |
|---|---|---|---|
| Claude Code | `<root>/claude/` | `CLAUDE_CONFIG_DIR` | `.claude/`、`.claude/agents/`、项目 `CLAUDE.md` |
| Codex | `<root>/codex/` | `CODEX_HOME` | `AGENTS.md`、项目配置 |
| OpenCode | `<root>/opencode/xdg/{config,data,cache,state}`、`<root>/opencode/tmp` | 启动包装仅对本进程设 XDG／TMP／TEMP | `opencode.json`、`.opencode/` |
| Qoder | 应用自管 `~/.qoder-cn` | 未验证可安全外移，**不改** | 项目仓内产物 |

公共变量：`KAI_AGENT_DATA_ROOT=<本机数据根>`。每个 agent 一个子目录，禁止把项目代码放进这个根。

## 2. 一次性配置（Windows）

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/setup-agent-data.ps1 `
  -Root "<本机数据根>" -Apply -Migrate -OpenCodeLauncher
```

- 默认 dry-run；`-Apply` 才写用户环境变量。
- 旧环境值备份到 `<root>/env-backup.json`。
- `-Migrate` 复制现有配置/认证；**不移动、不删除**旧数据。
- `-OpenCodeLauncher` 写 `<root>/bin/opencode.cmd`（及 Git Bash 用的 `opencode`），
  并把 `<root>/bin` 放到用户 PATH 前面；只对 OpenCode 进程改 XDG。
- Qoder 不在脚本覆盖范围；需要时等 Qoder 官方给出可验证的数据目录口，再按 §5 补。

## 3. 迁移边界

- **复制不搬家**：旧 `~/.claude`、`~/.codex`、旧 XDG 目录都保留。
- **符号链接不复制成实体**：Claude `skills/`、OpenCode `skills/`／`node_modules` 用 junction 指回原库。
- **运行中的大库不硬搬**：Codex 历史、OpenCode `opencode.db` 留在旧路径；新会话从新根开始。
  需要旧历史时，先退出对应进程，再单独复制。
- 不覆盖已有目标：目标已有 `settings.json` / `config.toml` / `opencode.json` 时跳过复制。

## 4. 验证

```bash
claude --version && claude doctor
codex doctor
opencode debug paths
```

- Claude：`claude doctor` 正常；`<root>/claude/` 有 `settings.json` 与 `.claude.json`。
- Codex：`codex doctor` 的 config 项不再报错；`<root>/codex/` 有 `config.toml`、`auth.json`。
- OpenCode：`debug paths` 里 data/config/cache/state/tmp 都在 `<root>/opencode/`。
- 用户环境变量：新开终端后 `echo $env:CLAUDE_CONFIG_DIR`（PowerShell）有值；已在运行的宿主需重启。

## 5. 加一个新 agent

1. 找官方支持的重定向变量；没有就写仅进程生效的启动包装。
2. 在本文件 §1 加一行，并在 `scripts/setup-agent-data.ps1` 加同样的目录/变量。
3. 跑 §4 验证；没有可验证口径的，按缺件登记，不假装支持。

## 6. 已登记的例外

- **Qoder**：`QODER_CONFIG_DIR` 由应用进程设置，未验证用户级外移不会影响登录/扩展；暂不自作主张。
- **Claude Desktop**：`%APPDATA%\Claude` 是桌面应用数据，不是 CLI 的 `CLAUDE_CONFIG_DIR`；不混为一谈。
- **Copilot / Cursor**：本机未安装；装后按 §5 补。
- **OpenCode Desktop**：桌面应用数据在 `%APPDATA%\ai.opencode.desktop`；本规范只接管 `opencode` CLI 启动。

## 7. 开发数据不提交

运行/验证产生的**会话、日志、数据库、缓存、验证报告、agent 数据**一律不进 git、不推送。

- 全局数据住 `KAI_AGENT_DATA_ROOT`（仓库外）；验证报告住 `<root>/verify/`。
- 仓库内只留可复用件（规范、代码、测试、模板、ADR）；临时产物走 `.gitignore`。
- `.gitignore` 已覆盖 `*.db`／`*.db-wal`／`*.db-shm`／`*.sqlite*`／`*.log`／`*.jsonl`／
  `*.tmp`／`*.pid`，以及根级 `agent-data/`、`.agent-data/`、`verify/`、`logs/`、`.cache/`。
- 如果某件已被跟踪：先 `git rm --cached <path>` 移出索引，再加忽略规则；**不要直接删盘上的证据**。
- `doctor` 的 `tracked-cache` 项会拦“被跟踪的缓存/运行数据”，当前仓库应为 0 命中。
