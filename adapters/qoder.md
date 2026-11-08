# Qoder 适配器：装什么、放哪、叫什么都

> 本文只讲 Qoder（Alibaba 的 AI 编码 IDE/CLI）。总则见 [README.md](README.md)。
> 事实来源：docs.qoder.com（2026-10-27 查）；**未实测的 flag 不写死，装机时 `qoder --help` 现场核对**。

## 0. 官方事实（可点开）

| 事实 | 落点／命令 | 来源 |
|---|---|---|
| 项目技能 | `.qoder/skills/<name>/SKILL.md` | https://docs.qoder.com/extensions/skills |
| 用户技能 | `~/.qoder/skills/<name>/SKILL.md` | https://docs.qoder.com/cli/Skills |
| 插件技能 | `<plugin>/skills/<name>/SKILL.md` | https://docs.qoder.com/cli/plugins |
| 插件清单 | `.qoder-plugin/plugin.json`；`qoder plugins install <dir> -s project` | https://docs.qoder.com/cli/plugins |
| 项目规则 | `.qoder/rules/**/*.md`；`AGENTS.md` 也读 | https://docs.qoder.com/user-guide/rules |
| 子代理 | `.qoder/agents/<名>.md`（项目）／`~/.qoder/agents/<名>.md`（用户）；名字由 frontmatter `name` 决定，不由文件名决定 | https://docs.qoder.com/cli/subagent |
| 子代理字段面 | `name` `description` `tools` `disallowedTools` `effort` `hooks` `initialPrompt` `isolation` `maxTurns` `mcpServers` `memory` `model` `permissionMode` `skills` `temperature` `timeoutMins` `background` `color`；不认识的字段忽略 | 同上（2026-11-08 复查） |
| 定时任务 | CLI `<project>/.qoder/scheduled_tasks.json`、`/loop`、`/crontab`；IDE「Automations」 | https://docs.qoder.com/cli/scheduled-tasks |
| 兼容 Claude 配置 | CLI 0.1.22 发布说明有 `--with-claude-config`（读 Claude Skills/Commands/Subagents）；CLI 参考页未列 | https://docs.qoder.com/release-notes/qoder-cli |

- **技能 frontmatter**：官方只要求 `name`（小写字母数字连字符，≤64）与 `description`（≤1024）；
  本仓的八字段在 Qoder 里按「额外字段忽略」处理，不会报错。
- **优先级（2026-11-08 复查，取代旧句）**：官方现行表是 `Built-in < User < Project < Plugin < --agents`，
  即**项目级高于用户级、插件级高于项目级**；旧文写的「用户级优先」与此相反，已废。
  同名遮蔽可用 `qoder agents list` 的 shadowed 标记核。装机时仍以**实际加载到的那份**为准，
  并把版本与优先级读数写进回执。
- **角色文件必须装项目级、不随插件腿**（ADR-0033 D4）：官方明写插件提供的子代理会被剥掉
  `hooks`、`mcpServers`、`permissionMode`，只保留 `tools`/`disallowedTools` 与 `isolation: worktree`；
  加上插件优先级高于项目级，随插件装会既丢门禁又盖掉项目级那份。
- `qoder_cron` 在公开文档里**查不到**；旧文那条是运行时观测。以 `.qoder/scheduled_tasks.json`／`/loop` 为准。

## 1. 装什么

一个剧本一个插件目录。以机场剧本为例，装三样：

| 装什么 | 源 | 放哪 |
|---|---|---|
| 插件清单 | `<plugin>/.qoder-plugin/plugin.json` | 项目 `.qoder-plugin/plugin.json`，或 `qoder plugins install <plugin目录> -s project` |
| 技能 | `<plugin>/skills/<名>/SKILL.md` ＋ `scripts/`、`templates/`、`references/` | `.qoder/skills/<名>/`（项目级优先于用户级——先按项目级装） |
| 命令 | `<plugin>/commands/<role>.md` | Qoder 无同形 commands 目录：用 `--with-claude-config`（若本机版本支持），否则把命令正文当角色提示词 |

- **不要装全局**：`~/.qoder/skills/` 只在你明确要跨项目共用时用；项目级优先，且不会和别人的框架打架。
- **路径不写死**：项目技能目录可由项目配置实例 `registry.skills.project_skills_dir` 覆盖；读不到就报缺件，不猜。
- `.agents/skills` 也是 Qoder 的兼容来源（IDE 0.4.2＋／CLI 1.1.11＋），但解析规则未公开；不作为首选落点。

## 2. 叫什么都

Qoder 没有 Claude Code 那种 `/plugin:command` 命名空间。舰桥用两种叫法：

1. **自然语言**：说「舰桥」「开工」「发货」「清理脏文件」——技能 `description` 里的触发词负责命中。
2. **显式提示词**：

```text
读取并执行 <项目>/.qoder/skills/bridge/SKILL.md 全文；只做该文件写的动作。
```

- 如果本机 CLI 支持 `--with-claude-config`，Claude 风格的命令名会一并被读到；**先 `qoder --help` 确认**。
- 提示词里不放长规则；规则只住 `SKILL.md`。

## 3. 默认入口（不装定时器）

机场体系下线后没有塔台轮巡，也没有 60 分钟唤醒定时器。

