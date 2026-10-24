# Claude Code 适配器（cc cli）

> 本文只讲**怎么在这个宿主上起岗位**。人格怎么落成 `.claude/agents/<名>.md`（权限/模型/禁派生）见 [README.md](README.md)。
> 全局非项目数据放哪、怎么迁移，见 [docs/agent-data-layout.md](../docs/agent-data-layout.md) 与 [ADR-0012](../docs/adr/0012-global-agent-data-root.md)。

> 适用：本机原生 Windows / WSL 的 Claude Code CLI。
> **付费档**：需要 Claude 订阅或 Anthropic Console 认证；未登录 ⇒ 记 `paid-not-authorized`，不偷偷换模型或借别的账号。

## 探测

```bash
Get-Command claude        # Windows 常见 claude.cmd / claude.exe
claude --version          # 本机实测 2.1.310
claude doctor             # 安装/配置/认证健康检查
```

没有入口 ⇒ 本档不可用，缺件登记 `no-launcher`。`claude doctor` 报未登录 ⇒ 登记 `paid-not-authorized`，
交人工登录；不要尝试自动登录或写入他人凭据。

安装：Windows 优先官方原生安装器（`irm https://claude.ai/install.ps1 | iex`）；网络不可达时
可用官方 npm 包 `npm install -g @anthropic-ai/claude-code`（本机即此路径）。

## 全局数据根

- CLI 的全局配置、认证、会话、日志、插件都跟 `CLAUDE_CONFIG_DIR` 走：
  `<本机数据根>/claude/`（含 `settings.json` 与 `.claude.json`）。
- 项目级配置仍住项目仓 `.claude/`（`agents/`、`settings.json`、`CLAUDE.md` 等），**不把项目数据搬进全局根**。
- 不设 `CLAUDE_CONFIG_DIR` 时才会落回 `~/.claude`；装机时应统一设置，见 [agent-data-layout.md](../docs/agent-data-layout.md)。

## 宿主工具探测（schema 2 `execution.host_tools` 契约迁入，[0004](../docs/adr/0004-project-config-schema.md) D6）

- **Builder（施工）**：`claude` 交互会话或 `claude -p` 非交互；工具权限按项目 `.claude/settings.json` 与用户 settings 合并。
- **Reviewer（评审）**：**另起一次** Claude 会话（新上下文），只给 AC/diff/证据；复用施工会话 ⇒ 不算独立验收。
- **Researcher（检索/探索）**：只读工具集（Read/Grep/Glob），产出研究稿，不写实现。
- **降级**：子代理通过 `.claude/agents/` 落人格；没有对应产物 ⇒ 登记 `no-subagent-slot`，不假装有独立上下文。

## 起角色（可写，仅人工执行）

> 任何角色不得自动调用会话创建口起另一个角色（[ADR-0010](../docs/adr/0010-role-wake-fence.md)）。
> Claude Code 没有 `qoder_cron` 类定时口；60 分钟唤醒塔台仍靠宿主定时口或人工。

```bash
cd <项目仓根>
claude
# 会话内：读取并执行 skills/<角色>/SKILL.md 全文；
# 你的角色是 cc-<角色>-<时间戳>；只做该文件写的动作。
```

非交互执行（脚本/回执）：

```bash
claude -p "读取并执行 <项目仓根>/skills/<角色>/SKILL.md 全文；只做该文件写的动作。" \
  --output-format text > <回执文件>
```

未实测的 flag（如 `--permission-mode`、`--allowedTools`）先 `claude --help` 当场核对，不把猜测写进正本。

## 人格落点

- 项目级：`<项目仓根>/.claude/agents/<名>.md`，frontmatter `name` / `description` / `tools` / `model`；
  **不装全局**（全局同名人格会和用户其它框架打架）。
- 只读：`tools` 只给 Read/Grep/Glob 等读类工具；禁派生：子代理不给 Task/Agent 类工具。
- 模型：读项目实例 `models.agents.<人格>.model`；`null` ⇒ 不写 `model`，用宿主默认（inherit）。
- 装完自证：让只读人格写一个临时文件，必须被拒；写成功＝权限没落住，按 `soft-permission-only` 登记。

## 执行三职

- **Researcher**：只读工具集，产出 `research-<票>.md`；不写实现。
- **Implementer**：独立 worktree 与分支；必带派工卡（票号/AC/允许禁止修改/验证命令/环境口径）；不 push、不合并。
- **Reviewer**：另起新会话，只拿 AC/diff/证据，输出 `verdict=pass|fail` ＋逐条证据；不得复用施工会话。
- 缺 reviewer 或 `reviewer==implementer` ⇒ 不算独立验收。

## 边界

- 不在未授权时消耗付费额度；未登录/未授权 ⇒ `paid-not-authorized`。
- 不建/删其他宿主的定时任务；不替角色施工。
- 版本、认证状态与探针读数写进项目本机配置，不回写人格。
