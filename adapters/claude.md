# Claude Code 适配器

> 本文只讲**怎么在 Claude Code 上装插件与起角色**。总则见 [README.md](README.md)。
> 适用：本机原生 Windows / WSL 的 Claude Code CLI。
> **付费档**：需要 Claude 订阅或 Anthropic Console 认证；未登录 ⇒ 记 `paid-not-authorized`，不偷偷换模型或借别的账号。

## 探测

```bash
Get-Command claude        # Windows 常见 claude.cmd / claude.exe
claude --version          # 本机实测 2.1.310
claude doctor             # 安装/配置/认证健康检查
claude --help             # 现场核对 plugin / agents / settings 相关 flag
```

没有入口 ⇒ 本档不可用，缺件登记 `no-launcher`。`claude doctor` 报未登录 ⇒ 登记 `paid-not-authorized`，
交人工登录；不要尝试自动登录或写入他人凭据。

## 全局数据根

- CLI 的全局配置、认证、会话、日志、插件都跟 `CLAUDE_CONFIG_DIR` 走：`<本机数据根>/claude/`
  （含 `settings.json` 与 `.claude.json`）。
- 项目级配置仍住项目仓 `.claude/`（`skills/`、`agents/`、`settings.json`、`CLAUDE.md` 等），
  **不把项目数据搬进全局根**。
- 不设 `CLAUDE_CONFIG_DIR` 时才会落回 `~/.claude`；装机时应统一设置，见
  [agent-data-layout.md](../docs/agent-data-layout.md)。

## 装什么、放哪、叫什么

| 装什么 | 源 | 放哪 | 叫什么 |
|---|---|---|---|
| 插件清单 | `.claude-plugin/marketplace.json` ＋ `<plugin>/.claude-plugin/plugin.json` | 仓库根；作为本地 marketplace 交给宿主（`/plugin marketplace add <本仓路径>`，先按本机版本核对） | 插件名 `airport`／`core`／`board`／`intake`／`ops` |
| 技能 | `<plugin>/skills/<名>/SKILL.md` ＋ `scripts/`、`templates/`、`references/` | 项目 `.claude/skills/<名>/`；或中央库 `<...>/magpie/data/library/skills/<名>/`，宿主目录指向它 | 技能名；插件安装后按插件命名空间寻址 |
| 命令 | `<plugin>/commands/<role>.md` | 随插件安装 | `/airport:pilot` 这类插件命令；自然语言「机长开工」也命中 |
| 子代理 | 宿主原生 `.claude/agents/<名>.md`（可选，宿主自有格式） | 项目 `.claude/agents/` | 宿主 agent 名 |

- **不装全局**：`.claude/agents/` 与 `.claude/skills/` 只在项目级装，避免和用户其它框架的同名项打架。
- 框架不再定义人格文件：需要新上下文时用 Claude Code 原生子代理，或另起一次 `claude -p`。
- 只读靠工具白名单（`tools` 只给 Read/Grep/Glob），不是靠 prompt 自觉。

## 起角色（可写，仅人工执行）

> 任何角色不得自动调用会话创建口起另一个角色（唤醒围栏）。

```bash
cd <项目仓根>
claude
# 会话内：读取并执行 airport/skills/<角色>/SKILL.md 全文；
# 你的角色是 cc-<角色>-<时间戳>；只做该文件写的动作。
```

插件命令装好后也可以直接 `/airport:pilot`、`/airport:tower`、`/airport:ground-crew`、`/airport:copilot`、`/airport:ace`。

非交互执行（脚本/回执）：

```bash
claude -p "读取并执行 <项目仓根>/airport/skills/<角色>/SKILL.md 全文；只做该文件写的动作。" \
  --output-format text > <回执文件>
```

未实测的 flag（如 `--permission-mode`、`--allowedTools`）先 `claude --help` 当场核对，不把猜测写进正本。

## 新上下文与执行三职

- **Researcher**：只读工具集，产出 `research-<票>.md`；不写实现。
- **Implementer**：独立车道工作树与票分支；必带派工卡（票号/AC/允许禁止修改/验证命令/环境口径）；
  不 push、不合并。
- **Reviewer**：另起新会话或原生子代理，只拿 AC/diff/证据，输出 `verdict=pass|fail` ＋逐条证据；
  不得复用施工会话。缺 reviewer 或 `reviewer==implementer` ⇒ 不算独立验收。
- 子代理不再派子代理（派生固定一层）。

## 装完自证

1. 起一个只读子代理，让它写一个临时文件 → **必须被拒**；被写入＝权限没落住，按 `soft-permission-only` 登记。
2. 起可写子代理做一次最小可回滚写 → 通过即说明可写侧也通。
3. 角色命令能读到 `SKILL.md`，且命令文件里没有长规则。
4. 回执写实测读数；做不到的写「未测」，不算完成。

## 边界

- 不在未授权时消耗付费额度；未登录/未授权 ⇒ `paid-not-authorized`。
- 不建/删其他宿主的定时任务；不替角色施工。
- 版本、认证状态与探针读数写进项目本机配置，不回写插件清单与技能正文。
