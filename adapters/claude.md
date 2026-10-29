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

插件命令装好后也可以直接 `/airport:pilot`、`/airport:tower`、`/airport:ground-crew`、`/airport:copilot`、`/airport:second-officer`、`/airport:ace`。

非交互执行（脚本/回执）：

```bash
claude -p "读取并执行 <项目仓根>/airport/skills/<角色>/SKILL.md 全文；只做该文件写的动作。" \
  --output-format text > <回执文件>
```

未实测的 flag（如 `--permission-mode`、`--allowedTools`）先 `claude --help` 当场核对，不把猜测写进正本。

## 定时唤醒塔台（门卫薄壳）

Claude 桌面端/Code 的定时任务每轮**都会拉起一次模型会话**，所以 prompt 必须是门卫薄壳，
不能直接写「读取并执行塔台技能全文」——否则没活、上一轮还在跑，都白烧一整轮。

```text
定时任务（每 60 分钟）
  ├─ cwd：项目仓根
  └─ prompt（薄壳，全文照抄，不加长规则）：
     在项目仓根执行 `python <tower 技能目录>/scripts/wake-gate.py`。
     退出码 10 ⇒ 只回复它打印的那一行，立即结束，不读任何技能、不扫 Issue、不排班。
     退出码 0 ⇒ 读取并执行 airport/skills/tower/SKILL.md 全文，按该文件跑一轮（本轮启用道 lanes=1+2）；任务名 cron-tower-<日期>-<时分>。
     退出码 2 ⇒ 按缺件三格如实报告，结束。
```

- 门卫判据住 `tower/scripts/wake-gate.py`，prompt 里不复述：上一轮还在跑（令牌心跳新于
  `tower_cron.interval_min + 5` 分钟）⇒ 跳过；零待发货且**启用道**日表都在下限以上 ⇒ 跳过；
  待发货探测失败 ⇒ 放行（失败不等于零活）。
- **跳过时零模型调用**：门卫是纯脚本，`rc=10` 那一轮只有一个短回合的回复，不加载 21KB 技能正文。
- 建完必回读：`list_scheduled_tasks` 看 `enabled`、`nextRunAt`、`lastRunAt` 有没有动；
  看到被手动停（`enabled=false`）⇒ 报「建过、现在是停的」两句，**不自动重开**。
- 只唤醒塔台；角色之间不互相拉起（唤醒围栏）。人工 `/tower` 不过门卫。

## 开票归属钩子（PreToolUse）

`gh` 落在哪仓看 cwd：在项目仓里跑 `gh issue create` 就把票开到项目仓。治法是宿主钩子拒掉缺 `--repo` 的开票命令；
判据住 `set-kai-mode/scripts/issue-guard.py`，**只在 `set-kai-mode` 第 6 步安装**，本文件只写接法与验收。

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "python \"<宿主技能目录>/set-kai-mode/scripts/issue-guard.py\"",
            "timeout": 10
          }
        ]
      }
    ]
  }
}
```

- 脚本从 stdin 读 `tool_input.command`，取不到就当放行（不拦空输入）；
  `gh issue create` / `gh pr create` 缺 `--repo` / `-R` ⇒ `exit 2`，提示里带实例 `issue.repo`。
- 验收两条：项目仓里 `gh issue create --title probe` 被拒；加 `--repo <owner/name>` 放行。
- 路径用**绝对路径**：钩子进程的 cwd 不保证是技能目录。
- 落点：用户级 `<本机数据根>/claude/settings.json`（全局拦）或项目级 `.claude/settings.json`（只拦本仓）；
  `set-kai-mode` 按缺口清单问过再写，写前备份。

## 内置子代理与同名覆盖

宿主自带这几类子代理，**装自定义 agent 不会替换它们**——除非用同名文件覆盖：

| 内置 | 干什么 | 默认模型 |
|---|---|---|
| `Explore` | 只读搜索（找文件、找符号） | 继承主会话 |
| `Plan` | 出实现计划 | 继承主会话（认 `CLAUDE_CODE_SUBAGENT_MODEL`） |
| `general-purpose` | 兜底通用，全工具 | `CLAUDE_CODE_SUBAGENT_MODEL`，没设就继承主会话 |
| `statusline-setup` / `claude-code-guide` | 状态栏配置 / 宿主用法问答 | 工具类，不覆盖 |

- **同名覆盖**：项目 `.claude/agents/` 下放一个与内置**同名**的定义（例如把内置 `Explore` 覆盖掉），会盖掉内置，并**保留文件自己的 `model` / `effort`**。
  优先级（高→低）：managed settings → `--agents` → 项目 `.claude/agents/` → `~/.claude/agents/` → 插件 `agents/`。
  **插件里的 agent 带命名空间**（`studio:Plan`），盖不掉内置——所以覆盖件必须由装机拷到**项目目录**。
- **只想禁用**：`permissions.deny: ["Agent(Explore)"]`；或 `CLAUDE_CODE_DISABLE_EXPLORE_PLAN_AGENTS=1`（Explore＋Plan 一起去掉）。
- **档位命名**：`sonnet` / `opus` / `haiku` / `fable`，或 `inherit`；`effort` 与 `maxTurns` 只对自定义定义生效。
- 别开 `CLAUDE_CODE_SUBAGENT_MODEL_FORCE=1` 与 `CLAUDE_CODE_EFFORT_LEVEL`：会把每个 agent 的分档压平。

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