- 在项目 `CLAUDE.md` / `AGENTS.md` 末尾写一段「默认入口＝舰桥」；
- 用户按需起会话；会话里不打斜杠命令时，读 `bridge` 技能执行；
- 施工由 `fleet warp`/`fleet jump` 派宿主原生子代理，不靠宿主定时任务。

## 4. 新上下文（审查腿）

- 首选 Qoder 原生 subagent：角色文件装**项目级** `.qoder/agents/<名>.md`，frontmatter 至少 `name`／`description`；
  只读用 `tools: [Read, Grep, Glob]` ＋ `disallowedTools: [Write, Edit, Bash]`（已查证是硬机制，写死）。
  禁止嵌套派工用 `disallowedTools: [Agent]`，或用 `Agent(Explore, Plan)` 精确允许派谁。
- **不随插件腿装角色**：插件提供的子代理会被剥掉 `hooks`/`mcpServers`/`permissionMode`（见 §0）。
- 次选：另起一个新会话，只给 AC／diff／证据。
- 再次：独立进程（若本机有 CLI 入口）。
- **复用施工会话 ⇒ 不算独立验收**；起不了新上下文 ⇒ 登记 `no-new-context`，不许记「已审查」。

## 5. 探测与验证（装完贴读数）

```bash
qoder --version                      # 入口与版本
qoder --help                         # 确认 plugins / scheduled / --with-claude-config 是否在
test -f .qoder/skills/bridge/SKILL.md && echo skill-ok
test -f .qoder-plugin/plugin.json && echo plugin-ok
```

再跑一次真实舰桥提示词，确认它能读到技能并只做技能里的事；做不到的写「未测」，不算完成。

## 6. 降级与缺件

| 缺什么 | 登记 | 退路 |
|---|---|---|
| 没有 `qoder` 入口 | `no-launcher` | 换 Codex／OpenCode 或人工 |
| 没有命令口 | — | 用角色提示词；不算缺件 |
| 没有原生 subagent | `no-new-context` | 另起新会话；再不行停审查腿并登记 |
| `--with-claude-config` 不存在 | — | 手动复制技能与命令正文 |
| 优先级与文档冲突 | `soft-permission-only`（如涉及权限） | 以实际加载到的那份为准，回执留读数 |

## 7. 边界

- 不替舰桥施工；只把舰桥按契约跑起来。
- 不建/删其他宿主的定时任务。
- 付费／额度未授权 ⇒ `paid-not-authorized`，不偷偷换模型。
- 版本、认证状态与探针读数写进项目本机配置，不回写框架正文。

## 原生子代理（舰队必需）

> **实测订正（2026-11-08，Desktop CN 构建）**：用户级 `~/.qoder-cn/agents/*.md` 里的定义
> **注册成「设备级 Agent」**（`list_agents` 能列出来，可用 `create_chat_session` 的 `agentId` 起会话），
> **不进子代理类型注册表**——`subagent_type` 仍只有宿主内建的七个，
> 用角色名去派会报 `Unknown agent type: '提里奥·弗丁'`。
> 所以「装到 `.qoder/agents/` 就能当 subagent 用」在 Desktop 上**不成立**；
> 两种派发面要分开对待。项目级落点与 `/agents reload` 的 Desktop 等价口仍未实测。
> 另外同一批装进去的八份里，`list_agents` 初读有 4 份 `enabled=false / ready=false`，
> 需要用户侧启用；装机回执必须逐份核对 readiness，不能只看文件写成功。
>
> **只读实测（2026-11-08，同一构建）**：用 `create_chat_session` 按 `agentId` 起「提里奥·弗丁」
> （渲染出来的 frontmatter 是 `tools: [Read, Grep, Glob]` ＋ `disallowedTools: [Write, Edit, Bash, Agent]`），
> 派它写一个临时文件——**写成功了**，`Write` 工具正常可用，同会话里 `Bash` 也在。
> 更硬的一条：只读角色与可写角色拿到的是**同一个工具面**（两边都是 25 个，含
> `Write`/`Edit`/`NotebookEdit`/`Bash`/`Agent`/`mcp_call`，逐项相同）——
> 定义文件在这条派发面上一点没收缩工具面，不是「收缩了但没拦住」。
> 也就是说 **Desktop 这条派发面上，角色定义的工具白名单没有被执行**。
> 结论：`readonly_hard = no`。审查腿的只读**不能**押在这份定义上，必须靠宿主无关三样
> （工作树隔离／范围校验／发货单点），并按 `soft-permission-only` 登记。

- 起新上下文：Qoder 原生 subagent，角色文件装项目级 `.qoder/agents/<名>.md`，由角色正本渲染而来、头部记正本指纹。
  **只装可派发的七个**；主 AI 人格（康娜）不进这一堆，她是会话级人格，走 `--agent` 那条路。
- 只读：`tools` 白名单 ＋ `disallowedTools`；起只读子代理让它写临时文件，**必须被拒**。
- 身份：`name` 只是调用方的选择键，子代理上下文里看不到它，也看不到调用时传的运行时名字；
  角色名与职业必须写进正文（正文＝子代理系统提示），实例编号写进任务包 prompt。
- `skills` 字段是**限制能用哪些技能**，不是把技能注入上下文；职业设定不能靠它承载。
- 报告落盘：子代理自己写或主会话代写到任务卡的 `report_path` / `review_report_path`。
