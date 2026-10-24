# 0012 全局 agent 数据根：非项目数据集中，项目数据自管

## Status

accepted —— 2026-10-24 用户令：适配 Claude Code CLI 并全局部署；非项目数据指向本机 workspaces 根，
以后所有 agent 的默认数据都指向这里；项目数据仍由项目自行管理。

## Context

- 各 CLI 默认把配置、认证、会话、日志写进用户目录（Claude `~/.claude`、Codex `~/.codex`、
  OpenCode 走 XDG）；项目级又各有 `.claude/`、`.opencode/`、`AGENTS.md`。
- 两套写入面混在用户目录里：换机器要翻多个隐藏目录，清理时也分不清哪些是全局、哪些属于项目。
- 本机已有历史数据与符号链接（Magpie 技能库），迁移不能丢、不能覆盖、不能把大库复制成第二份。

## Decision

### D1 一个非项目数据根

`KAI_AGENT_DATA_ROOT` 指向**整台机器**的 agent 非项目数据根；实际值只存在用户环境变量里，
**不写进框架正本**（框架仓保持可移植）。每个 agent 一个子目录：
`<root>/<agent>/…`。

### D2 各 agent 的官方重定向口

| Agent | 全局数据落点 | 机制 |
|---|---|---|
| Claude Code | `<root>/claude/` | `CLAUDE_CONFIG_DIR`（连 `.claude.json`、凭据一起搬） |
| Codex | `<root>/codex/` | `CODEX_HOME` |
| OpenCode | `<root>/opencode/xdg/{config,data,cache,state}`、`<root>/opencode/tmp` | **仅该进程**设置 XDG 与 TMP/TEMP 的启动包装；不改全局 XDG |
| Qoder | 应用自管 `~/.qoder-cn` | `QODER_CONFIG_DIR` 为应用进程级，未验证可安全外移；**不改**，如实登记 |
| Copilot / Cursor | 未安装 | 装后按 D6 补 |

OpenCode 没有独立数据目录变量，二进制只认 XDG；因此用启动包装隔离，避免把 git/gh/pnpm
等其它 XDG 用户一起搬走。

### D3 项目数据仍归项目

- Claude 项目人格 `.claude/agents/`、项目设置 `.claude/`、Codex 项目 `AGENTS.md`、
  OpenCode 项目 `opencode.json`／`.opencode/` 一律留在项目仓。
- **不把全局认证、会话、日志、缓存写进项目**；**不把项目历史写进全局数据根**。
- 全局数据根只放跨项目的东西；项目仓的 `.gitignore` 自己管项目内产物。

### D4 迁移是复制，不是搬家

- 先备份旧用户环境变量，再写新值；旧数据保留在原处，不删除。
- 符号链接/目录联接不复制成实体：Claude `skills/`、OpenCode `skills/`／`node_modules`
  用 junction 指回原库。
- 运行中的大库（Codex 历史、OpenCode DB）不强行复制；新会话写新根，旧历史留在旧路径。
- 不做 `robocopy /MIR` 之类会删除目标的动作。

### D5 验证

- `claude --version` 与 `claude doctor`；配置文件出现在 `<root>/claude/`。
- `codex doctor` 能加载新 `CODEX_HOME/config.toml`。
- `opencode debug paths` 的 data/config/cache/state/tmp 全在 `<root>/opencode/`。
- 新开一个终端后，用户环境变量已生效；已在运行的进程需重启才读到新值。

### D6 加新 agent

先找**官方支持**的重定向口；没有就写仅进程生效的启动包装。然后在
[`agent-data-layout.md`](../agent-data-layout.md) 加一行、在 `scripts/setup-agent-data.ps1`
加同样的配置，并跑 D5 验证。没有可验证口径的，登记为缺件，不假装支持。

## Consequences

- 换机器/备份只需处理一个根；项目仓里不再混入全局会话与认证。
- OpenCode 旧 DB 与 Codex 旧历史不会自动出现；需要时在进程停止后单独迁移。
- Qoder 仍由应用自管；这是已登记的例外，不是遗漏。
- 绝对路径只活在用户环境变量与本地启动包装里，框架仓不含机器路径。

## 验证

```bash
claude --version && claude doctor
codex doctor
opencode debug paths
```

具体命令与当前映射见 [`docs/agent-data-layout.md`](../agent-data-layout.md)。
